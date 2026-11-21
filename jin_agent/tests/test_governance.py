"""P22 - governance, integrity and release invariants."""

import hashlib
import os
import re
import tempfile
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
PKG = BASE / "jin_agent"
os.environ["JIN_AGENT_DATA"] = tempfile.mkdtemp(prefix="jin-gov-")

from jin_agent import VERSION, adapters, policy, store  # noqa: E402

PREFIX_BYTES = 17844
PREFIX_SHA256 = "1de53535942d8e7f1b31b3d9b55c9ae4854e85fd667e14e02f314a62010fd840"


def setUpModule():
    os.environ["JIN_AGENT_DATA"] = tempfile.mkdtemp(prefix="jin-gov-")
    store.init_db()


class TestRelease(unittest.TestCase):
    def test_version(self):
        self.assertEqual(VERSION, "2.9.0")

    def test_required_files_exist(self):
        for rel in ("README.md", "PHASES.md", "run.bat", "__init__.py", "__main__.py",
                    "channels.py", "telegram_bot.py", "watchdog.py", "config.py", "util.py", "policy.py", "store.py", "adapters.py",
                    "normalizer.py", "verifier.py", "ranker.py", "planner.py", "llm.py",
                    "briefer.py", "evaluator.py", "scheduler.py", "alerts.py",
                    "logging_setup.py", "metrics.py", "ci_gate.py",
                    "canonical.py", "snapshots.py", "ratelimit.py",
                    "orchestrator.py", "server.py", "web/index.html", "web/app.js",
                    "web/style.css", "web/favicon.svg"):
            self.assertTrue((PKG / rel).is_file(), rel)

    def test_phase_reviews_all_ready(self):
        text = (PKG / "PHASES.md").read_text(encoding="utf-8")
        reviews = re.findall(r"\*\*PHASE REVIEW — PHASE (\d+): (READY|NOT READY)\*\*", text)
        # P28-P44 ke reviews PHASES.md me add hue — is liye expected count 32.
        self.assertEqual(len(reviews), 32)
        self.assertEqual([n for n, _ in reviews],
                         [str(n) for n in range(13, 45)])
        self.assertTrue(all(status == "READY" for _, status in reviews))
        self.assertIn("N/A Register", text)

    def test_all_four_assumptions_documented(self):
        text = (PKG / "PHASES.md").read_text(encoding="utf-8")
        for key in ("A-JIN-1", "A-JIN-2", "A-JIN-3", "A-JIN-4"):
            self.assertIn(key, text)


class TestIntegrity(unittest.TestCase):
    def test_agent_md_verbatim_prefix_unchanged(self):
        raw = (BASE / "agent.md").read_bytes()
        self.assertEqual(hashlib.sha256(raw[:PREFIX_BYTES]).hexdigest(), PREFIX_SHA256)
        self.assertNotIn(b"\r\n", raw[:PREFIX_BYTES])

    def test_mobilelab_untouched(self):
        src = (BASE / "MobileLab" / "server.py").read_text(encoding="utf-8")
        self.assertIn('VERSION = "1.4.0"', src)

    def test_gitignore_covers_agent_runtime(self):
        text = (BASE / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("jin_agent/data/", text)

    def test_no_forbidden_dependencies(self):
        banned = ("import requests", "import flask", "import fastapi", "import feedparser",
                  "import bs4", "import telethon", "import selenium", "import playwright",
                  "import torch", "import numpy", "import pandas")
        for path in PKG.glob("*.py"):
            text = path.read_text(encoding="utf-8")
            for token in banned:
                self.assertNotIn(token, text, f"{path.name}: {token}")

    def test_run_bat_has_no_pip_install(self):
        # A message saying "koi pip install zaroori nahi" is fine; an actual
        # install COMMAND is not.
        lines = [l.strip().lower() for l in
                 (PKG / "run.bat").read_text(encoding="utf-8").splitlines()]
        self.assertFalse(any(l.startswith("pip install") for l in lines))

    def test_no_hardcoded_secrets(self):
        for path in list(PKG.glob("*.py")) + [PKG / "web" / "app.js"]:
            text = path.read_text(encoding="utf-8")
            self.assertNotRegex(text, r"sk-[A-Za-z0-9]{16,}", path.name)
            self.assertNotRegex(text, r"bot\d{8,}:[A-Za-z0-9_-]{20,}", path.name)

    def test_light_theme(self):
        css = (PKG / "web" / "style.css").read_text(encoding="utf-8")
        self.assertIn("--bg: #f5f7fa", css)
        self.assertIn("prefers-reduced-motion", css)
        self.assertNotIn("prefers-color-scheme: dark", css)

    def test_no_inline_scripts(self):
        html = (PKG / "web" / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("<script", html.replace('<script src="/app.js"></script>', ""))
        self.assertNotIn("onclick=", html)


class TestBoundaries(unittest.TestCase):
    def test_loopback_and_csp(self):
        src = (PKG / "server.py").read_text(encoding="utf-8")
        self.assertIn('"127.0.0.1"', src)
        self.assertIn("Content-Security-Policy", src)
        self.assertNotIn('"0.0.0.0"', src)

    def test_adapter_and_register_counts(self):
        # P40: +12 keyless engine adapters (27 -> 39).
        # P41: +18 dork/extra adapters (39 -> 57).
        self.assertEqual(len(adapters.ADAPTERS), 57)
        # P2.1: 12 legal/public institutional sources (33 -> 45).
        # P39: +1 keyless Bing HTML search (45 -> 46).
        # P40: +46 key-free engine list (46 -> 92).
        # P41: +38 dork/extra engines (92 -> 130).
        # P43: +1 Lyzem Telegram-wide discovery engine (130 -> 131).
        self.assertEqual(len(policy.register()), 131)

    def test_onion_fetch_prohibited_in_code(self):
        self.assertFalse(policy.check_url("http://abcdefghijklmnop.onion/x")[0])
        src = (PKG / "adapters.py").read_text(encoding="utf-8")
        self.assertIn("LINKS ONLY", src)

    def test_policy_id(self):
        self.assertEqual(policy.POLICY_ID, "SAHULAT-SAFE-SERVICE-v1")

    def test_bypass_still_blocked(self):
        self.assertEqual(policy.classify("FRP bypass kar do")["verdict"], "blocked")
        self.assertEqual(policy.classify("iCloud activation lock bypass")["verdict"], "blocked")


if __name__ == "__main__":
    unittest.main()
