import os, sys, types, unittest
from unittest import mock

os.environ.setdefault("SLACK_BOT_TOKEN", "xoxb-test")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test")

with mock.patch("slack_bolt.App") as App:
    App.return_value.client.auth_test.return_value = {"user_id": "UBOT"}
    import bot


class ThreadToMessages(unittest.TestCase):
    def test_roles_merge_and_placeholder(self):
        replies = [
            {"user": "UAJ", "text": "Draft a post about NADA"},
            {"user": "UBOT", "bot_id": "B1", "text": bot.PLACEHOLDER},
            {"user": "UBOT", "bot_id": "B1", "text": "*Draft:* ..."},
            {"user": "UAJ", "text": "shorter"},
            {"user": "UAJ", "text": "and less salesy"},
        ]
        msgs = bot.thread_to_messages(replies, "UBOT")
        self.assertEqual([m["role"] for m in msgs], ["user", "assistant", "user"])
        self.assertEqual(msgs[2]["content"], "shorter\n\nand less salesy")

    def test_leading_bot_message_dropped(self):
        replies = [{"user": "UBOT", "bot_id": "B1", "text": "Here are ideas"}, {"user": "UAJ", "text": "do #2"}]
        self.assertEqual(bot.thread_to_messages(replies, "UBOT"), [{"role": "user", "content": "do #2"}])

    def test_system_prompt_has_rules_and_style_guide(self):
        self.assertIn("Never invent facts", bot.SYSTEM_PROMPT)
        self.assertIn("Gold-standard posts", bot.SYSTEM_PROMPT)


class AskClaude(unittest.TestCase):
    def test_request_shape_and_text(self):
        block = types.SimpleNamespace(type="text", text="Hello post")
        resp = types.SimpleNamespace(stop_reason="end_turn", content=[block])
        with mock.patch.object(bot.claude.beta.messages, "create", return_value=resp) as create:
            self.assertEqual(bot.ask_claude([{"role": "user", "content": "x"}]), "Hello post")
        kw = create.call_args.kwargs
        self.assertEqual(kw["model"], "claude-opus-5-5")
        self.assertEqual(kw["extra_body"], {"fallbacks": "default"})

    def test_refusal(self):
        resp = types.SimpleNamespace(stop_reason="refusal", content=[])
        with mock.patch.object(bot.claude.beta.messages, "create", return_value=resp):
            self.assertIn("couldn't draft", bot.ask_claude([{"role": "user", "content": "x"}]))


if __name__ == "__main__":
    unittest.main()
