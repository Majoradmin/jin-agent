"""Phase 2: aggregate confidence, threshold gate, report file, /explore.

Competitor patterns (web research):
  * per-claim confidence + hard caps (single-source 0.6, 2+ independent 0.7+)
  * report ko chat flood ki jagah sendDocument (file) ki shakal me
  * rozana scored digest / explore
"""

import json
import os
import tempfile
import unittest
from unittest import mock

from jin_agent import (briefer, config, orchestrator, scheduler, store,
                       telegram_bot as tb, verifier)  # noqa: E402


def setUpModule():
    os.environ["JIN_AGENT_DATA"] = tempfile.mkdtemp(prefix="jin-p2-")
    store.init_db()


class DocAPI:
    def __init__(self):
        self.sent = []
        self.docs = []

    def send(self, chat_id, text, buttons=None):
        self.sent.append((int(chat_id), str(text), buttons))
        return {"ok": True}

    def send_document(self, chat_id, file_path, caption="", timeout=120):
        self.docs.append((int(chat_id), str(file_path), str(caption)))
        return {"ok": True, "result": {"message_id": 1}}

    def get_updates(self, offset, timeout=None):
        return []

    def answer_callback(self, callback_id, text=""):
        return {"ok": True}


class TestAggregateConfidence(unittest.TestCase):
    def test_caps_and_score_weighting(self):
        items = [
            {"confidence": 0.9, "score": 10, "verified": True, "cross_verified": True},
            {"confidence": 0.9, "score": 1, "verified": False, "cross_verified": False},
        ]
        out = verifier.aggregate_confidence(items)
        # cross: min(0.99, 0.90+0.05)=0.95 ; single: cap 0.60
        expected = round((0.95 * 10 + 0.60 * 1) / 11, 3)
        self.assertAlmostEqual(out["value"], expected, places=3)
        self.assertEqual(out["cross_verified"], 1)
        self.assertEqual(out["verified"], 1)

    def test_single_source_never_above_cap(self):
        out = verifier.aggregate_confidence([{"confidence": 0.99, "score": 5}])
        self.assertLessEqual(out["value"], 0.6)

    def test_empty(self):
        out = verifier.aggregate_confidence([])
        self.assertEqual(out["value"], 0.0)
        self.assertEqual(out["label"], "n/a")

    def test_briefer_includes_confidence(self):
        items = [{"confidence": 0.8, "score": 3, "verified": True,
                  "cross_verified": False, "title": "t", "category": "Security"}]
        built = briefer.build("q", items, [], config.load())
        self.assertIn("confidence", built)
        self.assertIn("confidence", json.loads(built["json"]))
        self.assertIn("Confidence:", built["markdown"])

    def test_orchestrator_metrics_confidence(self):
        out = orchestrator.run("MediaTek preloader", live=False, save=False)
        self.assertIn("confidence", out["metrics"])
        self.assertIn("confidence_label", out["metrics"])
        self.assertGreaterEqual(out["metrics"]["confidence"], 0.0)
        self.assertLessEqual(out["metrics"]["confidence"], 1.0)

    def test_threshold_env(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("JIN_AGENT_REPORT_CONFIDENCE", None)
            self.assertEqual(verifier.confidence_threshold(), 0.6)
        with mock.patch.dict(os.environ, {"JIN_AGENT_REPORT_CONFIDENCE": "0.75"}):
            self.assertEqual(verifier.confidence_threshold(), 0.75)
        with mock.patch.dict(os.environ, {"JIN_AGENT_REPORT_CONFIDENCE": "abc"}):
            self.assertEqual(verifier.confidence_threshold(), 0.6)


class TestReportFileDelivery(unittest.TestCase):
    def _patch_full(self, path, confidence, label="high"):
        def fake_full(query, cfg, save=True, live=True, skip_sources=None,
                      skip_channels=None):
            return {"ok": True, "markdown": "# Report\n" + "x" * 5000,
                    "sources": ["s1"], "channels": ["c1"],
                    "failed_channels": [], "report_path": path,
                    "confidence": confidence, "confidence_label": label}
        return mock.patch.object(tb, "research_full", fake_full)

    def test_high_confidence_sends_document_not_chunks(self):
        path = os.path.join(config.reports_dir(), "brief-test-high.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("# Report")
        api = DocAPI()
        with self._patch_full(path, 0.9):
            res = tb._send_research(42, "q", {"telegram_chat_id": "42", "llm": {}}, api)
        self.assertTrue(res["ok"])
        self.assertEqual(len(api.docs), 1)
        self.assertEqual(api.docs[0][1], path)
        self.assertIn("Confidence", api.docs[0][2])
        # markdown ke 4-11 chunks nahi — sirf chhota summary
        self.assertLessEqual(len(api.sent), 3)
        self.assertTrue(any("Report tayyar hai" in t for _, t, _ in api.sent))

    def test_low_confidence_no_document(self):
        path = os.path.join(config.reports_dir(), "brief-test-low.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("# Report")
        api = DocAPI()
        with self._patch_full(path, 0.2, label="low"):
            res = tb._send_research(42, "q", {"telegram_chat_id": "42", "llm": {}}, api)
        self.assertTrue(res["ok"])
        self.assertEqual(api.docs, [])
        self.assertTrue(any("bharosemand nahi" in t for _, t, _ in api.sent))

    def test_send_document_multipart(self):
        path = os.path.join(config.reports_dir(), "brief-multipart.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("# file")
        seen = {}

        class Resp:
            def read(self):
                return b'{"ok": true, "result": {"message_id": 1}}'

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        class FakeOpener:
            def open(self, req, timeout=None):
                seen["body"] = req.data
                seen["ctype"] = req.get_header("Content-type")
                return Resp()

        cfg = {"proxy_type": "", "proxy_host": "", "proxy_port": 0}
        with mock.patch.object(tb.urllib.request, "build_opener",
                               lambda *a, **k: FakeOpener()):
            api = tb._api("TOK", cfg)
            res = api.send_document(42, path, caption="caption here")
        self.assertTrue(res.get("ok"))
        self.assertIn(b'name="document"', seen["body"])
        self.assertIn(b'name="chat_id"', seen["body"])
        self.assertIn(b"caption here", seen["body"])
        self.assertTrue(seen["ctype"].startswith("multipart/form-data; boundary="))


class TestExplore(unittest.TestCase):
    def test_explore_job(self):
        out = scheduler.run_job("explore", {"query": "firmware", "offline": True},
                                config.load(), offline=True)
        self.assertIn("discovery", out)
        self.assertIn("scored", out)
        self.assertIn("items", out)

    def test_format_explore(self):
        text = tb.format_explore({"topic": "firmware", "items": 4,
                                  "discovery": {"added": ["a"], "dead": ["d"],
                                                "candidates": 5, "probed": 2},
                                  "scored": [{"title": "Story", "score": 3,
                                              "source": "x"}]})
        self.assertIn("Explore: firmware", text)
        self.assertIn("Story", text)
        self.assertIn("1 naye active", text)

    def test_dispatch_explore(self):
        api = DocAPI()
        res = tb.dispatch(42, "/explore firmware", {"telegram_chat_id": "42"}, api=api)
        self.assertTrue(res["ok"])
        self.assertEqual(res["action"], "explore")
        self.assertIn("Explore", "\n".join(t for _, t, _ in api.sent))

    def test_explore_job_registered(self):
        self.assertIn("explore", scheduler.JOB_MINUTES)
        self.assertEqual(scheduler.JOB_MINUTES["explore"], "explore_minutes")
        self.assertEqual(config.DEFAULT["schedule"]["explore_minutes"], 1440)


if __name__ == "__main__":
    unittest.main()
