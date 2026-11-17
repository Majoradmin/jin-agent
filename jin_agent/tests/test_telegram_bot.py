"""P25 - Telegram bot front-end helpers: command parsing, chunks, allowlist, dispatch."""

import os
import tempfile
import unittest

from jin_agent import config, store, telegram_bot as tb


def setUpModule():
    os.environ["JIN_AGENT_DATA"] = tempfile.mkdtemp(prefix="jin-bot-")
    store.init_db()


class FakeAPI:
    def __init__(self):
        self.sent = []

    def send(self, chat_id, text):
        self.sent.append((int(chat_id), str(text)))
        return {"ok": True, "result": {"message_id": len(self.sent)}}

    def get_updates(self, offset, timeout=None):
        return []


class TestBotHelpers(unittest.TestCase):
    def test_parse_command_research(self):
        self.assertEqual(tb.parse_command("/research kya hua"), ("research", "kya hua"))

    def test_parse_command_start(self):
        self.assertEqual(tb.parse_command("/start"), ("start", ""))
        self.assertEqual(tb.parse_command("/research@somebot q"), ("research", "q"))

    def test_parse_command_unknown(self):
        self.assertEqual(tb.parse_command("hello world"), ("unknown", "hello world"))

    def test_split_text_chunks_respect_limit(self):
        text = "line\n" * 3000  # ~6000 chars
        chunks = tb.split_text(text, limit=4096)
        self.assertGreaterEqual(len(chunks), 2)
        for c in chunks:
            self.assertLessEqual(len(c), 4096)

    def test_is_owner_allowlist(self):
        self.assertTrue(tb.is_owner(123, {"telegram_chat_id": "123"}))
        self.assertFalse(tb.is_owner(456, {"telegram_chat_id": "123"}))
        self.assertTrue(tb.is_owner(999, {"telegram_chat_id": ""}))
        self.assertTrue(tb.is_owner(None, {}))

    def test_dispatch_research_sends_markdown_chunks(self):
        api = FakeAPI()

        def fake_research(q, cfg, save=True, live=False):
            return "# Research Brief\n" + ("x" * 5000)

        res = tb.dispatch(42, "/research testquery", {"telegram_chat_id": "42"},
                          api=api, research=fake_research)
        self.assertTrue(res["ok"])
        self.assertEqual(res["action"], "research")
        self.assertEqual(len(api.sent), 2)
        self.assertIn("# Research Brief", api.sent[0][1])

    def test_dispatch_research_requires_query(self):
        api = FakeAPI()
        res = tb.dispatch(42, "/research", {"telegram_chat_id": "42"}, api=api)
        self.assertFalse(res["ok"])

    def test_dispatch_unknown_sends_hint(self):
        api = FakeAPI()
        res = tb.dispatch(42, "/bogus cmd", {"telegram_chat_id": "42"}, api=api)
        self.assertFalse(res["ok"])
        self.assertEqual(api.sent[0][0], 42)


if __name__ == "__main__":
    unittest.main()
