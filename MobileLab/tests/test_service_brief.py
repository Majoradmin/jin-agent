"""PHASE 12 - Service Brief & Official Status Checks (stdlib unittest, offline).

Covers the blank official status-check worksheet, the Apple GSX *request*
worksheet, the narrow status-check classifier exception, the problem-to-research
brief, identifier masking, source provenance, the new loopback API and the UI
wiring. Every outbound research call is mocked; the production DB is untouched.
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

import knowledge        # noqa: E402
import sahulat          # noqa: E402
import server           # noqa: E402
import service_brief as sb  # noqa: E402

_HTTPD = None
_PORT = 0

REQUIRED_PROOF = [c["id"] for c in sahulat.CHECKLIST if c["required"]]
FULL = {
    "customer": "Ali Khan", "contact": "0300-1234567", "model": "iPhone 13",
    "brand": "apple", "device_id": "123456789012345", "consent": True,
    "proof": REQUIRED_PROOF,
}
FULL_IMEI = "123456789012345"

FAKE_RESULT = {
    "items": [
        {"title": "Official security bulletin", "url": "https://example.org/news/item",
         "source": "TestFeed", "published": "2026-11-09", "khulasa": " Roman Urdu khulasa "},
        {"title": "Unsafe javascript link", "url": "javascript:alert(1)",
         "source": "TestFeed", "published": "", "khulasa": ""},
    ],
    "diagnostics": [{"source": "gnews", "ok": True, "count": 2}],
    "sources_ok": 1, "sources_failed": 0, "terms": ["iphone", "news"],
}
EMPTY_RESULT = {"items": [], "diagnostics": [], "sources_ok": 0, "sources_failed": 0,
                "terms": []}


def setUpModule():
    global _HTTPD, _PORT
    _HTTPD, _PORT = H.start()


def tearDownModule():
    global _HTTPD
    H.stop(_HTTPD)
    _HTTPD = None


class TestSourceRegister(unittest.TestCase):
    def test_new_and_legacy_sources_have_url_and_date_checked(self):
        ids = [s["id"] for s in sb.SOURCES]
        self.assertEqual(ids, ["S17", "S18", "S19", "S20", "S21", "S22", "S23", "S24"])
        for s in sb.SOURCES:
            with self.subTest(source=s["id"]):
                self.assertTrue(s["url"].startswith("https://"))
                self.assertRegex(s["date_checked"], r"^2026-11-\d{2}$")
                self.assertTrue(s["label"])
                self.assertTrue(s["purpose"])

    def test_dead_activation_lock_url_is_excluded_not_cited(self):
        urls = [s["url"] for s in sb.SOURCES]
        self.assertNotIn("https://www.icloud.com/activationlock/", urls)
        self.assertEqual(len(sb.EXCLUDED_SOURCES), 1)
        reason = sb.EXCLUDED_SOURCES[0]["reason"]
        self.assertIn(sb.DATE_CHECKED, reason)
        self.assertIn("excluded", reason.lower())

    def test_overview_metadata_is_complete(self):
        o = sb.overview()
        for key in ("policy", "policy_id", "version", "modes", "brands", "checks",
                    "check_ids", "sources", "excluded_sources", "date_checked",
                    "disclaimer", "gsx_disclaimer", "privacy_note", "gate_note",
                    "checklist", "consent_text"):
            with self.subTest(key=key):
                self.assertIn(key, o)
        self.assertFalse(o["gsx_is_report"])
        self.assertFalse(o["gsx_access_performed"])
        self.assertEqual(o["policy_id"], sahulat.POLICY_ID)

    def test_every_official_check_link_is_https_and_in_register(self):
        known = {s["url"] for s in sb.SOURCES}
        for brand, checks in sb.CHECKS.items():
            for c in checks:
                with self.subTest(brand=brand, check=c["id"]):
                    self.assertTrue(c["where"])
                    self.assertTrue(c["how"])
                    self.assertTrue(c["note"])
                    for label, url in c.get("links", []):
                        self.assertTrue(url.startswith("https://"), url)
                        self.assertIn(url, known, url)

    def test_no_mislabelled_source_links(self):
        # P12 QA: a label must never point at a different brand's page.
        for brand, checks in sb.CHECKS.items():
            for c in checks:
                for label, url in c.get("links", []):
                    if "Google" in label or "Android" in label:
                        self.assertTrue(("google" in url), (label, url))
                    if "Apple" in label or "GSX" in label or "Activation" in label:
                        self.assertTrue(("apple.com" in url or "locate.apple" in url),
                                        (label, url))


class TestIdentifierMasking(unittest.TestCase):
    def test_mask_identifier_never_echoes_full_imei(self):
        masked, full = sb.mask_identifier(FULL_IMEI)
        self.assertEqual(masked, "•••• 2345")
        self.assertTrue(full)
        self.assertNotIn(FULL_IMEI, masked)

    def test_mask_identifier_handles_empty_and_short_values(self):
        self.assertEqual(sb.mask_identifier(""), ("", False))
        self.assertEqual(sb.mask_identifier(None), ("", False))
        self.assertEqual(sb.mask_identifier("abcd"), ("", False))
        self.assertEqual(sb.mask_identifier("12"), ("•••• 12", False))

    def test_mask_identifier_caps_input_length(self):
        masked, _ = sb.mask_identifier("9" * 5000)
        self.assertEqual(len(masked), len("•••• 9999"))


class TestStatusWorksheet(unittest.TestCase):
    def test_status_report_is_a_blank_worksheet(self):
        r = sb.build_status_report(FULL)
        self.assertTrue(r["ok"])
        self.assertEqual(r["kind"], "status")
        self.assertIn("WORKSHEET", r["report"])
        self.assertIn("KHALI worksheet", r["report"])
        self.assertIn("Status (khali)", r["report"])
        self.assertIn("Result / reference no : ____________________", r["report"])
        self.assertNotIn("is_gsx_report", r)
        self.assertNotIn(FULL_IMEI, r["report"])
        self.assertTrue(r["full_identifier_supplied"])
        self.assertEqual(r["identifier_masked"], "•••• 2345")

    def test_status_report_never_asserts_a_device_result(self):
        r = sb.build_status_report(FULL)
        for banned in ("verified: ON", "status: unlocked", "MobileLab verified",
                       "blacklist: clean", "FMI: OFF"):
            self.assertNotIn(banned.lower(), r["report"].lower())

    def test_status_report_has_disclaimer_and_policy(self):
        r = sb.build_status_report(FULL)
        self.assertIn(sb.DISCLAIMER, r["report"])
        self.assertIn(sb.PRIVACY_NOTE, r["report"])
        self.assertEqual(r["policy"], sahulat.POLICY_ID)
        self.assertEqual(r["date_checked"], sb.DATE_CHECKED)

    def test_status_report_official_links_are_https_only(self):
        for brand in ("apple", "android", "other"):
            with self.subTest(brand=brand):
                r = sb.build_status_report({**FULL, "brand": brand})
                self.assertTrue(r["official_links"])
                for label, url in r["official_links"]:
                    self.assertTrue(url.startswith("https://"), url)
                    self.assertTrue(label)

    def test_status_report_checks_filter_is_bounded(self):
        r = sb.build_status_report({**FULL, "checks": ["warranty", "not-a-real-check"]})
        self.assertEqual([c["id"] for c in r["checks"]], ["warranty"])

    def test_status_report_requires_customer_and_consent(self):
        with self.assertRaises(ValueError) as ctx:
            sb.build_status_report({"brand": "apple"})
        self.assertIn("Customer", str(ctx.exception))
        self.assertIn("consent", str(ctx.exception))

    def test_status_report_proof_is_advisory_not_blocking(self):
        r = sb.build_status_report({**FULL, "proof": []})
        self.assertTrue(r["ok"])
        self.assertFalse(r["proof_ok"])
        self.assertIn("WARNING", r["report"])
        self.assertTrue(r["missing_proof"])

    def test_status_report_brand_falls_back_to_other(self):
        r = sb.build_status_report({**FULL, "brand": "unknown"})
        self.assertEqual(r["brand"], "other")


class TestGsxWorksheet(unittest.TestCase):
    def test_gsx_worksheet_is_not_a_gsx_report(self):
        g = sb.build_gsx_worksheet(FULL)
        self.assertTrue(g["ok"])
        self.assertEqual(g["kind"], "gsx")
        self.assertFalse(g["is_gsx_report"])
        self.assertFalse(g["gsx_access_performed"])
        self.assertFalse(g["credentials_stored"])
        self.assertIn("NOT A GSX REPORT", g["worksheet"])
        self.assertIn("GSX", g["eligibility_note"])

    def test_gsx_worksheet_has_only_blank_findings(self):
        g = sb.build_gsx_worksheet(FULL)
        text = g["worksheet"]
        findings = text.split("FINDINGS - SIRF", 1)[1].split("OFFICIAL LINKS", 1)[0]
        checked = 0
        for line in findings.splitlines():
            if " : " not in line:
                continue
            self.assertIn("____________________", line)   # no fabricated value
            checked += 1
        self.assertGreaterEqual(checked, 7)
        self.assertIn("Koi bhi upar wala field MobileLab ne KHUD nahi bhara", text)
        self.assertIn(sb.GSX_DISCLAIMER, text)
        self.assertIn("koi dawa nahi hai", text)

    def test_gsx_worksheet_requires_full_proof(self):
        with self.assertRaises(ValueError) as ctx:
            sb.build_gsx_worksheet({**FULL, "proof": ["invoice"]})
        self.assertIn("proof", str(ctx.exception).lower())

    def test_gsx_worksheet_never_stores_credentials(self):
        g = sb.build_gsx_worksheet({**FULL, "gsx_user": "admin", "gsx_password": "secret"})
        text = g["worksheet"].lower()
        self.assertNotIn("admin", text)
        self.assertNotIn("secret", text)
        self.assertNotIn("password", text)
        self.assertFalse(g["credentials_stored"])

    def test_gsx_worksheet_masks_identifier(self):
        g = sb.build_gsx_worksheet(FULL)
        self.assertNotIn(FULL_IMEI, g["worksheet"])
        self.assertEqual(g["identifier_masked"], "•••• 2345")

    def test_gsx_worksheet_lists_verified_sources(self):
        g = sb.build_gsx_worksheet(FULL)
        self.assertEqual(len(g["sources"]), 8)
        for s in g["sources"]:
            self.assertIn(s["url"], g["worksheet"])


class TestClassifier(unittest.TestCase):
    def test_user_status_request_is_allowed(self):
        r = sb.classify("apple iphone black list carrier lock unlock or fmi off on check krky report dea kry")
        self.assertFalse(r["blocked"])
        self.assertEqual(r["suggested_mode"], "status")
        self.assertEqual(r["suggested_brand"], "apple")
        self.assertTrue(r["status_check_exception"])

    def test_gsx_request_is_allowed_but_routes_to_worksheet(self):
        r = sb.classify("apple iphone ki gsx report b nikal dea kry")
        self.assertFalse(r["blocked"])
        self.assertEqual(r["suggested_mode"], "gsx")
        self.assertEqual(r["suggested_brand"], "apple")

    def test_android_imei_information_is_allowed(self):
        r = sb.classify("other android model ki imei information chahiye")
        self.assertFalse(r["blocked"])
        self.assertEqual(r["suggested_brand"], "android")
        self.assertEqual(r["suggested_mode"], "status")

    def test_problem_news_request_routes_to_brief(self):
        r = sb.classify("mere phone ka masla hai uss related news aur service batao")
        self.assertFalse(r["blocked"])
        self.assertEqual(r["suggested_mode"], "brief")
        self.assertTrue(r["terms"])

    def test_action_requests_are_all_blocked(self):
        blocked_phrases = (
            "iphone FMI off kar do",
            "FRP bypass kar do",
            "unlock code do",
            "imei change kar do",
            "blacklist clean karo",
            "huawei id remove kar do",
            "carrier unlock kar do",
            "activation lock status check",   # conservative: strict gate retained
            "erase frp ka tareeqa batao",
        )
        for phrase in blocked_phrases:
            with self.subTest(phrase=phrase):
                r = sb.classify(phrase)
                self.assertTrue(r["blocked"], phrase)
                self.assertEqual(r["suggested_mode"], "")
                self.assertFalse(r["status_check_exception"])
                self.assertTrue(r["official_links"], phrase)
                self.assertTrue(r["safe_next_steps"], phrase)
                self.assertTrue(r["refusal_line"], phrase)

    def test_blocked_answer_links_are_https_only(self):
        for phrase in ("FRP bypass kar do", "unlock code do", "iphone FMI off kar do"):
            with self.subTest(phrase=phrase):
                for label, url in sb.classify(phrase)["official_links"]:
                    self.assertTrue(str(url).startswith("https://"), url)

    def test_legacy_gate_still_blocks_generic_bypass_wording(self):
        r = sb.classify("mujhe bypass chahiye")
        self.assertTrue(r["blocked"])
        self.assertIn("SERVER", r["reason"])

    def test_terms_for_is_network_free_and_bounded(self):
        terms = sb.terms_for("iphone blacklist carrier status check news " + "khabar " * 200)
        self.assertTrue(terms)
        self.assertLessEqual(len(terms), 8)
        self.assertNotIn("bypass", terms)


class TestProblemBrief(unittest.TestCase):
    def test_facts_and_recommendations_are_separated(self):
        b = sb.build_problem_brief("iphone masla ki news chahiye", FAKE_RESULT)
        self.assertTrue(b["ok"])
        self.assertEqual(b["kind"], "brief")
        self.assertEqual(len(b["facts"]), 1)  # javascript: URL dropped
        for f in b["facts"]:
            self.assertEqual(f["fact_or_recommendation"], "fact")
            self.assertTrue(f["url"].startswith("https://"))
            self.assertEqual(f["date_checked"], sb.DATE_CHECKED)
        for r in b["recommendations"]:
            self.assertEqual(r["fact_or_recommendation"], "recommendation")
        self.assertIn("1) FACTS", b["brief"])
        self.assertIn("2) RECOMMENDATIONS", b["brief"])

    def test_offline_brief_invents_no_news(self):
        b = sb.build_problem_brief("mere phone ka masla hai", EMPTY_RESULT)
        self.assertTrue(b["offline"])
        self.assertEqual(b["facts"], [])
        self.assertIn("OFFLINE MODE", b["brief"])
        self.assertIn("koi banawati khabar nahi", b["brief"])

    def test_blocked_brief_has_official_links_and_no_facts(self):
        b = sb.build_problem_brief("FRP bypass kar do", FAKE_RESULT)
        self.assertTrue(b["blocked"])
        self.assertEqual(b["facts"], [])
        self.assertEqual(b["recommendations"], [])
        self.assertTrue(b["official_links"])
        self.assertIn("YE REQUEST BLOCK HAI", b["brief"])

    def test_brief_lists_sources_and_excluded_url(self):
        b = sb.build_problem_brief("iphone ki news", FAKE_RESULT)
        self.assertEqual(len(b["sources"]), 8)
        self.assertEqual(len(b["excluded_sources"]), 1)
        for s in b["sources"]:
            self.assertIn(s["url"], b["brief"])

    def test_brief_requires_query(self):
        with self.assertRaises(ValueError):
            sb.build_problem_brief("   ", EMPTY_RESULT)


class TestServiceBriefHTTP(unittest.TestCase):
    def setUp(self):
        H.reset_db()
        self.calls = []
        holder = self

        def fake(params, settings):
            holder.calls.append(dict(params))
            return dict(FAKE_RESULT)

        self.patch = mock.patch("research.research", side_effect=fake)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_overview_endpoint(self):
        code, hdrs, body = H.get_json(_PORT, "/api/service-brief/overview")
        self.assertEqual(code, 200)
        self.assertEqual(len(body["sources"]), 8)
        self.assertFalse(body["gsx_is_report"])
        self.assertIsNotNone(H.header(hdrs, "Content-Security-Policy"))

    def test_overview_has_csp_header(self):
        code, hdrs, _ = H.request(_PORT, "/api/service-brief/overview")
        self.assertEqual(code, 200)
        self.assertIsNotNone(H.header(hdrs, "Content-Security-Policy"))

    def test_classify_get_endpoint(self):
        code, _, body = H.get_json(
            _PORT, "/api/service-brief/classify?q=" +
            "iphone%20blacklist%20carrier%20status%20check%20report")
        self.assertEqual(code, 200)
        self.assertFalse(body["blocked"])
        self.assertEqual(body["suggested_mode"], "status")

    def test_classify_post_endpoint(self):
        code, _, body = H.post_json(_PORT, "/api/service-brief/classify",
                                    {"q": "FRP bypass kar do"})
        self.assertEqual(code, 200)
        self.assertTrue(body["blocked"])
        self.assertTrue(body["official_links"])

    def test_status_endpoint(self):
        code, _, body = H.post_json(_PORT, "/api/service-brief/status", FULL)
        self.assertEqual(code, 200)
        self.assertEqual(body["kind"], "status")
        self.assertIn("WORKSHEET", body["report"])
        self.assertNotIn(FULL_IMEI, json.dumps(body, ensure_ascii=False))

    def test_status_endpoint_validation_returns_400(self):
        code, _, body = H.post_json(_PORT, "/api/service-brief/status", {"brand": "apple"})
        self.assertEqual(code, 400)
        self.assertIn("error", body)
        self.assertNotIn("Traceback", json.dumps(body))

    def test_gsx_endpoint(self):
        code, _, body = H.post_json(_PORT, "/api/service-brief/gsx", FULL)
        self.assertEqual(code, 200)
        self.assertFalse(body["is_gsx_report"])
        self.assertFalse(body["gsx_access_performed"])
        self.assertFalse(body["credentials_stored"])

    def test_gsx_endpoint_requires_proof(self):
        code, _, body = H.post_json(_PORT, "/api/service-brief/gsx",
                                    {**FULL, "proof": []})
        self.assertEqual(code, 400)
        self.assertIn("error", body)

    def test_problem_endpoint_uses_mocked_research(self):
        code, _, body = H.post_json(_PORT, "/api/service-brief/problem",
                                    {"q": "iphone ki taaza khabarain", "live": True})
        self.assertEqual(code, 200)
        self.assertEqual(body["kind"], "brief")
        self.assertEqual(len(body["facts"]), 1)
        self.assertEqual(len(self.calls), 1)
        self.assertTrue(body["classification"]["terms"])

    def test_problem_endpoint_offline_degrades_gracefully(self):
        with mock.patch("research.research", return_value=dict(EMPTY_RESULT)):
            code, _, body = H.post_json(_PORT, "/api/service-brief/problem",
                                        {"q": "mere phone ka masla hai"})
        self.assertEqual(code, 200)
        self.assertTrue(body["offline"])
        self.assertEqual(body["facts"], [])
        self.assertIn("OFFLINE MODE", body["brief"])

    def test_problem_endpoint_never_searches_for_blocked_request(self):
        with mock.patch("research.research",
                        side_effect=AssertionError("blocked request must not search")) as m:
            code, _, body = H.post_json(_PORT, "/api/service-brief/problem",
                                        {"q": "FRP bypass kar do"})
        self.assertEqual(code, 200)
        self.assertTrue(body["blocked"])
        self.assertTrue(body["official_links"])
        m.assert_not_called()

    def test_problem_endpoint_live_false_skips_network(self):
        with mock.patch("research.research",
                        side_effect=AssertionError("live=false must not search")) as m:
            code, _, body = H.post_json(_PORT, "/api/service-brief/problem",
                                        {"q": "iphone ki news", "live": False})
        self.assertEqual(code, 200)
        self.assertTrue(body["offline"])
        m.assert_not_called()

    def test_problem_endpoint_requires_query(self):
        code, _, body = H.post_json(_PORT, "/api/service-brief/problem", {})
        self.assertEqual(code, 400)
        self.assertIn("error", body)

    def test_unknown_service_brief_api_returns_404(self):
        code, _, body = H.get_json(_PORT, "/api/service-brief/nope")
        self.assertEqual(code, 404)

    def test_status_endpoint_version_and_policy(self):
        code, _, body = H.get_json(_PORT, "/api/status")
        self.assertEqual(code, 200)
        self.assertEqual(body["version"], server.VERSION)
        self.assertEqual(body["policy_id"], sahulat.POLICY_ID)
        self.assertEqual(body["service_brief_sources"], 8)
        self.assertEqual(body["service_brief_version"], sb.VERSION)
        self.assertEqual(body["memory_version"], "1.0")


class TestStaticWiring(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (H.BASE / "web" / "index.html").read_text(encoding="utf-8")
        cls.js = (H.BASE / "web" / "app.js").read_text(encoding="utf-8")
        cls.css = (H.BASE / "web" / "style.css").read_text(encoding="utf-8")

    def test_index_has_service_brief_section(self):
        for el in ("svcCard", "svcAsk", "svcAskBtn", "svcAskOut", "svcMode",
                   "svcBrand", "svcCustomer", "svcModel", "svcId", "svcChecks",
                   "svcProof", "svcConsentChk", "svcLive", "svcRunBtn",
                   "svcCopyBtn", "svcOutput", "svcFacts", "svcSources",
                   "svcDisclaimer", "svcMsg"):
            with self.subTest(id=el):
                self.assertIn('id="' + el + '"', self.html)

    def test_view_invariant_is_preserved(self):
        # P13 added the 9th view ("Agent Memory"); the invariant still holds.
        self.assertEqual(self.html.count('class="view'), 9)
        self.assertEqual(self.html.count('id="view-'), 9)
        self.assertEqual(self.html.count('data-view="'), 9)
        self.assertEqual(self.html.count('role="tabpanel"'), 9)
        self.assertEqual(len(re.findall(r'id="sah[A-Za-z]', self.html)), 27)
        self.assertIn('lang="ur-PK-Latn"', self.html)
        self.assertIn('aria-live', self.html)

    def test_js_has_service_brief_wiring(self):
        for token in ("renderServiceBrief", "svcAnalyze", "svcRun", "svcShowResult",
                      "/api/service-brief/overview", "/api/service-brief/classify",
                      "/api/service-brief/status", "/api/service-brief/gsx",
                      "/api/service-brief/problem", "safe_url", "linkHtml"):
            with self.subTest(token=token):
                self.assertIn(token, self.js)

    def test_css_has_service_brief_styles(self):
        for token in (".svc-cols", ".svc-src", "#svcOutput"):
            self.assertIn(token, self.css)
        # P13's Agent Memory view added exactly one responsive rule.
        self.assertEqual(self.css.count("@media"), 10)

    def test_knowledge_base_documents_p12(self):
        text = " ".join(str(x) for x in (
            knowledge.GLOSSARY, knowledge.HELP, knowledge.BOUNDARY, knowledge.SECURITY_NOTE))
        self.assertIn("GSX", text)
        self.assertIn("DIRBS", text)
        self.assertIn("Masked identifier", text)
        self.assertIn("full-IMEI", text)

    def test_no_banned_device_commands_in_new_module(self):
        src = (H.BASE / "service_brief.py").read_text(encoding="utf-8").lower()
        for tok in ("fastboot flash", "fastboot erase", "adb shell", "dd if=",
                    "os.system", "os.popen", "subprocess", "erase frp", "write seccfg"):
            with self.subTest(tok=tok):
                self.assertNotIn(tok, src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
