"""P14 / P16 / P21 - evaluation harness, scheduler, firehose, alerts, backup."""

import os
import tempfile
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]

from jin_agent import alerts, config, evaluator, scheduler, store  # noqa: E402


def setUpModule():
    os.environ["JIN_AGENT_DATA"] = tempfile.mkdtemp(prefix="jin-eval-")
    store.init_db()


class TestEvaluationHarness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = evaluator.run(live=False, save=True)

    def test_01_twenty_five_queries(self):
        self.assertEqual(len(evaluator.QUERIES), 25)
        self.assertEqual(self.result["queries"], 25)
        self.assertEqual(len(self.result["per_query"]), 25)

    def test_02_mode_is_honest(self):
        self.assertEqual(self.result["mode"], "offline-fixture")
        self.assertIn("Offline mode measures pipeline", evaluator.to_markdown(self.result))

    def test_03_no_fabricated_citations(self):
        self.assertEqual(self.result["metrics"]["fabricated_citations"], 0)

    def test_04_no_crashes(self):
        self.assertEqual(self.result["metrics"]["offline_crashes"], 0)

    def test_05_provenance_kpi(self):
        self.assertGreaterEqual(self.result["metrics"]["provenance_pct"], 100.0)

    def test_06_coverage_kpi(self):
        self.assertGreaterEqual(self.result["metrics"]["coverage_pct"],
                                evaluator.KPI["coverage_pct"])

    def test_07_precision_kpi(self):
        self.assertGreaterEqual(self.result["metrics"]["precision_at_10"],
                                evaluator.KPI["precision_at_10"])

    def test_08_safety_checks_all_pass(self):
        failing = [k for k, v in self.result["safety"].items() if not v]
        self.assertEqual(failing, [], "Safety failures: " + ", ".join(failing))

    def test_09_verdict_pass(self):
        self.assertTrue(self.result["passed"])

    def test_10_report_written(self):
        path = Path(self.result["report_path"])
        self.assertTrue(path.is_file())
        self.assertIn("Evaluation Report", path.read_text(encoding="utf-8"))

    def test_11_latency_recorded(self):
        self.assertGreater(self.result["metrics"]["avg_latency_ms"], 0)
        self.assertGreater(self.result["metrics"]["total_elapsed_ms"], 0)


class TestScheduler(unittest.TestCase):
    def test_firehose_stores_records(self):
        out = scheduler.firehose("MediaTek preloader", offline=True)
        self.assertGreater(out["raw"], 0)
        self.assertGreater(out["records"], 0)
        self.assertGreater(store.counts()["items"], 0)

    def test_tick_enqueues_and_processes(self):
        # An earlier thread test may have already advanced the due timestamps;
        # reset the schedule clock so this test is order-independent.
        with store.session() as con:
            con.execute("DELETE FROM schedule_state")
        out = scheduler.tick(config.load(), offline=True)
        self.assertIn("feeds", out["enqueued"])
        self.assertEqual(out["errors"], [])
        self.assertTrue(out["processed"])

    def test_watchlist_job(self):
        store.add_watchlist("MediaTek")
        # Watchlist user-facing archive par chalti hai — synthetic (offline
        # fixture) items wo se bahar hain, is liye asli item daalte hain.
        store.upsert_items([{
            "title": "MediaTek preloader scatter analysis",
            "url": "https://news.google.com/mediatek-preloader-scatter",
            "source": "Google News RSS", "source_key": "gnews",
            "excerpt": "MediaTek preloader scatter",
            "category": "Mobile & Firmware",
        }])
        out = scheduler.run_job("watchlist", {}, config.load(), offline=True)
        self.assertTrue(any(h["term"] == "MediaTek" for h in out["hits"]))

    def test_digest_job(self):
        out = scheduler.run_job("digest", {}, config.load(), offline=True)
        self.assertTrue(out["report"])
        self.assertGreaterEqual(out["items"], 0)

    def test_retention_and_backup_job(self):
        out = scheduler.run_job("retention", {}, config.load(), offline=True)
        self.assertIn("removed", out)
        self.assertTrue(Path(out["backup"]["path"]).is_file())

    def test_unknown_job_returns_error(self):
        self.assertIn("Unknown job", scheduler.run_job("nope")["error"])

    def test_thread_start_stop(self):
        worker = scheduler.Scheduler(config.load(), offline=True, poll_seconds=5)
        worker.start()
        self.assertTrue(worker.is_alive())
        self.assertIn("running", worker.state())
        worker.stop(15)
        self.assertFalse(worker.is_alive())


class TestAlerts(unittest.TestCase):
    def test_notify_without_token_is_local_only(self):
        out = alerts.notify("Unit test alert")
        self.assertTrue(out["local"])
        self.assertFalse(out["telegram"]["ok"])

    def test_no_token_configured(self):
        self.assertFalse(alerts.configured({"telegram_bot_token": "", "telegram_chat_id": ""}))
        self.assertEqual(alerts.get_updates({"telegram_bot_token": "", "telegram_chat_id": ""}), [])

    def test_events_never_contain_token(self):
        alerts.notify("bot123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ test")
        blob = " ".join(e["detail"] for e in store.list_events(50))
        self.assertNotIn("ABCDEFGHIJKLMNOP", blob)

    def test_commands(self):
        self.assertIn("JIN Agent", alerts.handle_command("/status"))
        self.assertIn("Commands", alerts.handle_command("/help"))
        self.assertIn("Eval", alerts.handle_command("/eval"))

    def test_config_mask(self):
        public = config.public()
        self.assertEqual(public["telegram_bot_token"], "")


if __name__ == "__main__":
    unittest.main()
