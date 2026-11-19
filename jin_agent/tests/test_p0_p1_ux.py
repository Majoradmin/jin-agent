"""P0 + P1 (user ka explore/UX muksad): 6-command surface, seedha matn =
/research, /channels add/rm, /search alias, /research --deep, setMyCommands,
live progress stages, trace path, explore cards + confirm gate, /status explore
block. Sab kuch stdlib-only, network mocked."""

import os
import tempfile
import time
import unittest
from unittest import mock

from jin_agent import (channels, config, orchestrator, store,
                       telegram_bot as tb)


def setUpModule():
    os.environ["JIN_AGENT_DATA"] = tempfile.mkdtemp(prefix="jin-p0p1-")
    store.init_db()
    channels.ensure_table()
    tb.memory_mod.ensure_table()


class FakeAPI:
    def __init__(self):
        self.sent = []
        self.docs = []
        self.edits = []
        self.cmds = None

    def send(self, chat_id, text, buttons=None):
        self.sent.append((int(chat_id), str(text), buttons))
        return {"ok": True, "result": {"message_id": len(self.sent)}}

    def edit(self, chat_id, message_id, text, parse_mode=None):
        self.edits.append((int(chat_id), int(message_id), str(text)))
        return {"ok": True}

    def send_document(self, chat_id, file_path, caption="", timeout=120):
        self.docs.append((int(chat_id), str(file_path), str(caption)))
        return {"ok": True}

    def get_updates(self, offset, timeout=None):
        return []

    def answer_callback(self, callback_id, text=""):
        return {"ok": True}

    def set_my_commands(self, commands, timeout=30):
        self.cmds = list(commands)
        return {"ok": True}


class PlainAPI:
    """API jis me edit/set_my_commands nahi (purana fake)."""

    def send(self, chat_id, text, buttons=None):
        return {"ok": True}

    def get_updates(self, offset, timeout=None):
        return []

    def answer_callback(self, callback_id, text=""):
        return {"ok": True}


class TestHelpAndRouting(unittest.TestCase):
    def test_help_lists_six_commands_with_examples(self):
        for cmd in ("research", "search", "channels", "explore", "status", "help"):
            self.assertIn("/" + cmd, tb.HELP_TEXT)
        self.assertEqual(tb.HELP_TEXT.count("Misal:"), 6)

    def test_help_lists_remaining_commands(self):
        self.assertIn("Baqi commands:", tb.HELP_TEXT)
        for cmd in ("report", "addchannel", "rmchannel", "tgsearch", "engines",
                    "deep", "dork", "memory", "digest", "alerts", "reports",
                    "schedule", "channelhealth", "memoryaudit", "selftest",
                    "new", "stop"):
            self.assertIn("/" + cmd, tb.HELP_TEXT)

    def test_plain_text_becomes_research(self):
        self.assertEqual(tb.route_plain_text("firmware unlock"), "/research firmware unlock")
        self.assertEqual(tb.route_plain_text(""), "")

    def test_link_and_handle_stay_addchannel(self):
        self.assertEqual(tb.route_plain_text("https://t.me/durov"),
                         "/addchannel https://t.me/durov")
        self.assertEqual(tb.route_plain_text("@durov"), "/addchannel @durov")
        self.assertEqual(tb.route_plain_text("salam", forwarded="origin_ch"),
                         "/addchannel @origin_ch")

    def test_split_deep_flag(self):
        self.assertEqual(tb.split_deep_flag("firmware --deep"), ("firmware", True))
        self.assertEqual(tb.split_deep_flag("firmware"), ("firmware", False))
        self.assertEqual(tb.split_deep_flag("--deep"), ("", True))
        self.assertEqual(tb.split_deep_flag("--deep firmware"), ("--deep firmware", False))

    def test_bot_commands_surface(self):
        self.assertEqual([c["command"] for c in tb.BOT_COMMANDS],
                         ["research", "search", "channels", "explore", "status", "help"])

    def test_register_commands_best_effort(self):
        api = FakeAPI()
        self.assertTrue(tb.register_commands(api))
        self.assertEqual(len(api.cmds), 6)
        self.assertFalse(tb.register_commands(PlainAPI()))


class TestChannelsSearchAndDeep(unittest.TestCase):
    def tearDown(self):
        tb._pending_add.pop(42, None)

    def test_channels_add_confirm_gate(self):
        api = FakeAPI()
        res = tb.dispatch(42, "/channels add https://t.me/gsmlabbot_test",
                          {"telegram_chat_id": "42"}, api=api)
        self.assertEqual(res["action"], "addchannel_pending")
        self.assertFalse(any(r["channel"] == "gsmlabbot_test"
                             for r in channels.list_channels()))
        with mock.patch.object(tb.channels_mod, "check_channel",
                               lambda h, cfg=None: {"alive": True, "title": "T",
                                                     "subscribers": "1", "post_count": 1}):
            res2 = tb.handle_callback(42, "add:ok:gsmlabbot_test",
                                      {"telegram_chat_id": "42"}, api=api)
        self.assertTrue(res2["ok"])
        self.assertTrue(any(r["channel"] == "gsmlabbot_test"
                            for r in channels.list_channels()))

    def test_channels_add_requires_link(self):
        api = FakeAPI()
        res = tb.dispatch(42, "/channels add", {"telegram_chat_id": "42"}, api=api)
        self.assertFalse(res["ok"])

    def test_channels_rm_archives(self):
        channels.add_channel("rmch_test", origin="manual")
        api = FakeAPI()
        res = tb.dispatch(42, "/channels rm @rmch_test",
                          {"telegram_chat_id": "42"}, api=api)
        self.assertTrue(res["ok"])
        row = [r for r in channels.list_channels() if r["channel"] == "rmch_test"][0]
        self.assertEqual(row["status"], "archived")

    def test_search_alias_and_keyword(self):
        def fake_search(query, cfg=None, **kw):
            return {"query": query, "channels": ["ch"], "ok": 1, "failed": [],
                    "items": [{"channel": "ch", "url": "https://t.me/s/ch/1",
                               "excerpt": "hit"}]}

        api = FakeAPI()
        res = tb.dispatch(42, "/search firmware", {"telegram_chat_id": "42"},
                          api=api, tg_search=fake_search)
        self.assertEqual(res["action"], "search")
        self.assertEqual(res["count"], 1)

        api2 = FakeAPI()
        res2 = tb.dispatch(42, "/channels firmware", {"telegram_chat_id": "42"},
                           api=api2, tg_search=fake_search)
        self.assertEqual(res2["action"], "channels_search")

    def test_research_deep_flag_appends_deep_links(self):
        api = FakeAPI()
        res = tb.dispatch(42, "/research firmware --deep",
                          {"telegram_chat_id": "42"}, api=api,
                          research=lambda q, cfg: "# Report")
        self.assertTrue(res["ok"])
        self.assertTrue(res.get("deep"))
        joined = "\n".join(t for _, t, _ in api.sent)
        self.assertIn("ahmia.fi/search/?q=firmware", joined)

    def test_research_requires_query(self):
        api = FakeAPI()
        res = tb.dispatch(42, "/research --deep", {"telegram_chat_id": "42"}, api=api)
        self.assertFalse(res["ok"])


class TestProgressAndTrace(unittest.TestCase):
    def tearDown(self):
        tb._STATUS_MESSAGES.pop(42, None)
        tb._STATUS_LAST_EDIT.pop(42, None)

    def test_stage_status_throttled(self):
        api = FakeAPI()
        tb._STATUS_MESSAGES[42] = 7
        self.assertTrue(tb._stage_status(42, api, "Plan"))
        self.assertFalse(tb._stage_status(42, api, "Sources"))  # 3s gap
        self.assertEqual(len(api.edits), 1)
        tb._STATUS_LAST_EDIT[42] = time.monotonic() - 10
        self.assertTrue(tb._stage_status(42, api, "Fetch"))
        self.assertEqual(len(api.edits), 2)

    def test_bluf_shows_local_trace_path(self):
        path = str(config.data_dir() / "runs" / "3.json")
        text = tb._bluf_text("q", {"items": []}, 0.9, "high", [], [],
                             trace_path=path)
        self.assertIn("data/runs/3.json", text)
        self.assertNotIn("http", text)

    def test_orchestrator_stages_and_trace(self):
        stages = []
        out = orchestrator.run("firmware unlock", live=False,
                               cfg=config.load(), save=False,
                               on_stage=lambda name, detail="": stages.append(name))
        self.assertTrue(out["ok"])
        for name in ("Plan", "Sources", "Fetch", "Verify", "Brief"):
            self.assertIn(name, stages)
        trace = str(out.get("trace_path") or "")
        self.assertTrue(trace.endswith(".json"), trace)
        self.assertTrue(os.path.isfile(trace), trace)
        self.assertIn("runs", trace)


class TestExploreGate(unittest.TestCase):
    def tearDown(self):
        tb._EXPLORE_PENDING.pop(42, None)
        tb._EXPLORE_SHOWN.pop(42, None)

    def _res(self):
        return {
            "topic": "android security", "query": "android security", "items": 1,
            "discovery": {"added": ["expch1"], "dead": [], "candidates": 2,
                          "probed": 1,
                          "counts": {"active": 1, "dead": 0, "archived": 0,
                                     "stale": 0, "total": 1}},
            "scored": [{"title": "Site A", "url": "https://example.com/a",
                        "source": "example", "score": 5}],
        }

    def test_explore_cards_links_and_gate(self):
        api = FakeAPI()
        with mock.patch.object(tb.scheduler, "run_job", lambda *a, **k: self._res()):
            res = tb.dispatch(42, "/explore android security",
                              {"telegram_chat_id": "42"}, api=api)
        self.assertTrue(res["ok"])
        cards = api.sent[-1][1]
        self.assertIn("https://t.me/expch1", cards)
        self.assertIn("@expch1", cards)
        self.assertIn("https://example.com/a", cards)
        buttons = api.sent[-1][2]
        self.assertIn("exp:keep:ch:expch1", buttons[0][0]["callback_data"])
        self.assertIn("exp:skip:all", buttons[-1][1]["callback_data"])

    def test_explore_keep_and_skip(self):
        channels.add_channel("expch1", origin="auto")
        api = FakeAPI()
        with mock.patch.object(tb.scheduler, "run_job", lambda *a, **k: self._res()):
            tb.dispatch(42, "/explore android security",
                        {"telegram_chat_id": "42"}, api=api)
        # pehla item skip -> archive
        res = tb.handle_callback(42, "exp:skip:ch:expch1",
                                 {"telegram_chat_id": "42"}, api=api)
        self.assertTrue(res["ok"])
        row = [r for r in channels.list_channels() if r["channel"] == "expch1"][0]
        self.assertEqual(row["status"], "archived")
        # site keep -> tg_sites memory
        res2 = tb.handle_callback(42, "exp:keep:st:0",
                                  {"telegram_chat_id": "42"}, api=api)
        self.assertTrue(res2["ok"])
        self.assertTrue(any(s["url"] == "https://example.com/a"
                            for s in channels.list_sites()))

    def test_explore_bulk_keep(self):
        api = FakeAPI()
        with mock.patch.object(tb.scheduler, "run_job", lambda *a, **k: self._res()):
            tb.dispatch(42, "/explore android security",
                        {"telegram_chat_id": "42"}, api=api)
        res = tb.handle_callback(42, "exp:keep:all",
                                 {"telegram_chat_id": "42"}, api=api)
        self.assertTrue(res["ok"])
        # channel + site dono memory me (deep links bhi gate me shaamil)
        self.assertGreaterEqual(res["kept"], 2)
        self.assertTrue(any(r["channel"] == "expch1" for r in channels.list_channels()))
        self.assertTrue(any(s["url"] == "https://example.com/a"
                            for s in channels.list_sites()))


class TestStatusExploreBlock(unittest.TestCase):
    def test_status_has_explore_block(self):
        api = FakeAPI()
        res = tb.dispatch(42, "/status", {"telegram_chat_id": "42"}, api=api)
        self.assertTrue(res["ok"])
        text = api.sent[0][1]
        self.assertIn("Telegram:", text)
        self.assertIn("pending candidates", text)
        self.assertIn("Sources:", text)
        self.assertIn("Explore:", text)
        self.assertIn("Sites memory:", text)
        self.assertIn("pending_candidates", res)


if __name__ == "__main__":
    unittest.main()
