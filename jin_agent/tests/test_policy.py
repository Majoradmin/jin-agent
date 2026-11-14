"""P13 / P17 - legal source register, SSRF guard, safe-service boundary."""

import os
import tempfile
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]

from jin_agent import config, policy, store  # noqa: E402


def setUpModule():
    # Per-module isolation: discovery imports ALL modules before running any,
    # so a module-level env assignment would be overwritten by the last import.
    os.environ["JIN_AGENT_DATA"] = tempfile.mkdtemp(prefix="jin-policy-")
    store.init_db()


class TestSourceRegister(unittest.TestCase):
    def test_register_has_provenance(self):
        reg = policy.register()
        self.assertGreaterEqual(len(reg), 20)
        for row in reg:
            self.assertEqual(row["date_checked"], "2026-11-14")
            self.assertTrue(row["url"].startswith("https://"))
            self.assertIn(row["tier"], {"T0", "T1", "T2", "T3", "T4"})
            self.assertGreaterEqual(row["trust"], 0.0)
            self.assertLessEqual(row["trust"], 1.0)

    def test_dark_web_rule_is_links_only(self):
        row = next(r for r in policy.register() if r["key"] == "ahmia")
        self.assertIn("never fetched", row["notes"])
        self.assertFalse(row["auto"])
        self.assertIn("links_only", policy.TOR_MODES)

    def test_na_adapters_have_written_justification(self):
        for key in ("patents", "virustotal", "urlscan"):
            row = next(r for r in policy.register() if r["key"] == key)
            self.assertFalse(row["auto"])
            self.assertIn("N/A", row["notes"])

    def test_no_illegal_source_categories(self):
        blob = " ".join(r["notes"].lower() + " " + r["name"].lower()
                        for r in policy.register())
        for banned in ("stolen credential", "marketplace", "credential dump", "malware sample"):
            self.assertNotIn(banned, blob)


class TestURLGuard(unittest.TestCase):
    def test_allows_registered_public_host(self):
        ok, reason = policy.check_url("https://news.google.com/rss/search?q=x")
        self.assertTrue(ok, reason)

    def test_blocks_loopback_and_ip_literals(self):
        for url in ("http://127.0.0.1:9/x", "http://localhost/x", "http://[::1]/x",
                    "http://10.0.0.1/x", "http://192.168.1.5/x",
                    "http://169.254.169.254/latest", "https://8.8.8.8/x"):
            self.assertFalse(policy.check_url(url)[0], url)

    def test_blocks_internal_and_onion(self):
        for url in ("http://metadata.google.internal/x", "https://foo.local/x",
                    "http://abcdefghijklmnop.onion/x", "https://evil.example.com/x"):
            self.assertFalse(policy.check_url(url)[0], url)

    def test_blocks_credentials_and_ports_and_schemes(self):
        for url in ("https://user:pass@api.github.com/x",
                    "https://api.github.com:8443/x", "file:///etc/passwd",
                    "ftp://api.github.com/x"):
            self.assertFalse(policy.check_url(url)[0], url)

    def test_custom_endpoint_check(self):
        self.assertTrue(policy.trusted_public_endpoint("https://llm.example.com/v1"))
        for url in ("http://127.0.0.1:11434/v1", "https://8.8.8.8/v1",
                    "https://foo.onion/v1", "http://llm.example.com/v1"):
            self.assertFalse(policy.trusted_public_endpoint(url))


class TestSafeServiceBoundary(unittest.TestCase):
    def test_bypass_action_requests_blocked(self):
        for text in ("FRP bypass kar do", "erase frp partition", "FMI off karo",
                     "huawei id bypass", "imei change kar do", "mdm remove karo"):
            out = policy.classify(text)
            self.assertEqual(out["verdict"], "blocked", text)
            self.assertTrue(out["official_links"][0].startswith("https://"))
            self.assertTrue(out["safe_steps"])
            self.assertEqual(out["reason"], policy.BLOCK_REASON)

    def test_legitimate_research_not_blocked(self):
        for text in ("Android security bulletin FRP research",
                     "iPhone activation lock policy explained",
                     "Qualcomm firehose EDL 9008"):
            self.assertEqual(policy.classify(text)["verdict"], "allowed", text)

    def test_banned_phrase_survives_padding_inside_window(self):
        # classify() scans a bounded 4000-char window; orchestrator caps the
        # query at the same bound. Padding inside that window cannot hide it.
        out = policy.classify("news " * 300 + "frp bypass")
        self.assertEqual(out["verdict"], "blocked")
        self.assertEqual(policy.classify("frp bypass")["verdict"], "blocked")

    def test_educational_deep_web_note(self):
        out = policy.classify("legal dark web onion research")
        self.assertEqual(out["verdict"], "allowed")
        self.assertIn("never fetched", out["note"])

    def test_trust_labels(self):
        self.assertEqual(policy.trust_label(1.0), "Official")
        self.assertEqual(policy.trust_label(0.85), "Verified")
        self.assertEqual(policy.trust_label(0.65), "Reported")
        self.assertEqual(policy.trust_label(0.45), "Unverified")
        self.assertEqual(policy.trust_label(0.1), "Rumor")


class TestConfig(unittest.TestCase):
    def test_defaults_include_documented_assumptions(self):
        cfg = config.load()
        self.assertEqual(cfg["tor_mode"], "links_only")
        self.assertEqual(cfg["llm"]["provider"], "off")
        self.assertEqual(len(cfg["topics"]), 12)
        self.assertEqual(len(cfg["assumptions"]), 4)

    def test_public_masks_secrets(self):
        out = config.public({"llm": {"key": "sk-abcdef123456"},
                             "telegram_bot_token": "123456:ABCDEF"})
        self.assertEqual(out["llm"]["key"], "***")
        self.assertEqual(out["telegram_bot_token"], "***")

    def test_save_merges_and_ignores_masked_sentinel(self):
        config.save({"tor_mode": "off", "llm": {"provider": "ollama", "model": "qwen2.5:7b"}})
        config.save({"llm": {"key": "***"}})
        cfg = config.load()
        self.assertEqual(cfg["tor_mode"], "off")
        self.assertEqual(cfg["llm"]["model"], "qwen2.5:7b")
        self.assertEqual(cfg["llm"]["key"], "")
        config.save({"tor_mode": "links_only", "llm": {"provider": "off", "model": "", "key": ""}})


if __name__ == "__main__":
    unittest.main()
