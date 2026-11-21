"""P0: /explore "sab dikhao" mode — har probed candidate card par aaye.

Live bug (2026-11-20): ``/explore free api key`` par RightDAO 11 handles milte
the, magar ``check_channel`` ne sab ko dead/insufficient mark kar diya (30-din
rule) — ``added`` 0, is liye gate sirf 1 archive card dikhata tha. Ab
``run_discovery`` har probed candidate ka row (status + note + score + title +
subs + last_post_at) return karti hai aur ``_explore_groups`` active ko top par
rakh kar sab cards dikhati hai. Liveness logic (30-din rule) waisi hi hai.

Stdlib-only, network mocked.
"""

import os
import tempfile
import unittest
from unittest import mock

from jin_agent import channels, config, store
from jin_agent import telegram_bot as tb


def setUpModule():
    os.environ["JIN_AGENT_DATA"] = tempfile.mkdtemp(prefix="jin-explore-all-")
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


def _dead_row(handle, note="dead: aakhri post 40 din purani (30-din rule)",
              title="", score=1, subs="", last_post_at="2026-05-24 10:00:00"):
    return {"channel": handle, "status": "dead", "score": score,
            "title": title, "subscribers": subs, "last_post_at": last_post_at,
            "post_count": 0, "note": note}


def _res(probe_rows, added=None):
    return {
        "topic": "free api key", "query": "free api key", "items": 1,
        "discovery": {"added": list(added or []), "dead": [],
                      "candidates": len(probe_rows),
                      "probed": len(probe_rows), "probe_rows": probe_rows,
                      "counts": {"active": len(added or []), "dead": 0,
                                 "archived": 0, "stale": 0, "total": 0}},
        "scored": [],
    }


class TestRunDiscoveryProbeRows(unittest.TestCase):
    """run_discovery: candidates list (active + dead) + note/title/subs."""

    def test_probe_rows_include_dead_candidates(self):
        rows = {"ch_a": _dead_row("ch_a", note="dead: 0 posts on preview"),
                "ch_b": _dead_row("ch_b", title="Some Channel", subs="1.2K")}
        seen = {}

        def fake_web(query, cfg=None, info=None, merge=False, providers=None):
            seen["web"] = query
            return ["ch_a", "ch_b"]

        with mock.patch.object(channels, "web_search_candidates", fake_web), \
             mock.patch.object(channels, "harvest_archive",
                               lambda cfg=None, query="": []), \
             mock.patch.object(channels, "check_channel",
                               lambda ch, cfg=None: rows[ch]):
            out = channels.run_discovery(config.load(), offline=False,
                                         max_add=5, query="python")
        self.assertEqual(seen.get("web"), "python")
        self.assertEqual(out.get("added"), [])
        # candidates ab bhi int (purane tests/compatible shape)
        self.assertIsInstance(out.get("candidates"), int)
        self.assertEqual(out["candidates"], 2)
        self.assertEqual(len(out["probe_rows"]), 2)  # dead bhi list me
        by = {r["channel"]: r for r in out["probe_rows"]}
        self.assertEqual(by["ch_a"]["status"], "dead")
        self.assertEqual(by["ch_a"]["note"], "dead: 0 posts on preview")
        self.assertEqual(by["ch_b"]["title"], "Some Channel")
        self.assertEqual(by["ch_b"]["subscribers"], "1.2K")
        self.assertEqual(by["ch_b"]["last_post_at"], "2026-05-24 10:00:00")

    def test_probe_rows_mark_active_added(self):
        row = {"channel": "act_ch", "status": "active", "score": 8,
               "title": "Live", "subscribers": "10K",
               "last_post_at": "2026-11-19 10:00:00", "post_count": 9,
               "note": "auto-discovered liveness check"}
        with mock.patch.object(channels, "web_search_candidates",
                               lambda q, cfg=None, info=None, merge=False, providers=None: ["act_ch"]), \
             mock.patch.object(channels, "harvest_archive",
                               lambda cfg=None, query="": []), \
             mock.patch.object(channels, "check_channel",
                               lambda ch, cfg=None: dict(row)):
            out = channels.run_discovery(config.load(), offline=False,
                                         max_add=5, query="python")
        self.assertEqual(out["added"], ["act_ch"])
        self.assertEqual(out["probe_rows"][0]["status"], "active")
        self.assertTrue(out["probe_rows"][0]["note"])

    def test_probe_rows_include_insufficient_data(self):
        row = {"channel": "low_ch", "status": "insufficient_data", "score": 2,
               "title": "Low", "subscribers": "", "last_post_at": "",
               "post_count": 0, "note": "insufficient_data: sirf 2 positive signs"}
        with mock.patch.object(channels, "web_search_candidates",
                               lambda q, cfg=None, info=None, merge=False, providers=None: ["low_ch"]), \
             mock.patch.object(channels, "harvest_archive",
                               lambda cfg=None, query="": []), \
             mock.patch.object(channels, "check_channel",
                               lambda ch, cfg=None: dict(row)):
            out = channels.run_discovery(config.load(), offline=False,
                                         max_add=5, query="python")
        self.assertEqual(out["added"], [])
        self.assertEqual(out["probe_rows"][0]["status"], "insufficient_data")
        self.assertEqual(out["probe_rows"][0]["note"],
                         "insufficient_data: sirf 2 positive signs")


class TestExploreGroupsAll(unittest.TestCase):
    def setUp(self):
        tb._EXPLORE_PENDING.pop(42, None)
        tb._EXPLORE_SHOWN.pop(42, None)
        tb._EXPLORE_TOPICS.clear()

    def tearDown(self):
        tb._EXPLORE_PENDING.pop(42, None)
        tb._EXPLORE_SHOWN.pop(42, None)

    def test_active_first_and_cap_15(self):
        rows = [_dead_row(f"dead{i:02d}", score=i) for i in range(1, 17)]
        rows.insert(0, {"channel": "act_ch", "status": "active", "score": 5,
                       "title": "Live", "subscribers": "10K",
                       "last_post_at": "2026-11-19 10:00:00",
                       "post_count": 9, "note": "auto-discovered"})
        groups = tb._explore_groups(_res(rows, added=["act_ch"]),
                                     "free api key", "all")
        tg = groups["tg"]
        self.assertEqual(len(tg), 15)  # cap
        self.assertEqual(tg[0]["handle"], "act_ch")  # active top par
        # score ke mutabiq top 15 — sab se kam score wala (dead01) nahi aaya
        self.assertNotIn("dead01", [it["handle"] for it in tg])
        self.assertIn("dead16", [it["handle"] for it in tg])
        # auto-save sirf active par
        self.assertTrue(tg[0]["auto_saved"])
        self.assertTrue(all(not it["auto_saved"] for it in tg[1:]))
        self.assertTrue(all(it["status"] == "dead" for it in tg[1:]))

    def test_badges_private_bot_stale(self):
        rows = [
            _dead_row("zlibrary_official", title="Private Channel",
                      note="dead: 0 posts on preview"),
            _dead_row("crypto_bot", title="Crypto Bot",
                      note="dead: 0 posts on preview"),
            _dead_row("medvedev_telegram", title="Medvedev",
                      note="dead: aakhri post 150 din purani (30-din rule)"),
        ]
        groups = tb._explore_groups(_res(rows), "free api key", "all")
        by = {it["handle"]: it for it in groups["tg"]}
        self.assertEqual(tb._explore_status_badge(by["zlibrary_official"]),
                         "🤖 bot/private")
        self.assertEqual(tb._explore_status_badge(by["crypto_bot"]),
                         "🤖 bot/private")
        self.assertEqual(tb._explore_status_badge(by["medvedev_telegram"]),
                         "⏳ stale (30+ din)")

    def test_probe_error_and_contact_are_bot_private(self):
        rows = [
            _dead_row("err_ch", note="probe error: TimeoutError"),
            _dead_row("join_ch", note="dead: Contact @admin for access"),
            _dead_row("low_ch", note="insufficient_data: sirf 2 positive signs",
                      last_post_at="2026-11-18 10:00:00"),
        ]
        groups = tb._explore_groups(_res(rows), "free api key", "all")
        by = {it["handle"]: it for it in groups["tg"]}
        self.assertEqual(tb._explore_status_badge(by["err_ch"]),
                         "🤖 bot/private")
        self.assertEqual(tb._explore_status_badge(by["join_ch"]),
                         "🤖 bot/private")
        # insufficient_data stale bucket me gira (3-badge scheme)
        self.assertEqual(tb._explore_status_badge(by["low_ch"]),
                         "⏳ stale (30+ din)")

    def test_counts_line_in_cards(self):
        rows = [{"channel": "act_ch", "status": "active", "score": 8,
                 "title": "Live", "subscribers": "10K", "last_post_at": "",
                 "post_count": 9, "note": ""}]
        rows += [_dead_row(f"dead{i}") for i in range(8)]
        rows += [_dead_row("priv_ch", title="Private Channel"),
                 _dead_row("bot_ch", title="Crypto Bot")]
        groups = tb._explore_groups(_res(rows, added=["act_ch"]),
                                     "free api key", "all")
        text = tb.format_explore_cards_v2("free api key", "all", groups)
        self.assertIn("📡 Telegram (11): 1 active · 8 stale · 2 private/bot",
                      text)
        self.assertEqual(text.count("auto-save ✅"), 1)

    def test_gate_shows_all_candidates(self):
        rows = [{"channel": "act_ch", "status": "active", "score": 8,
                 "title": "Live", "subscribers": "10K", "last_post_at": "",
                 "post_count": 9, "note": ""}]
        rows += [_dead_row(f"dead{i:02d}") for i in range(1, 15)]
        api = FakeAPI()
        with mock.patch.object(tb.scheduler, "run_job",
                               lambda *a, **k: _res(rows, added=["act_ch"])):
            res = tb.dispatch(42, "/explore free api key",
                              {"telegram_chat_id": "42"}, api=api)
        self.assertTrue(res["ok"])
        cards = api.sent[-1][1]
        self.assertIn("📡 Telegram (15): 1 active · 14 stale · 0 private/bot",
                      cards)
        self.assertIn("@act_ch", cards)
        self.assertIn("@dead01", cards)
        self.assertIn("auto-save ✅", cards)
        self.assertIn("⏳ stale (30+ din)", cards)
        self.assertNotIn("@dead15", cards)  # cap 15

    def test_topic_picker_intact(self):
        # ``/explore`` bina topic: picker buttons, discovery NAHI chalti.
        api = FakeAPI()
        with mock.patch.object(tb.scheduler, "run_job") as rj:
            res = tb.dispatch(42, "/explore", {"telegram_chat_id": "42"},
                              api=api)
        self.assertTrue(res["ok"])
        self.assertEqual(res["action"], "explore_topics")
        rj.assert_not_called()
        buttons = api.sent[-1][2]
        self.assertTrue(buttons)
        self.assertTrue(all(b["callback_data"].startswith("exp:topic:")
                            for row in buttons for b in row))

    def test_old_shape_added_only_still_works(self):
        # Purane ``added`` wala shape (probe_rows ke baghair) — fallback.
        res = {"topic": "python", "query": "python", "items": 0,
               "discovery": {"added": ["oldch"], "dead": [], "candidates": 1,
                             "probed": 1, "counts": {"active": 1}},
               "scored": []}
        groups = tb._explore_groups(res, "python", "all")
        self.assertEqual(len(groups["tg"]), 1)
        self.assertEqual(groups["tg"][0]["status"], "active")
        self.assertTrue(groups["tg"][0]["auto_saved"])
        text = tb.format_explore_cards_v2("python", "all", groups)
        self.assertIn("✅ active", text)
        self.assertIn("auto-save ✅", text)


if __name__ == "__main__":
    unittest.main()
