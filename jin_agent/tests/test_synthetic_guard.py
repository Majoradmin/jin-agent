"""Synthetic (offline fixture) items user-facing archive se bahar hain.

Hosted deploy par scheduler offline chalne par `adapters._offline_items`
`https://example.org/<fingerprint>` jaisi banawati links deta tha; wo items
archive me jamate the aur `/explore` / `/digest` unhe asli khabar ki tarah
dikhate the. Ye tests us pollution ko rokte hain.
"""

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from jin_agent import config, server, store, util

OLD_ITEMS_DDL = """
CREATE TABLE items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  guid TEXT NOT NULL UNIQUE,
  url TEXT NOT NULL DEFAULT '',
  canonical TEXT NOT NULL DEFAULT '',
  title TEXT NOT NULL DEFAULT '',
  source TEXT NOT NULL DEFAULT '',
  source_key TEXT NOT NULL DEFAULT '',
  tier TEXT NOT NULL DEFAULT 'T0',
  trust REAL NOT NULL DEFAULT 0.5,
  trust_label TEXT NOT NULL DEFAULT 'Unverified',
  category TEXT NOT NULL DEFAULT 'Custom Watchlist',
  published TEXT NOT NULL DEFAULT '',
  date_checked TEXT NOT NULL DEFAULT '',
  fetched_at TEXT NOT NULL DEFAULT '',
  excerpt TEXT NOT NULL DEFAULT '',
  body TEXT NOT NULL DEFAULT '',
  fingerprint TEXT NOT NULL DEFAULT '',
  content_hash TEXT NOT NULL DEFAULT '',
  entities TEXT NOT NULL DEFAULT '[]',
  score REAL NOT NULL DEFAULT 0,
  reasons TEXT NOT NULL DEFAULT '[]',
  confidence REAL NOT NULL DEFAULT 0,
  verified INTEGER NOT NULL DEFAULT 0,
  cross_verified INTEGER NOT NULL DEFAULT 0,
  link_only INTEGER NOT NULL DEFAULT 0,
  useful INTEGER NOT NULL DEFAULT 0,
  meta TEXT NOT NULL DEFAULT '{}'
);
"""


def _rec(title, url, key="test", **extra):
    item = {
        "guid": key + ":" + util.fingerprint(title),
        "title": title, "url": url, "canonical": "",
        "source": "Test", "source_key": key, "category": "Security",
        "published": util.now_iso(), "date_checked": util.now_iso(),
        "fetched_at": util.now_iso(), "excerpt": title, "body": "",
        "fingerprint": util.fingerprint(title), "content_hash": util.sha256(title),
        "entities": [], "score": 1.0, "reasons": [], "confidence": 0.8,
        "verified": True, "cross_verified": False, "link_only": False,
        "useful": 0, "meta": {},
    }
    item.update(extra)
    return item


def setUpModule():
    os.environ["JIN_AGENT_DATA"] = tempfile.mkdtemp(prefix="jin-synth-")


class TestSyntheticGuard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state = store.init_db()
        store.upsert_items([
            _rec("iPhone activation policy server-side explained",
                 "https://example.org/8badfbb73842", "androidpolice",
                 kind="fixture", offline=True),
            _rec("Real bootloader vulnerability note",
                 "https://news.google.com/real-bootloader", "gnews"),
        ])

    def test_01_fts5_available(self):
        self.assertTrue(self.state["fts5"], self.state["fts_error"])

    def test_02_fixture_item_flagged_synthetic(self):
        row = store.get_item("androidpolice:" +
                             util.fingerprint("iPhone activation policy server-side explained"))
        self.assertIsNotNone(row)
        self.assertEqual(row["synthetic"], 1)

    def test_03_real_item_not_synthetic(self):
        row = store.get_item("gnews:" +
                             util.fingerprint("Real bootloader vulnerability note"))
        self.assertIsNotNone(row)
        self.assertEqual(row["synthetic"], 0)

    def test_04_search_archive_hides_fixture(self):
        rows = store.search_archive("iPhone activation", 20)
        self.assertEqual(rows, [])
        # asli item abhi bhi dhoondha ja sakta hai
        self.assertTrue(store.search_archive("bootloader", 20))

    def test_05_example_org_url_never_returned(self):
        for rows in (store.search_archive("", 200), store.search_archive("iPhone", 200)):
            for r in rows:
                self.assertNotIn("example.org", str(r.get("url") or ""))
                self.assertNotIn("example.org", str(r.get("canonical") or ""))

    def test_06_old_db_migration_marks_example_org(self):
        tmp = tempfile.mkdtemp(prefix="jin-olddb-")
        db = Path(tmp) / "jin_agent.db"
        con = sqlite3.connect(str(db))
        con.executescript(OLD_ITEMS_DDL)
        con.execute(
            "INSERT INTO items(guid,url,title,source,source_key,category,excerpt,"
            "fetched_at,date_checked) VALUES(?,?,?,?,?,?,?,?,?)",
            ("old:1", "https://example.org/8badfbb73842", "Purani fixture khabar",
             "Android Police", "androidpolice", "Security", "purani", "2026-01-01",
             "2026-01-01"))
        con.commit()
        con.close()

        prev = os.environ.get("JIN_AGENT_DATA")
        try:
            os.environ["JIN_AGENT_DATA"] = tmp
            store.init_db()
            with store.session() as c:
                row = c.execute("SELECT synthetic FROM items WHERE guid='old:1'").fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["synthetic"], 1)
            # aur user-facing search se bhi bahar
            self.assertEqual(store.search_archive("Purani fixture", 20), [])
        finally:
            if prev is None:
                os.environ.pop("JIN_AGENT_DATA", None)
            else:
                os.environ["JIN_AGENT_DATA"] = prev
            store.init_db()


class TestSchedulerLiveDefault(unittest.TestCase):
    def test_07_scheduler_default_live(self):
        prev = os.environ.get("JIN_AGENT_SCHEDULER_OFFLINE")
        try:
            os.environ.pop("JIN_AGENT_SCHEDULER_OFFLINE", None)
            self.assertFalse(server._scheduler_offline_default())
            os.environ["JIN_AGENT_SCHEDULER_OFFLINE"] = "1"
            self.assertTrue(server._scheduler_offline_default())
        finally:
            if prev is None:
                os.environ.pop("JIN_AGENT_SCHEDULER_OFFLINE", None)
            else:
                os.environ["JIN_AGENT_SCHEDULER_OFFLINE"] = prev

    def test_08_scheduler_enabled_flag_still_works(self):
        prev = os.environ.get("JIN_AGENT_SCHEDULER")
        try:
            os.environ["JIN_AGENT_SCHEDULER"] = "off"
            self.assertFalse(server._scheduler_enabled())
            os.environ["JIN_AGENT_SCHEDULER"] = "on"
            self.assertTrue(server._scheduler_enabled())
        finally:
            if prev is None:
                os.environ.pop("JIN_AGENT_SCHEDULER", None)
            else:
                os.environ["JIN_AGENT_SCHEDULER"] = prev


if __name__ == "__main__":
    unittest.main()
