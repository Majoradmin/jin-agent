"""PHASE 8 - security / path-authorization regression tests (stdlib unittest).

Read-only characterization only: path authorization, header/body hardening,
secret masking and SSRF/URL validation. NO account/activation-lock bypass and
NO device write/erase/flash operation is present or required. The existing
policy-boundary assertions in test_sahulat.py stay intact.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _harness as H

BASE, ROOT = H.BASE, H.ROOT
import db            # noqa: E402
import research      # noqa: E402
import server        # noqa: E402

_HTTPD = None
_PORT = 0


def setUpModule():
    global _HTTPD, _PORT
    _HTTPD, _PORT = H.start()


def tearDownModule():
    global _HTTPD
    H.stop(_HTTPD)
    _HTTPD = None


class TestSecurity(unittest.TestCase):
    def setUp(self):
        H.reset_db()

    def test_settings_no_secret_leak(self):
        # Unit: _mask_settings masks llm_key to the "***" indicator.
        masked = server._mask_settings({"llm_key": "SUPERSECRET_PLAINTEXT",
                                        "llm_endpoint": ""})
        self.assertEqual(masked["llm_key"], "***")
        self.assertNotIn("SUPERSECRET_PLAINTEXT", json.dumps(masked))
        # Endpoint: no response may echo the plaintext key.
        code, _, raw = H.request(_PORT, "/api/settings",
                                 payload={"llm_key": "PLAINTEXT_SECRET_999"})
        self.assertEqual(code, 200)
        self.assertNotIn(b"PLAINTEXT_SECRET_999", raw)
        _, _, got = H.get_json(_PORT, "/api/settings")
        self.assertEqual(got["llm_key"], "***")
        _, _, status = H.get_json(_PORT, "/api/status")
        self.assertEqual(status["settings"]["llm_key"], "***")
        self.assertNotIn("PLAINTEXT_SECRET_999", json.dumps(status))

    def test_llm_endpoint_rejects_internal(self):
        # server.validate_llm_endpoint is the point-of-use SSRF validator.
        for url in ("http://127.0.0.1:9/x", "http://localhost/x",
                    "http://[::1]/x", "http://169.254.169.254/latest",
                    "http://10.0.0.1/x", "http://metadata.google.internal/x"):
            with self.subTest(url=url):
                self.assertFalse(server.validate_llm_endpoint(url), url)
        # Internal endpoint -> 400 (SSRF block); safe public https -> 200.
        code, _, body = H.post_json(_PORT, "/api/settings",
                                    {"llm_endpoint": "http://127.0.0.1:9/x"})
        self.assertEqual(code, 400)
        self.assertIn("error", body)
        code, _, body = H.post_json(_PORT, "/api/settings",
                                    {"llm_endpoint": "https://api.example.com/v1"})
        self.assertEqual(code, 200)
        self.assertIs(body["ok"], True)

    def test_javascript_url_rejected(self):
        # research.validate_url() is the feed-side validator (QA #4).
        for u in ("javascript:alert(1)", "data:text/html,<script>x</script>",
                  "vbscript:msgbox(1)", "file:///etc/passwd", "ftp://host/x",
                  "http://127.0.0.1/x", "http://localhost/x",
                  "https://metadata.google.internal/x"):
            with self.subTest(url=u):
                with self.assertRaises(ValueError):
                    research.validate_url(u)
        # Frontend defense-in-depth: safe_url() gates http/https only.
        js = (BASE / "web" / "app.js").read_text(encoding="utf-8")
        self.assertIn("const safe_url", js)
        self.assertIn(r"/^https?:\/\//i", js)

    def test_security_headers_present(self):
        required = ("Content-Security-Policy", "X-Frame-Options",
                    "Referrer-Policy", "X-Content-Type-Options")
        for path in ("/api/status", "/index.html", "/style.css",
                     "/api/nope", "/api/packages?limit=bad"):
            with self.subTest(path=path):
                _, hdrs, _ = H.request(_PORT, path)
                for name in required:
                    self.assertIsNotNone(H.header(hdrs, name), (path, name))
                self.assertEqual(H.header(hdrs, "X-Frame-Options"), "DENY")
                self.assertEqual(H.header(hdrs, "X-Content-Type-Options"), "nosniff")
                self.assertEqual(H.header(hdrs, "Referrer-Policy"), "no-referrer")

    def test_body_size_cap_413(self):
        code, _, raw = H.request(_PORT, "/api/settings",
                                 body=b"x" * (server.MAX_BODY + 512))
        self.assertEqual(code, 413)
        self.assertIn("error", json.loads(raw.decode("utf-8", "replace")))

    def test_status_no_abs_db_path(self):
        code, _, status = H.get_json(_PORT, "/api/status")
        self.assertEqual(code, 200)
        dbname = status["db"]
        self.assertEqual(dbname, pathlib.PureWindowsPath(dbname).name)  # basename only
        self.assertNotIn("\\", dbname)
        self.assertNotIn("/", dbname)
        self.assertNotIn(":", dbname)
        self.assertNotIn(db.DB_PATH.lower(), json.dumps(status).lower())
        # additive relative sample_dir (resolved against BASE by the scan guard)
        sd = status["sample_dir"]
        self.assertTrue(sd)
        self.assertFalse(pathlib.PureWindowsPath(sd).is_absolute())
        self.assertNotIn(":", sd)

    def test_reveal_rejects_sibling_prefix(self):
        # A path sharing the WORKSPACE string prefix but actually a sibling
        # must be denied by commonpath (not a naive startswith).
        sibling = str(ROOT / (BASE.name + "_Evil") / "secret")
        code, _, body = H.post_json(_PORT, "/api/reveal", {"path": sibling})
        self.assertEqual(code, 403)
        err = body["error"]
        self.assertIn("ijazat", err.lower())
        self.assertIsNone(re.search(r"[A-Za-z]:[\\/]", err))  # no abs path leak
        with self.assertRaises(server._PathDenied):
            server._authorize_path(sibling)

    def test_scan_outside_denied_by_default(self):
        code, _, body = H.post_json(_PORT, "/api/scan", {"path": str(ROOT)})
        self.assertEqual(code, 400)
        self.assertIn("ijazat", body["error"].lower())

    def test_scan_outside_allowed_with_flag(self):
        code, _, body = H.post_json(_PORT, "/api/scan",
                                    {"path": str(ROOT), "allow_outside": True})
        self.assertEqual(code, 200)
        self.assertIs(body["ok"], True)
        self.assertIn("id", body)
        self.assertIn("health", body["report"])

    def test_scan_rejects_symlink_escape(self):
        # /api/scan authorizes via _authorize_path before scan_folder. A path
        # whose lexical form is inside WORKSPACE but resolves outside (junction)
        # is denied by realpath + commonpath, never a startswith prefix.
        outside = str(ROOT / "p8_symlink_escape_target")
        with mock.patch("server.os.path.realpath", return_value=outside):
            with self.assertRaises(server._PathDenied) as cm:
                server._authorize_path("samples")
        self.assertIn("symlink", str(cm.exception).lower())
        # Endpoint level: the escape is denied with 400 (never a 500).
        import os as _os
        orig = _os.path.realpath

        def fake(p):
            return outside if ("samples" in str(p) and "MobileLab" in str(p)) else orig(p)

        with mock.patch("server.os.path.realpath", side_effect=fake):
            code, _, body = H.post_json(_PORT, "/api/scan", {"path": "samples"})
        self.assertEqual(code, 400)
        self.assertIn("error", body)

    def test_scan_rejects_unc_path(self):
        code, _, body = H.post_json(_PORT, "/api/scan",
                                    {"path": "\\\\NAS\\share\\firmware"})
        self.assertEqual(code, 400)
        self.assertIn("UNC", body["error"])
        with self.assertRaises(server._PathDenied):
            server._authorize_path("//NAS/share/firmware")


if __name__ == "__main__":
    unittest.main(verbosity=2)
