"""P27 - page snapshots and change detection ("naya kya aaya")."""

import os
import tempfile
import unittest
from pathlib import Path

os.environ["JIN_AGENT_DATA"] = tempfile.mkdtemp(prefix="jin-changes-")

from jin_agent import config, snapshots, store, util  # noqa: E402


def setUpModule():
    os.environ["JIN_AGENT_DATA"] = tempfile.mkdtemp(prefix="jin-changes-")
    store.init_db()
    snapshots.ensure_table()


class TestDiff(unittest.TestCase):
    def test_diff_counts_and_first_lines(self):
        old = "alpha\nbeta\ngamma"
        new = "alpha\nbeta changed\ngamma\ndelta"
        diff = snapshots.diff_text(old, new, max_lines=2)
        self.assertTrue(diff["changed"])
        self.assertEqual(diff["removed_lines"], 1)
        self.assertEqual(diff["added_lines"], 2)
        self.assertEqual(len(diff["changed_lines"]), 2)
        self.assertTrue(any(line.startswith("- ") for line in diff["changed_lines"]))

    def test_identical_text_has_no_changes(self):
        diff = snapshots.diff_text("same\nlines", "same\nlines")
        self.assertFalse(diff["changed"])
        self.assertEqual(diff["added_lines"], 0)
        self.assertEqual(diff["removed_lines"], 0)
        self.assertEqual(diff["changed_lines"], [])


class TestSnapshots(unittest.TestCase):
    def setUp(self):
        os.environ["JIN_AGENT_DATA"] = tempfile.mkdtemp(prefix="jin-changes-case-")
        store.init_db()
        snapshots.ensure_table()

    def test_first_snapshot_stored_with_hash_size_and_timestamp(self):
        result = snapshots.record("hn", "https://example.com/a?utm_source=x",
                                  "line one\nline two")
        self.assertTrue(result["new"])
        self.assertTrue(result["changed"])
        self.assertEqual(result["canonical"], "https://example.com/a")
        self.assertEqual(result["size"], len("line one\nline two".encode("utf-8")))
        self.assertEqual(len(result["content_hash"]), 64)
        self.assertTrue(result["ts"].endswith("Z"))
        rows = snapshots.list_snapshots(10)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source_key"], "hn")
        self.assertEqual(rows[0]["changed_lines"][0], "+ line one")

    def test_identical_snapshot_not_changed_and_upserted(self):
        url = "https://example.com/a"
        first = snapshots.record("hn", url, "alpha\nbeta")
        second = snapshots.record("hn", url, "alpha\nbeta")
        self.assertFalse(second["new"])
        self.assertFalse(second["changed"])
        self.assertEqual(first["content_hash"], second["content_hash"])
        self.assertEqual(len(snapshots.list_snapshots(10)), 1)

    def test_modified_snapshot_reports_added_removed(self):
        url = "https://example.com/a"
        snapshots.record("wikipedia", url, "old one\nold two")
        result = snapshots.record("wikipedia", url, "old one\nnew two\nnew three")
        self.assertTrue(result["changed"])
        self.assertEqual(result["removed_lines"], 1)
        self.assertEqual(result["added_lines"], 2)
        self.assertEqual(len(result["changed_lines"]), 3)

    def test_invalid_url_is_not_stored(self):
        result = snapshots.record("hn", "not-a-url", "body")
        self.assertFalse(result["changed"])
        self.assertEqual(result["size"], 0)
        self.assertEqual(snapshots.list_snapshots(10), [])

    def test_changes_since_groups_per_source(self):
        snapshots.record("hn", "https://example.com/a", "one")
        snapshots.record("hn", "https://example.com/a", "one two")
        snapshots.record("nvd", "https://example.com/b", "cve one")
        result = snapshots.changes_since(None, limit=20)
        self.assertEqual(result["total"], 2)
        keys = {row["source_key"] for row in result["sources"]}
        self.assertEqual(keys, {"hn", "nvd"})
        self.assertGreaterEqual(result["added_lines"], 2)
        future = "2999-01-01T00:00:00Z"
        self.assertEqual(snapshots.changes_since(future)["total"], 0)

    def test_changes_since_last_run_marker(self):
        snapshots.record("reddit", "https://example.com/r", "post one")
        self.assertGreaterEqual(snapshots.changes_since_last_run()["total"], 1)
        snapshots.mark_seen(util.epoch() + 120)
        self.assertEqual(snapshots.changes_since_last_run()["total"], 0)

    def test_recent_changes_limit_and_counts(self):
        snapshots.record("reddit", "https://example.com/reddit", "post line")
        for i in range(4):
            snapshots.record("s%d" % i, "https://example.com/%d" % i, "line %d" % i)
        result = snapshots.recent_changes(limit=2)
        self.assertEqual(result["total"], 2)
        counts = snapshots.counts()
        self.assertGreaterEqual(counts["snapshots"], 4)
        self.assertGreaterEqual(counts["sources"], 4)
        self.assertIn("reddit", counts["by_source"])

    def test_prune_removes_old_rows(self):
        snapshots.record("hn", "https://example.com/old", "old")
        with store.session() as con:
            con.execute("UPDATE page_snapshots SET ts='2000-01-01T00:00:00Z'")
        self.assertGreaterEqual(snapshots.prune(1), 1)


class TestTable(unittest.TestCase):
    def test_page_snapshots_table_registered(self):
        db = config.db_path()
        self.assertTrue(Path(db).is_file())
        with store.session() as con:
            row = con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='page_snapshots'").fetchone()
        self.assertIsNotNone(row)


if __name__ == "__main__":
    unittest.main()
