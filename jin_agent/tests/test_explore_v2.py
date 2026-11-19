"""P0: /explore v2 — topic required (koi niche default nahi), topic-driven
discovery, dedupe + per-chat shown memory, 4 scope buttons, har item par link,
deep web sirf links (onion fetch nahi), /status explore block, purane callbacks.

Sab kuch stdlib-only, network mocked.
"""

import os
import tempfile
import unittest
from unittest import mock

from jin_agent import channels, config, policy, scheduler, store
from jin_agent import telegram_bot as tb


def setUpModule():
    os.environ["JIN_AGENT_DATA"] = tempfile.mkdtemp(prefix="jin-explore-v2-")
    store.init_db()
    channels.ensure_table()


class FakeAPI:
    def __init__(self):
        self.sent = []
        self.edits = []

    def send(self, chat_id, text, buttons=None):
        self.sent.append((int(chat_id), str(text), buttons))
        return {"ok": True, "result": {"message_id": len(self.sent)}}

    def edit(self, chat_id, message_id, text, parse_mode=None):
        self.edits.append((int(chat_id), int(message_id), str(text)))
        return {"ok": True}

    def get_updates(self, offset, timeout=None):
        return []

    def answer_callback(self, callback_id, text=""):
        return {"ok": True}

    def set_my_commands(self, commands, timeout=30):
        return {"ok": True}


def _res(topic="android security", added=None, scored=None):
    return {
        "topic": topic, "query": topic, "items": 1,
        "discovery": {"added": list(added or ["expch1"]), "dead": [],
                      "candidates": 2, "probed": 1,
                      "counts": {"active": 1, "dead": 0, "archived": 0,
                                 "stale": 0, "total": 1}},
        "scored": list(scored or [
            {"title": "Site A", "url": "https://example.com/a",
             "source": "example", "source_key": "example", "score": 5}]),
    }


class TestTopicRequired(unittest.TestCase):
    def setUp(self):
        tb._EXPLORE_PENDING.pop(42, None)
        tb._EXPLORE_SHOWN.pop(42, None)
        tb._EXPLORE_TOPICS.clear()

    def test_explore_without_topic_shows_picker(self):
        api = FakeAPI()
        with mock.patch.object(tb.scheduler, "run_job") as rj:
            res = tb.dispatch(42, "/explore", {"telegram_chat_id": "42"}, api=api)
        self.assertTrue(res["ok"])
        self.assertEqual(res["action"], "explore_topics")
        rj.assert_not_called()
        text = api.sent[-1][1]
        self.assertIn("topic", text.lower())
        self.assertNotIn("mobile firmware security tools", text)
        buttons = api.sent[-1][2]
        self.assertTrue(buttons)
        self.assertTrue(all(b["callback_data"].startswith("exp:topic:")
                            for row in buttons for b in row))

    def test_no_niche_default_in_scheduler(self):
        # explore() bina topic par config.TOPICS se rotate kare (niche nahi)
        with mock.patch.object(scheduler.channels, "run_discovery",
                               return_value={"added": [], "dead": [],
                                             "counts": {"active": 0}}), \
             mock.patch.object(scheduler.orchestrator, "digest",
                               return_value={"saved": {},
                                             "report": {"facts_count": 0}}):
            out = scheduler.explore("", config.load(), offline=True)
        self.assertIn(out["topic"], config.TOPICS)
        self.assertNotEqual(out["topic"], "mobile firmware security tools")

    def test_run_job_explore_empty_query_rotates(self):
        with mock.patch.object(scheduler.channels, "run_discovery",
                               return_value={"added": [], "dead": [],
                                             "counts": {"active": 0}}), \
             mock.patch.object(scheduler.orchestrator, "digest",
                               return_value={"saved": {},
                                             "report": {"facts_count": 0}}):
            out = scheduler.run_job("explore", {}, config.load(), offline=True)
        self.assertIn(out["topic"], config.TOPICS)


class TestDedupeAndShown(unittest.TestCase):
    def setUp(self):
        tb._EXPLORE_PENDING.pop(42, None)
        tb._EXPLORE_SHOWN.pop(42, None)
        tb._EXPLORE_TOPICS.clear()

    def tearDown(self):
        tb._EXPLORE_PENDING.pop(42, None)
        tb._EXPLORE_SHOWN.pop(42, None)

    def test_same_handle_and_url_appear_once(self):
        scored = [
            {"title": "A", "url": "https://example.com/x", "source": "s",
             "source_key": "s", "score": 5},
            {"title": "B", "url": "https://example.com/x", "source": "s",
             "source_key": "s", "score": 4},
        ]
        api = FakeAPI()
        with mock.patch.object(tb.scheduler, "run_job",
                               lambda *a, **k: _res(added=["dup_ch"],
                                                    scored=scored)):
            res = tb.dispatch(42, "/explore android security",
                              {"telegram_chat_id": "42"}, api=api)
        self.assertTrue(res["ok"])
        cards = api.sent[-1][1]
        self.assertEqual(cards.count("@dup_ch"), 1)
        self.assertEqual(cards.count("https://example.com/x"), 1)
        self.assertEqual(res["items"], 6)  # 1 channel + 1 url (dedupe) + 4 deep

    def test_shown_memory_skips_repeat(self):
        api = FakeAPI()
        with mock.patch.object(tb.scheduler, "run_job",
                               lambda *a, **k: _res()):
            tb.dispatch(42, "/explore android security",
                        {"telegram_chat_id": "42"}, api=api)
            first_items = tb._EXPLORE_PENDING[42]["items"]
            self.assertTrue(first_items)
            res2 = tb.dispatch(42, "/explore android security",
                               {"telegram_chat_id": "42"}, api=api)
        self.assertTrue(res2["ok"])
        self.assertTrue(res2.get("empty"))
        self.assertEqual(res2["items"], 0)
        self.assertNotIn(42, tb._EXPLORE_PENDING)
        self.assertIn("pehle dikhaye", api.sent[-1][1])


class TestScopes(unittest.TestCase):
    def setUp(self):
        tb._EXPLORE_PENDING.pop(42, None)
        tb._EXPLORE_SHOWN.pop(42, None)
        tb._EXPLORE_TOPICS.clear()

    def tearDown(self):
        tb._EXPLORE_PENDING.pop(42, None)
        tb._EXPLORE_SHOWN.pop(42, None)

    def _dispatch_all(self, api):
        with mock.patch.object(tb.scheduler, "run_job",
                               lambda *a, **k: _res()):
            return tb.dispatch(42, "/explore android security",
                               {"telegram_chat_id": "42"}, api=api)

    def test_four_scope_buttons_present(self):
        api = FakeAPI()
        self._dispatch_all(api)
        cbs = [b["callback_data"] for row in api.sent[-1][2]
               for b in row]
        for scope in ("tg", "web", "oss", "deep"):
            self.assertTrue(any(c.startswith(f"exp:scope:{scope}:") for c in cbs),
                            scope)

    def test_deep_scope_links_only_and_onion_not_fetched(self):
        api = FakeAPI()
        self._dispatch_all(api)
        deep_cb = [b["callback_data"] for row in api.sent[-1][2]
                   for b in row
                   if b["callback_data"].startswith("exp:scope:deep:")][0]

        def no_onion(url, *a, **k):
            self.assertNotIn(".onion", str(url).lower(),
                             "deep scope ne onion fetch ki — mana hai")
            return ""

        with mock.patch.object(tb.scheduler, "run_job",
                               lambda *a, **k: _res()), \
             mock.patch.object(channels.adapters, "fetch", no_onion):
            res = tb.handle_callback(42, deep_cb,
                                     {"telegram_chat_id": "42"}, api=api)
        self.assertTrue(res["ok"])
        text = api.sent[-1][1]
        self.assertIn("Deep web links", text)
        self.assertIn(".onion", text)
        self.assertIn("fetch nahi", text)

    def test_onion_fetch_blocked_by_policy(self):
        ok, reason = policy.check_url("http://exampleabc123.onion/search")
        self.assertFalse(ok)
        self.assertIn("onion", reason.lower())

    def test_scope_callback_topic_from_pending(self):
        api = FakeAPI()
        self._dispatch_all(api)
        tg_cb = [b["callback_data"] for row in api.sent[-1][2]
                 for b in row
                 if b["callback_data"].startswith("exp:scope:tg:")][0]
        with mock.patch.object(tb.scheduler, "run_job",
                               lambda *a, **k: _res()):
            res = tb.handle_callback(42, tg_cb,
                                     {"telegram_chat_id": "42"}, api=api)
        self.assertTrue(res["ok"])
        self.assertEqual(res["scope"], "tg")
        self.assertIn("📡 Telegram", api.sent[-1][1])


class TestStatusBlock(unittest.TestCase):
    def test_status_has_full_explore_block(self):
        api = FakeAPI()
        res = tb.dispatch(42, "/status", {"telegram_chat_id": "42"}, api=api)
        self.assertTrue(res["ok"])
        text = api.sent[0][1]
        for needle in ("Telegram:", "Sites memory:", "Sources:",
                       "Explore:", "Aakhri explore:"):
            self.assertIn(needle, text)
        self.assertIn("pending_candidates", res)
        self.assertIn("last_explore_scope", res)
        self.assertIn("last_explore_topic", res)


class TestOldCallbacks(unittest.TestCase):
    def setUp(self):
        tb._EXPLORE_PENDING.pop(42, None)
        tb._EXPLORE_SHOWN.pop(42, None)
        tb._EXPLORE_TOPICS.clear()
        channels.add_channel("oldch", origin="auto")

    def tearDown(self):
        tb._EXPLORE_PENDING.pop(42, None)
        tb._EXPLORE_SHOWN.pop(42, None)

    def test_keep_and_skip_callbacks_still_work(self):
        api = FakeAPI()
        with mock.patch.object(tb.scheduler, "run_job",
                               lambda *a, **k: _res(added=["oldch"])):
            tb.dispatch(42, "/explore android security",
                        {"telegram_chat_id": "42"}, api=api)
        res = tb.handle_callback(42, "exp:skip:ch:oldch",
                                 {"telegram_chat_id": "42"}, api=api)
        self.assertTrue(res["ok"])
        row = [r for r in channels.list_channels()
               if r["channel"] == "oldch"][0]
        self.assertEqual(row["status"], "archived")
        res2 = tb.handle_callback(42, "exp:keep:all",
                                  {"telegram_chat_id": "42"}, api=api)
        self.assertTrue(res2["ok"])
        self.assertGreaterEqual(res2["kept"], 1)


class TestDiscoveryQuery(unittest.TestCase):
    def test_run_discovery_uses_query_for_web_and_harvest(self):
        seen = {}

        def fake_web(query, cfg=None, info=None):
            seen["web"] = query
            return ["web_ch"]

        def fake_harvest(cfg=None, query=""):
            seen["harvest_query"] = query
            return []

        def fake_probe(channel, cfg=None):
            return {"channel": channel, "status": "dead", "score": 0}

        with mock.patch.object(channels, "web_search_candidates", fake_web), \
             mock.patch.object(channels, "harvest_archive", fake_harvest), \
             mock.patch.object(channels, "check_channel", fake_probe):
            out = channels.run_discovery(config.load(), offline=False,
                                         max_add=2, query="python")
        self.assertEqual(seen.get("web"), "python")
        self.assertEqual(seen.get("harvest_query"), "python")
        self.assertEqual(out.get("query"), "python")

    def test_scheduler_explore_passes_query_to_discovery(self):
        seen = {}

        def fake_discovery(cfg, offline, query=""):
            seen["query"] = query
            return {"added": [], "dead": [], "counts": {"active": 0}}

        with mock.patch.object(scheduler.channels, "run_discovery",
                               fake_discovery), \
             mock.patch.object(scheduler.orchestrator, "digest",
                               return_value={"saved": {},
                                             "report": {"facts_count": 0}}):
            out = scheduler.explore("python", config.load(), offline=True)
        self.assertEqual(seen.get("query"), "python")
        self.assertEqual(out["topic"], "python")

    def test_scheduler_explore_scope_web_skips_channel_probe(self):
        with mock.patch.object(scheduler.channels, "run_discovery") as rd, \
             mock.patch.object(scheduler.orchestrator, "digest",
                               return_value={"saved": {},
                                             "report": {"facts_count": 0}}):
            scheduler.explore("python", config.load(), offline=True, scope="web")
        rd.assert_not_called()


if __name__ == "__main__":
    unittest.main()
