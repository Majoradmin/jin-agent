"""P36 - /status source health: non-overlapping buckets + honest breakdown.

Live bug (2026-11-19): bot ne `45 ok / 1 fail (total 45)` dikhaya — aik
source (status ok, fail_count>0) dono buckets me gina gaya tha. Ye tests
regression ke tor par us overlap ko rokti hain.

Store `enabled` ko `auto` se seed karta hai. Registry-only sources
(adapter ke baghair) alag ginche jate hain — wo `disabled` nahi hain,
is liye buckets ka total hamesha `auto` (27) ke barabar hota hai.
"""

import os
import tempfile
import unittest

from jin_agent import store, telegram_bot as tb  # noqa: E402


def setUpModule():
    os.environ["JIN_AGENT_DATA"] = tempfile.mkdtemp(prefix="jin-status-")
    store.init_db()


class TestSourceHealth(unittest.TestCase):
    def test_auto_registry_breakdown_in_text(self):
        text = tb.format_status_text()
        self.assertIn("Sources:", text)
        self.assertIn("46 total", text)
        self.assertIn("27 auto / 19 registry-only", text)

    def test_buckets_cover_every_source_once(self):
        h = tb.source_health()
        b = h["buckets"]
        self.assertEqual(h["total"], 46)
        self.assertEqual(sum(b.values()), h["auto"])   # buckets sirf auto sources
        self.assertEqual(h["auto"], 27)
        self.assertEqual(h["registry_only"], 19)
        self.assertEqual(h["auto"] + h["registry_only"], h["total"])
        # Seed state: 27 auto enabled (ok), 19 registry-only alag ginche.
        self.assertEqual(b["ok"], 27)
        self.assertEqual(b["disabled"], 0)

    def test_disabled_bucket(self):
        before = tb.source_health()["buckets"]["disabled"]
        store.set_source_enabled("gsmarena", False)   # auto source band karo
        b = tb.source_health()["buckets"]
        self.assertEqual(b["disabled"], before + 1)
        self.assertEqual(b["ok"], 26)
        self.assertEqual(sum(b.values()), 27)          # auto sources ka total
        # Fail bhi hone par disabled hi jeetta hai (ek bucket).
        store.touch_source("gsmarena", False, "wajah")
        b2 = tb.source_health()["buckets"]
        self.assertEqual(b2["disabled"], before + 1)
        self.assertEqual(b2["failed"], 0)
        self.assertEqual(sum(b2.values()), 27)

    def test_failed_source_name_and_error_in_status(self):
        before = len(tb.source_health()["failed"])
        store.touch_source("android-bulletin", False, "HTTP 503 gateway timeout")
        h = tb.source_health()
        self.assertEqual(h["buckets"]["failed"], before + 1)
        self.assertEqual(sum(h["buckets"].values()), h["auto"])
        text = tb.format_status_text()
        self.assertIn("Android Security Bulletin", text)
        self.assertIn("HTTP 503 gateway timeout", text)

    def test_ok_status_with_fail_count_not_double_counted(self):
        # Asli live case: status ok magar fail_count>0 — sirf ok bucket.
        before = len(tb.source_health()["failed"])
        with store.session() as con:
            con.execute("UPDATE sources SET fail_count=7, last_error='purani wajah',"
                        " status='ok' WHERE key='9to5google'")
        h = tb.source_health()
        b = h["buckets"]
        self.assertEqual(len(h["failed"]), before)
        self.assertEqual(b["failed"], before)
        self.assertEqual(sum(b.values()), h["auto"])
        self.assertFalse(any(s.get("key") == "9to5google" for s in h["failed"]))

    def test_stale_source_shown_with_name(self):
        with store.session() as con:
            con.execute("UPDATE sources SET status='stale',"
                        " last_error='verification 30 din purana' WHERE key='samsung-smr'")
        h = tb.source_health()
        self.assertEqual(h["buckets"]["stale"], 1)
        self.assertEqual(sum(h["buckets"].values()), h["auto"])
        self.assertIn("Samsung Security (SMR)", tb.format_status_text())


if __name__ == "__main__":
    unittest.main()
