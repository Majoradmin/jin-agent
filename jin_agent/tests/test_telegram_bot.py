"""P25 - Telegram bot front-end helpers: command parsing, chunks, allowlist, dispatch."""

import os
import socket
import tempfile
import unittest
from unittest import mock

from jin_agent import config, llm, searchmemory, store, telegram_bot as tb


def _public_dns(host, port, *args, **kwargs):
    """Offline DNS mock — custom LLM endpoint public IP par resolve hota hai."""
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]


def setUpModule():
    os.environ["JIN_AGENT_DATA"] = tempfile.mkdtemp(prefix="jin-bot-")
    store.init_db()


class FakeAPI:
    def __init__(self):
        self.sent = []
        self.modes = []          # har send ka parse_mode (highlight wiring ke liye)

    def send(self, chat_id, text, buttons=None, parse_mode=None):
        self.sent.append((int(chat_id), str(text), buttons))
        self.modes.append(parse_mode)
        return {"ok": True, "result": {"message_id": len(self.sent)}}

    def get_updates(self, offset, timeout=None):
        return []

    def answer_callback(self, callback_id, text=""):
        return {"ok": True}

    def send_document(self, chat_id, file_path, caption="", timeout=120):
        self.sent.append((int(chat_id), str(caption), None))
        self.modes.append(None)
        return {"ok": True, "result": {"message_id": len(self.sent)}}


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
        # 1 progress + 2 report chunks + 1 'mil gaya?' question
        # (5000-char report ab entity-safe, tag-balanced split_html se 2 chunks me)
        self.assertEqual(len(api.sent), 4)
        self.assertIn("Research chal rahi hai", api.sent[0][1])
        self.assertIn("# Research Brief", api.sent[1][1])
        for _, text, _ in api.sent[1:-1]:
            self.assertLessEqual(len(text), 4096)
        last = api.sent[-1]
        self.assertIn("mil gayi", last[1])
        # inline buttons attach hain
        self.assertIsNotNone(last[2])
        self.assertIn("done", last[2][0][0]["callback_data"])

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
        joined = "\n".join(t for _, t, _ in api.sent)
        self.assertIn("https://t.me/s/gsmlab/120", joined)

    def test_dispatch_tgsearch_no_results_suggests_next_step(self):
        api = FakeAPI()

        def empty_search(query, cfg=None, **kw):
            return {"query": query, "channels": ["gsmlab"], "ok": 1,
                    "failed": [], "items": []}

        tb.dispatch(42, "/tgsearch zzz", {"telegram_chat_id": "42"}, api=api,
                    tg_search=empty_search)
        joined = "\n".join(t for _, t, _ in api.sent)
        self.assertIn("nahi mila", joined)
        self.assertIn("/research", joined)

    def test_dispatch_channels_lists_saved(self):
        from jin_agent import channels
        channels.add_channel("gsmlabtan", origin="manual")
        api = FakeAPI()
        res = tb.dispatch(42, "/channels", {"telegram_chat_id": "42"}, api=api)
        self.assertTrue(res["ok"])
        joined = "\n".join(t for _, t, _ in api.sent)
        self.assertIn("https://t.me/gsmlabtan", joined)


class TestDeepWebAndCallbacks(unittest.TestCase):
    """P29: dark/deep engines, 'mil gaya?' buttons aur search memory."""

    def setUp(self):
        tb.memory_mod.ensure_table()

    def test_format_deep_without_query_has_links(self):
        text = tb.format_deep()
        self.assertIn("https://ahmia.fi/search/", text)
        self.assertIn(".onion", text)
        self.assertIn("Legal onion discovery only", text)

    def test_format_deep_with_query_fills_keyword(self):
        text = tb.format_deep("firmware unlock")
        self.assertIn("q=firmware%20unlock", text)

    def test_dispatch_deep(self):
        api = FakeAPI()
        res = tb.dispatch(42, "/deep onion markets", {"telegram_chat_id": "42"}, api=api)
        self.assertTrue(res["ok"])
        joined = "\n".join(t for _, t, _ in api.sent)
        self.assertIn("ahmia.fi/search/?q=onion%20markets", joined)

    def test_parse_callback(self):
        self.assertEqual(tb.parse_callback("mem:17:more"), (17, "more"))
        self.assertEqual(tb.parse_callback("garbage"), (0, ""))
        self.assertEqual(tb.parse_callback("mem:1:extra!!"), (0, ""))

    def test_callback_done_marks_memory(self):
        row = tb.memory_mod.begin(42, "signal leaks")
        tb.memory_mod.remember(row["id"], ["gsmarena"], ["chA"])
        api = FakeAPI()
        res = tb.handle_callback(42, f"mem:{row['id']}:done",
                                 {"telegram_chat_id": "42"}, api=api)
        self.assertTrue(res["ok"])
        self.assertEqual(tb.memory_mod.get(row["id"])["status"], "done")

    def test_callback_more_runs_next_round_and_remembers(self):
        row = tb.memory_mod.begin(42, "firmware unlock")
        tb.memory_mod.remember(row["id"], ["gsmarena"], ["chA"])
        api = FakeAPI()
        res = tb.handle_callback(42, f"mem:{row['id']}:more",
                                 {"telegram_chat_id": "42"}, api=api,
                                 research=lambda q, cfg: "# Round report\n" + "x" * 4500)
        self.assertTrue(res["ok"])
        updated = tb.memory_mod.get(row["id"])
        self.assertGreaterEqual(updated["round_no"], 2)
        self.assertIn("gsmarena", updated["used_sources"])
        self.assertIn("Round", api.sent[0][1])  # round-2 header

    def test_callback_unknown_row(self):
        api = FakeAPI()
        res = tb.handle_callback(42, "mem:999999:done",
                                 {"telegram_chat_id": "42"}, api=api)
        self.assertFalse(res["ok"])

    def test_format_memory_empty_and_rows(self):
        self.assertIn("Memory khali", tb.format_memory([]))
        row = tb.memory_mod.begin(42, "firmware")
        tb.memory_mod.remember(row["id"], ["a"], ["c"], advance=True)
        out = tb.format_memory([tb.memory_mod.get(row["id"])])
        self.assertIn("firmware", out)
        self.assertIn("Round 2", out)

    def test_research_full_appends_channel_section(self):
        def fake_run(*args, **kwargs):
            return {"ok": True, "blocked": False, "gate": {},
                    "diagnostics": [{"key": "gsmarena", "count": 2},
                                    {"key": "xda", "count": 0}],
                    "report": {"markdown": "# Brief"}}

        def fake_search(*args, **kwargs):
            return {"items": [{"channel": "gsmlab",
                               "url": "https://t.me/s/gsmlab/1",
                               "excerpt": "firmware news"}],
                    "channels": ["gsmlab"], "failed": []}

        with mock.patch.object(tb.orchestrator, "run", fake_run), \
                mock.patch.object(tb.channels_mod, "search_posts", fake_search):
            out = tb.research_full("firmware", config.load(), save=False, live=False)
        self.assertTrue(out["ok"])
        self.assertIn("Telegram Channels", out["markdown"])
        self.assertIn("https://t.me/s/gsmlab/1", out["markdown"])
        self.assertEqual(out["sources"], ["gsmarena"])  # sirf count > 0

    def test_research_full_skip_lists_reach_channels(self):
        seen = {}

        def fake_search(query, channels_list=None, cfg=None, limit=8, **kw):
            seen["channels"] = channels_list
            return {"items": [], "channels": channels_list or [], "failed": []}

        with mock.patch.object(tb.orchestrator, "run",
                               lambda *a, **k: {"ok": True, "blocked": False,
                                                "gate": {}, "diagnostics": [],
                                                "report": {"markdown": "x"}}), \
                mock.patch.object(tb.channels_mod, "search_posts", fake_search):
            tb.research_full("q", config.load(), skip_channels=["skipme"],
                             save=False, live=False)
        self.assertNotIn("skipme", seen["channels"])


class TestRelatedSearchAndTranslation(unittest.TestCase):
    """P29 phase 2 (user option C): related queries + Roman Urdu translation."""

    def _llm_cfg(self):
        return {"llm": {"provider": "custom", "model": "llama-3.3-70b-versatile",
                        "key": "k", "endpoint": "https://api.groq.com/openai/v1"}}

    def test_llm_related_queries_disabled_returns_empty(self):
        self.assertEqual(llm.related_queries(config.load(), "firmware"), [])

    def test_llm_related_queries_parses_json_array(self):
        fake_chat = mock.MagicMock(return_value={"ok": True, "text": '["firmware unlock", "kernel panic fix"]'})
        with mock.patch.object(llm, "chat", fake_chat), \
                mock.patch("socket.getaddrinfo", _public_dns):
            qs = llm.related_queries(self._llm_cfg(), "firmware")
        self.assertEqual(qs, ["firmware unlock", "kernel panic fix"])

    def test_llm_related_queries_bad_json_returns_empty(self):
        with mock.patch.object(llm, "chat", mock.MagicMock(
                return_value={"ok": True, "text": "nahi samajh aaya"})), \
                mock.patch("socket.getaddrinfo", _public_dns):
            self.assertEqual(llm.related_queries(self._llm_cfg(), "x"), [])

    def test_llm_translate_text_disabled_returns_empty(self):
        self.assertEqual(llm.translate_text(config.load(), "hello world"), "")

    def test_llm_translate_text_returns_translation(self):
        with mock.patch.object(llm, "chat", mock.MagicMock(
                return_value={"ok": True, "text": "Firmware unlock ka solution"})), \
                mock.patch("socket.getaddrinfo", _public_dns):
            self.assertEqual(llm.translate_text(self._llm_cfg(), "Firmware unlock ka solution"),
                             "Firmware unlock ka solution")

    def test_related_callback_more_searches_related_queries(self):
        row = tb.memory_mod.begin(42, "firmware unlock")
        calls = []

        def fake_research_full(q, cfg=None, save=True, live=True,
                                skip_sources=None, skip_channels=None):
            calls.append(q)
            return {"ok": True, "markdown": "# Related: " + q,
                    "sources": ["brave"], "channels": ["chA"]}

        with mock.patch.object(tb.llm, "related_queries",
                                lambda cfg, query, n=3, timeout=30: ["rel1", "rel2"]), \
             mock.patch.object(tb, "research_full", fake_research_full):
            api = FakeAPI()
            res = tb.handle_callback(42, f"mem:{row['id']}:more",
                                    {"telegram_chat_id": "42"}, api=api)
        self.assertTrue(res["ok"])
        # pehla related query mila -> loop break -> final report = "rel1"
        self.assertEqual(calls, ["rel1"])
        joined = "\n".join(t for _, t, _ in api.sent)
        self.assertIn("Related: rel1", joined)


if __name__ == "__main__":
    unittest.main()
