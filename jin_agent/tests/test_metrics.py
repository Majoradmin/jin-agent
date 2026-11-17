"""P26 - metrics counters/p50-p95 aur structured logging ki secret redaction."""

import json
import os
import tempfile
import threading
import unittest
from pathlib import Path

os.environ["JIN_AGENT_DATA"] = tempfile.mkdtemp(prefix="jin-metrics-")

from jin_agent import logging_setup, metrics  # noqa: E402

TOKEN = "bot" + "9" * 10 + ":" + "A" * 30
LLM_KEY = "sk-" + "b" * 24


class TestCounters(unittest.TestCase):
    def setUp(self):
        metrics.reset()

    def test_inc_counts(self):
        metrics.inc("queries_total")
        metrics.inc("queries_total", 2)
        self.assertEqual(metrics.get("queries_total"), 3)
        self.assertEqual(metrics.counters()["queries_total"], 3)

    def test_known_counters_start_at_zero(self):
        for name in ("queries_total", "runs_ok", "runs_blocked", "fetch_errors",
                     "reports_total"):
            self.assertEqual(metrics.get(name), 0, name)

    def test_gauge_roundtrip_and_bad_value_ignored(self):
        metrics.set_gauge("items_last_run", 12)
        self.assertEqual(metrics.gauges()["items_last_run"], 12.0)
        metrics.set_gauge("items_last_run", "nahi")
        self.assertEqual(metrics.gauges()["items_last_run"], 12.0)

    def test_thread_safe_increments(self):
        def worker():
            for _ in range(250):
                metrics.inc("runs_ok")

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(metrics.get("runs_ok"), 1000)

    def test_reset_zeroes_counters(self):
        metrics.inc("runs_blocked", 5)
        metrics.reset()
        self.assertEqual(metrics.get("runs_blocked"), 0)
        self.assertEqual(metrics.latency("run")["count"], 0)


class TestLatency(unittest.TestCase):
    def setUp(self):
        metrics.reset()

    def test_p50_p95_helpers(self):
        self.assertEqual(metrics.p50([10, 20, 30]), 20.0)
        self.assertEqual(metrics.p95([10, 20, 30, 40]), 40.0)
        self.assertEqual(metrics.percentile([], 95), 0.0)
        self.assertEqual(metrics.percentile([7], 95), 7.0)

    def test_observe_and_latency_summary(self):
        for ms in (10, 20, 30, 40):
            metrics.observe("run", ms)
        lat = metrics.latency("run")
        self.assertEqual(lat["count"], 4)
        self.assertEqual(lat["p50_ms"], 30.0)
        self.assertEqual(lat["p95_ms"], 40.0)
        self.assertEqual(lat["max_ms"], 40.0)
        self.assertEqual(metrics.latency("missing")["count"], 0)

    def test_snapshot_is_json_serialisable(self):
        metrics.inc("runs_ok")
        metrics.observe("run", 42)
        snap = metrics.snapshot()
        for key in ("ts", "counters", "gauges", "latency"):
            self.assertIn(key, snap)
        self.assertIn("run", snap["latency"])
        self.assertIn("runs_ok", json.dumps(snap))

    def test_compact_block(self):
        for ms in (10, 20, 30, 40):
            metrics.observe("run", ms)
        compact = metrics.compact()
        self.assertEqual(compact["run_p50_ms"], 30.0)
        self.assertEqual(compact["run_p95_ms"], 40.0)
        self.assertEqual(compact["latency_samples"], 4)
        self.assertIn("counters", compact)

    def test_persist_writes_summary(self):
        metrics.inc("reports_total", 2)
        path = metrics.persist()
        self.assertTrue(path)
        raw = Path(path).read_text(encoding="utf-8")
        self.assertEqual(json.loads(raw)["counters"]["reports_total"], 2)
        self.assertNotIn(TOKEN, raw)
        self.assertNotIn(LLM_KEY, raw)


class TestRedaction(unittest.TestCase):
    def test_redact_bot_token_and_llm_key(self):
        clean = logging_setup.redact(f"token {TOKEN} key {LLM_KEY}",
                                     secrets=(TOKEN, LLM_KEY))
        self.assertNotIn(TOKEN, clean)
        self.assertNotIn(LLM_KEY, clean)
        self.assertIn("***", clean)

    def test_redact_pattern_without_config(self):
        clean = logging_setup.redact(f"send {TOKEN} now")
        self.assertNotIn(TOKEN, clean)

    def test_redact_nested_fields(self):
        out = logging_setup.redact({"telegram_bot_token": TOKEN,
                                    "llm": {"key": LLM_KEY, "provider": "off"}})
        self.assertEqual(out["telegram_bot_token"], "***")
        self.assertEqual(out["llm"]["key"], "***")
        self.assertEqual(out["llm"]["provider"], "off")

    def test_secret_values_from_config(self):
        values = logging_setup.secret_values({"telegram_bot_token": TOKEN,
                                              "llm": {"key": LLM_KEY}})
        self.assertIn(TOKEN, values)
        self.assertIn(LLM_KEY, values)

    def test_log_file_is_json_lines_and_secret_free(self):
        logger = logging_setup.get_logger("test")
        logger.info("probe token=%s key=%s", TOKEN, LLM_KEY,
                    extra={"fields": {"telegram_bot_token": TOKEN,
                                      "llm": {"key": LLM_KEY}}})
        path = logging_setup.log_path()
        self.assertTrue(path.is_file())
        raw = path.read_text(encoding="utf-8", errors="replace")
        self.assertNotIn(TOKEN, raw)
        self.assertNotIn(LLM_KEY, raw)
        entries = [e for e in logging_setup.read_lines(200) if "probe" in e.get("msg", "")]
        self.assertTrue(entries)
        entry = entries[-1]
        for key in ("ts", "level", "logger", "msg"):
            self.assertIn(key, entry)
        self.assertEqual(entry["fields"]["telegram_bot_token"], "***")
        self.assertEqual(entry["fields"]["llm"]["key"], "***")


if __name__ == "__main__":
    unittest.main()
