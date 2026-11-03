"""Mae LinkedIn drafter: a Slack bot that drafts posts in Vivian's voice.

How it works
- DM the bot a topic or rough note: it replies in a thread with a draft.
- Reply in that thread with edits: it sends back the revised post.
- Reply with a check mark, or react to its message with :white_check_mark:,
  and it sends the clean final version to copy into LinkedIn.
- Optional: once a week it DMs each reviewer 5 post ideas.

It never posts to LinkedIn and only talks to the Slack users listed in
REVIEWER_USER_IDS.
"""

import logging
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import anthropic
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("mae-bot")

HERE = Path(__file__).parent.parent
MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("CLAUDE_EFFORT", "medium")
REVIEWERS = {u.strip() for u in os.environ.get("REVIEWER_USER_IDS", "").split(",") if u.strip()}
TESTER_NOTE = os.environ.get("TESTER_NOTE", "").strip()
# Weekly ideas, e.g. WEEKLY_IDEAS="MON 09:00" (24h, in WEEKLY_TZ). Empty = off.
WEEKLY_IDEAS = os.environ.get("WEEKLY_IDEAS", "").strip()
WEEKLY_TZ = ZoneInfo(os.environ.get("WEEKLY_TZ", "America/Toronto"))
APPROVE_REACTIONS = {"white_check_mark", "heavy_check_mark", "ballot_box_with_check"}
PLACEHOLDER = "✍️ Drafting…"


def load_system_prompt() -> str:
    drafter = (HERE / "prompts" / "drafter.md").read_text(encoding="utf-8")
    style = (HERE / "prompts" / "style-guide.md").read_text(encoding="utf-8")
    parts = [
        drafter,
        "## Reference: Vivian's full style guide\n\n" + style,
        "## Slack formatting\n\nYou are replying in Slack. Use *single asterisks* for bold labels "
        "(Draft:, Angle:, Alternate hooks:, Check:, Final version:, Learned:).",
    ]
    if TESTER_NOTE:
        parts.append("## Current reviewer\n\n" + TESTER_NOTE)
    return "\n\n".join(parts)


SYSTEM_PROMPT = load_system_prompt()
claude = anthropic.Anthropic()
app = App(token=os.environ["SLACK_BOT_TOKEN"])
BOT_USER_ID = app.client.auth_test()["user_id"]


def is_reviewer(user_id: str) -> bool:
    return not REVIEWERS or user_id in REVIEWERS


def thread_to_messages(replies: list[dict], bot_user_id: str) -> list[dict]:
    """Turn a Slack thread into Claude messages: bot = assistant, people = user.

    Placeholders are skipped, consecutive turns from the same side are merged,
    and the list always starts with a user turn.
    """
    messages: list[dict] = []
    for msg in replies:
        text = (msg.get("text") or "").strip()
        if not text or text == PLACEHOLDER:
            continue
        from_bot = msg.get("user") == bot_user_id or bool(msg.get("bot_id"))
        role = "assistant" if from_bot else "user"
        if messages and messages[-1]["role"] == role:
            messages[-1]["content"] += "\n\n" + text
        else:
            messages.append({"role": role, "content": text})
    while messages and messages[0]["role"] != "user":
        messages.pop(0)
    return messages


def ask_claude(messages: list[dict]) -> str:
    response = claude.beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        messages=messages,
        output_config={"effort": EFFORT},
        betas=["server-side-fallback-2026-07-01"],
        extra_body={"fallbacks": "default"},
    )
    if response.stop_reason == "refusal":
        return "Sorry, I couldn't draft that one. Try rephrasing the request."
    text = "".join(b.text for b in response.content if getattr(b, "type", "") == "text").strip()
    if response.stop_reason == "max_tokens":
        text += "\n\n_(cut off, ask me to continue)_"
    return text or "Sorry, I came back empty. Try again?"


def reply_in_thread(client, channel: str, thread_ts: str, extra_user_turn: str | None = None):
    placeholder = client.chat_postMessage(channel=channel, thread_ts=thread_ts, text=PLACEHOLDER)
    try:
        replies = client.conversations_replies(channel=channel, ts=thread_ts, limit=200)["messages"]
        messages = thread_to_messages(replies, BOT_USER_ID)
        if extra_user_turn:
            if messages and messages[-1]["role"] == "user":
                messages[-1]["content"] += "\n\n" + extra_user_turn
            else:
                messages.append({"role": "user", "content": extra_user_turn})
        if not messages:
            text = "Send me a topic or a rough note and I'll draft a post."
        else:
            text = ask_claude(messages)
    except Exception:
        log.exception("Drafting failed")
        text = "Something went wrong on my side. Try again in a minute."
    client.chat_update(channel=channel, ts=placeholder["ts"], text=text)


@app.event("message")
def on_dm(event, client):
    # Only plain messages from people in a DM with the bot.
    if event.get("channel_type") != "im" or event.get("subtype") or event.get("bot_id"):
        return
    user = event.get("user", "")
    if not is_reviewer(user):
        client.chat_postMessage(channel=event["channel"], text="Sorry, I'm only set up for Mae's LinkedIn reviewers.")
        return
    thread_ts = event.get("thread_ts") or event["ts"]
    reply_in_thread(client, event["channel"], thread_ts)


@app.event("app_mention")
def on_mention(event, client):
    if not is_reviewer(event.get("user", "")):
        return
    thread_ts = event.get("thread_ts") or event["ts"]
    reply_in_thread(client, event["channel"], thread_ts)


@app.event("reaction_added")
def on_reaction(event, client):
    item = event.get("item", {})
    if (
        event.get("reaction") not in APPROVE_REACTIONS
        or item.get("type") != "message"
        or event.get("item_user") != BOT_USER_ID
        or not is_reviewer(event.get("user", ""))
    ):
        return
    channel, ts = item["channel"], item["ts"]
    found = client.conversations_replies(channel=channel, ts=ts, limit=1)["messages"]
    thread_ts = (found[0].get("thread_ts") if found else None) or ts
    reply_in_thread(client, channel, thread_ts, extra_user_turn="✅ Approved. Send the final version.")


def weekly_ideas_loop():
    """DM each reviewer 5 post ideas at the configured weekly time."""
    day_name, hhmm = WEEKLY_IDEAS.split()
    target_day = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"].index(day_name.upper()[:3])
    hour, minute = (int(x) for x in hhmm.split(":"))
    last_sent = None
    while True:
        now = datetime.now(WEEKLY_TZ)
        if now.weekday() == target_day and (now.hour, now.minute) >= (hour, minute) and last_sent != now.date():
            last_sent = now.date()
            for user in REVIEWERS:
                try:
                    channel = app.client.conversations_open(users=user)["channel"]["id"]
                    opener = app.client.chat_postMessage(
                        channel=channel,
                        text="Good morning! Here are this week's LinkedIn ideas. Reply in this thread with the one you want drafted.",
                    )
                    reply_in_thread(
                        app.client, channel, opener["ts"],
                        extra_user_turn="Give me 5 post ideas for this week.",
                    )
                except Exception:
                    log.exception("Weekly ideas failed for %s", user)
        time.sleep(60)


if __name__ == "__main__":
    if WEEKLY_IDEAS and REVIEWERS:
        threading.Thread(target=weekly_ideas_loop, daemon=True).start()
        log.info("Weekly ideas on: %s %s", WEEKLY_IDEAS, WEEKLY_TZ)
    log.info("Mae drafter running as %s, model %s, reviewers %s", BOT_USER_ID, MODEL, sorted(REVIEWERS) or "anyone")
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
