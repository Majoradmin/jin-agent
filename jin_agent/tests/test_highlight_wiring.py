"""Highlight wiring — BLUF/report me query ke lafz <b> se highlight hote hain.

`jin_agent/highlight.py` ka module `tests/test_highlight.py` me test hua hai.
Yahan **bot ke send path** ka wiring test hai: escape-safe, tags/URLs me nahi,
aur HTML parse_mode ke saath bheja jata hai.
"""

import os
import tempfile
import unittest
from unittest import mock

from jin_agent import store, telegram_bot as tb
from jin_agent.tests.test_telegram_bot import FakeAPI


def setUpModule():
    os.environ.setdefault("JIN_AGENT_DATA", tempfile.mkdtemp(prefix="jin-hl-"))
    store.init_db()


class TestHighlightWiring(unittest.TestCase):
    def test_highlight_html_escapes_and_marks_text(self):
        html = tb._highlight_html("Android security bulletin & news", "android security")
        self.assertIn("<b>Android</b>", html)
        self.assertIn("<b>security</b>", html)
        # & escape hota hai, magar entity ke andar highlight nahi
        self.assertIn("&amp;", html)
        self.assertNotIn("<b>&amp;</b>", html)

    def test_highlight_html_does_not_touch_urls_or_tags(self):
        md = "see [android](https://x.test/android) and <b>android</b>"
        html = tb._highlight_html(md, "android")
        # URL ke andar highlight nahi
        self.assertNotIn("<b>https://x.test/android</b>", html)
        # pehle se mojood tag ke andar nahi (tag adhua nahi)
        self.assertNotIn("<b><b>", html)

    def test_highlight_html_koi_match_nahi_to_waisa_hi(self):
        # markdown input — raw HTML nahi (markdown_to_html pehle escape karta hai)
        html = tb._highlight_html("**Report**: kuch aur", "android")
        self.assertEqual(html, "<b>Report</b>: kuch aur")

    def test_bluf_bheja_jata_hai_html_parse_mode_ke_sath(self):
        api = FakeAPI()
        path = os.path.join(tempfile.mkdtemp(prefix="jin-rep-"), "brief.md")
        with open(path, "w") as fh:
            fh.write("# Brief\nandroid security report\n")

        def fake_research(q, cfg):
            return {"markdown": "# Brief\nandroid security findings",
                    "report_path": path, "trace_path": "",
                    "confidence": 0.9, "confidence_label": "high",
                    "sources": ["a"], "channels": [], "failed_channels": [],
                    "absence_kind": "ok"}

        with mock.patch.dict(os.environ, {"JIN_AGENT_REPORT_CONFIDENCE": "0"}):
            res = tb.dispatch(42, "/research android security",
                              {"telegram_chat_id": "42"}, api=api,
                              research=fake_research)
        self.assertTrue(res["ok"])
        idx = [i for i, m in enumerate(api.sent) if "📌 Report tayyar hai" in m[1]]
        self.assertTrue(idx, "BLUF message nahi mila")
        i = idx[0]
        self.assertEqual(api.modes[i], "HTML")
        self.assertIn("<b>android</b>", api.sent[i][1])

    def test_fallback_chunks_balanced_hain(self):
        from jin_agent import highlight
        md = "# Brief\n" + ("android " * 900)
        html = tb._highlight_html(md, "android")
        chunks = highlight.split_html(html)
        self.assertGreaterEqual(len(chunks), 2)
        for c in chunks:
            self.assertLessEqual(len(c), 4096)
            # koi adhura <b> tag nahi (har chunk me open == close)
            self.assertEqual(c.count("<b>"), c.count("</b>"))
            self.assertEqual(c.count("<i>"), c.count("</i>"))


if __name__ == "__main__":
    unittest.main()
