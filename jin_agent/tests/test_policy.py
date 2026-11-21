"""P13 / P17 - legal source register, SSRF guard, safe-service boundary."""

import os
import socket
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from urllib.parse import urlsplit

BASE = Path(__file__).resolve().parents[2]

from jin_agent import config, policy, store  # noqa: E402


def _fake_dns(mapping):
    """``socket.getaddrinfo`` ka offline mock — host -> IP list."""
    def fake(host, port, *args, **kwargs):
        ips = mapping.get(str(host).lower())
        if not ips:
            raise socket.gaierror(-2, "Name or service not known")
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))
                for ip in ips]
    return fake


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


# P2.1 - legal/public institutional sources (registry-only)
LEGAL_NEW = ("who", "un-news", "un-data", "eu-open-data", "eu-publications",
             "worldbank", "oecd", "cdc", "nasa", "ourworldindata", "pmc", "imf")


class TestLegalInstitutionalSources(unittest.TestCase):
    def _rows(self) -> dict:
        return {r["key"]: r for r in policy.register()}

    def test_new_legal_sources_reachable(self):
        rows = self._rows()
        for key in LEGAL_NEW:
            self.assertIn(key, rows)
            ok, reason = policy.check_url(rows[key]["url"])
            self.assertTrue(ok, f"{key}: {reason}")

    def test_new_legal_sources_registry_only(self):
        rows = self._rows()
        for key in LEGAL_NEW:
            self.assertFalse(rows[key]["auto"], key)
            self.assertIn("Registry-only", rows[key]["notes"], key)

    def test_new_hosts_in_allowlist(self):
        rows = self._rows()
        for key in LEGAL_NEW:
            host = urlsplit(rows[key]["url"]).hostname
            self.assertIn(host, policy.ALLOWED_HOSTS, key)

    def test_onion_fetch_still_blocked(self):
        ok, _ = policy.check_url("http://abcdefghijklmnop.onion/x")
        self.assertFalse(ok)

    def test_query_blocks_retired(self):
        # P47 — user ke hukm par query-level block patterns retire ho gaye.
        self.assertEqual(policy.BLOCK_PATTERNS, [])
        for text in ("FRP bypass kar do", "samsung frp unlock", "imei change",
                     "icloud lock remove", "mdm bypass", "blacklist clean",
                     "carrier unlock kar do"):
            self.assertEqual(policy.classify(text)["verdict"], "allowed", text)


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
        # P1-5: hostname resolve kar ke hi allow hoga. DNS offline mock.
        with mock.patch("socket.getaddrinfo",
                        _fake_dns({"llm.example.com": ["93.184.216.34"]})):
            self.assertTrue(policy.trusted_public_endpoint("https://llm.example.com/v1"))
        for url in ("http://127.0.0.1:11434/v1", "https://8.8.8.8/v1",
                    "https://foo.onion/v1", "http://llm.example.com/v1"):
            self.assertFalse(policy.trusted_public_endpoint(url))

    def test_custom_endpoint_resolves_internal_ip_rejected(self):
        # foo.example.com jaisa public naam jo internal IP par resolve ho.
        for ip in ("127.0.0.1", "169.254.169.254", "10.1.2.3", "192.168.0.5",
                   "169.254.0.1", "0.0.0.0", "224.0.0.1", "::1", "fc00::1"):
            with mock.patch("socket.getaddrinfo",
                            _fake_dns({"foo.example.com": [ip]})):
                self.assertFalse(
                    policy.trusted_public_endpoint("https://foo.example.com/v1"), ip)

    def test_custom_endpoint_public_resolution_allowed(self):
        with mock.patch("socket.getaddrinfo",
                        _fake_dns({"llm.example.com": ["93.184.216.34"]})):
            self.assertTrue(policy.trusted_public_endpoint("https://llm.example.com/v1"))

    def test_custom_endpoint_mixed_public_private_rejected(self):
        with mock.patch("socket.getaddrinfo",
                        _fake_dns({"llm.example.com": ["93.184.216.34", "10.0.0.2"]})):
            self.assertFalse(policy.trusted_public_endpoint("https://llm.example.com/v1"))

    def test_custom_endpoint_dns_failure_rejected(self):
        with mock.patch("socket.getaddrinfo",
                        _fake_dns({"nx.example.org": ["93.184.216.34"]})):
            self.assertFalse(policy.trusted_public_endpoint("https://llm.example.com/v1"))
        with mock.patch("socket.getaddrinfo",
                        side_effect=OSError("DNS down")):
            self.assertFalse(policy.trusted_public_endpoint("https://llm.example.com/v1"))


class TestSafeServiceBoundary(unittest.TestCase):
    def test_bypass_action_requests_allowed(self):
        # P47: ownership-control action queries bhi allowed (research/educational).
        for text in ("FRP bypass kar do", "erase frp partition", "FMI off karo",
                     "huawei id bypass", "imei change kar do", "mdm remove karo"):
            out = policy.classify(text)
            self.assertEqual(out["verdict"], "allowed", text)
            self.assertEqual(out["official_links"], [])
            self.assertEqual(out["safe_steps"], [])

    def test_legitimate_research_not_blocked(self):
        for text in ("Android security bulletin FRP research",
                     "iPhone activation lock policy explained",
                     "Qualcomm firehose EDL 9008"):
            self.assertEqual(policy.classify(text)["verdict"], "allowed", text)

    def test_classify_long_text_safe(self):
        # classify() pehle 4000 char par hai bounded; lamba text bhi mehfoos.
        out = policy.classify("news " * 3000 + "frp bypass")
        self.assertEqual(out["verdict"], "allowed")
        self.assertIn("verdict", out)

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


class TestDarkWebGate(unittest.TestCase):
    def test_wants_onion_true_for_dark_terms(self):
        for q in ("dark web markets", "deep web database", "onion links",
                  "tor hidden service", "ahmia"):
            self.assertTrue(policy.wants_onion(q), q)

    def test_wants_onion_false_for_normal(self):
        for q in ("android firmware update", "mediatek scatter file", ""):
            self.assertFalse(policy.wants_onion(q), q)

    def test_dark_query_gate_note_in_classify(self):
        gate = policy.classify("dark web onion search")
        self.assertEqual(gate["verdict"], "allowed")
        self.assertIn("never fetched", gate["note"])


if __name__ == "__main__":
    unittest.main()
