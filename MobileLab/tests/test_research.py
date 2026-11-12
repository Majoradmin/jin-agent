"""PHASE 8 - research.py characterization tests. FULLY OFFLINE.

Every outbound call is mocked: ``research.fetch`` (pipeline), ``urllib.request.urlopen``
(LLM rewrite) and ``research.socket.getaddrinfo`` (URL validation). ZERO real network.
"""
from __future__ import annotations

import json
import pathlib
import sys
import time
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _harness as H

import research as R    # noqa: E402
import server           # noqa: E402

_HTTPD = None
_PORT = 0


def setUpModule():
    global _HTTPD, _PORT
    _HTTPD, _PORT = H.start()


def tearDownModule():
    global _HTTPD
    H.stop(_HTTPD)
    _HTTPD = None


class TestResearchOffline(unittest.TestCase):
    def setUp(self):
        H.reset_db()

    def test_research_source_timeout_degrades_gracefully(self):
        params = {"q": "firmware", "preset": "all", "refresh": True,
                  "limit": 5, "sources": ["gsmarena", "xda"]}
        with mock.patch("research.fetch", side_effect=TimeoutError("timed out")):
            out = R.research(params, {})
        self.assertIsInstance(out, dict)
        self.assertEqual(out["items"], [])
        self.assertFalse(out["cached"])
        self.assertGreater(len(out["diagnostics"]), 0)
        self.assertTrue(all(not d["ok"] for d in out["diagnostics"]))
        self.assertTrue(all("TimeoutError" in d["error"] for d in out["diagnostics"]))
        self.assertEqual(out["sources_ok"], 0)
        self.assertEqual(out["sources_failed"], out["sources_total"])
        for key in ("query", "preset", "category", "total", "returned",
                    "terms", "fetched_at"):
            self.assertIn(key, out)

    def test_cache_bounded(self):
        R._CACHE.clear()
        now = time.time()
        for i in range(server._CACHE_MAX + 44):
            R._CACHE["k%d" % i] = (now, {"x": i})
        self.assertGreater(len(R._CACHE), server._CACHE_MAX)
        server._prune_research_cache()
        self.assertLessEqual(len(R._CACHE), server._CACHE_MAX)

        # TTL eviction of stale entries, fresh ones retained.
        R._CACHE.clear()
        R._CACHE["stale"] = (now - server._CACHE_TTL - 10, {"x": 1})
        R._CACHE["fresh"] = (now, {"x": 2})
        server._prune_research_cache()
        self.assertNotIn("stale", R._CACHE)
        self.assertIn("fresh", R._CACHE)

        # research() cache hit for an unchanged query returns cached=True.
        R._CACHE.clear()
        p = {"q": "firehose", "preset": "all", "refresh": False,
             "limit": 5, "sources": ["gsmarena"]}
        with mock.patch("research.fetch", side_effect=TimeoutError("timed out")):
            first = R.research(p, {})
            second = R.research(dict(p), {})
        self.assertFalse(first["cached"])
        self.assertTrue(second["cached"])

    def test_llm_failure_logged_not_swallowed(self):
        settings = {"llm_endpoint": "https://api.example.com/v1",
                    "llm_key": "k", "llm_model": "m"}
        with mock.patch("urllib.request.urlopen", side_effect=RuntimeError("boom")):
            with self.assertLogs("research", level="WARNING") as cm:
                result = R.llm_rewrite("ek note", settings)
        self.assertIsNone(result)
        self.assertTrue(any("LLM rewrite failed" in line for line in cm.output))
        # Missing settings -> feature disabled, no call, no exception.
        self.assertIsNone(R.llm_rewrite("note", {}))


class TestResearchHelpers(unittest.TestCase):
    def setUp(self):
        H.reset_db()

    def test_validate_url_rejects_unsafe(self):
        for bad in ("javascript:alert(1)", "data:text/html,x", "vbscript:msgbox(1)",
                    "file:///etc/passwd", "ftp://host/x", "http://127.0.0.1/x",
                    "http://localhost/x", "https://metadata.google.internal/x",
                    "http://8.8.8.8/x"):
            with self.subTest(url=bad):
                with self.assertRaises(ValueError):
                    R.validate_url(bad)
        # A non-allowlisted host is rejected before any DNS work.
        with self.assertRaises(ValueError):
            R.validate_url("https://evil.example.com/x", allowlist=R.FEED_HOSTS)

    def test_validate_url_allows_feed_host_offline(self):
        url = "https://www.gsmarena.com/rss-news-reviews.php3"
        self.assertIn("www.gsmarena.com", R.FEED_HOSTS)
        # DNS fails offline -> fail-open (returns URL), no live network.
        with mock.patch("research.socket.getaddrinfo", side_effect=OSError("offline")):
            self.assertEqual(R.validate_url(url, allowlist=R.FEED_HOSTS), url)
        # A resolved internal IP is rejected even for an allowlisted host.
        with mock.patch("research.socket.getaddrinfo",
                        return_value=[(2, 1, 6, "", ("10.0.0.1", 443))]):
            with self.assertRaises(ValueError):
                R.validate_url(url, allowlist=R.FEED_HOSTS)

    def test_query_terms(self):
        terms = R.query_terms("Huawei EMUI 16 firmware OR Snapdragon firehose")
        self.assertEqual(terms, ["huawei", "emui", "firmware", "snapdragon", "firehose"])
        self.assertNotIn("or", terms)
        self.assertNotIn("new", terms)
        self.assertLessEqual(len(R.query_terms("word " * 30)), 14)

    def test_has_word_boundary(self):
        # Short terms (<=4 chars) require a word boundary; long ones use substring.
        self.assertTrue(R._has("ufs", "the ufs storage"))
        self.assertFalse(R._has("ufs", "notufsx"))
        self.assertTrue(R._has("firehose", "a firehose loader"))
        self.assertTrue(R._has("firehose", "firehoses"))

    def test_score_item(self):
        rec = {"title": "Qualcomm firehose EDL 9008",
               "excerpt": "new loader", "published": ""}
        sc, matched = R.score_item(rec, ["firehose", "edl", "9008"], "qcom")
        self.assertEqual(sc, 9.5)
        self.assertEqual(matched, ["firehose", "edl", "9008"])

    def test_make_khulasa(self):
        high = R.make_khulasa({"source": "XDA", "published": "2026-11-08 10:00 UTC"},
                              "qcom", ["firehose"], 8.0)
        for part in ("XDA", "2026-11-08 10:00 UTC", "firehose",
                     "pehle isay parhein"):
            self.assertIn(part, high)
        low = R.make_khulasa({"source": "X"}, "general", [], 1.0)
        self.assertNotIn("pehle isay parhein", low)

    def test_parse_feed(self):
        rss = ('<rss><channel><item><title>Hi</title>'
               '<link>https://x/a</link><guid>g1</guid>'
               '<description>body</description></item></channel></rss>')
        items = R.parse_feed(rss, "XDA", "tools")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "Hi")
        self.assertEqual(items[0]["url"], "https://x/a")
        self.assertEqual(items[0]["guid"], "g1")
        self.assertEqual(items[0]["source_cat"], "tools")
        atom = ('<feed><entry><title>A</title>'
                '<link href="https://y/b"/><id>id2</id></entry></feed>')
        a = R.parse_feed(atom, "Src", "")
        self.assertEqual(len(a), 1)
        self.assertEqual(a[0]["guid"], "id2")
        self.assertEqual(a[0]["url"], "https://y/b")
        self.assertEqual(R.parse_feed("not xml at all", "X"), [])

    def test_category_of(self):
        cases = {"Huawei EMUI update": "huawei",
                 "Qualcomm firehose EDL": "qcom",
                 "iPhone activation lock": "apple",
                 "CVE-2024 exploit": "security",
                 "random blog post": "general"}
        for text, cat in cases.items():
            with self.subTest(text=text):
                self.assertEqual(R.category_of(text), cat)


class TestLocalLLMConfig(unittest.TestCase):
    """P14: local model support without weakening the QA #6 SSRF guard."""

    def test_off_is_rule_based_with_reason(self):
        c = R.resolve_llm({})
        self.assertFalse(c["enabled"])
        self.assertEqual(c["mode"], "rule_based")
        self.assertTrue(c["reason"])
        self.assertFalse(c["key_required"])   # OFF means no key is needed either

    def test_ollama_needs_no_key(self):
        c = R.resolve_llm({"llm_provider": "ollama", "llm_model": "qwen2.5:0.5b"})
        self.assertTrue(c["enabled"])
        self.assertEqual(c["base"], "http://127.0.0.1:11434/v1")
        self.assertFalse(c["key_required"])

    def test_lmstudio_endpoint(self):
        c = R.resolve_llm({"llm_provider": "lmstudio", "llm_model": "local-model"})
        self.assertTrue(c["enabled"])
        self.assertEqual(c["base"], "http://127.0.0.1:1234/v1")

    def test_local_without_model_stays_off(self):
        c = R.resolve_llm({"llm_provider": "ollama"})
        self.assertFalse(c["enabled"])
        self.assertIn("Model ka naam", c["reason"])

    def test_custom_requires_key(self):
        base = {"llm_provider": "custom", "llm_endpoint": "https://api.example.com/v1",
                "llm_model": "m"}
        self.assertFalse(R.resolve_llm(base)["enabled"])
        self.assertTrue(R.resolve_llm({**base, "llm_key": "k"})["enabled"])

    def test_custom_internal_endpoint_blocked(self):
        for ep in ("http://127.0.0.1:11434/v1", "http://localhost/v1",
                   "http://169.254.169.254/latest", "http://10.0.0.1/v1",
                   "ftp://x/v1"):
            with self.subTest(ep=ep):
                c = R.resolve_llm({"llm_provider": "custom", "llm_endpoint": ep,
                                   "llm_key": "k", "llm_model": "m"})
                self.assertFalse(c["enabled"])

    def test_legacy_endpoint_still_custom(self):
        c = R.resolve_llm({"llm_endpoint": "https://api.example.com/v1",
                           "llm_key": "k", "llm_model": "m"})
        self.assertTrue(c["enabled"])
        self.assertEqual(c["provider"], "custom")

    def test_status_never_leaks_key(self):
        st = R.llm_status({"llm_provider": "custom",
                           "llm_endpoint": "https://api.example.com/v1",
                           "llm_key": "SUPERSECRET", "llm_model": "m"})
        self.assertNotIn("SUPERSECRET", json.dumps(st))
        self.assertNotIn("llm_key", st)

    def test_probe_disabled_returns_reason(self):
        r = R.llm_probe({})
        self.assertFalse(r["ok"])
        self.assertTrue(r["error"])

    def test_probe_success_mocked(self):
        resp = mock.MagicMock()
        resp.__enter__.return_value.read.return_value = (
            b'{"choices":[{"message":{"content":" OK "}}]}')
        with mock.patch("urllib.request.urlopen", return_value=resp):
            r = R.llm_probe({"llm_provider": "ollama", "llm_model": "tiny"}, timeout=1)
        self.assertTrue(r["ok"])
        self.assertEqual(r["reply"], "OK")

    def test_rewrite_local_omits_auth_header(self):
        resp = mock.MagicMock()
        resp.__enter__.return_value.read.return_value = (
            b'{"choices":[{"message":{"content":"Roman Urdu"}}]}')
        with mock.patch("urllib.request.urlopen", return_value=resp) as u:
            out = R.llm_rewrite("note", {"llm_provider": "ollama", "llm_model": "tiny"})
        self.assertEqual(out, "Roman Urdu")
        req = u.call_args[0][0]
        self.assertNotIn("Authorization", req.headers)
        self.assertIn("127.0.0.1:11434", req.full_url)


class TestLLMHTTP(unittest.TestCase):
    def setUp(self):
        H.reset_db()

    def test_status_llm_block_off(self):
        code, _, body = H.get_json(_PORT, "/api/status")
        self.assertEqual(code, 200)
        self.assertIn("llm", body)
        self.assertFalse(body["llm"]["enabled"])

    def test_llm_status_endpoint(self):
        code, _, body = H.get_json(_PORT, "/api/llm/status")
        self.assertEqual(code, 200)
        self.assertIn("mode", body)

    def test_invalid_provider_rejected(self):
        code, _, _ = H.post_json(_PORT, "/api/settings", {"llm_provider": "evil"})
        self.assertEqual(code, 400)

    def test_ollama_settings_enable_model(self):
        code, _, _ = H.post_json(_PORT, "/api/settings",
                                 {"llm_provider": "ollama", "llm_model": "tiny"})
        self.assertEqual(code, 200)
        _, _, st = H.get_json(_PORT, "/api/status")
        self.assertTrue(st["llm"]["enabled"])
        self.assertEqual(st["llm"]["provider"], "ollama")

    def test_llm_test_endpoint_off_is_safe(self):
        code, _, body = H.post_json(_PORT, "/api/llm/test", {})
        self.assertEqual(code, 200)
        self.assertFalse(body["ok"])
        self.assertTrue(body.get("error"))

    def test_ssrf_guard_still_rejects_loopback_endpoint(self):
        code, _, _ = H.post_json(
            _PORT, "/api/settings",
            {"llm_provider": "custom", "llm_endpoint": "http://127.0.0.1:9/v1"})
        self.assertEqual(code, 400)


if __name__ == "__main__":
    unittest.main(verbosity=2)
