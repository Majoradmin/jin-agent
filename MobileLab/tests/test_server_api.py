"""PHASE 8 - HTTP-level API regression tests (stdlib unittest, fully offline).

``research.research`` is mocked for the whole class so no request ever reaches
the live internet; the loopback server itself is real (in-process).
"""
from __future__ import annotations

import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _harness as H

import db                # noqa: E402
import server            # noqa: E402

_HTTPD = None
_PORT = 0


def setUpModule():
    global _HTTPD, _PORT
    _HTTPD, _PORT = H.start()


def tearDownModule():
    global _HTTPD
    H.stop(_HTTPD)
    _HTTPD = None


class TestServerAPI(unittest.TestCase):
    def setUp(self):
        H.reset_db()
        self._calls = []
        holder = self

        def fake_research(params, settings):
            holder._calls.append(dict(params))
            return {"items": [], "diagnostics": [], "fetched_at": "offline",
                    "cached": False, "query": "", "terms": []}

        self._patch = mock.patch("research.research", side_effect=fake_research)
        self._patch.start()
        self.addCleanup(self._patch.stop)

    # ---------------- required named regression tests ----------------
    def test_invalid_query_params_return_400(self):
        for path in ("/api/research?limit=bad", "/api/research?days=abc",
                     "/api/research?min_score=nan", "/api/packages?limit=bad",
                     "/api/packages?offset=oops"):
            with self.subTest(path=path):
                code, _, body = H.get_json(_PORT, path)
                self.assertEqual(code, 400)
                self.assertIn("error", body)

    def test_no_stacktrace_on_bad_input(self):
        for path in ("/api/research?limit=bad", "/api/packages?limit=bad",
                     "/api/research?days=abc"):
            with self.subTest(path=path):
                code, _, raw = H.request(_PORT, path)
                self.assertEqual(code, 400)
                text = raw.decode("utf-8", "replace")
                self.assertNotIn("Traceback", text)
                self.assertNotIn('File "', text)
                self.assertNotIn("C:\\", text)

    def test_unknown_api_returns_404(self):
        for path in ("/api/definitely-unknown", "/api/nope"):
            with self.subTest(path=path):
                code, _, body = H.get_json(_PORT, path)
                self.assertEqual(code, 404)
                self.assertIn("error", body)
        code, _, body = H.post_json(_PORT, "/api/does-not-exist", {})
        self.assertEqual(code, 404)
        self.assertIn("error", body)

    def test_list_packages_empty_db(self):
        code, _, body = H.get_json(_PORT, "/api/packages")
        self.assertEqual(code, 200)
        self.assertEqual(body["items"], [])
        self.assertEqual(body["total"], 0)
        self.assertEqual(body["page"], 1)
        self.assertEqual(body["pages"], 1)

    def test_limit_clamped_to_5_200(self):
        H.get_json(_PORT, "/api/research?limit=1")
        H.get_json(_PORT, "/api/research?limit=99999")
        H.get_json(_PORT, "/api/research?limit=50")
        limits = [c["limit"] for c in self._calls]
        self.assertEqual(limits, [5, 200, 50])

    def test_min_score_boundary(self):
        for bad in ("abc", "nan", "inf"):
            with self.subTest(bad=bad):
                code, _, body = H.get_json(_PORT, "/api/research?min_score=" + bad)
                self.assertEqual(code, 400)
                self.assertIn("error", body)
        self._calls.clear()
        code, _, _ = H.get_json(_PORT, "/api/research?min_score=7")
        self.assertEqual(code, 200)
        self.assertEqual(self._calls[-1]["min_score"], 7.0)
        # Numeric values (incl. negative) are accepted: no lo/hi clamp here.
        code, _, _ = H.get_json(_PORT, "/api/research?min_score=-3.5")
        self.assertEqual(code, 200)
        self.assertEqual(self._calls[-1]["min_score"], -3.5)

    def test_packages_paginated(self):
        for name in ("P1", "P2", "P3"):
            db.save_package(
                {"root": "X:/" + name, "files": [], "total_size": 0, "meta": {}},
                {"health": 100}, name=name)
        code, _, first = H.get_json(_PORT, "/api/packages?limit=2&offset=0")
        self.assertEqual(code, 200)
        self.assertEqual(len(first["items"]), 2)
        self.assertEqual(first["total"], 3)
        self.assertEqual(first["page"], 1)
        self.assertEqual(first["pages"], 2)
        code, _, second = H.get_json(_PORT, "/api/packages?limit=2&offset=2")
        self.assertEqual(code, 200)
        self.assertEqual(len(second["items"]), 1)
        self.assertEqual(second["page"], 2)
        self.assertEqual(second["pages"], 2)

    def test_article_action_allowlist(self):
        for act in ("save", "unsave", "read", "unread"):
            with self.subTest(act=act):
                code, _, body = H.post_json(
                    _PORT, "/api/article", {"guid": "g1", "action": act})
                self.assertEqual(code, 200)
                self.assertEqual(body["action"], act)
        for bad in ("evil", "save; DROP TABLE articles", ""):
            with self.subTest(bad=bad):
                code, _, body = H.post_json(
                    _PORT, "/api/article", {"guid": "g1", "action": bad})
                self.assertEqual(code, 400)
        # The action -> SQL map is an allowlist of parameterized statements only.
        self.assertIsInstance(server._ARTICLE_UPDATES, dict)
        for sql, _val in server._ARTICLE_UPDATES.values():
            self.assertIn("?", sql)
        # Injection-looking strings never damaged the articles table.
        self.assertIsNotNone(db.one("SELECT COUNT(*) n FROM articles"))

    # ---------------- endpoint coverage (offline) ----------------
    def test_core_get_endpoints_ok(self):
        checks = {
            "/api/status": ("app", "version", "policy", "counts", "settings"),
            "/api/knowledge": ("boundary", "official_routes", "glossary", "help"),
            "/api/sources": ("sources", "presets", "categories"),
            "/api/settings": ("llm_key", "llm_endpoint"),
            "/api/models": ("items",),
            "/api/jobs": ("items",),
            "/api/model-brief?q=SM8650&live=0":
                ("term", "card", "packages", "live", "official"),
        }
        for path, keys in checks.items():
            with self.subTest(path=path):
                code, _, body = H.get_json(_PORT, path)
                self.assertEqual(code, 200)
                for k in keys:
                    self.assertIn(k, body)

    def test_scan_endpoint_with_demo_samples(self):
        for rel in ("samples/MTK_Demo_MT6899_UFS", "samples/QCOM_Demo_SM8650_UFS"):
            with self.subTest(rel=rel):
                code, _, body = H.post_json(_PORT, "/api/scan", {"path": rel})
                self.assertEqual(code, 200)
                self.assertIs(body["ok"], True)
                self.assertIn("id", body)
                self.assertIn("health", body["report"])
                self.assertGreater(body["file_count"], 0)
        self.assertEqual(db.counts()["packages"], 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
