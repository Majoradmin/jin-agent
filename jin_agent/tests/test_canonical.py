"""P27 - URL canonicalisation, content hashing and near-duplicate detection."""

import unittest

from jin_agent import canonical


class TestCanonicalize(unittest.TestCase):
    def test_host_lowercased_and_fragment_dropped(self):
        got = canonical.canonicalize("HTTPS://Example.COM/Path/#section")
        self.assertEqual(got, "https://example.com/Path")

    def test_default_ports_removed_and_other_ports_kept(self):
        self.assertEqual(canonical.canonicalize("https://example.com:443/x"),
                         "https://example.com/x")
        self.assertEqual(canonical.canonicalize("http://example.com:80/x"),
                         "http://example.com/x")
        self.assertEqual(canonical.canonicalize("https://example.com:8443/x"),
                         "https://example.com:8443/x")

    def test_trailing_slash_and_root(self):
        self.assertEqual(canonical.canonicalize("https://example.com/a///"),
                         "https://example.com/a")
        self.assertEqual(canonical.canonicalize("https://example.com"),
                         "https://example.com/")

    def test_tracking_params_stripped_and_query_sorted(self):
        got = canonical.canonicalize(
            "https://example.com/a?utm_source=x&b=2&a=1&fbclid=z&gclid=y")
        self.assertEqual(got, "https://example.com/a?a=1&b=2")
        self.assertEqual(canonical.canonicalize(
            "https://example.com/a?utm_medium=email"), "https://example.com/a")

    def test_duplicate_slashes_collapsed(self):
        self.assertEqual(canonical.canonicalize("https://example.com/a//b"),
                         "https://example.com/a/b")

    def test_redirect_wrapper_unwrapped_offline(self):
        got = canonical.canonicalize(
            "https://www.google.com/url?q=https%3A%2F%2Fexample.org%2Fstory%3Futm_source%3Dx")
        self.assertEqual(got, "https://example.org/story")
        ddg = canonical.canonicalize(
            "https://html.duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.org%2Fa")
        self.assertEqual(ddg, "https://example.org/a")

    def test_invalid_inputs_rejected(self):
        for raw in ("", "   ", "/relative", "ftp://example.com/x",
                    "https://user:pass@example.com/x", "https:///nohost",
                    "javascript:alert(1)"):
            self.assertEqual(canonical.canonicalize(raw), "", raw)

    def test_same_url(self):
        self.assertTrue(canonical.same_url(
            "https://Example.com/a/?utm_source=x", "https://example.com/a"))
        self.assertFalse(canonical.same_url("https://example.com/a",
                                            "https://example.com/b"))
        self.assertFalse(canonical.same_url("", ""))


class TestContentHash(unittest.TestCase):
    def test_stable_across_case_and_whitespace(self):
        a = canonical.content_hash("MediaTek Preloader", "DA update", "")
        b = canonical.content_hash("  mediatek   preloader ", "da   update", "")
        self.assertEqual(a, b)
        self.assertEqual(len(a), 64)

    def test_content_changes_hash(self):
        a = canonical.content_hash("Title", "old body")
        b = canonical.content_hash("Title", "new body")
        self.assertNotEqual(a, b)


class TestNearDuplicate(unittest.TestCase):
    def test_exact_title_is_duplicate(self):
        self.assertTrue(canonical.near_duplicate_titles("Same title", "same title"))

    def test_close_titles_are_duplicates(self):
        a = "MediaTek preloader DA v2 released for Dimensity"
        b = "MediaTek preloader DA v2 released for Dimensity chips"
        self.assertGreaterEqual(canonical.jaccard(a, b), 0.72)
        self.assertTrue(canonical.near_duplicate_titles(a, b))

    def test_unrelated_titles_are_not_duplicates(self):
        a = "Qualcomm firehose loader UFS coverage"
        b = "iPhone activation policy explained"
        self.assertFalse(canonical.near_duplicate_titles(a, b))
        self.assertEqual(canonical.jaccard("", "anything"), 0.0)

    def test_dedupe_key_prefers_canonical_url(self):
        item = {"url": "https://example.com/a?utm_source=x", "title": "T",
                "fingerprint": "fp", "guid": "g"}
        self.assertEqual(canonical.dedupe_key(item), "https://example.com/a")

    def test_dedupe_records_removes_url_and_near_title(self):
        rows = [
            {"url": "https://example.com/a?utm_source=x", "title": "Story one"},
            {"url": "https://example.com/a", "title": "Other headline"},
            {"url": "https://example.com/b",
             "title": "MediaTek preloader DA v2 released for Dimensity"},
            {"url": "https://example.com/c",
             "title": "MediaTek preloader DA v2 released for Dimensity chips"},
        ]
        kept = canonical.dedupe_records(rows)
        self.assertEqual(len(kept), 2)
        self.assertEqual(kept[0]["url"], rows[0]["url"])


if __name__ == "__main__":
    unittest.main()
