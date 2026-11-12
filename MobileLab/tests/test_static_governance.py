"""PHASE 8 - static governance / asset / a11y assertions (read-only).

These are pure source/markup checks: no production module is modified and no
network or production DB is touched.
"""
from __future__ import annotations

import hashlib
import pathlib
import re
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _harness as H

BASE, ROOT = H.BASE, H.ROOT

VERBATIM_SHA256 = "1de53535942d8e7f1b31b3d9b55c9ae4854e85fd667e14e02f314a62010fd840"
VERBATIM_BOUNDARY = 17844

_HTTPD = None
_PORT = 0


def setUpModule():
    global _HTTPD, _PORT
    _HTTPD, _PORT = H.start()


def tearDownModule():
    global _HTTPD
    H.stop(_HTTPD)
    _HTTPD = None


HTML = (BASE / "web" / "index.html").read_text(encoding="utf-8")
CSS = (BASE / "web" / "style.css").read_text(encoding="utf-8")


class TestStaticGovernance(unittest.TestCase):
    def test_a11y_markup(self):
        # 9 views / 9 nav items / 9 tabpanels / 27 sah* IDs (P13 added Memory).
        self.assertEqual(HTML.count('class="view'), 9)
        self.assertEqual(HTML.count('id="view-'), 9)
        self.assertEqual(HTML.count('data-view="'), 9)
        self.assertEqual(HTML.count('class="nav-item'), 9)
        self.assertEqual(HTML.count('role="tab"'), 9)
        self.assertEqual(HTML.count('role="tabpanel"'), 9)
        self.assertEqual(len(re.findall(r'id="sah[A-Za-z]', HTML)), 27)
        # Language + live-region + focus/motion accessibility.
        self.assertIn('lang="en"', HTML)
        self.assertIn("aria-live", HTML)
        self.assertIn(":focus-visible", CSS)
        self.assertIn("prefers-reduced-motion", CSS)
        # Zero INLINE <script> blocks: every script tag is an external src load.
        tags = re.findall(r"<script\b[^>]*>", HTML, re.I)
        self.assertTrue(tags)
        for tag in tags:
            self.assertIn("src=", tag, tag)
        self.assertNotIn("<script>", HTML)
        for body in re.findall(r"<script\b[^>]*>(.*?)</script>", HTML, re.I | re.S):
            self.assertEqual(body.strip(), "")

    def test_agent_md_verbatim_prefix_integrity(self):
        raw = (ROOT / "agent.md").read_bytes()
        self.assertGreaterEqual(len(raw), VERBATIM_BOUNDARY)
        self.assertEqual(raw.find(b"\n---\n\n## Project Addendum"), VERBATIM_BOUNDARY)
        self.assertEqual(hashlib.sha256(raw[:VERBATIM_BOUNDARY]).hexdigest(),
                         VERBATIM_SHA256)
        self.assertNotIn(b"\r\n", raw)
        self.assertNotIn(b"HARD POLICY", raw[:VERBATIM_BOUNDARY])

    def test_docs_count_exactly_9(self):
        docs = sorted((BASE / "docs").glob("*.md"))
        self.assertEqual(len(docs), 9)

    def test_run_bat_python_version_guard(self):
        bat = (BASE / "run.bat").read_text(encoding="utf-8", errors="replace")
        for tok in ("CHECKVER", "PYMAJOR", "PYMINOR", "LSS 3", "GTR 3",
                    "LSS 10", "TOOOLD", "3.10 or newer", "sys.version_info"):
            with self.subTest(tok=tok):
                self.assertIn(tok, bat)

    def test_no_bypass_flash_erase_commands_in_production(self):
        # Command strings that would appear only if a device write/erase/flash or
        # account/activation-lock bypass capability were added. Domain words such
        # as "firehose", "qfil", "sp flash tool" are legitimate references and are
        # intentionally NOT in this list.
        banned = ("erase frp", "write seccfg", "fastboot ", "fastboot flash",
                  "fastboot erase", "adb shell", "hex edit", "patch auth",
                  "dd if=", "test point", "short the", "os.system", "os.popen",
                  "subprocess", "shutil.rmtree", "os.remove", "os.unlink")
        prod = "\n".join(p.read_text(encoding="utf-8", errors="replace")
                         for p in sorted(BASE.glob("*.py"))).lower()
        self.assertTrue(prod)
        for tok in banned:
            with self.subTest(tok=tok):
                self.assertNotIn(tok, prod, tok)

    def test_policy_boundary_unchanged_static(self):
        sah = (BASE / "sahulat.py").read_text(encoding="utf-8")
        kn = (BASE / "knowledge.py").read_text(encoding="utf-8")
        self.assertIn("Sahulat & Safe Service Policy", sah)
        self.assertIn("waisa ka waisa", sah)
        self.assertIn("HARD POLICY", sah)
        self.assertIn("Sahulat & Safe Service Policy", kn)
        self.assertIn("bypass", kn.lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
