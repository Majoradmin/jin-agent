"""P37 - HTML report export: escaping, bucket headings, adhuri report valid.

PDF stdlib-only project me support nahi — jaan-boojh kar nahi gaya.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path

from jin_agent import briefer, config, report_export, store, telegram_bot as tb  # noqa: E402


def setUpModule():
    os.environ["JIN_AGENT_DATA"] = tempfile.mkdtemp(prefix="jin-export-")
    store.init_db()


def _item(title, category="Android", url="https://example.com/a", source="Example",
          **kw):
    row = {
        "title": title, "url": url, "source": source, "source_key": "k",
        "category": category, "tier": "T0", "trust_label": "High",
        "published": "2026-11-01", "date_checked": "2026-11-19",
        "confidence": 0.8, "score": 1.0, "verified": True,
        "cross_verified": False, "link_only": False, "meta": {},
    }
    row.update(kw)
    return row


class TestHtmlExport(unittest.TestCase):
    def test_escapes_markup_in_title_query_and_items(self):
        report = {
            "title": '<script>alert("x")</script>',
            "query": "<b>sawal</b>",
            "items": [_item("<b>breaking</b> & news")],
            "diagnostics": [{"name": "<i>src</i>", "tier": "T0", "ok": True,
                             "count": 1, "error": ""}],
            "confidence": {"label": "High", "value": 0.9, "items": 1,
                           "verified": 1, "cross_verified": 0},
            "audit": {},
        }
        html = report_export.to_html(report)
        self.assertNotIn("<script>", html)
        self.assertNotIn("<b>breaking</b>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("&lt;b&gt;breaking&lt;/b&gt; &amp; news", html)
        self.assertIn("&lt;i&gt;src&lt;/i&gt;", html)

    def test_partial_report_still_valid_html(self):
        html = report_export.to_html({})
        self.assertTrue(html.startswith("<!DOCTYPE html>"))
        self.assertIn("<html", html)
        self.assertIn("</body>", html)
        self.assertTrue(html.rstrip().endswith("</html>"))

    def test_bucket_headings(self):
        report = {"query": "q", "items": [
            _item("android story", "Android"),
            _item("security story", "Security"),
        ]}
        html = report_export.to_html(report)
        self.assertIn("<h3>Technical</h3>", html)
        self.assertIn("<h3>Security</h3>", html)

    def test_sources_table_and_confidence(self):
        report = {
            "query": "q",
            "diagnostics": [{"name": "Android Bulletin", "tier": "T0", "ok": False,
                             "count": 0, "error": "timeout"}],
            "confidence": {"label": "Medium", "value": 0.5, "items": 0,
                           "verified": 0, "cross_verified": 0},
        }
        html = report_export.to_html(report)
        self.assertIn("Android Bulletin", html)
        self.assertIn("FAIL", html)
        self.assertIn("timeout", html)
        self.assertIn("Medium", html)

    def test_javascript_url_is_not_a_link(self):
        report = {"query": "q", "items": [
            _item("bad", url="javascript:alert(1)"),
            _item("good", url="https://example.com/ok"),
        ]}
        html = report_export.to_html(report)
        self.assertNotIn('href="javascript:', html)
        self.assertIn('href="https://example.com/ok"', html)

    def test_briefer_build_roundtrip(self):
        items = [_item("Android 17 patch", "Android")]
        built = briefer.build("android patch", items,
                              [{"name": "Android Bulletin", "tier": "T0",
                                "ok": True, "count": 1, "error": ""}],
                              audit={"total": 1, "with_url": 1, "with_date": 1,
                                     "with_source": 1, "provenance_pct": 100,
                                     "fabricated": 0},
                              metrics={"items": 1})
        html = report_export.to_html(built)
        self.assertIn("android patch", html)
        self.assertIn("Android 17 patch", html)
        self.assertIn("Android Bulletin", html)

    def test_md_report_highlights_query_terms(self):
        items = [_item("Free Dictionary API key",
                       excerpt="A free dictionary API service.")]
        built = briefer.build("free api key", items, [], config.load())
        md = built["markdown"]
        self.assertIn("**Query:** **free** **api** **key**", md)
        self.assertIn("**Free**", md)
        self.assertNotIn("<b>", md)
        # URL ke andar highlight nahi hota
        self.assertNotIn("https://example.com/**api**", md)

    def test_html_report_highlights_query_terms(self):
        items = [_item("Free Dictionary API key",
                       excerpt="A free dictionary API service.")]
        built = briefer.build("free api key", items, [], config.load())
        html = report_export.to_html(built)
        self.assertIn("<b>free</b>", html)
        self.assertIn("<b>api</b>", html)
        self.assertIn("<b>Free</b>", html)
        # href ke andar highlight nahi
        self.assertIn('href="https://example.com/a"', html)

    def test_from_report_file(self):
        folder = config.reports_dir()
        md = folder / "brief-export-test.md"
        js = folder / "brief-export-test.json"
        md.write_text("# md", encoding="utf-8")
        js.write_text(json.dumps({"query": "sawal", "items": [_item("Title <x>")],
                                  "diagnostics": [], "audit": {},
                                  "confidence": {"label": "High", "value": 0.9}}),
                      encoding="utf-8")
        html, err = report_export.from_report_file(str(md))
        self.assertEqual(err, "")
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("Title &lt;x&gt;", html)
        missing_html, missing_err = report_export.from_report_file(
            str(folder / "nope.md"))
        self.assertEqual(missing_html, "")
        self.assertTrue(missing_err)


class FakeAPI:
    def __init__(self):
        self.sent = []
        self.docs = []

    def send(self, chat_id, text, buttons=None, parse_mode=None):
        self.sent.append((int(chat_id), str(text)))
        return {"ok": True}

    def send_document(self, chat_id, file_path, caption="", timeout=120):
        self.docs.append((int(chat_id), str(file_path), caption))
        return {"ok": True}


class TestReportCommand(unittest.TestCase):
    def test_report_html_then_md(self):
        folder = config.reports_dir()
        md = folder / "brief-cmd-test.md"
        js = folder / "brief-cmd-test.json"
        md.write_text("# md", encoding="utf-8")
        js.write_text(json.dumps({"query": "sawal", "items": [_item("Title <x>")],
                                  "diagnostics": [], "audit": {},
                                  "confidence": {"label": "High", "value": 0.9}}),
                      encoding="utf-8")
        store.save_report("Test report", "sawal", str(md), "md")
        api = FakeAPI()
        res = tb.dispatch(42, "/report html", {"telegram_chat_id": "42"}, api=api)
        self.assertTrue(res["ok"], res)
        self.assertEqual(res["fmt"], "html")
        self.assertTrue(os.path.isfile(res["path"]))
        self.assertTrue(res["path"].endswith(".html"))
        content = Path(res["path"]).read_text(encoding="utf-8")
        self.assertIn("<!DOCTYPE html>", content)
        self.assertIn("Title &lt;x&gt;", content)
        res_md = tb.dispatch(42, "/report", {"telegram_chat_id": "42"}, api=api)
        self.assertEqual(res_md["fmt"], "md")
        self.assertEqual(res_md["path"], str(md))
        bad = tb.dispatch(42, "/report pdf", {"telegram_chat_id": "42"}, api=api)
        self.assertFalse(bad["ok"])
        self.assertEqual(bad["error"], "bad format")


if __name__ == "__main__":
    unittest.main()
