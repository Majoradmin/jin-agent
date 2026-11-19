"""Phase 3: log-scale scoring + 30-din rule, source/channel lifecycle,
suppression memory, per-run trace, repeated-claim detection."""

import json
import os
import tempfile
import time
import unittest
from unittest import mock

from jin_agent import (briefer, channels, config, llm, orchestrator,
                       searchmemory as memory, store, verifier)  # noqa: E402


def setUpModule():
    os.environ["JIN_AGENT_DATA"] = tempfile.mkdtemp(prefix="jin-p3-")
    store.init_db()
    memory.ensure_table()
    channels.ensure_table()


def _rec(**kw):
    base = {"channel": "x", "alive": True, "post_count": 5, "title": "GSM Lab",
            "last_post_at": "2026-11-18 10:00", "subscribers": "5000",
            "avg_text_len": 120, "harvested": [], "checked_at": time.time()}
    base.update(kw)
    return base


class TestLogScaleScoring(unittest.TestCase):
    def test_big_channels_not_over_rewarded(self):
        small = channels.score(_rec(subscribers="10000", post_count=10), config.load())
        big = channels.score(_rec(subscribers="1000000", post_count=1000), config.load())
        self.assertGreaterEqual(small, 1)
        self.assertLess(big - small, 4)   # log-scale: farq shayed barabar nahi

    def test_dead_channel_scores_low(self):
        sc = channels.score(_rec(alive=False, post_count=0, subscribers="",
                                 last_post_at="", title="", avg_text_len=0),
                            config.load())
        self.assertLessEqual(sc, 1)

    def test_channel_signs_and_insufficient_data(self):
        info = channels.channel_signs(_rec(), config.load())
        self.assertGreaterEqual(info["signs"], 3)
        poor = channels.channel_signs(_rec(post_count=0, subscribers="",
                                           avg_text_len=0, title=""), config.load())
        self.assertLess(poor["signs"], 3)

    def test_30_day_dead_rule(self):
        old = time.strftime("%Y-%m-%d %H:%M", time.gmtime(time.time() - 40 * 86400))
        rec = _rec(last_post_at=old)
        self.assertFalse(channels.channel_signs(rec, config.load())["recent"])
        with mock.patch.object(channels, "probe", lambda ch, cfg=None: rec):
            res = channels.check_channel("oldch", config.load())
        self.assertEqual(res["status"], "dead")

    def test_insufficient_data_status(self):
        rec = _rec(post_count=0, subscribers="", avg_text_len=0, title="")
        with mock.patch.object(channels, "probe", lambda ch, cfg=None: rec):
            res = channels.check_channel("thin_ch", config.load())
        self.assertEqual(res["status"], "insufficient_data")


class TestLifecycle(unittest.TestCase):
    def test_source_migration_columns(self):
        with store.session() as con:
            cols = {r[1] for r in con.execute("PRAGMA table_info(sources)")}
        for name in ("status", "last_verified_at", "stale_days"):
            self.assertIn(name, cols)

    def test_touch_source_sets_lifecycle(self):
        store.touch_source("nvd", True)
        with store.session() as con:
            row = con.execute("SELECT status,last_verified_at FROM sources "
                              "WHERE key='nvd'").fetchone()
        self.assertEqual(row["status"], "ok")
        self.assertTrue(row["last_verified_at"])
        store.touch_source("nvd", False, "boom")
        with store.session() as con:
            row = con.execute("SELECT status FROM sources WHERE key='nvd'").fetchone()
        self.assertEqual(row["status"], "verification_failed")

    def test_mark_stale_sources(self):
        store.touch_source("nvd", True)
        with store.session() as con:
            con.execute("UPDATE sources SET last_verified_at='2020-01-01T00:00:00Z' "
                        "WHERE key='nvd'")
        self.assertGreaterEqual(store.mark_stale_sources(), 1)
        with store.session() as con:
            row = con.execute("SELECT status FROM sources WHERE key='nvd'").fetchone()
        self.assertEqual(row["status"], "stale")

    def test_channel_stale_marking(self):
        now = int(time.time())
        with store.session() as con:
            con.execute("INSERT INTO tg_channels(channel,status,last_checked) "
                        "VALUES('stale_active','active',1)")
            con.execute("INSERT INTO tg_channels(channel,status,last_checked) "
                        "VALUES('fresh_active','active',?)", (now,))
        self.assertGreaterEqual(channels.mark_stale_channels(), 1)
        rows = {r["channel"]: r for r in channels.list_channels()}
        self.assertEqual(rows["stale_active"]["status"], "stale")
        self.assertEqual(rows["fresh_active"]["status"], "active")


class TestSuppressionMemory(unittest.TestCase):
    def test_rejected_ideas(self):
        row = memory.begin(1, "rejected ideas")
        memory.remember_rejected(row["id"], ["idea one", "idea two", "idea one"])
        self.assertEqual(memory.rejected_ideas(row["id"]), ["idea one", "idea two"])

    def test_source_counters(self):
        row = memory.begin(1, "source counters")
        memory.note_source_stat(row["id"], "nvd", "cited")
        memory.note_source_stat(row["id"], "nvd", "cited")
        memory.note_source_stat(row["id"], "brave", "skipped")
        stats = memory.source_stats(row["id"])
        self.assertEqual(stats["nvd"]["cited"], 2)
        self.assertEqual(stats["brave"]["skipped"], 1)

    def test_migration_columns(self):
        with store.session() as con:
            cols = {r[1] for r in con.execute("PRAGMA table_info(search_memory)")}
        self.assertIn("rejected_ideas", cols)
        self.assertIn("source_stats", cols)


class TestTraceAndTokens(unittest.TestCase):
    def test_run_writes_trace_json(self):
        out = orchestrator.run("MediaTek preloader", live=False, save=False)
        path = config.runs_dir() / f"{out['run_id']}.json"
        self.assertTrue(path.is_file())
        data = json.loads(path.read_text(encoding="utf-8"))
        for key in ("run_id", "query", "plan", "tools", "diagnostics",
                    "tokens", "duration_ms", "confidence"):
            self.assertIn(key, data)
        self.assertEqual(data["tokens"]["total_tokens"], 0)  # offline: LLM off

    def test_llm_budget_env(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("JIN_AGENT_TOKEN_BUDGET", None)
            self.assertEqual(llm.token_budget(), 100_000)
        with mock.patch.dict(os.environ, {"JIN_AGENT_TOKEN_BUDGET": "50"}):
            self.assertEqual(llm.token_budget(), 50)
        with mock.patch.dict(os.environ, {"JIN_AGENT_COST_PER_1M": "1.5"}):
            self.assertEqual(llm.cost_per_1m(), 1.5)

    def test_metrics_budget_meter(self):
        with mock.patch.dict(os.environ, {"JIN_AGENT_TOKEN_BUDGET": "0"}):
            out = orchestrator.run("Qualcomm EDL", live=False, save=False)
        self.assertIn("token_budget", out["metrics"])
        self.assertIn("budget_exceeded", out["metrics"])


class TestRepeatedClaims(unittest.TestCase):
    def test_cross_vs_same_channel(self):
        items = [
            {"fingerprint": "f1", "title": "Same story", "channel": "chA",
             "source_key": "s1"},
            {"fingerprint": "f1", "title": "Same story", "channel": "chB",
             "source_key": "s2"},
            {"fingerprint": "f2", "title": "Dup", "channel": "chA",
             "source_key": "s1"},
            {"fingerprint": "f2", "title": "Dup", "channel": "chA",
             "source_key": "s1"},
        ]
        out = {r["key"]: r for r in verifier.repeated_claims(items)}
        self.assertEqual(out["f1"]["label"], "cross-channel")
        self.assertEqual(out["f2"]["label"], "same-channel")

    def test_briefer_surfaces_repeated(self):
        items = [
            {"fingerprint": "f1", "title": "Story", "channel": "chA",
             "source_key": "s1", "confidence": 0.5, "score": 1},
            {"fingerprint": "f1", "title": "Story", "channel": "chB",
             "source_key": "s2", "confidence": 0.5, "score": 1},
        ]
        built = briefer.build("q", items, [], config.load())
        self.assertEqual(len(built["repeated_claims"]), 1)
        self.assertIn("Repeated Claims", built["markdown"])


if __name__ == "__main__":
    unittest.main()
