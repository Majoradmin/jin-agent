"""Report quality - item-specific khulasa (P0).

Masla: khulasa per-item nahi, category ki canned jumla thi. Ab har item apne
title / source / date / excerpt / entities se apni line banata hai. LLM on
ho to asli summary; off ho to rule-based fallback (hallucination nahi).
"""

import os
import socket
import tempfile
import unittest
from unittest import mock

from jin_agent import briefer, config, report_export  # noqa: E402


def _public_dns(host, port, *args, **kwargs):
    """Offline DNS mock — custom endpoint public IP par resolve hota hai."""
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]


def setUpModule():
    os.environ["JIN_AGENT_DATA"] = tempfile.mkdtemp(prefix="jin-brief-q-")


def _item(title, source="Example", category="Android", excerpt="", **kw):
    row = {
        "title": title, "url": "https://example.com/" + title.replace(" ", "-"),
        "source": source, "source_key": "k", "category": category,
        "published": "2026-11-19", "date_checked": "2026-11-19",
        "tier": "T0", "trust_label": "High", "confidence": 0.8,
        "score": 1.0, "verified": True, "cross_verified": False,
        "link_only": False, "excerpt": excerpt, "entities": [], "meta": {},
    }
    row.update(kw)
    return row


class TestItemSpecificKhulasa(unittest.TestCase):
    def test_two_items_have_different_lines_from_own_fields(self):
        a = _item("Free Dictionary API", excerpt="A free dictionary API service.")
        b = _item("macOS turns off display", category="iOS",
                  excerpt="macOS app display behaviour.")
        ka, kb = briefer.khulasa(a), briefer.khulasa(b)
        self.assertNotEqual(ka, kb)
        self.assertIn("Free Dictionary API", ka)
        self.assertIn("A free dictionary API service.", ka)
        self.assertIn("macOS turns off display", kb)
        self.assertIn("macOS app display behaviour.", kb)

    def test_category_canned_sentence_is_not_used(self):
        # "Free Dictionary API" Android category honay ke bawajood flashing
        # wali category jumla khulasa me NA aani chahiye.
        line = briefer.khulasa(_item("Free Dictionary API",
                                     category="Android"))
        for hint in briefer.HINTS.values():
            self.assertNotIn(hint, line)
        self.assertNotIn("Flash karne", line)
        self.assertNotIn("cracked builds", line)
        # iOS item par bhi macOS/display wala category hint nahi.
        line = briefer.khulasa(_item("macOS turns off MacBook display",
                                     category="iOS"))
        self.assertNotIn("Activation aur carrier policy", line)

    def test_source_date_and_entities_come_from_item(self):
        line = briefer.khulasa(_item(
            "Android 17 patch", source="Android Bulletin",
            excerpt="Security patch taqreeban.",
            entities=[{"kind": "version", "value": "Android 17"}]))
        self.assertIn("Android Bulletin", line)
        self.assertIn("2026-11-19", line)
        self.assertIn("Android 17", line)

    def test_llm_off_never_calls_model(self):
        def _boom(*a, **k):
            raise AssertionError("LLM off hone par model call nahi honi chahiye")

        old = briefer.llm.chat
        briefer.llm.chat = _boom
        try:
            line = briefer.khulasa(_item("Android 17 patch"),
                                   config.load())
        finally:
            briefer.llm.chat = old
        self.assertIn("Android 17 patch", line)

    def test_llm_mode_uses_model_summary(self):
        cfg = {"llm": {"provider": "custom", "endpoint": "https://llm.example.com/v1",
                       "model": "test-model", "key": "k"}}

        def fake_chat(cfg, system, user, timeout=30):
            self.assertIn("Free Dictionary API", user)
            return {"ok": True, "text": "Yeh API free dictionary khaatir hai."}

        old = briefer.llm.chat
        briefer.llm.chat = fake_chat
        with mock.patch("socket.getaddrinfo", _public_dns):
            try:
                line = briefer.khulasa(_item("Free Dictionary API"), cfg)
            finally:
                briefer.llm.chat = old
        self.assertEqual(line, "Yeh API free dictionary khaatir hai.")

    def test_llm_failure_falls_back_to_rule_based(self):
        cfg = {"llm": {"provider": "custom", "endpoint": "https://llm.example.com/v1",
                       "model": "test-model", "key": "k"}}

        def fail_chat(*a, **k):
            return {"ok": False, "text": "", "error": "timeout"}

        old = briefer.llm.chat
        briefer.llm.chat = fail_chat
        with mock.patch("socket.getaddrinfo", _public_dns):
            try:
                line = briefer.khulasa(_item("Android 17 patch"), cfg)
            finally:
                briefer.llm.chat = old
        self.assertIn("Android 17 patch", line)
        for hint in briefer.HINTS.values():
            self.assertNotIn(hint, line)

    def test_summarize_items_off_returns_empty(self):
        self.assertEqual(briefer.summarize_items([_item("a")], config.load()), {})

    def test_markdown_uses_item_specific_line(self):
        md = briefer._markdown(
            "q", [_item("Free Dictionary API", excerpt="Dictionary API.")], [],
            {"tor_mode": "links_only"}, {}, {}, {}, 0, "offline")
        self.assertIn("Free Dictionary API", md)
        self.assertIn("Dictionary API.", md)
        self.assertNotIn("Flash karne", md)


class TestReportCompletenessAndSources(unittest.TestCase):
    def test_all_items_shown_no_archive_note(self):
        items = [_item(f"Story {i}") for i in range(7)]
        md = briefer._markdown("q", items, [], {"tor_mode": "links_only"},
                               {}, {}, {}, 0, "offline")
        for i in range(7):
            self.assertIn(f"Story {i}", md)
        self.assertNotIn("archive mein", md)

    def test_html_all_items_shown(self):
        items = [_item(f"Story {i}") for i in range(7)]
        built = briefer.build("q", items, [], config.load())
        html = report_export.to_html(built)
        for i in range(7):
            self.assertIn(f"Story {i}", html)
        self.assertNotIn("archive mein", html)

    def test_sources_table_is_query_specific(self):
        diags = [
            {"key": "gsmarena", "name": "GSMArena", "tier": "T0",
             "ok": True, "count": 20, "error": ""},
            {"key": "androidauthority", "name": "Android Authority", "tier": "T0",
             "ok": True, "count": 1, "error": ""},
        ]
        items = [_item("Android story", source="Android Authority",
                        source_key="androidauthority")]
        md = briefer._markdown("q", items, diags, {"tor_mode": "links_only"},
                               {}, {}, {}, 0, "offline")
        self.assertIn("Android Authority", md)
        self.assertNotIn("GSMArena", md)
        # count raw 20 nahi, is query ka 1
        self.assertIn("| Android Authority | T0 | OK | 1 |", md)

    def test_html_sources_table_is_query_specific(self):
        diags = [
            {"key": "gsmarena", "name": "GSMArena", "tier": "T0",
             "ok": True, "count": 20, "error": ""},
            {"key": "androidauthority", "name": "Android Authority", "tier": "T0",
             "ok": True, "count": 1, "error": ""},
        ]
        items = [_item("Android story", source="Android Authority",
                        source_key="androidauthority")]
        built = briefer.build("q", items, diags, config.load())
        html = report_export.to_html(built)
        self.assertIn("Android Authority", html)
        self.assertNotIn("GSMArena", html)


if __name__ == "__main__":
    unittest.main()
