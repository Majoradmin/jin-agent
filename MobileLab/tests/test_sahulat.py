"""PHASE 1B — Sahulat & Safe Service Toolkit: targeted stdlib unittest suite.

Scope note (C15): ye PHASE 1B feature ka targeted regression suite hai
(AC-12 … AC-17). Poore project ka full suite PHASE 8 ka deliverable hai —
is file ko us ka jhootha "green" claim samajhna galat hoga.

Guarantees:
  * koi live internet call nahi
  * production DB (`MobileLab/data/mobilelab.db`) kabhi touch nahi
  * temporary DB / server sirf `J:\\Ai Agent` ke andar (C10)
  * koi bypass instruction test mein generate ya expect nahi hoti
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import sys
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

BASE = pathlib.Path(__file__).resolve().parents[1]          # ...\MobileLab
ROOT = BASE.parent                                          # J:\Ai Agent
sys.path.insert(0, str(BASE))

import db            # noqa: E402
import knowledge     # noqa: E402
import sahulat       # noqa: E402
import server        # noqa: E402

VERBATIM_SHA256 = "1de53535942d8e7f1b31b3d9b55c9ae4854e85fd667e14e02f314a62010fd840"

# Real instruction tokens. The WORD "bypass" is intentionally absent: it appears
# in the refusal text itself, which is a boundary statement, not an instruction.
INSTRUCTION_TOKENS = (
    "erase frp", "write seccfg", "firehose", "exploit", "fastboot ",
    "adb shell", "hex edit", "patch auth", "dd if=", "step 1:",
    "qfil", "sp flash tool", "test point", "short the",
)

BANNED_QUERIES = (
    "FRP bypass kar do",
    "Huawei ID remove karna hai EMUI 16",
    "iCloud activation lock hatana hai",
    "Knox Guard / MDM unlock chahiye",
    "carrier network unlock code do",
    "IMEI clean karwana hai blacklist se",
    "erase frp partition with firehose",
    "mujhe bypass chahiye",
    "UnlockTool ya Chimera jaisa kaam karo",
)

FULL_PAYLOAD = {
    "technician": "Test Technician",
    "shop": "Local workspace",
    "customer": "Test Customer",
    "contact": "0300-0000000",
    "brand": "Huawei / Honor",
    "model": "Test Model",
    "device_id": "****1234",
    "issue_type": "Account recovery request",
    "route_id": "huawei",
    "notes": "Only official route.",
    "consent": True,
    "proof": list(sahulat.REQUIRED_IDS),
    "lang": "roman",
}

# One fixed throwaway DB inside the already-gitignored `MobileLab/data/`.
# The production DB is NEVER touched. State is reset with SQL (DELETE), not by
# deleting files: the sandbox safe-delete hook refuses Python file deletions.
TEST_DB = str(BASE / "data" / "_p1b_test.db")

_ORIG_DATA_DIR = db.DATA_DIR
_ORIG_DB_PATH = db.DB_PATH
_HTTPD: ThreadingHTTPServer | None = None
_PORT = 0


def _table_names() -> list[str]:
    return [r["name"] for r in db.rows(
        "SELECT name FROM sqlite_master WHERE type='table'")]


def setUpModule() -> None:
    """Point db at a throwaway local DB and start a loopback-only server."""
    global _HTTPD, _PORT
    db.DATA_DIR = str(BASE / "data")
    db.DB_PATH = TEST_DB
    db.init()
    db.execute("DELETE FROM cases")           # deterministic, no file deletion
    _HTTPD = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    _PORT = _HTTPD.server_address[1]
    threading.Thread(target=_HTTPD.serve_forever, daemon=True).start()


def tearDownModule() -> None:
    global _HTTPD
    if _HTTPD:
        _HTTPD.shutdown()
        _HTTPD.server_close()
        _HTTPD = None
    db.DATA_DIR = _ORIG_DATA_DIR
    db.DB_PATH = _ORIG_DB_PATH


def _http(path: str, payload: dict | None = None):
    url = f"http://127.0.0.1:{_PORT}{path}"
    if payload is None:
        req = urllib.request.Request(url, method="GET")
    else:
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


class TestRoutesAndPolicy(unittest.TestCase):
    def test_overview_shape(self):
        o = sahulat.overview()
        self.assertEqual(set(o), {"policy", "routes", "checklist", "consent_text",
                                  "letter_langs", "version"})
        self.assertEqual(len(o["routes"]), 6)
        self.assertEqual(len(o["checklist"]), 8)
        self.assertEqual(o["letter_langs"], ["roman", "english"])
        self.assertEqual(o["policy"]["name"], "Sahulat & Safe Service Policy")
        self.assertIn("sahulat", o["policy"]["lead"].lower())
        self.assertTrue(o["consent_text"].startswith("CUSTOMER CONSENT"))
        self.assertEqual(o["version"], sahulat.POLICY_ID)

    def test_route_ids_unique(self):
        ids = [r["id"] for r in sahulat.ROUTES]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(ids), set(sahulat.ROUTE_BY_ID))

    def test_routes_have_https_links(self):
        with_links = 0
        for r in sahulat.ROUTES:
            self.assertEqual({"id", "brand", "issue", "documents", "steps", "links", "note"},
                             set(r))
            for pair in r["links"]:
                self.assertEqual(len(pair), 2)
                self.assertTrue(pair[1].startswith("https://"), pair[1])
            if r["links"]:
                with_links += 1
        self.assertGreaterEqual(with_links, 5)

    def test_routes_no_bypass_steps(self):
        for r in sahulat.ROUTES:
            for step in r["steps"]:
                low = step.lower()
                for tok in INSTRUCTION_TOKENS:
                    self.assertNotIn(tok, low, (r["id"], step, tok))

    def test_checklist_required_set(self):
        self.assertEqual(sahulat.REQUIRED_IDS,
                         {"invoice", "owner_id", "consent", "device_id"})
        self.assertEqual(len(sahulat.CHECKLIST_IDS), 8)
        self.assertTrue(all(isinstance(c["required"], bool) for c in sahulat.CHECKLIST))

    def test_policy_boundary_unchanged(self):
        blob = json.dumps(sahulat.POLICY, ensure_ascii=False).lower()
        for kw in ("huawei id", "frp", "knox guard", "mdm", "carrier lock",
                   "activation lock", "write / erase", "server-side"):
            self.assertIn(kw, blob, kw)
        self.assertIn("waisa ka waisa", sahulat.POLICY["canonical"])
        self.assertIn("HARD POLICY", sahulat.POLICY["canonical"])
        kb = json.dumps(knowledge.BOUNDARY, ensure_ascii=False).lower()
        self.assertIn("bypass", kb)
        self.assertEqual(knowledge.BOUNDARY["policy_name"], "Sahulat & Safe Service Policy")
        # Out-of-scope list must still be the full original list, not shortened.
        self.assertGreaterEqual(len(knowledge.BOUNDARY["does_not"]), 4)


class TestCheckRequest(unittest.TestCase):
    def test_check_blocks_frp(self):
        r = sahulat.check_request("FRP unlock chahiye")
        self.assertTrue(r["blocked"])
        self.assertEqual(r["route_id"], "google")

    def test_check_blocks_huawei_id(self):
        r = sahulat.check_request("Huawei ID remove karo")
        self.assertTrue(r["blocked"])
        self.assertEqual(r["route_id"], "huawei")

    def test_check_blocks_icloud(self):
        r = sahulat.check_request("iCloud activation lock")
        self.assertTrue(r["blocked"])
        self.assertEqual(r["route_id"], "apple")

    def test_check_allows_firmware(self):
        r = sahulat.check_request("preloader aur rawprogram validate karna hai")
        self.assertFalse(r["blocked"])
        self.assertEqual(r["route_id"], "")
        self.assertTrue(r["safe_next_steps"])

    def test_check_all_blocked_have_official_links(self):
        for q in BANNED_QUERIES:
            r = sahulat.check_request(q)
            with self.subTest(q=q):
                self.assertTrue(r["blocked"])
                self.assertTrue(r["official_links"], "official link missing")
                self.assertTrue(all(u.startswith("https://") for _, u in r["official_links"]))
                self.assertTrue(r["reason"])
                self.assertTrue(r["refusal_line"])
                self.assertEqual(len(r["safe_next_steps"]), 4)
                self.assertEqual(r["policy"], sahulat.POLICY_ID)

    def test_check_output_has_no_bypass_steps(self):
        for q in BANNED_QUERIES:
            blob = json.dumps(sahulat.check_request(q), ensure_ascii=False).lower()
            with self.subTest(q=q):
                for tok in INSTRUCTION_TOKENS:
                    self.assertNotIn(tok, blob, (q, tok))

    def test_check_generic_no_fake_brand(self):
        r = sahulat.check_request("mujhe bypass chahiye")
        self.assertTrue(r["blocked"])
        self.assertEqual(r["route_id"], "")
        self.assertIn("brand", r["official_route"])

    def test_check_query_cap(self):
        r = sahulat.check_request("x" * 2000 + " FRP bypass")
        self.assertTrue(r["blocked"])
        r2 = sahulat.check_request("x" * 2000 + " firmware validate")
        self.assertFalse(r2["blocked"])


class TestValidationAndLetter(unittest.TestCase):
    def test_validate_case_unknown_proof_dropped(self):
        d, errors = sahulat.validate_case({**FULL_PAYLOAD, "proof": ["invoice", "owner_id",
                                                                     "consent", "device_id",
                                                                     "HACKED", "<script>"]})
        self.assertEqual(errors, [])
        self.assertEqual(d["proof"], sorted(sahulat.REQUIRED_IDS))
        self.assertTrue(d["proof_ok"])

    def test_validate_case_requires_consent(self):
        _, errors = sahulat.validate_case({**FULL_PAYLOAD, "consent": False})
        self.assertTrue(any("consent" in e.lower() for e in errors))

    def test_validate_case_requires_customer_and_model(self):
        _, errors = sahulat.validate_case({"customer": "", "model": "", "brand": "",
                                          "consent": True, "proof": []})
        self.assertGreaterEqual(len(errors), 2)

    def test_validate_case_unknown_route_reset(self):
        d, _ = sahulat.validate_case({**FULL_PAYLOAD, "route_id": "not_a_route"})
        self.assertEqual(d["route_id"], "")

    def test_validate_case_field_caps(self):
        d, _ = sahulat.validate_case({**FULL_PAYLOAD, "customer": "A" * 900,
                                     "notes": "N" * 3000, "device_id": "D" * 100})
        self.assertEqual(len(d["customer"]), 200)
        self.assertEqual(len(d["notes"]), 1000)
        self.assertEqual(len(d["device_id"]), 40)

    def test_letter_roman_shape(self):
        text = sahulat.make_letter(FULL_PAYLOAD, "roman")
        for part in ("SERVICE REQUEST", "Test Customer", "Test Model", "****1234",
                     "OFFICIAL", "Attach / hazir documents", "Purchase invoice"):
            self.assertIn(part, text)

    def test_letter_english_shape(self):
        text = sahulat.make_letter(FULL_PAYLOAD, "english")
        for part in ("OFFICIAL SERVICE REQUEST", "Test Customer", "Test Model",
                     "Supporting documents", "NOT requesting any unofficial"):
            self.assertIn(part, text)

    def test_letter_rejects_bad_lang(self):
        with self.assertRaisesRegex(ValueError, "sirf"):
            sahulat.make_letter(FULL_PAYLOAD, "french")

    def test_letter_requires_proof(self):
        with self.assertRaisesRegex(ValueError, "proof items"):
            sahulat.make_letter({**FULL_PAYLOAD, "proof": ["invoice"]}, "roman")

    def test_letter_requires_consent(self):
        with self.assertRaisesRegex(ValueError, "consent"):
            sahulat.make_letter({**FULL_PAYLOAD, "consent": False}, "roman")

    def test_letter_no_bypass_wording(self):
        for lang in sahulat.LETTER_LANGS:
            low = sahulat.make_letter(FULL_PAYLOAD, lang).lower()
            with self.subTest(lang=lang):
                for tok in INSTRUCTION_TOKENS:
                    self.assertNotIn(tok, low, (lang, tok))

    def test_case_no_unique(self):
        nums = {sahulat.make_case_no() for _ in range(100)}
        self.assertEqual(len(nums), 100)
        self.assertTrue(all(n.startswith("ML-") for n in nums))


class TestCaseRegister(unittest.TestCase):
    def test_add_case_temp_db(self):
        before = db.counts()["cases"]
        row = db.add_case({**FULL_PAYLOAD, "case_no": sahulat.make_case_no(),
                           "status": "ready", "proof_ok": True})
        self.assertTrue(row["case_no"].startswith("ML-"))
        self.assertEqual(row["customer"], "Test Customer")
        self.assertEqual(row["status"], "ready")
        self.assertEqual(sorted(row["proof"]), sorted(sahulat.REQUIRED_IDS))
        self.assertEqual(db.counts()["cases"], before + 1)

    def test_list_cases_bad_limit(self):
        if db.counts()["cases"] == 0:          # self-contained after the migration test
            db.add_case({**FULL_PAYLOAD, "case_no": sahulat.make_case_no()})
        for bad in ("abc", "", None, -5, 99999, 0):
            with self.subTest(limit=bad):
                items = db.list_cases(bad)
                self.assertGreaterEqual(len(items), 1)
                self.assertLessEqual(len(items), 500)
                self.assertTrue(all("case_no" in r for r in items))

    def test_case_no_unique_constraint(self):
        no = sahulat.make_case_no()
        db.add_case({**FULL_PAYLOAD, "case_no": no})
        with self.assertRaises(Exception):
            db.add_case({**FULL_PAYLOAD, "case_no": no})

    def test_existing_db_autocreates_cases(self):
        """Additive migration: a DB created from the PRE-1B schema gains `cases` on init()."""
        legacy = re.sub(
            r"CREATE TABLE IF NOT EXISTS cases \(.*?\);\s*"
            r"CREATE INDEX IF NOT EXISTS idx_cases_created ON cases\(created_at\);",
            "", db.SCHEMA, flags=re.S)
        self.assertNotIn("CREATE TABLE IF NOT EXISTS cases", legacy)
        # Simulate a pre-1B database in-place: only the new table/index are gone.
        db.execute("DROP INDEX IF EXISTS idx_cases_created")
        db.execute("DROP TABLE IF EXISTS cases")
        self.assertNotIn("cases", _table_names())
        db.init()
        self.assertIn("cases", _table_names())
        self.assertIsNotNone(db.counts()["cases"])


class TestServerAPI(unittest.TestCase):
    def test_status_has_policy_and_cases(self):
        code, body = _http("/api/status")
        self.assertEqual(code, 200)
        self.assertEqual(body["policy"], "Sahulat & Safe Service Policy")
        self.assertEqual(body["policy_id"], sahulat.POLICY_ID)
        self.assertIn("cases", body["counts"])

    def test_overview_endpoint(self):
        code, body = _http("/api/sahulat/overview")
        self.assertEqual(code, 200)
        self.assertEqual(len(body["routes"]), 6)

    def test_check_get_and_post(self):
        code, body = _http("/api/sahulat/check?q=FRP%20bypass")
        self.assertEqual(code, 200)
        self.assertTrue(body["blocked"])
        self.assertTrue(body["official_links"])
        code2, body2 = _http("/api/sahulat/check", {"q": "preloader validate"})
        self.assertEqual(code2, 200)
        self.assertFalse(body2["blocked"])

    def test_letter_endpoint_ok_and_400(self):
        code, body = _http("/api/sahulat/letter", FULL_PAYLOAD)
        self.assertEqual(code, 200)
        self.assertIn("SERVICE REQUEST", body["letter"])
        code2, body2 = _http("/api/sahulat/letter",
                             {**FULL_PAYLOAD, "proof": ["invoice"]})
        self.assertEqual(code2, 400)
        self.assertIn("proof", json.dumps(body2, ensure_ascii=False).lower())
        code3, _ = _http("/api/sahulat/letter", {**FULL_PAYLOAD, "lang": "french"})
        self.assertEqual(code3, 400)

    def test_case_endpoint_draft_with_letter_error(self):
        code, body = _http("/api/sahulat/case",
                           {**FULL_PAYLOAD, "customer": "Draft Customer",
                            "proof": ["invoice"]})
        self.assertEqual(code, 200)
        self.assertEqual(body["case"]["status"], "draft")
        self.assertEqual(body["letter"], "")
        self.assertIn("proof", body["letter_error"].lower())

    def test_case_endpoint_ready_and_list(self):
        code, body = _http("/api/sahulat/case",
                           {**FULL_PAYLOAD, "customer": "Ready Customer"})
        self.assertEqual(code, 200)
        self.assertEqual(body["case"]["status"], "ready")
        self.assertIn("SERVICE REQUEST", body["letter"])
        self.assertEqual(body["letter_error"], "")
        code2, listed = _http("/api/sahulat/cases?limit=oops")
        self.assertEqual(code2, 200)
        self.assertGreaterEqual(len(listed["items"]), 1)

    def test_case_endpoint_missing_consent_400(self):
        code, _ = _http("/api/sahulat/case", {**FULL_PAYLOAD, "consent": False})
        self.assertEqual(code, 400)

    def test_unknown_api_404(self):
        code, _ = _http("/api/sahulat/does-not-exist")
        self.assertEqual(code, 404)


class TestStaticAssets(unittest.TestCase):
    """8th-view UI wiring: served files, sections, element IDs, JS/CSS contract."""

    def _get_text(self, path: str) -> tuple[int, str]:
        req = urllib.request.Request(f"http://127.0.0.1:{_PORT}{path}", method="GET")
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.read().decode("utf-8", "replace")

    def test_index_and_assets_200(self):
        for p in ("/", "/index.html", "/app.js", "/style.css"):
            with self.subTest(path=p):
                code, body = self._get_text(p)
                self.assertEqual(code, 200)
                self.assertTrue(body.strip())

    def test_nine_views_and_nav(self):
        _, html = self._get_text("/index.html")
        self.assertEqual(html.count('class="view'), 9)
        self.assertEqual(html.count('id="view-'), 9)
        self.assertEqual(html.count('data-view="'), 9)
        self.assertIn('id="view-sahulat"', html)
        self.assertIn('data-view="sahulat"', html)
        self.assertIn('id="view-memory"', html)
        self.assertIn('data-view="memory"', html)

    def test_sahulat_element_ids(self):
        _, html = self._get_text("/index.html")
        for el in ("sahPolicyTitle", "sahPolicyLead", "sahCheckQ", "sahCheckOut",
                   "sahRoutes", "sahChecklist", "sahConsent", "sahConsentCopy",
                   "sahCustomer", "sahConsentChk", "sahLetterBtn", "sahCaseBtn",
                   "sahLetter", "sahCases", "sahBoundary", "sahFormMsg"):
            with self.subTest(id=el):
                self.assertIn(f'id="{el}"', html)

    def test_js_has_safe_url_and_sahulat_wiring(self):
        _, js = self._get_text("/app.js")
        for token in ("safe_url", "linkHtml", "loadSahulat", "renderSahulat",
                      "sahFormData", "sahSaveCase", "/api/sahulat/overview",
                      "/api/sahulat/letter", "/api/sahulat/case"):
            with self.subTest(token=token):
                self.assertIn(token, js)

    def test_css_has_sahulat_styles(self):
        _, css = self._get_text("/style.css")
        for token in (".sah-grid", ".sah-routes", ".sah-checklist", ".sah-letter",
                      "max-width:1050px"):
            with self.subTest(token=token):
                self.assertIn(token, css)


class TestVerbatimAndDocs(unittest.TestCase):
    def test_verbatim_hash(self):
        p = (ROOT / "agent.md").read_bytes()
        sep = p.find(b"\n---\n\n## Project Addendum")
        self.assertGreater(sep, 0)
        self.assertEqual(hashlib.sha256(p[:sep]).hexdigest(), VERBATIM_SHA256)
        self.assertNotIn(b"\r\n", p)
        self.assertNotIn(b"HARD POLICY", p[:sep])

    def test_docs_count_9(self):
        docs = sorted((BASE / "docs").glob("*.md"))
        self.assertEqual(len(docs), 9)
        expected = {"PRD.md", "architecture.md", "design.md", "rules.md", "phases.md",
                    "memory.md", "progress.md", "decisions.md", "changelog.md"}
        self.assertEqual({d.name for d in docs}, expected)

    def test_docs_boundary_present(self):
        for name in ("PRD.md", "rules.md", "decisions.md", "phases.md"):
            text = (BASE / "docs" / name).read_text(encoding="utf-8").lower()
            with self.subTest(doc=name):
                self.assertIn("sahulat & safe service policy", text)
                self.assertIn("bypass", text)

    def test_no_false_policy_removal_claim(self):
        text = (BASE / "docs" / "PRD.md").read_text(encoding="utf-8").lower()
        # "policy hata di" appears ONCE, quoted inside an Error-case rule that
        # says such a claim makes the review NOT READY. It is not an assertion.
        self.assertEqual(text.count("policy hata di"), 1)
        self.assertIn('"policy hata di" wala jhootha claim', text)
        self.assertIn("qaida bilkul barqarar", text)
        self.assertIn("koi chhoot", text)
        for bad in ("bypass allowed", "policy remove kar di gayi", "ab bypass mumkin hai",
                    "government employee exception", "sarkari mulazim ko chhoot"):
            self.assertNotIn(bad, text, bad)


if __name__ == "__main__":
    unittest.main(verbosity=2)
