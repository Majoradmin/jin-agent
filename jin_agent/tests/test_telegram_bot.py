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
        # 1 progress message + 2 report chunks
        self.assertEqual(len(api.sent), 3)
        self.assertIn("Research chal rahi hai", api.sent[0][1])
        self.assertIn("# Research Brief", api.sent[1][1])

    def test_dispatch_research_requires_query(self):
        api = FakeAPI()
        res = tb.dispatch(42, "/research", {"telegram_chat_id": "42"}, api=api)
        self.assertFalse(res["ok"])

    def test_dispatch_unknown_sends_hint(self):
        api = FakeAPI()
        res = tb.dispatch(42, "/bogus cmd", {"telegram_chat_id": "42"}, api=api)
        self.assertFalse(res["ok"])
        self.assertEqual(api.sent[0][0], 42)


class TestChannelsAndEngines(unittest.TestCase):
    """P28: channel registration, 1-click links, channel-internal search."""

    def setUp(self):
        from jin_agent import channels
        channels.ensure_table()

    def test_forwarded_handle_from_channel_origin(self):
        msg = {"forward_origin": {"type": "channel",
                                  "chat": {"username": "gsmlab"}}}
        self.assertEqual(tb.forwarded_handle(msg), "gsmlab")

    def test_forwarded_handle_ignores_user_forward(self):
        msg = {"forward_origin": {"type": "user",
                                  "sender_user": {"id": 1}}}
        self.assertEqual(tb.forwarded_handle(msg), "")

    def test_forwarded_handle_legacy_field(self):
        msg = {"forward_from_chat": {"type": "channel", "username": "old_ch"}}
        self.assertEqual(tb.forwarded_handle(msg), "old_ch")

    def test_format_channels_empty_gives_instructions(self):
        text = tb.format_channels([])
        self.assertIn("forward", text)
        self.assertIn("/addchannel", text)

    def test_format_channels_has_clickable_link(self):
        text = tb.format_channels([
            {"channel": "gsmlab", "title": "GSM Lab", "subscribers": "25K",
             "post_count": 12}])
        self.assertIn("https://t.me/gsmlab", text)
        self.assertIn("@gsmlab", text)

    def test_format_engines_has_verified_links(self):
        text = tb.format_engines()
        for handle in ("SearcheeBot", "MotherSearchBot", "oSearchBot"):
            self.assertIn(f"https://t.me/{handle}", text)

    def test_dispatch_engines(self):
        api = FakeAPI()
        res = tb.dispatch(42, "/engines", {"telegram_chat_id": "42"}, api=api)
        self.assertTrue(res["ok"])
        self.assertIn("https://t.me/SearcheeBot", api.sent[0][1])

    def test_dispatch_addchannel_with_probe(self):
        api = FakeAPI()

        def fake_check(handle, cfg=None):
            return {"channel": handle, "alive": True, "title": "GSM Lab",
                    "subscribers": "25K", "post_count": 12, "status": "active",
                    "score": 7}

        res = tb.dispatch(42, "/addchannel https://t.me/gsmlabbot_test",
                          {"telegram_chat_id": "42"}, api=api,
                          probe=fake_check)
        self.assertTrue(res["ok"])
        self.assertEqual(res["channel"], "gsmlabbot_test")
        self.assertIn("https://t.me/gsmlabbot_test", api.sent[0][1])

    def test_dispatch_addchannel_requires_handle(self):
        api = FakeAPI()
        res = tb.dispatch(42, "/addchannel", {"telegram_chat_id": "42"}, api=api)
        self.assertFalse(res["ok"])

    def test_dispatch_tgsearch_formats_results(self):
        api = FakeAPI()

        def fake_search(query, cfg=None, **kw):
            return {"query": query, "channels": ["gsmlab"], "ok": 1,
                    "failed": [],
                    "items": [{"channel": "gsmlab",
                               "excerpt": "firmware update mila",
                               "url": "https://t.me/s/gsmlab/120"}]}

        res = tb.dispatch(42, "/tgsearch firmware",
                          {"telegram_chat_id": "42"}, api=api,
                          tg_search=fake_search)
        self.assertTrue(res["ok"])
        self.assertEqual(res["count"], 1)
        joined = "\n".join(t for _, t in api.sent)
        self.assertIn("https://t.me/s/gsmlab/120", joined)

    def test_dispatch_tgsearch_no_results_suggests_next_step(self):
        api = FakeAPI()

        def empty_search(query, cfg=None, **kw):
            return {"query": query, "channels": ["gsmlab"], "ok": 1,
                    "failed": [], "items": []}

        tb.dispatch(42, "/tgsearch zzz", {"telegram_chat_id": "42"}, api=api,
                    tg_search=empty_search)
        joined = "\n".join(t for _, t in api.sent)
        self.assertIn("nahi mila", joined)
        self.assertIn("/research", joined)

    def test_dispatch_channels_lists_saved(self):
        from jin_agent import channels
        channels.add_channel("gsmlabtan", origin="manual")
        api = FakeAPI()
        res = tb.dispatch(42, "/channels", {"telegram_chat_id": "42"}, api=api)
        self.assertTrue(res["ok"])
        joined = "\n".join(t for _, t in api.sent)
        self.assertIn("https://t.me/gsmlabtan", joined)


if __name__ == "__main__":
    unittest.main()
