"""P29 - search memory: used sources/channels yaad rakhna, agla round skip.

Sirf SQLite local hota hai; koi network nahi.
"""

import os
import tempfile
import unittest

from jin_agent import config, searchmemory, store


def setUpModule():
    os.environ["JIN_AGENT_DATA"] = tempfile.mkdtemp(prefix="jin-memory-")
    store.init_db()


class TestSearchMemory(unittest.TestCase):
    def test_begin_creates_round_one(self):
        row = searchmemory.begin(7, "Dark Web Markets 2026")
        self.assertEqual(row["round_no"], 1)
        self.assertEqual(row["status"], "active")
        self.assertEqual(row["used_sources"], [])
        again = searchmemory.begin(7, "dark   web markets 2026")
        self.assertEqual(again["id"], row["id"])  # normalize -> wahi row

    def test_remember_merges_and_dedupes(self):
        row = searchmemory.begin(8, "firmware unlock")
        updated = searchmemory.remember(row["id"], ["gsmarena", "xda", "gsmarena"],
                                        ["chA", "chB"])
        self.assertEqual(updated["used_sources"], ["gsmarena", "xda"])
        self.assertEqual(updated["used_channels"], ["chA", "chB"])

    def test_advance_increments_round(self):
        row = searchmemory.begin(9, "frp unlock")
        searchmemory.remember(row["id"], ["nvd"], ["chA"])
        next_row = searchmemory.remember(row["id"], ["arxiv"], [], advance=True)
        self.assertEqual(next_row["round_no"], 2)
        self.assertEqual(set(next_row["used_sources"]), {"nvd", "arxiv"})

    def test_mark_done_then_new_begin(self):
        row = searchmemory.begin(10, "signal leaks")
        searchmemory.mark_done(row["id"])
        self.assertEqual(searchmemory.get(row["id"])["status"], "done")
        fresh = searchmemory.begin(10, "signal leaks")
        self.assertNotEqual(fresh["id"], row["id"])
        self.assertEqual(fresh["round_no"], 1)

    def test_reset_clears_used_lists(self):
        row = searchmemory.begin(11, "onion sites")
        searchmemory.remember(row["id"], ["ahmia"], ["chA"], advance=True)
        reset = searchmemory.reset(row["id"])
        self.assertEqual(reset["used_sources"], [])
        self.assertEqual(reset["used_channels"], [])
        self.assertEqual(reset["round_no"], 1)
        self.assertEqual(reset["status"], "active")

    def test_get_missing_returns_none(self):
        self.assertIsNone(searchmemory.get(999999))

    def test_recent_only_for_chat(self):
        searchmemory.begin(1, "shared query")
        searchmemory.begin(2, "other user query")
        rows = searchmemory.recent(1, 10)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["chat_id"], 1)


if __name__ == "__main__":
    unittest.main()
