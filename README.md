# Mae LinkedIn Drafter (Slack bot)

A Slack bot that drafts LinkedIn posts in Vivian Liu's voice for Mae - Making Auto Easy.
The reviewer edits the draft in a Slack thread and approves it with ✅. The bot then sends a clean final version to copy into LinkedIn. **It never posts to LinkedIn.**

- DM the bot a topic or rough note → it replies in a thread with a draft, an angle, alternate hooks and a check list.
- Reply in the thread with edits → it sends the revised post.
- Reply ✅ or react ✅ to its message → it sends the **Final version** plus a **Learned** note on what you changed.
- Every Monday at 9:00 (Toronto) it DMs each reviewer 5 post ideas. Set `WEEKLY_IDEAS` to blank to turn this off.

The voice comes from `prompts/drafter.md` (rules and review loop) and `prompts/style-guide.md` (analysis of 66 of Vivian's posts). To change how it writes, edit those files and redeploy.

## Setup (about 15 minutes)

### 1. Create the Slack app
1. Go to https://api.slack.com/apps → **Create New App** → **From a manifest** → pick the workspace.
2. Paste the contents of `slack-app-manifest.yaml` → **Next** → **Create**.
3. **Install App** (left menu) → **Install to Workspace** → **Allow**. Copy the **Bot User OAuth Token** (`xoxb-…`).
4. **Basic Information** → **App-Level Tokens** → **Generate Token and Scopes** → name it `socket`, add the scope `connections:write` → **Generate**. Copy the token (`xapp-…`).

### 2. Get the other values
- **Anthropic API key:** https://console.anthropic.com → **API keys** → **Create key** (`sk-ant-…`). Add a few dollars of credit and a monthly spend limit.
- **Your Slack member ID:** in Slack, click your profile picture → **Profile** → **⋮** → **Copy member ID** (`U…`). That goes in `REVIEWER_USER_IDS`. Add Vivian's ID later, comma separated.

### 3. Deploy on Render
1. Render → **New** → **Blueprint** → pick this repo. It reads `render.yaml` and creates a background worker (Starter plan, about $7/month).
2. Fill in `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, `ANTHROPIC_API_KEY` and `REVIEWER_USER_IDS` when Render asks → **Apply**.
3. The logs should show `Mae drafter running as …`.

It uses Slack Socket Mode, so it needs no public URL.

### Run it on your own PC instead (for a quick test)
```sh
pip install -r requirements.txt
cp .env.example .env   # fill it in
# Windows PowerShell: Get-Content .env | % { $k,$v = $_ -split '=',2; if ($k -and $k -notmatch '^#') { Set-Item "env:$k" $v } }
python bot.py
```

### 4. Test
In Slack, open **Mae Drafter** (under Apps) and send: `Draft a post about our NADA booth`.

## Switching from AJ (tester) to Vivian
- Add Vivian's member ID to `REVIEWER_USER_IDS`.
- Change `TESTER_NOTE` to blank (or remove it) so the bot treats Vivian as the reviewer.

## Settings
| Variable | Default | What it does |
|---|---|---|
| `CLAUDE_MODEL` | `claude-opus-5-5` | Model used for drafts |
| `CLAUDE_EFFORT` | `medium` | `low` is cheaper and faster, `high` is more careful |
| `REVIEWER_USER_IDS` | (required) | Only these Slack users can use the bot |
| `WEEKLY_IDEAS` | `MON 09:00` | Weekly ideas DM; blank turns it off |
| `WEEKLY_TZ` | `America/Toronto` | Time zone for the weekly DM |

## Tests
```sh
python -m unittest test_bot -v
```
