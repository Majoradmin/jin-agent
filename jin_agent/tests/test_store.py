"""P15 / P21 - SQLite WAL + FTS5, dedupe, jobs, retention, backup."""

import os
import tempfile
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]

from jin_agent import store, util  # noqa: E402


def setUpModule():
    os.environ["JIN_AGENT_DATA"] = tempfile.mkdtemp(prefix="jin-store-")


def rec(title, url=None, source="Test", key="test"):
    return {
        "guid": key + ":" + util.fingerprint(title),
        "title": title, "url": url or ("https://news.google.com/" + util.fingerprint(title)[:10]),
        "canonical": "", "source": source, "source_key": key,
        "category": "Security", "published": util.now_iso(),
        "date_checked": util.now_iso(), "fetched_at": util.now_iso(),
        "excerpt": "Bootloader vulnerability CVE-2026-44120 on SM-G991B",
        "body": "", "fingerprint": util.fingerprint(title),
        "content_hash": util.sha256(title), "entities": [{"kind": "cve", "value": "CVE-2026-44120"}],
        "score": 1.0, "reasons": ["test"], "confidence": 0.8,
        "verified": True, "cross_verified": False, "link_only": False,
        "useful": 0, "meta": {"kind": "rss"},
    }


class TestStore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state = store.init_db()

    def test_01_fts5_available(self):
        self.assertTrue(self.state["fts5"], self.state["fts_error"])

    def test_02_upsert_insert_then_update(self):
        first = store.upsert_items([rec("Android bulletin November")])
        self.assertEqual(first["inserted"], 1)
        second = store.upsert_items([rec("Android bulletin November")])
        self.assertEqual(second["inserted"], 0)
        self.assertEqual(second["updated"], 1)
        self.assertEqual(store.counts()["items"], 1)

    def test_03_fts_search(self):
        store.upsert_items([rec("Qualcomm firehose loader UFS")])
        rows = store.search_archive("firehose", 10)
        self.assertTrue(any("firehose" in r["title"].lower() for r in rows))

    def test_04_fts_query_sanitized(self):
        rows = store.search_archive('" OR * ) (', 5)
        self.assertIsInstance(rows, list)

    def test_05_entities_synced(self):
        store.upsert_items([rec("CVE entity sync check")])
        self.assertGreater(store.counts()["entities"], 0)

    def test_06_watchlist_archive_not_delete(self):
        store.add_watchlist("MT6789")
        store.add_watchlist("MT6789")
        self.assertEqual(len([w for w in store.list_watchlist() if w["term"] == "MT6789"]), 1)
        store.remove_watchlist("MT6789")
        row = next(w for w in store.list_watchlist() if w["term"] == "MT6789")
        self.assertEqual(row["active"], 0)
        self.assertFalse(any(w["term"] == "MT6789"
                             for w in store.list_watchlist(active_only=True)))

    def test_07_jobs_lifecycle(self):
        jid = store.enqueue_job("feeds", {"offline": True})
        job = None
        for _ in range(5):
            job = store.claim_job()
            if job:
                break
        self.assertIsNotNone(job)
        self.assertEqual(job["kind"], "feeds")
        store.finish_job(job["id"], True)
        self.assertIn("done", [j["status"] for j in store.list_jobs()])

    def test_08_reports(self):
        saved = store.save_report("Unit brief", "test", str(BASE / "jin_agent" / "data" / "x.md"))
        self.assertGreater(saved["id"], 0)
        self.assertTrue(any(r["title"] == "Unit brief" for r in store.list_reports()))

    def test_09_feedback(self):
        guid = rec("Feedback item")["guid"]
        store.upsert_items([rec("Feedback item")])
        store.add_feedback(guid, True, "useful")
        self.assertEqual(store.feedback_score(guid), 1)

    def test_10_events_redact_secrets(self):
        store.add_event("test", "bot123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ and sk-abcdefghijklmnop")
        detail = store.list_events(1)[0]["detail"]
        self.assertNotIn("ABCDEFGHIJKLMNOP", detail)
        self.assertNotIn("sk-abcdefghijklmnop", detail)

    def test_11_retention_keeps_sources(self):
        old = rec("Ancient item")
        old["guid"] = "test:ancient"
        old["fetched_at"] = "2020-01-01T00:00:00Z"
        store.upsert_items([old])
        before = store.counts()["sources"]
        out = store.retention(30)
        self.assertGreaterEqual(out["removed"], 1)
        self.assertEqual(store.counts()["sources"], before)

    def test_12_backup(self):
        out = store.backup()
        self.assertTrue(Path(out["path"]).is_file())
        self.assertGreater(out["bytes"], 0)

    def test_13_overview_shape(self):
        ov = store.overview()
        for key in ("items", "runs", "sources", "fts5", "db", "cross_verified"):
            self.assertIn(key, ov)


if __name__ == "__main__":
    unittest.main()
