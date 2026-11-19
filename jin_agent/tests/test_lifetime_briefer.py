"""Lifetime fix (briefer): reports dir bounded pruning (G4)."""

import os
import tempfile
import time
import unittest
from unittest import mock

from jin_agent import briefer, config, store  # noqa: E402


def setUpModule():
    os.environ["JIN_AGENT_DATA"] = tempfile.mkdtemp(prefix="jin-life-brief-")
    store.init_db()


def _old_file(name: str, age_days: int):
    path = config.reports_dir() / name
    path.write_text("old", encoding="utf-8")
    ts = time.time() - age_days * 86400
    os.utime(path, (ts, ts))
    return path


class TestReportPruning(unittest.TestCase):
    def test_prune_removes_old_md_csv_json_only(self):
        old_md = _old_file("brief-old.md", 200)
        old_csv = _old_file("brief-old.csv", 200)
        old_json = _old_file("brief-old.json", 200)
        old_txt = _old_file("brief-old.txt", 200)      # allowed nahi — rehta hai
        fresh = _old_file("brief-fresh.md", 1)
        pruned = briefer.prune_reports(90)
        self.assertEqual(pruned, 3)
        for path in (old_md, old_csv, old_json):
            self.assertFalse(path.exists())
        self.assertTrue(old_txt.exists())
        self.assertTrue(fresh.exists())

    def test_report_days_env(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("JIN_AGENT_REPORT_DAYS", None)
            self.assertEqual(briefer.report_days(), 90)
        with mock.patch.dict(os.environ, {"JIN_AGENT_REPORT_DAYS": "10"}):
            self.assertEqual(briefer.report_days(), 10)
        with mock.patch.dict(os.environ, {"JIN_AGENT_REPORT_DAYS": "abc"}):
            self.assertEqual(briefer.report_days(), 90)

    def test_save_prunes_old_reports(self):
        old = _old_file("brief-ancient.md", 300)
        built = {"title": "t", "markdown": "m", "csv": "c", "json": "{}"}
        out = briefer.save(built, "q")
        self.assertIn("pruned_reports", out)
        self.assertGreaterEqual(out["pruned_reports"], 1)
        self.assertFalse(old.exists())
        self.assertTrue(os.path.isfile(out["md"]))


if __name__ == "__main__":
    unittest.main()
