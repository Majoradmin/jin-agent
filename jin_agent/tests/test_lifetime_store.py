"""Lifetime fixes (store): retention tables, rolling backups, VACUUM.

Context: retention sirf items delete karta tha — events/runs/reports/jobs/
search_memory/tg_candidates unbounded barte the. Backups bhi unbounded.
Ye tests G2/G3/G11 assert karte hain.
"""

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from jin_agent import channels, config, searchmemory, store, util  # noqa: E402


def setUpModule():
    os.environ["JIN_AGENT_DATA"] = tempfile.mkdtemp(prefix="jin-life-store-")
    store.init_db()
    searchmemory.ensure_table()
    channels.ensure_table()


OLD_ISO = "2020-01-01T00:00:00Z"


class TestRetentionTables(unittest.TestCase):
    def _seed(self):
        now_iso = util.now_iso()
        now_epoch = int(util.epoch())
        with store.session() as con:
            # purani rows
            con.execute("INSERT INTO events(ts,kind,detail) VALUES(?,?,?)",
                        (OLD_ISO, "old", "x"))
            con.execute("INSERT INTO runs(query,mode,started_at,status) "
                        "VALUES('q','offline',?,'done')", (OLD_ISO,))
            con.execute("INSERT INTO reports(title,query,path,created_at) "
                        "VALUES('t','q','p',?)", (OLD_ISO,))
            con.execute("INSERT INTO jobs(kind,payload,created_at) "
                        "VALUES('feeds','{}',?)", (OLD_ISO,))
            con.execute("INSERT INTO search_memory(chat_id,query_key,query,"
                        "updated_at) VALUES(1,'oldk','oldq',1)")
            con.execute("INSERT INTO tg_candidates(handle,found_at) "
                        "VALUES('oldhandle',1)")
            con.execute("INSERT INTO tg_channels(channel,status,last_checked) "
                        "VALUES('olddead','dead',1)")
            # fresh rows — ye bache rehne chahiye
            con.execute("INSERT INTO events(ts,kind,detail) VALUES(?,?,?)",
                        (now_iso, "new", "y"))
            con.execute("INSERT INTO runs(query,mode,started_at,status) "
                        "VALUES('q2','offline',?,'done')", (now_iso,))
            con.execute("INSERT INTO reports(title,query,path,created_at) "
                        "VALUES('t2','q2','p2',?)", (now_iso,))
            con.execute("INSERT INTO jobs(kind,payload,created_at) "
                        "VALUES('feeds','{}',?)", (now_iso,))
            con.execute("INSERT INTO search_memory(chat_id,query_key,query,"
                        "updated_at) VALUES(1,'newk','newq',?)", (now_epoch,))
            con.execute("INSERT INTO tg_candidates(handle,found_at) "
                        "VALUES('newhandle',?)", (now_epoch,))
            con.execute("INSERT INTO tg_channels(channel,status,last_checked) "
                        "VALUES('newdead','dead',?)", (now_epoch,))

    def test_retention_prunes_each_operational_table(self):
        self._seed()
        out = store.retention(30)
        self.assertGreaterEqual(out["pruned"].get("events", 0), 1)
        self.assertGreaterEqual(out["pruned"].get("runs", 0), 1)
        self.assertGreaterEqual(out["pruned"].get("reports", 0), 1)
        self.assertGreaterEqual(out["pruned"].get("jobs", 0), 1)
        self.assertGreaterEqual(out["pruned"].get("search_memory", 0), 1)
        self.assertGreaterEqual(out["pruned"].get("tg_candidates", 0), 1)
        self.assertGreaterEqual(out["pruned"].get("tg_channels_dead", 0), 1)
        # fresh rows bache
        with store.session() as con:
            self.assertEqual(con.execute(
                "SELECT COUNT(*) FROM events WHERE kind='new'").fetchone()[0], 1)
            self.assertEqual(con.execute(
                "SELECT COUNT(*) FROM runs WHERE query='q2'").fetchone()[0], 1)
            self.assertEqual(con.execute(
                "SELECT COUNT(*) FROM reports WHERE title='t2'").fetchone()[0], 1)
            self.assertEqual(con.execute(
                "SELECT COUNT(*) FROM jobs WHERE created_at<>'' AND created_at<?",
                (OLD_ISO,)).fetchone()[0], 0)
            self.assertEqual(con.execute(
                "SELECT COUNT(*) FROM search_memory WHERE query_key='newk'"
            ).fetchone()[0], 1)
            self.assertEqual(con.execute(
                "SELECT COUNT(*) FROM tg_candidates WHERE handle='newhandle'"
            ).fetchone()[0], 1)
            self.assertEqual(con.execute(
                "SELECT COUNT(*) FROM tg_channels WHERE channel='newdead'"
            ).fetchone()[0], 1)

    def test_retention_days_env_default(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("JIN_AGENT_RETENTION_DAYS", None)
            self.assertEqual(store._retention_days(None), 180)
        with mock.patch.dict(os.environ, {"JIN_AGENT_RETENTION_DAYS": "45"}):
            self.assertEqual(store._retention_days(None), 45)
        with mock.patch.dict(os.environ, {"JIN_AGENT_RETENTION_DAYS": "abc"}):
            self.assertEqual(store._retention_days(None), 180)

    def test_retention_sources_and_watchlist_survive(self):
        before_sources = store.counts()["sources"]
        store.add_watchlist("lifetime-term")
        store.retention(30)
        self.assertEqual(store.counts()["sources"], before_sources)
        self.assertTrue(any(w["term"] == "lifetime-term"
                            for w in store.list_watchlist()))


class TestBackupRollingRetention(unittest.TestCase):
    def test_prune_backups_keeps_last_n(self):
        folder = config.backups_dir()
        for old in folder.glob("jin_agent-*.db"):
            old.unlink()
        for i in range(10):
            (folder / f"jin_agent-2020010{i:02d}-000000.db").write_bytes(b"x")
        (folder / "other.db").write_text("keep")
        pruned = store._prune_backups(3)
        self.assertEqual(pruned, 7)
        remaining = sorted(p.name for p in folder.glob("jin_agent-*.db"))
        self.assertEqual(len(remaining), 3)
        self.assertEqual(remaining[0], "jin_agent-202001007-000000.db")
        self.assertTrue((folder / "other.db").is_file())

    def test_backup_keep_env(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("JIN_AGENT_BACKUP_KEEP", None)
            self.assertEqual(store._backup_keep(), 7)
        with mock.patch.dict(os.environ, {"JIN_AGENT_BACKUP_KEEP": "2"}):
            self.assertEqual(store._backup_keep(), 2)
        with mock.patch.dict(os.environ, {"JIN_AGENT_BACKUP_KEEP": "abc"}):
            self.assertEqual(store._backup_keep(), 7)

    def test_backup_rolling_retention_end_to_end(self):
        folder = config.backups_dir()
        for i in range(9):
            (folder / f"jin_agent-2021010{i}-000000.db").write_bytes(b"x")
        out = store.backup()
        self.assertEqual(out["keep"], 7)
        self.assertGreaterEqual(out["pruned"], 2)
        self.assertEqual(len(list(folder.glob("jin_agent-*.db"))), 7)
        self.assertTrue(Path(out["path"]).is_file())


class TestVacuum(unittest.TestCase):
    def test_vacuum_rebuilds_freelist(self):
        recs = [{"guid": f"bulk:{i}", "title": f"bulk {i}",
                 "url": f"https://example.com/{i}", "source": "t",
                 "source_key": "t", "fetched_at": util.now_iso()}
                for i in range(200)]
        store.upsert_items(recs)
        with store.session() as con:
            con.execute("DELETE FROM items")
        con = sqlite3.connect(str(config.db_path()))
        try:
            before = int(con.execute("PRAGMA freelist_count").fetchone()[0])
        finally:
            con.close()
        self.assertGreater(before, 0)
        out = store.vacuum_db(threshold_pages=1)
        self.assertTrue(out["vacuumed"])
        self.assertEqual(out["freelist_after"], 0)

    def test_vacuum_skips_when_small(self):
        out = store.vacuum_db(threshold_pages=10**9)
        self.assertFalse(out["vacuumed"])

    def test_retention_reports_vacuum_result(self):
        out = store.retention(3650)
        self.assertIn("vacuum", out)
        self.assertIn("freelist_before", out["vacuum"])


if __name__ == "__main__":
    unittest.main()
