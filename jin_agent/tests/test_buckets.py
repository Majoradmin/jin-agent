"""P1.6 - 12 categories ko 4 beginner buckets me group karna."""

import os
import tempfile
import unittest

from jin_agent import briefer, config  # noqa: E402


def setUpModule():
    os.environ["JIN_AGENT_DATA"] = tempfile.mkdtemp(prefix="jin-buckets-")


def _item(category: str, title: str = "t") -> dict:
    return {
        "title": title, "category": category, "source": "src",
        "url": "https://example.com/x", "published": "2026-11-19",
        "date_checked": "2026-11-19", "confidence": 0.5,
        "trust_label": "Reported", "score": 1.0, "tier": "T1",
        "verified": False, "cross_verified": False, "link_only": False,
        "meta": {},
    }


def _md(items: list[dict]) -> str:
    return briefer._markdown("q", items, [], {"tor_mode": "links_only"},
                             {}, {}, {}, 0, "offline")


class TestBucketMap(unittest.TestCase):
    def test_four_beginner_buckets(self):
        self.assertEqual(briefer.BUCKET_ORDER,
                         ("Technical", "Security", "Science & World", "Watchlist"))

    def test_all_topics_covered_once(self):
        members = [c for group in briefer.CATEGORY_BUCKETS.values() for c in group]
        self.assertEqual(sorted(members), sorted(config.TOPICS))
        self.assertEqual(len(members), len(set(members)))

    def test_bucket_for_known_and_unknown(self):
        self.assertEqual(briefer.bucket_for("Android"), "Technical")
        self.assertEqual(briefer.bucket_for("Security"), "Security")
        self.assertEqual(briefer.bucket_for("World"), "Science & World")
        self.assertEqual(briefer.bucket_for("Custom Watchlist"), "Watchlist")
        self.assertEqual(briefer.bucket_for("kuch nahi"), "Watchlist")
        self.assertEqual(briefer.bucket_for(""), "Watchlist")


class TestReportBuckets(unittest.TestCase):
    def test_report_shows_four_bucket_headings(self):
        items = [_item(c, c) for c in config.TOPICS]
        md = _md(items)
        headings = [ln for ln in md.splitlines() if ln.startswith("### ")]
        self.assertEqual(headings, ["### Technical", "### Security",
                                    "### Science & World", "### Watchlist"])

    def test_original_category_stays_in_metadata(self):
        md = _md([_item("Android"), _item("Security")])
        self.assertIn("Category: Android", md)
        self.assertIn("Category: Security", md)

    def test_empty_report_has_no_bucket_headings(self):
        self.assertNotIn("### ", _md([]))

    def test_unknown_category_lands_in_watchlist(self):
        md = _md([_item("Unknown Thing")])
        self.assertIn("### Watchlist", md)
        self.assertIn("Category: Unknown Thing", md)

    def test_config_topics_unchanged(self):
        self.assertEqual(len(config.TOPICS), 12)


if __name__ == "__main__":
    unittest.main()
