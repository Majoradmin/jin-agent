"""PHASE 13 - agent memory + Telegram public preview tests (offline).

The DB is the shared harness throwaway DB (``data/_p8_test.db``); every network
call is mocked. No production DB and no live Telegram request is touched.
"""
from __future__ import annotations

import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _harness as H

import agent_memory     # noqa: E402
import db               # noqa: E402
import server           # noqa: E402
import telegram_public  # noqa: E402

_HTTPD = None
_PORT = 0


def setUpModule():
    global _HTTPD, _PORT
    _HTTPD, _PORT = H.start()


def tearDownModule():
    global _HTTPD
    H.stop(_HTTPD)
    _HTTPD = None


PREVIEW_HTML = """<!DOCTYPE html><html><body>
<div class="tgme_widget_message_wrap js-widget_message_wrap">
  <div class="tgme_widget_message" data-post="testch/10">
    <a class="tgme_widget_message_date" href="https://t.me/testch/10">
      <time datetime="2026-11-08T10:00:00+00:00"></time>
    </a>
    <div class="tgme_widget_message_bubble">
      <div class="tgme_widget_message_text js-message_text" dir="auto">
        Samsung <b>firmware</b> update released<br>check the build number
      </div>
      <span class="tgme_widget_message_views">1.2K</span>
    </div>
  </div>
</div>
<div class="tgme_widget_message_wrap js-widget_message_wrap">
  <div class="tgme_widget_message" data-post="testch/9">
    <a class="tgme_widget_message_date" href="https://t.me/testch/9">
      <time datetime="2026-11-07T08:30:00+00:00"></time>
    </a>
    <div class="tgme_widget_message_text js-message_text" dir="auto">MediaTek preloader notes</div>
  </div>
</div>
</body></html>"""


class _FakeResponse:
    status = 200

    def __init__(self, body: bytes):
        self._body = body

    def read(self, n=-1):
        return self._body if not n or n < 0 else self._body[:n]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class TestMemoryCore(unittest.TestCase):
    def setUp(self):
        H.reset_db()

    def test_seed_sources_exist_and_are_ranked(self):
        items = agent_memory.list_sources()
        self.assertGreaterEqual(len(items), 15)
        names = {s["name"] for s in items}
        self.assertIn("Android Security Bulletin", names)
        self.assertIn("GSMArena", names)
        priorities = [s["priority"] for s in items]
        self.assertEqual(priorities, sorted(priorities, reverse=True))

    def test_add_custom_source_then_archive(self):
        row = agent_memory.add_source({
            "name": "My Firmware Forum", "url": "https://example.com/feed",
            "type": "feed", "category": "firmware", "usefulness": 5,
        })
        self.assertGreater(row["id"], 0)
        self.assertEqual(row["status"], "active")
        self.assertEqual(row["added_by"], "user")
        self.assertEqual(row["usefulness"], 5)
        self.assertGreaterEqual(row["priority"], 4)
        archived = agent_memory.archive_source(row["id"])
        self.assertEqual(archived["status"], "archived")
        self.assertEqual(archived["priority"], 0)
        active_names = {s["name"] for s in agent_memory.list_sources()}
        self.assertNotIn("My Firmware Forum", active_names)
        all_names = {s["name"] for s in agent_memory.list_sources(include_archived=True)}
        self.assertIn("My Firmware Forum", all_names)

    def test_add_source_rejects_unsafe_urls(self):
        for url in ("http://127.0.0.1/private", "http://localhost/feed",
                    "javascript:alert(1)", "ftp://example.com/feed"):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    agent_memory.add_source({"name": "bad", "url": url})

    def test_problem_and_feedback_memory(self):
        p = agent_memory.add_problem({"title": "SM-S918B bootloop after update",
                                      "model": "SM-S918B", "symptoms": "stuck on logo"})
        self.assertGreater(p["id"], 0)
        self.assertEqual(p["status"], "open")
        row = db.one("SELECT usefulness FROM memory_sources WHERE name='GSMArena'")
        before = row["usefulness"]
        fb = agent_memory.add_feedback({"target_type": "item", "target_key": "g1",
                                        "source": "GSMArena", "rating": "useful",
                                        "note": "kaam ka source"})
        self.assertEqual(fb["rating"], "useful")
        after = db.one("SELECT usefulness FROM memory_sources WHERE name='GSMArena'")["usefulness"]
        self.assertEqual(after, min(5, before + 1))
        self.assertEqual(len(agent_memory.list_feedback()), 1)

    def test_record_research_query_and_recall(self):
        result = {
            "query": "Samsung SM-S918B bootloop", "category": "android",
            "terms": ["samsung", "sm-s918b", "bootloop"],
            "total": 12, "returned": 5, "sources_ok": 3, "sources_failed": 1,
            "diagnostics": [{"source": "GSMArena", "ok": True, "count": 4},
                            {"source": "XDA Developers", "ok": False, "error": "timeout"}],
            "items": [{"title": "CVE-2026-20545 fixed", "excerpt": "SM-S918B patch"}],
        }
        saved = agent_memory.record_research({"q": result["query"]}, result)
        self.assertIsNotNone(saved)
        self.assertEqual(saved["hits"], 1)
        again = agent_memory.record_research({"q": result["query"]}, result)
        self.assertEqual(again["hits"], 2)
        rec = agent_memory.recall("SM-S918B")
        self.assertTrue(rec["known"])
        self.assertEqual(rec["queries"][0]["hits"], 2)
        entities = {e["name"] for e in db.rows("SELECT name FROM memory_entities")}
        self.assertIn("CVE-2026-20545", entities)
        self.assertIn("SM-S918B", entities)
        src = db.one("SELECT ok_count,fail_count FROM memory_sources WHERE name='GSMArena'")
        self.assertEqual(src["ok_count"], 2)
        xda = db.one("SELECT fail_count FROM memory_sources WHERE name='XDA Developers'")
        self.assertEqual(xda["fail_count"], 2)

    def test_export_markdown_contains_live_memory(self):
        agent_memory.add_source({"name": "My Private Feed", "url": "https://example.org/rss",
                                 "category": "ai", "usefulness": 4})
        agent_memory.add_telegram({"channel": "@gsm_mobile_lab", "category": "gsm",
                                   "title": "GSM Lab"})
        text = agent_memory.export_markdown()
        for token in ("# agent_memory.md", "## 3. Source Registry",
                      "My Private Feed", "@gsm_mobile_lab", "## 10. Learning Rules"):
            with self.subTest(token=token):
                self.assertIn(token, text)


class TestTelegramPublic(unittest.TestCase):
    def setUp(self):
        H.reset_db()

    def test_normalize_channel_variants(self):
        for raw in ("@mychannel", "mychannel", "t.me/mychannel",
                    "https://t.me/mychannel", "https://t.me/s/mychannel?q=gsm"):
            with self.subTest(raw=raw):
                self.assertEqual(telegram_public.normalize_channel(raw), "mychannel")
        for bad in ("", "ab", "t.me/+invite123", "bad-channel", "https://t.me/joinchat/x"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    telegram_public.normalize_channel(bad)

    def test_parse_preview_extracts_text_date_link(self):
        items = telegram_public.parse_preview(PREVIEW_HTML)
        self.assertEqual(len(items), 2)
        self.assertIn("Samsung firmware update released", items[0]["text"])
        self.assertIn("check the build number", items[0]["text"])
        self.assertEqual(items[0]["published"], "2026-11-08T10:00:00+00:00")
        self.assertEqual(items[0]["url"], "https://t.me/testch/10")
        self.assertEqual(items[0]["views"], "1.2K")
        self.assertIn("MediaTek preloader", items[1]["text"])

    def test_fetch_channel_mocked_ok(self):
        with mock.patch("urllib.request.urlopen",
                        return_value=_FakeResponse(PREVIEW_HTML.encode("utf-8"))), \
             mock.patch.object(telegram_public, "validate_url",
                               side_effect=lambda url, allowlist=None: url):
            res = telegram_public.fetch_channel("@testch", "firmware", 5)
        self.assertTrue(res["ok"])
        self.assertEqual(res["channel"], "testch")
        self.assertEqual(res["count"], 2)
        self.assertEqual(res["items"][0]["published"], "2026-11-08 10:00 UTC")
        self.assertIn("q=firmware", res["url"])

    def test_fetch_channel_mocked_failure_is_graceful(self):
        with mock.patch("urllib.request.urlopen", side_effect=RuntimeError("boom")), \
             mock.patch.object(telegram_public, "validate_url",
                               side_effect=lambda url, allowlist=None: url):
            res = telegram_public.fetch_channel("testch")
        self.assertFalse(res["ok"])
        self.assertIn("boom", res["error"])
        self.assertEqual(res["items"], [])


class TestMemoryApi(unittest.TestCase):
    def setUp(self):
        H.reset_db()

    def test_source_routes_add_list_archive(self):
        code, _, body = H.post_json(_PORT, "/api/memory/sources", {
            "name": "API Added Source", "url": "https://example.com/feed",
            "type": "feed", "category": "gsm", "usefulness": 4,
        })
        self.assertEqual(code, 200)
        sid = body["source"]["id"]
        code, _, body = H.get_json(_PORT, "/api/memory/sources")
        self.assertEqual(code, 200)
        self.assertIn("API Added Source", {s["name"] for s in body["items"]})
        code, _, body = H.delete_json(_PORT, "/api/memory/sources/%d" % sid)
        self.assertEqual(code, 200)
        self.assertTrue(body["archived"])
        code, _, body = H.get_json(_PORT, "/api/memory/sources")
        self.assertNotIn("API Added Source", {s["name"] for s in body["items"]})

    def test_source_route_rejects_private_url(self):
        code, _, body = H.post_json(_PORT, "/api/memory/sources",
                                    {"name": "bad", "url": "http://127.0.0.1/x"})
        self.assertEqual(code, 400)
        self.assertIn("error", body)

    def test_telegram_add_and_search_mocked(self):
        code, _, body = H.post_json(_PORT, "/api/memory/telegram",
                                    {"channel": "@gsm_lab", "category": "gsm"})
        self.assertEqual(code, 200)
        self.assertEqual(body["telegram"]["channel"], "gsm_lab")
        fake = {"ok": True, "channel": "gsm_lab", "url": "https://t.me/s/gsm_lab",
                "query": "", "fetched_at": "2026-11-09 00:00 UTC", "count": 1,
                "items": [{"text": "hello", "published": "2026-11-09 00:00 UTC",
                           "url": "https://t.me/gsm_lab/1", "views": "10"}], "error": ""}
        with mock.patch.object(server.telegram_public, "fetch_channel", return_value=fake):
            code, _, body = H.get_json(_PORT, "/api/memory/telegram/search?channel=@gsm_lab")
        self.assertEqual(code, 200)
        self.assertTrue(body["ok"])
        self.assertEqual(body["items"][0]["text"], "hello")
        row = db.one("SELECT ok_count FROM memory_telegram WHERE channel='gsm_lab'")
        self.assertEqual(row["ok_count"], 1)

    def test_telegram_search_requires_valid_channel(self):
        code, _, body = H.get_json(_PORT, "/api/memory/telegram/search?channel=bad-channel")
        self.assertEqual(code, 400)
        self.assertIn("error", body)

    def test_overview_recall_and_feedback_routes(self):
        H.post_json(_PORT, "/api/memory/problems",
                    {"title": "bootloop", "model": "SM-S918B"})
        code, _, body = H.get_json(_PORT, "/api/memory/overview")
        self.assertEqual(code, 200)
        self.assertEqual(body["counts"]["problems"], 1)
        code, _, body = H.get_json(_PORT, "/api/memory/recall?q=bootloop")
        self.assertEqual(code, 200)
        self.assertTrue(body["known"])
        code, _, body = H.post_json(_PORT, "/api/memory/feedback",
                                    {"target_type": "item", "target_key": "g1",
                                     "source": "GSMArena", "rating": "not_useful"})
        self.assertEqual(code, 200)
        self.assertEqual(body["feedback"]["rating"], "not_useful")

    def test_markdown_endpoint(self):
        H.post_json(_PORT, "/api/memory/sources", {"name": "Markdown Source",
                                                   "url": "https://example.net/x"})
        code, hdrs, raw = H.request(_PORT, "/api/memory/markdown")
        self.assertEqual(code, 200)
        text = raw.decode("utf-8")
        self.assertIn("Markdown Source", text)
        self.assertIn("Agent Runtime Memory", text)

    def test_research_response_includes_memory(self):
        code, _, body = H.get_json(
            _PORT, "/api/research?q=memory+route+test&sources=does-not-exist&limit=5")
        self.assertEqual(code, 200)
        self.assertIn("memory", body)
        self.assertEqual(body["memory"]["saved"]["query"], "memory route test")
        self.assertIn("recall", body["memory"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
