# phases.md — 12 Phases, Gates aur PHASE REVIEW

**Date:** 2026-11-08 · **Updated:** 2026-11-09 · **Current phase:** PHASE 11 (Docs / Monitoring) — ✅ **READY / project complete** · **Next:** koi nahi (N7: naye kaam par phase-by-phase approval wapas)
**Rule:** koi phase skip nahi. Jin items ka is app par matlab nahi, unhein **"N/A + wajah"** likh kar gate pass kiya jaye ga. Har `READY` ke baad **user ki ijazat** zaroori; khud aage na barhna. C15: har phase mukammal, kuch incomplete na chhorhein. **C23 / D29** ki P3–P11 blanket auto-continue ijazat is run me consume ho chuki; N7 ke mutabiq agle naye kaam par asli phase-by-phase rule wapas lagu hoga. P5 / P10 `N/A` justified, **gates passed not skipped** (`D30` / `D31` / `C25`).

---

## 1. Phase matrix

| Phase | Objective | Deliverables | Dependencies | Verification gate | Risks | Effort |
|---|---|---|---|---|---|---|
| **P0 Discovery / Bootstrap** | governance ko source of truth banana | `agent.md` verbatim + addendum, 9 docs, `.gitignore`, local `git init` + `chore:` commit | user ki manzoori (mili) | 22-section read-back, 10 governance files + `.gitignore`, clean `git status`, conventional `git log -1` | R1 drift, R5 scan policy | chhota |
| **P1 Requirements / PRD** | PRD finalize | `PRD.md` poora, har feature ka AC block, route checklist | P0 READY | PRD vs `server.py` route-by-route; criterion "`min_score=x` → 400" darj | requirements invent hona | chhota |
| **P2 Architecture / Tech** | architecture + research | `architecture.md` final, `decisions.md` ADRs, **asli URLs + date checked** | P1 READY | doc vs `db.py`/`server.py`; koi banawati citation na ho | R2 banawati citations | darmiyana |
| **P3 Design / UX** | design system finalize — **DONE** | `design.md` final `READY`, tokens audit, a11y plan, O12 resolved | P2 READY | doc vs `style.css`/`index.html`; `test_a11y_markup` green | doc drift | chhota |
| **P4 Project setup** | launcher harden — **DONE** | `run.bat` Python ≥3.10 guard, zero installs | P3 READY | clean shell se `run.bat`, `python --version`, `PY_COMPILE_OK` | version mismatch | chhota |
| **P5 Auth / Authorization** | N/A justify — **DONE** (N/A justified, `D30`) | `phases.md` + `decisions.md` mein N/A + wajah (`D30`) | P4 READY | justification signed + `READY — N/A justified` | koi auth zaroori na ho | bohot chhota |
| **P6 Core features / CRUD** | core gaps band — **DONE** | QA #2 safe numeric parse, #11 minor bugs, `_err` stack trace hatana, CRUD audit, `db._session()` | P5 READY | bad-param checks + P8 suite; zero `500` | filter behavior badalna | darmiyana |
| **P7 Integrations** | research integrations document + offline — **DONE** | `research.py` `validate_url` / feed host allowlist / offline degradation, mocked tests, in-app KB | P6 READY | network mocked offline run | feed schema drift | darmiyana |
| **P8 Testing / QA** | suite banana — **DONE** | `tests\` 8 files / 101 tests, helpers, regression + characterization tests | P7 READY | `python -W error::ResourceWarning -m unittest discover -s tests -p "test_*.py" -v` → OK | DB/internet contamination | bara |
| **P9 Security / Perf / A11y** | 13 QA findings band — **DONE** | fixes + `safe_url`, realpath, XML hardening, SSRF, headers, pagination, a11y | P8 READY (red tests) | poora suite green + `run.bat` 8-view smoke + `node --check` + `py_compile` | R3 workflow tootna | bara |
| **P10 Deploy / CI-CD** | N/A justify — **DONE** (N/A justified, `D31`) | `decisions.md` mein local-only distribution (`D31`) | P9 READY | justification signed, koi remote na ho | — | bohot chhota |
| **P11 Docs / Monitoring** | final consistency — **DONE** | 9 docs final, in-app KB, local logging, final `status`, doc-vs-code audit, `D30`–`D34` | P10 READY | suite final green, docs checklist, `status` output | R4 doc drift | darmiyana |

## 2. N/A items (pehle se tay, gate pass — skip nahi)

| Phase | N/A item | Wajah |
|---|---|---|
| P5 | multi-user auth, sessions, password/token, tenant isolation, cross-origin CORS | `127.0.0.1` single-user offline app; koi account / cloud / doosra user nahi. **N/A justified `D30`:** loopback-only, single local user, no remote, no multi-tenant access, no session model; `http.server` production / LAN ke liye unsuitable (`D26` / `R13` / `O13`). Agar kabhi loopback se bahar expose ho to naya ADR + auth + TLS + framework review lazmi. **Gate passed, skip nahi** (`C25`). |
| P10 | cloud deploy, hosted CI/CD, containers, remote git | distribution `run.bat` aik Windows PC par; C7 = sirf local git, koi remote/cloud/credentials. **N/A justified `D31`:** zero installs / zero cloud / zero CI secrets, `git remote -v` empty (C7); reproducibility = stdlib-only + version guard + local git. Online distribution kabhi chahiye to pehle naya ADR. **Gate passed, skip nahi** (`C25`). |
| P3 | dark mode toggle, RTL layout | user ne light theme confirm kiya; Roman Urdu Latin script (`ur-PK-Latn`) hai |
| P2 | horizontal scaling / load balancer | single-user local tool; scale ka matlab sirf bade folders aur zyada feeds |

## 3. PHASE REVIEW template

```
PHASE REVIEW — PHASE N <name> — <date>
Confirmed / Assumptions / Open questions / Risks: ...
Deliverables: [x] paths
Verification evidence: <command> -> <result>
N/A items + justification: ... | none
Security review: ...
Documentation status: ...
Tests passed: ...  |  Tests failed: ...
Definition of done: met | not met
Gate: READY | NOT READY (reason + open items)
Next: PHASE N+1 (blocked if NOT READY)
```

`NOT READY` par khud agla phase shuru nahi; pehle exact baqi kaam batao. `READY` par user ki manzoori maango (jab tak "automatically continue" na kaha ho).

## 4. Per-task record (har task par)

`TASK` (name, purpose, scope, files to inspect, files to change, dependencies, acceptance criteria, risks) → `IMPLEMENTATION` (approach, smallest safe change, existing behavior preserve) → `VERIFICATION` (tests, type/lint/build, flows, failure + empty states, a11y, security) → `RESULT` (files changed, commands + results, limitations, next task).
Har task ke baad `memory.md`, `progress.md`, zarurat par `decisions.md` (ADR) aur `changelog.md` update.

## 5. Special commands

`next` gate check · `continue` sirf current approved task · `status` `progress.md` se phase/blockers/risks/next · `review` read-only, code na badlo · `research` sirf requested topic + sources · `explain` Roman Urdu, koi change nahi · `fix` reproduce → root cause → smallest fix → regression test → verify · `stop` foran ruk kar progress save.

## 6. QA → fix → regression test mapping

| QA # | Fix phase | Regression test | Status |
|---|---|---|---|
| 1 `llm_key` plaintext leak | P9 | `test_settings_no_secret_leak` | CLOSED |
| 2 invalid query params → 500 | P6 / P9 | `test_invalid_query_params_return_400`, `test_no_stacktrace_on_bad_input` | CLOSED |
| 3 `/api/reveal` prefix bypass + C6 | P9 | `test_reveal_rejects_sibling_prefix`, `test_scan_outside_denied_by_default`, `test_scan_outside_allowed_with_flag`, `test_scan_rejects_symlink_escape`, `test_scan_rejects_unc_path` | CLOSED |
| 4 unsafe feed URL | P9 | `test_javascript_url_rejected` | CLOSED |
| 5 XML DTD/entity | P9 | `test_dtd_entity_rejected` | CLOSED |
| 6 `llm_endpoint` SSRF | P9 | `test_llm_endpoint_rejects_internal` | CLOSED |
| 7 headers / body cap / path leak | P9 | `test_security_headers_present`, `test_body_size_cap_413`, `test_status_no_abs_db_path` | CLOSED |
| 8 f-string SQL identifier | P9 | `test_article_action_allowlist` | CLOSED |
| 9 a11y markup | P9 | `test_a11y_markup` | CLOSED |
| 10 perf | P9 | `test_save_package_single_txn`, `test_cache_bounded`, `test_packages_paginated` | CLOSED |
| 11 minor bugs / version guard | P4 / P6 | characterization tests | CLOSED |
| 12 swallowed LLM errors | P9 | `test_llm_failure_logged_not_swallowed` | CLOSED |
| 13 zero automated tests | P8 | poora suite | CLOSED |

**Status:** 13/13 closed — har finding ka named passing regression test aur asli code-fix mapping `decisions.md` `D32` / `D33` mein; `python -W error::ResourceWarning -m unittest discover -s tests -p "test_*.py" -v` → `Ran 101 tests in 77.621s — OK`, zero `ResourceWarning`. Koi bypass capability add nahi hui.

Baqi named cases: `test_scan_valid_mtk_package_happy_path`, `test_scan_valid_qcom_package_happy_path`, `test_unknown_api_returns_404`, `test_list_packages_empty_db`, `test_research_source_timeout_degrades_gracefully`, `test_duplicate_guid_is_idempotent`, `test_limit_clamped_to_5_200`, `test_min_score_boundary`, `test_file_count_boundary_4000`, `test_model_upsert`, `test_job_validation_failure`, `test_package_delete_not_found`.

## 7. Definition of Done (poora project)

- [x] `agent.md` verbatim + addendum barqarar — SHA-256 `1de53535942d8e7f1b31b3d9b55c9ae4854e85fd667e14e02f314a62010fd840` MATCH, size `37314`, `CRLF False`.
- [x] 9 docs consistent, Roman Urdu prose + English surface, Sahulat & Safe Service Policy encoded — docs `9/9`.
- [x] `PHASE REVIEW` gates sab `READY` — `phases.md` §8–§20 (P0 / P1 / P1B / P2 + P3–P11 ke 9 reviews); P5 / P10 `READY — N/A justified` (`D30` / `D31`).
- [x] Suite fully green bina live internet / production DB — `Ran 101 tests in 77.621s — OK`, zero `ResourceWarning`, `tests/` 8 files / 101 tests / 32 named tests, sab outbound mocked, SQL-only reset.
- [x] 13 QA findings band with passing tests — §6 `Status` column + `D32`.
- [x] Default scan workspace-restricted + explicit opt-in (C6) — `_authorize_path`, `MAX_FILES=4000` / `MAX_DEPTH=6`.
- [x] `run.bat` Python ≥3.10 guard.
- [x] Local git, koi remote nahi — `git remote -v` empty, `core.autocrlf=false`, `git diff --check` clean.
- [x] Skills/MCP `Open question` (O1) aur baqi deferred O2/O3/O4/O5/O6/O7/O8/O11/O13 — `D34`, koi jhootha resolution nahi.
- [x] Stdlib-only, local, light theme, koi cloud / paid / secret exposure nahi — `_mask_settings` (`llm_key` `***`), `PY_COMPILE_OK`, `NODE_CHECK_OK`.
- [x] `server._log` local-only logging, offline graceful degradation, in-app KB (`/api/knowledge` 200).
- [x] **Sab files `J:\Ai Agent` mein (C10)**.

---

## 8. PHASE REVIEW — PHASE 0 — Discovery / Bootstrap — 2026-11-08

- **Confirmed:** C1–C10 (khaas kar C9 Roman Urdu, C10 `J:\Ai Agent` root). **Assumptions:** A1–A7. **Open questions:** O1–O3 (critical nahi). **Risks:** R1 mitigated (byte-compare + `core.autocrlf=false`), R2 (P2 mein asli browsing due), R3 / R4 / R5 tracked.
- **Deliverables:** [x] `J:\Ai Agent\agent.md` · [x] 9 `MobileLab\docs\*.md` · [x] `J:\Ai Agent\.gitignore` · [x] local `.git` + conventional commit.
- **Verification evidence:** `agent.md` byte-identical `True` · 22 sections · sha256 `1de53535942d8e7f1b31b3d9b55c9ae4854e85fd667e14e02f314a62010fd840` · `CRLF present: False` · docs count `9` · staged files `38` · `git log -1` → `c25c3c6 chore: adopt agent.md governance + project docs` · `git status --short` → empty · `git remote -v` → empty · `git check-ignore` → 3/3.
- **N/A items + justification:** is phase par koi N/A nahi.
- **Security review:** secrets / runtime DB / logs / workspace-memory `.gitignore` se bahar; plaintext `llm_key` leak ka fix **P9 pending** (acknowledged, is phase ka scope nahi); koi remote / cloud / credentials nahi; Sahulat & Safe Service Policy 3 jagah encoded.
- **Documentation status:** 9/9 docs maujood, Roman Urdu, Sahulat & Safe Service Policy `rules.md` + `PRD.md` + `agent.md` addendum mein.
- **Tests passed:** verbatim read-back, 22-section count, Windows-path check, design-token / media-query / DB-schema source checks, toolchain, git checks. **Tests failed:** koi nahi. **Automated `unittest` suite:** P8 deliverable hai — abhi nahi bana, is ka koi jhootha claim nahi.
- **Definition of done:** **met**.
- **Gate:** **READY**
- **Next:** PHASE 1 (PRD finalize) — **user ki ijazat ke baghair shuru nahi**.

---

## 9. PHASE REVIEW — PHASE 1 — Requirements / PRD — 2026-11-08

- **Confirmed:** C1–C16 (naye C11 scoped internet · C12 Telegram Bot command/alert · C13 legal/authorized deep/dark web · C14 safe plan/report · C15 phase completeness · C16 provenance). User ne 3+1 chhote Roman Urdu sawalon mein ye pakke kiye; aakhri clarification me `Plan + report bhi` confirm hua.
- **Assumptions:** A1–A10. **Open questions:** O1–O10 (P1 ko nahi rokte; P2/P3/P7/P9/P11 me band honge). **Risks:** R1–R10; R2 P1 source register se mitigated, R6–R10 naye tracked.
- **Deliverables:** [x] `PRD.md` 1.1.0 (competitor map, future outlook, S1–S16, FR-01…FR-20, AC-01…AC-11, edge cases, metrics) · [x] `decisions.md` D13–D18 + classification · [x] `agent.md` addendum C1–C16 (verbatim block untouched) · [x] `architecture.md` §17 · [x] `design.md` §12 · [x] `rules.md` §14 · [x] `memory.md` / `progress.md` / `changelog.md` P1 update.
- **Verification evidence:** `agent.md` verbatim prefix sha256 `1de53535942d8e7f1b31b3d9b55c9ae4854e85fd667e14e02f314a62010fd840` → **MATCH** · `CRLF present: False` · Windows `J:\Ai Agent` count `9`, `J:/Ai Agent` count `0` · C11–C16 present `True` · docs count `9` · PRD checks `8/8 True` (`1.1.0`, S1–S16, `date checked`, FR-01…FR-20, AC-01…AC-11, C11–C16, Facts/Recommendations, Sahulat & Safe Service Policy) · `git diff --name-only` sirf `agent.md` + 9 docs · `git remote -v` empty · commit `94ae743 docs: finalize PHASE 1 PRD and decisions` · `git status --short` clean us commit ke baad.
- **N/A items + justification:** is phase par koi N/A nahi; P5/P10 apne apne gates par N/A + wajah ke sath aayenge.
- **Security review:** Sahulat & Safe Service Policy `PRD.md`, `rules.md`, `agent.md` mein barqarar. C13 legal research boundary, C14 policy gate, OWASP SSRF S16 aur O2/O4/O10 tracked. Koi token, credential, IMEI ya private data docs mein darj nahi. Koi code change nahi, is liye naya attack surface nahi.
- **Documentation status:** 9/9 docs maujood, Roman Urdu prose, C9/C10 barqarar; 16 sources ke URL + `date checked = 2026-11-08`; facts aur recommendations alag; low-authority claims exclude.
- **Tests passed:** verbatim byte/hash check, line-ending check, Windows-path check, docs count, PRD marker checks, Git diff/remote/status checks. **Tests failed:** koi nahi. **Automated `unittest` suite:** P8 deliverable hai — abhi nahi bana; is ka koi jhootha green claim nahi.
- **Definition of done:** **met** — PRD finalize, har feature ka AC block, source register, classification, ADRs aur docs sync mukammal; C15 ke mutabiq koi P1 item incomplete nahi chhora.
- **Gate:** **READY**
- **Next:** PHASE 2 (Architecture / Tech Stack + S1–S16 technology citations) — **user ki ijazat ke baghair shuru nahi**. Final review commit: `docs: record PHASE 1 verification and PHASE REVIEW`.

---

## 10. PHASE REVIEW — PHASE 1B — Sahulat & Safe Service Toolkit — 2026-11-08

> **Sub-phase note:** PHASE 1B user ke naye request (`HARD POLICY` → "easy policy", sahulat-first tooling) par PHASE 1 ke andar ek scoped addendum tha. 12-phase matrix badli nahi; P2 abhi bhi agla gate hai.

- **Confirmed:** C1–C19. Naye: **C17** policy reframe — boundary unchanged, koi chhoot nahi (D19) · **C18** Sahulat toolkit scope (D20/D21) · **C19** language split content Roman Urdu / surface English (D22). User ne `"Sab kuch upar wala (Behtar)"` manzoor kiya, jis mein `bypass wali line waisi hi rehti hai` shamil tha. User ne alag se kaha: *"information report plan sbb mjhy roman urdu mein chiye werna baki sbb for professional looking eng use kro"* → D22.
- **Assumptions:** A1–A11. **A11** sarkari mulazim hona koi technical/legal exception paida nahi karta; sirf documentation tooling.
- **Open questions:** O1–O8 · ~~**O9**~~ **RESOLVED (D21): 8th view** · O10 · **O11** case retention/export/deletion (P11) · **O12** in-app Roman Urdu chrome → English surface migration phase (P3/P11). Koi bhi P1B ko nahi rokta.
- **Risks:** R1–R12. **R11** (naam badalne ko boundary hatana samajhna) canonical note + `test_policy_boundary_unchanged` + unchanged out-of-scope list se mitigated. **R12** (C19 ko C9 ki mansookhi samajhna) D22 se clarify.
- **Deliverables:** [x] `MobileLab\sahulat.py` (new) · [x] `MobileLab\tests\test_sahulat.py` (new) · [x] `db.py` `cases` table + `add_case()` / `list_cases()` / `counts()` · [x] `server.py` 6 `/api/sahulat/*` routes + `VERSION 1.1.0` + `/api/status` policy/cases · [x] `knowledge.py` policy reframe · [x] `web\index.html` 8th view · [x] `web\app.js` `safe_url()` / `linkHtml()` / Sahulat state · [x] `web\style.css` `.sah-*` · [x] `PRD.md` 1.2.0 · [x] `decisions.md` D19–D22 + C17–C19 · [x] `agent.md` addendum §K/§L (verbatim untouched) · [x] `architecture.md` §18 · [x] `design.md` §13 · [x] `rules.md` §15–§16 · [x] `progress.md` / `memory.md` / `changelog.md` · [x] `phases.md` §10.
- **Verification evidence:**
  - `python -m py_compile db.py firmware.py research.py knowledge.py sahulat.py server.py` → `PY_COMPILE_OK`
  - `node --check web/app.js` → `NODE_CHECK_OK`
  - `python -m unittest discover -s tests -p "test_*.py" -v` → `Ran 47 tests in 1.845s` → **OK** (failures `0`, hook noise `0`)
  - `agent.md` verbatim prefix sha256 → `1de53535942d8e7f1b31b3d9b55c9ae4854e85fd667e14e02f314a62010fd840` **MATCH**; `CRLF present: False`; `HARD POLICY` in verbatim `False`
  - API smoke (loopback): `overview 200`, `cases 200`, `check GET/POST 200`, `letter 200/400`, `case 200/400`, `status 200`, unknown `404`; `status=policy` → `Sahulat & Safe Service Policy`, `counts.cases` present
  - Acceptance criteria: AC-12 (6 routes, sab links `https://`, steps me 0 bypass tokens) · AC-13 (9 banned queries par 100% official links, 0 instruction tokens) · AC-14 (4/4 required proof enforced, unknown ids dropped) · AC-15 (dono languages + 4 validation errors → `400`) · AC-16 (1 case round-trip, `limit` clamp, pre-1B DB auto-migrate) · AC-17 (canonical note, boundary list unchanged, hash MATCH, 9 docs)
  - Static assets `/`, `/index.html`, `/app.js`, `/style.css` → 200; `class="view` × 8, `id="view-` × 8, `data-view="` × 8, 27 `sah*` IDs
  - `git remote -v` → empty; `git status --short` → clean after P1B commit; `core.autocrlf=false`
- **N/A items + justification:** is sub-phase par koi N/A nahi. P5 (multi-user auth) aur P10 (cloud deploy) apne apne gates par "N/A + wajah" ke sath aayenge; yahan unhe skip nahi kiya gaya.
- **Security review:** boundary **unchanged** — koi bypass automation / step-by-step tareeqa / exploit / loader trick / partition write-erase command nahi; tests is par gate hain. Naye 6 endpoints input-validated, read-only ya local validated write; koi arbitrary URL fetch nahi. `safe_url()` se `javascript:` / `data:` reject (QA #4 partial fix). Letter `<pre>` me `textContent` (koi HTML injection). `cases` parameterized SQL; koi credential / full IMEI / document upload; `data/` gitignored. Koi naya port, cloud, dependency ya remote. **Baaki 12 QA findings abhi P6/P9 par pending** — is phase ne unhe chheda nahi, jhootha "sab fix" claim nahi.
- **Documentation status:** 9/9 docs maujood aur sync; Roman Urdu content + English headings/labels (C19). C17 canonical note `agent.md` §D, `PRD.md` out-of-scope, `rules.md` §4/§15, `decisions.md` D19, `knowledge.py`, `sahulat.py` me. `agent.md` verbatim block par koi edit nahi. PHASE 1B me koi naya web browse nahi — sirf P1 ke verified S1–S16 aur unhin ke andar ke official links reuse hue; koi naya unverified URL / citation nahi.
- **Tests passed:** 47/47 targeted (`test_sahulat.py`), py_compile, JS check, loopback API smoke, static asset checks, verbatim byte/hash, line endings, docs count, boundary/read-back checks, additive migration simulation. **Tests failed:** koi nahi (pehle 7 failures the — 5 test assumptions + 2 asli gaps; gaps code me fix kiye aur assumptions theek kiye, dobara 47/47 green). **Full automated project suite:** P8 deliverable hai; abhi nahi bana — koi jhootha green claim nahi.
- **Definition of done:** **met** — C15 ke mutabiq PHASE 1B ka koi item incomplete nahi chhora. Jo kaam baqi hai wo apne apne gates ka scheduled kaam hai (P2…P11), is sub-phase ka adhoora kaam nahi.
- **Gate:** **READY**
- **Next:** PHASE 2 (Architecture / Tech Stack + S1–S16 technology citations) — **user ki ijazat ke baghair shuru nahi**. Har report / plan / jawab Roman Urdu me (C19).

---

## 11. PHASE REVIEW — PHASE 2 — Architecture / Tech Stack — 2026-11-08

- **Confirmed:** C1–C22. Naye: **C20** verified Python 3.13 stdlib stack barqarar, koi dependency / framework / code migration nahi (D23) · **C21** modular replacement sirf documented adapter contracts se, P2 rewrite nahi karta (D24) · **C22** research provenance — 12 P2 + 16 P1 sources, `URL + date checked`, facts/assumptions/recommendations alag, version nuance aur Telegram partial re-check explicitly darj (D28). User ne `"ye phase 2 start"` se ijazat di; `"请继续执行任务"` aur continuation messages par kaam jari raha.
- **Assumptions:** A1–A15. Naye **A12** docs `3.13.18` vs runtime `3.13.14` patch equality ka dawa nahi · **A13** Telegram P1 `S9` facts abhi sahih, P2 ne sirf endpoint / limit / 24h directly dobara dekhe · **A14** 2–5 saal ka trend assumption (revenue / market-share fact nahi) · **A15** feed / Bot API / LLM schema drift ke liye adapter layer zaruri.
- **Open questions:** O1–O13. Naya **O13** LAN / Internet exposure ka framework / auth / TLS / deployment model (tab P5/P10 N/A dobara khulenge). Koi bhi P2 ko nahi rokta.
- **Risks:** R1–R16. **R2** banawati citations ab P1 `S1–S16` + P2 `P2-01…P2-12` se **mitigated**. Naye **R13** `http.server` ko LAN/Internet par expose karna (loopback boundary + D26) · **R14** patch drift (A12/D28) · **R15** XML / SSRF / CSP / path-authz / secrets P9 pending · **R16** Telegram P2 anchor re-check juzwi, P7 me full re-check.
- **Deliverables:** [x] `architecture.md` **2.0.0** (15 headings, §2.1 10 technology rows × 5 fields, §2.2 11 criteria, §19 `P2-01…P2-12` + `S1–S16`, §20 facts/assumptions/recommendations, §21 adapter contracts, §22 `AC-P2-01…AC-P2-11`) · [x] `decisions.md` D23–D28 + C20–C22 + A12–A15 + O13 + R12–R16 · [x] `agent.md` addendum §M (verbatim prefix untouched) · [x] `PRD.md` 1.3.0 + §16 architecture linkage · [x] `rules.md` §17 research-honesty rule · [x] `progress.md` / `memory.md` / `changelog.md` · [x] `phases.md` §11 · [x] workspace memory · [x] do local conventional `docs:` commits.
- **Verification evidence:**
  - `architecture.md` numbered-heading read-back → `headings 15 / 15`; §2.1 → `technology_rows 10`; §2.2 → `criteria 11 / 11`; source IDs → `P2-01…P2-12 = 12` aur `S1–S16 = 16`; `AC-P2-* = 11 / 11`; §20.1 / §20.2 / §20.3 present `True`; `date checked = 2026-11-08` × 35.
  - Stale-wording checks → `stale_research_due False` · `stale_6_tables False` · `stale_p2_pending False`. Doc ↔ code → `cases` in DB design `True`, `4 indexes True`, `/api/sahulat/` mentions `22`, `test_sahulat.py True`, `VERSION 1.1.0 True`.
  - `python -m py_compile db.py firmware.py research.py knowledge.py sahulat.py server.py` → `PY_COMPILE_OK` · `node --check web/app.js` → `NODE_CHECK_OK` · `python -m unittest discover -s tests -p "test_*.py"` → `Ran 47 tests in 2.059s` → **OK**; docs sync ke baad final re-run → `Ran 47 tests in 1.752s` → **OK**. `git diff --check` → `DIFF_CHECK_OK`.
  - `agent.md` verbatim prefix SHA-256 → `1de53535942d8e7f1b31b3d9b55c9ae4854e85fd667e14e02f314a62010fd840` **MATCH** · `32443 bytes` · `sep_index 17844` · `CRLF present: False` · docs `9 / 9`.
  - `git remote -v` → empty · `core.autocrlf` → `false` · `git status --short` → clean after P2 commits · commits `docs: finalize PHASE 2 architecture and tech stack` + `docs: record PHASE 2 verification and PHASE REVIEW`.
  - **Honesty note:** aik verification script ke apne regex ghalat the (`^## N. exact-heading$` ne parenthetical suffixes wale headings miss kiye → `10/15`; `S\d\d` ne `S1–S9` miss kiye → `7/16`). Asli headings/IDs print kar ke script dobara chalaya gaya → `15/15` aur `16/16`. Doc mein koi ghalti nahi thi; galat tool output ko result ke tor par darj nahi kiya gaya.
- **N/A items + justification:** **P2 horizontal scaling / load balancer** — single-user local tool, scale ka matlab sirf bade folders aur zyada feeds (§2). **P5 auth** aur **P10 deploy** apne apne gates par `N/A + wajah` ke sath aayenge; yahan skip nahi kiye gaye. P2 ka authentication / authorization / deployment architecture loopback-only shart ke sath §8 / §9 / §14 mein darj hai.
- **Security review:** koi code change nahi, is liye naya attack surface nahi. `http.server` official docs ka production warning, CRLF header-injection aur symlink caveat, XML security (Expat `expat_2.8.1`), parameterized SQL, OWASP SSRF allowlist / resolved-IP binding / redirects-off, aur MDN CSP sab `architecture.md` §19 / §20 mein verified facts ke tor par darj. **Baaki 12 QA findings P6/P9 par pending** — P2 ne fix hone ka dawa nahi kiya. Loopback `127.0.0.1` boundary barqarar; Sahulat & Safe Service Policy bilkul unchanged; koi token, credential, IMEI ya private data docs mein nahi.
- **Documentation status:** 9/9 docs maujood aur P2 par sync; Roman Urdu content + English headings/labels (C19 / D22). `PRD.md` 1.3.0 §16 architecture se linked; `decisions.md` D23–D28; `rules.md` §17 ne `D28` ka referenced honesty rule poora kiya; `agent.md` verbatim block par koi edit nahi. Har P2 source ka full URL + `date checked = 2026-11-08`; facts aur recommendations alag; Python docs `3.13.18` vs local `3.13.14` aur Telegram partial re-check explicitly darj; koi banawati citation nahi.
- **Tests passed:** architecture read-back checks, verbatim byte/hash, line-ending, docs count, 15 headings, 10 technology rows, 11 criteria, 12 P2 + 16 P1 sources, 11 acceptance criteria, `py_compile`, `node --check`, `47/47` targeted `unittest`, Git hygiene. **Tests failed:** koi nahi. **Full automated project suite:** P8 deliverable hai; 47 tests targeted regression hain — koi jhootha "poora suite green" claim nahi.
- **Definition of done:** **met** — C15 ke mutabiq P2 ka koi item incomplete nahi chhora. Jo kaam baqi hai wo apne apne gates ka scheduled kaam hai (P3…P11), is phase ka adhoora kaam nahi.
- **Gate:** **READY**
- **Next:** PHASE 3 (Design / UX — design system finalize, tokens audit, a11y plan, O12) — **user ki ijazat ke baghair shuru nahi**. Har report / plan / jawab Roman Urdu me (C19).

---

## 12. PHASE REVIEW — PHASE 3 — Design / UX — 2026-11-09

- **Status:** READY
- **Confirmed / Assumptions / Risks:** C1–C25 · A1–A15 · R4 (final doc-vs-code audit P11) · R11 / R12 clarified. C23 / D29 auto-continue active.
- **TASK:** P3 design system finalize — token audit, responsive breakpoints, states, a11y plan, `AC-P3-01…AC-P3-08`, O12 language decision. Documentation-only gate.
- **IMPLEMENTATION:** `design.md` 2.0.0 final; 20-token light palette audit, 8 `@media` blocks / 4 breakpoints, per-view loading / empty / error / success states, WCAG intent + tab/tabpanel plan, `lang` ADR. P9 code ne a11y + CSP + URL + English chrome deliver kiya.
- **VERIFICATION:** `test_a11y_markup` green — 8 views / 8 nav items / 8 `role="tabpanel"` / 27 `sah*` IDs / zero inline `<script>` / `lang="en"` / `aria-live` / `:focus-visible` / `prefers-reduced-motion`; `node --check web/app.js` → `NODE_CHECK_OK`; `agent.md` verbatim hash MATCH.
- **RESULT:** P3 `READY`, O12 resolved (`D34`), koi scope creep / bulk rewrite nahi; design tokens / breakpoints / states / a11y plan / AC blocks barqarar.
- **Deliverables:** [x] `docs/design.md` · [x] `docs/phases.md` §12 · [x] `web/index.html` / `web/style.css` / `web/app.js` (P9 code) · [x] `docs/decisions.md` D34.
- **N/A items + justification:** dark mode toggle + RTL layout — `phases.md` §2; user ne light theme confirm kiya, Roman Urdu Latin script (`ur-PK-Latn`). Gate pass, skip nahi.
- **Security review:** Sahulat & Safe Service Policy boundary **unchanged** — koi bypass automation, device write / erase / flash / IMEI operation ya lock-removal step nahi.
- **Documentation status:** 9/9 docs; `design.md` status final / `READY`.
- **Tests passed:** `test_a11y_markup`, `test_javascript_url_rejected`, `test_security_headers_present`. **Tests failed:** koi nahi.
- **Definition of done:** met · **Gate:** READY.
- **Open questions:** O12 resolved; baqi deferred `D34`.
- **Commit:** Final review commit: pending central commit.
- **Next:** PHASE 4 (Project setup) — C23 / D29 auto-continue.

---

## 13. PHASE REVIEW — PHASE 4 — Project setup — 2026-11-09

- **Status:** READY
- **Confirmed / Assumptions / Risks:** C7 / C20 / C23 · A3 / A12 · R14 patch drift (`docs 3.13.18` vs runtime `3.13.14`).
- **TASK:** launcher harden — `run.bat` Python `>=3.10` guard, zero installs, zero dependency.
- **IMPLEMENTATION:** `run.bat` me version guard; `python --version` check; baqi setup stdlib-only / local git rehne diya gaya, koi installer / service nahi.
- **VERIFICATION:** `python --version` → `Python 3.13.14`; `python -m py_compile db.py server.py firmware.py research.py sahulat.py knowledge.py tests/*.py` → `PY_COMPILE_OK`; `node --check web/app.js` → `NODE_CHECK_OK`; `test_run_bat_python_version_guard` green; `git remote -v` empty.
- **RESULT:** P4 `READY`; launcher zero-install local PC par chal jata hai; koi naya dependency nahi.
- **Deliverables:** [x] `MobileLab/run.bat` · [x] `tests/test_static_governance.py` · [x] `docs/phases.md` §13 · [x] `docs/PRD.md` §17.
- **N/A items + justification:** hosted CI/CD / installer — P10 N/A (`D31`); yahan dohraya nahi.
- **Security review:** Sahulat & Safe Service Policy boundary **unchanged** — koi bypass / device write / erase / flash / IMEI operation nahi; version guard sirf launcher hai.
- **Documentation status:** 9/9 docs; `architecture.md` 2.1.0 / `PRD.md` 1.4.0 sync.
- **Tests passed:** `test_run_bat_python_version_guard`, `py_compile`, `node --check`. **Tests failed:** koi nahi.
- **Definition of done:** met · **Gate:** READY.
- **Open questions:** O1 skills/MCP deferred (`D34`); koi P4 blocker nahi.
- **Commit:** Final review commit: pending central commit.
- **Next:** PHASE 5 (Auth / Authorization — N/A justified) — C23 / D29 auto-continue.

---

## 14. PHASE REVIEW — PHASE 5 — Auth / Authorization — 2026-11-09

- **Status:** READY — N/A justified (D30), gate passed
- **Confirmed / Assumptions / Risks:** C3 / C7 / C11 / C23 / C25 · D26 / D30 · R13 / O13.
- **TASK:** P5 gate par auth / authorization ka faisla — multi-user auth, sessions, password/token, tenant isolation, cross-origin CORS.
- **IMPLEMENTATION:** koi auth code nahi likha. `N/A + wajah` (`D30`) darj: loopback-only `127.0.0.1`, single local user, no remote, no multi-tenant access, no session model. `http.server` production / LAN ke liye unsuitable (`D26`, `R13`). `llm_key` masking `_mask_settings` authentication nahi, P9 secret fix hai.
- **VERIFICATION:** `/api/status` 200 loopback par (`version 1.1.0`, `policy_id SAHULAT-SAFE-SERVICE-v1`, `llm_key` masked `***`); `git remote -v` empty; suite `Ran 101 tests in 77.621s — OK`. Loopback se bahar koi listener nahi.
- **RESULT:** P5 `READY — N/A justified`, **gate passed, skip nahi**. Agar kabhi exposure chahiye to naya ADR + auth + TLS + framework review mandatory (`D30` / `O13`).
- **Deliverables:** [x] `docs/decisions.md` D30 · [x] `docs/phases.md` §14 / §2 · [x] `docs/architecture.md` §8 / §23 · [x] `docs/PRD.md` §17 · [x] `docs/progress.md` / `docs/memory.md`.
- **N/A items + justification:** multi-user auth / sessions / password-token / tenant isolation / CORS — upar wali `D30` wajah; `C25` register.
- **Security review:** Sahulat & Safe Service Policy boundary **unchanged** — koi bypass / device write / erase / flash / IMEI operation nahi; N/A sirf loopback shart par qabool hai.
- **Documentation status:** 9/9 docs; ADR `D30` + register `C25`.
- **Tests passed:** poora suite (N/A ka koi auth test zaroori nahi). **Tests failed:** koi nahi.
- **Definition of done:** met · **Gate:** READY — N/A justified.
- **Open questions:** O13 (exposure model) deferred (`D34`); tab P5 / P10 N/A dobara khulenge.
- **Commit:** Final review commit: pending central commit.
- **Next:** PHASE 6 (Core features / CRUD) — C23 / D29 auto-continue.

---

## 15. PHASE REVIEW — PHASE 6 — Core features / CRUD — 2026-11-09

- **Status:** READY
- **Confirmed / Assumptions / Risks:** C4 / C6 / C20 / C23 · D20 / D25 / D32 · R3 (mitigated with regression tests) / R4.
- **TASK:** core gaps band — QA #2 safe numeric parse, QA #11 minor bugs, `_err` stack trace hatana, CRUD audit, zero `500`.
- **IMPLEMENTATION:** `server.py` `_parse_num`, `_authorize_path` (`realpath` / `commonpath`), article action allowlist, pagination, `_prune_research_cache`, `_log`, `_mask_settings`; `db._session()` connection lifecycle (har connection close); `firmware.py` `_xml_precheck`, `MAX_FILES=4000` / `MAX_DEPTH=6`. Koi naya dependency / schema rewrite nahi.
- **VERIFICATION:** `Ran 101 tests in 77.621s — OK` (`-W error::ResourceWarning`, zero warning); `test_invalid_query_params_return_400`, `test_no_stacktrace_on_bad_input`, `test_article_action_allowlist`, `test_packages_paginated`, `test_save_package_single_txn` green; bad input par `400`, kabhi `500` / stack trace nahi.
- **RESULT:** P6 `READY`; core CRUD / scan / catalog offline kaam karte hain; koi workflow regression nahi (R3 mitigated).
- **Deliverables:** [x] `MobileLab/server.py` · [x] `MobileLab/db.py` · [x] `MobileLab/firmware.py` · [x] `docs/decisions.md` D32 / D33 · [x] `docs/phases.md` §15.
- **N/A items + justification:** is phase par koi N/A nahi.
- **Security review:** Sahulat & Safe Service Policy boundary **unchanged** — app sirf read / validate / plan / record; koi bypass / device write / erase / flash / IMEI operation nahi.
- **Documentation status:** 9/9 docs; `architecture.md` 2.1.0 doc-vs-code sync `§23`.
- **Tests passed:** upar wale + poora suite. **Tests failed:** koi nahi.
- **Definition of done:** met · **Gate:** READY.
- **Open questions:** O11 (case retention / export / deletion) deferred (`D34`).
- **Commit:** Final review commit: pending central commit.
- **Next:** PHASE 7 (Integrations) — C23 / D29 auto-continue.

---

## 16. PHASE REVIEW — PHASE 7 — Integrations — 2026-11-09

- **Status:** READY
- **Confirmed / Assumptions / Risks:** C11 / C12 / C13 / C14 / C16 / C23 · D13 / D27 / D34 · A15 / R16.
- **TASK:** research integrations document + offline — outbound allowlist, graceful degradation, mocked tests, in-app KB.
- **IMPLEMENTATION:** `research.py` `validate_url` + feed host allowlist, offline graceful degradation, LLM error logging + rule-based fallback; `knowledge.py` 5 naye glossary + 4 naye help entries + extended `SECURITY_NOTE`. Koi MTProto/TDLib/Telethon, koi historical public-channel scrape, koi arbitrary URL default ON nahi.
- **VERIFICATION:** `/api/knowledge` 200 (`boundary`, `glossary 18`, `help 14`, `official_routes 5`, `security_note`, `tool_arch 5`); `test_research_source_timeout_degrades_gracefully`, `test_llm_failure_logged_not_swallowed` green; sab outbound network mocked; suite `Ran 101 tests in 77.621s — OK`.
- **RESULT:** P7 `READY`; core features offline bhi chalte hain; research / Telegram offline par safe degrade; O10 common SSRF allowlist resolved (`D34`).
- **Deliverables:** [x] `MobileLab/research.py` · [x] `MobileLab/knowledge.py` · [x] `tests/test_research.py` · [x] `docs/decisions.md` D34 · [x] `docs/phases.md` §16.
- **N/A items + justification:** is phase par koi N/A nahi; P7 integrations stdlib `urllib.request` adapters ke documented contracts par (`D24` / `D27`).
- **Security review:** Sahulat & Safe Service Policy boundary **unchanged** — legal/authorized sources only, koi bypass / device write / erase / flash / IMEI operation, koi illegal source / malware nahi.
- **Documentation status:** 9/9 docs; `PRD.md` §17 / `architecture.md` §23 sync.
- **Tests passed:** upar wale + poora suite. **Tests failed:** koi nahi.
- **Definition of done:** met · **Gate:** READY.
- **Open questions:** O2 / O4 / O5 / O6 / O7 / O8 deferred (`D34`); koi jhootha resolution nahi.
- **Commit:** Final review commit: pending central commit.
- **Next:** PHASE 8 (Testing / QA) — C23 / D29 auto-continue.

---

## 17. PHASE REVIEW — PHASE 8 — Testing / QA — 2026-11-09

- **Status:** READY
- **Confirmed / Assumptions / Risks:** C4 / C23 / C24 · A3 · D33 · R3 / R15 (mitigated with regression tests).
- **TASK:** poora project `unittest` suite banana — 8 files, regression + characterization tests, harness.
- **IMPLEMENTATION:** stdlib `unittest`; `tests/` = **8 files** (`_harness.py`, `test_sahulat.py`, `test_security.py`, `test_firmware.py`, `test_db.py`, `test_research.py`, `test_server_api.py`, `test_static_governance.py`), **101 test methods**, `phases.md` §6 ke **32/32** named regression / characterization tests. `_harness.py` fixed throwaway `data/_p8_test.db` + in-process loopback server; reset sirf SQL `DELETE FROM`; sab outbound mocked; production DB / live internet kabhi touch nahi.
- **VERIFICATION:** `python -W error::ResourceWarning -m unittest discover -s tests -p "test_*.py" -v` → `Ran 101 tests in 77.621s — OK`, **zero `ResourceWarning`**; verbatim-hash gate (`test_agent_md_verbatim_prefix_integrity`) aur 9-doc gate (`test_docs_count_exactly_9`) suite ke andar; `PY_COMPILE_OK`, `NODE_CHECK_OK`.
- **RESULT:** P8 `READY`; 13 QA findings sab closed with passing tests; `db._session()` leak fix se zero `ResourceWarning`.
- **Deliverables:** [x] `MobileLab/tests/_harness.py` · [x] `MobileLab/tests/test_db.py` · [x] `MobileLab/tests/test_firmware.py` · [x] `MobileLab/tests/test_research.py` · [x] `MobileLab/tests/test_sahulat.py` · [x] `MobileLab/tests/test_security.py` · [x] `MobileLab/tests/test_server_api.py` · [x] `MobileLab/tests/test_static_governance.py` · [x] `docs/decisions.md` D33 · [x] `docs/phases.md` §17 / §6.
- **N/A items + justification:** browser E2E / `pytest` — stdlib-only policy (`D4`); is phase par koi N/A gate nahi.
- **Security review:** Sahulat & Safe Service Policy boundary **unchanged** — tests mein bhi koi bypass capability nahi (`test_no_bypass_flash_erase_commands_in_production`, `test_policy_boundary_unchanged_static`).
- **Documentation status:** 9/9 docs; `rules.md` §19 testing rules.
- **Tests passed:** 101/101. **Tests failed:** koi nahi.
- **Definition of done:** met · **Gate:** READY.
- **Open questions:** koi P8 blocker nahi; deferred questions `D34`.
- **Commit:** Final review commit: pending central commit.
- **Next:** PHASE 9 (Security / Perf / A11y) — C23 / D29 auto-continue.

---

## 18. PHASE REVIEW — PHASE 9 — Security / Perf / A11y — 2026-11-09

- **Status:** READY
- **Confirmed / Assumptions / Risks:** C23 / C24 · D26 / D32 / D34 · R3 / R11 / R15 (mitigated with regression tests).
- **TASK:** 13 QA findings band — headers, body cap, path authz, XML, SSRF, secret masking, pagination, a11y.
- **IMPLEMENTATION:** `server.py` `_mask_settings`, `_parse_num`, `_authorize_path`, `validate_llm_endpoint`, `MAX_BODY` 1 MiB, four security headers + CSP, article action allowlist, `_prune_research_cache`, pagination, `_log`; `firmware.py` `_xml_precheck`; `research.py` `validate_url` / feed host allowlist / LLM error logging; `web/app.js` `safe_url()` http/https allowlist; static UI `lang="en"`, 8 `role="tabpanel"`, `aria-live`, `:focus-visible`, `prefers-reduced-motion`. **Koi bypass capability add nahi hui.**
- **VERIFICATION:** 13/13 QA rows `phases.md` §6 `CLOSED`; `test_security_headers_present`, `test_body_size_cap_413`, `test_status_no_abs_db_path`, `test_llm_endpoint_rejects_internal`, `test_dtd_entity_rejected`, `test_javascript_url_rejected`, `test_a11y_markup`, `test_settings_no_secret_leak` green; `/index.html` / `/style.css` / `/app.js` 200 with `Content-Security-Policy`; suite `Ran 101 tests in 77.621s — OK`.
- **RESULT:** P9 `READY`; security / perf / a11y baseline closed (`D32`); O10 / O12 resolved (`D34`); R3 / R15 mitigated.
- **Deliverables:** [x] `MobileLab/server.py` · [x] `MobileLab/firmware.py` · [x] `MobileLab/research.py` · [x] `MobileLab/web/app.js` · [x] `MobileLab/web/index.html` / `web/style.css` · [x] `docs/decisions.md` D32 / D34 · [x] `docs/rules.md` §18 · [x] `docs/phases.md` §18 / §6.
- **N/A items + justification:** is phase par koi N/A nahi.
- **Security review:** Sahulat & Safe Service Policy boundary **unchanged** — koi Huawei ID / Google FRP / Samsung Knox / MDM / carrier / iCloud bypass, koi device write / erase / flash / IMEI operation; app sirf read / validate / plan / record.
- **Documentation status:** 9/9 docs; `architecture.md` §23 / `PRD.md` §17.
- **Tests passed:** 101/101. **Tests failed:** koi nahi.
- **Definition of done:** met · **Gate:** READY.
- **Open questions:** O2 / O3 / O11 deferred (`D34`) — at-rest encryption, log retention, case retention / export / deletion ka koi jhootha resolution nahi.
- **Commit:** Final review commit: pending central commit.
- **Next:** PHASE 10 (Deploy / CI-CD — N/A justified) — C23 / D29 auto-continue.

---

## 19. PHASE REVIEW — PHASE 10 — Deploy / CI-CD — 2026-11-09

- **Status:** READY — N/A justified (D31), gate passed
- **Confirmed / Assumptions / Risks:** C7 / C11 / C23 / C25 · D31 · R13 / O13.
- **TASK:** P10 gate par cloud deploy, hosted CI/CD, containers, remote git ka faisla.
- **IMPLEMENTATION:** koi pipeline / container / remote add nahi kiya. `N/A + wajah` (`D31`) darj: local-only distribution via `run.bat`, zero installs, zero cloud, zero CI secrets, `git remote -v` empty (C7); reproducibility = stdlib-only + version guard + local git. Online distribution kabhi chahiye to pehle naya ADR.
- **VERIFICATION:** `git remote -v` → empty; `git diff --check` → clean; `core.autocrlf=false`; `PY_COMPILE_OK`; `NODE_CHECK_OK`; suite `Ran 101 tests in 77.621s — OK`; docs `9/9`.
- **RESULT:** P10 `READY — N/A justified`, **gate passed, skip nahi**; koi deployment / breaking change / destructive DB migration / naya dependency nahi.
- **Deliverables:** [x] `docs/decisions.md` D31 · [x] `docs/phases.md` §19 / §2 · [x] `docs/architecture.md` §14 / §23 · [x] `docs/PRD.md` §17 · [x] `docs/changelog.md` / `docs/progress.md` / `docs/memory.md`.
- **N/A items + justification:** cloud deploy / hosted CI/CD / containers / remote git — upar wali `D31` wajah; `C25` register.
- **Security review:** Sahulat & Safe Service Policy boundary **unchanged** — koi bypass / device write / erase / flash / IMEI operation nahi; koi remote / credential / secret store nahi.
- **Documentation status:** 9/9 docs; ADR `D31` + register `C25`.
- **Tests passed:** poora suite (N/A ka koi deploy test zaroori nahi). **Tests failed:** koi nahi.
- **Definition of done:** met · **Gate:** READY — N/A justified.
- **Open questions:** O13 (exposure model) deferred (`D34`); tab P5 / P10 N/A dobara khulenge.
- **Commit:** Final review commit: pending central commit.
- **Next:** PHASE 11 (Docs / Monitoring) — C23 / D29 auto-continue.

---

## 20. PHASE REVIEW — PHASE 11 — Docs / Monitoring — 2026-11-09

- **Status:** READY
- **Confirmed / Assumptions / Risks:** C1–C25 · A1–A15 · D30–D34 · R4 (**final doc-vs-code audit completed P11**) / R1 / R11.
- **TASK:** final documentation + monitoring — 9 docs sync, in-app KB, local logging, final `status`, doc-vs-code audit, P5 / P10 N/A ADRs, 9 `PHASE REVIEW` sections.
- **IMPLEMENTATION:** `server._log` local-only logging (koi telemetry / off-site export); 9 docs final sync (`PRD.md` 1.4.0, `architecture.md` 2.1.0, `design.md` READY, `rules.md` §18 / §19, `phases.md` §1 / §2 / §6 / §7 / §12–§20, `decisions.md` D30–D34 / C24–C25, `progress.md`, `changelog.md`, `memory.md`). O3 / O11 / O2 / O4 / O5 / O6 / O7 / O8 / O1 / O13 honestly deferred; O10 / O12 resolved (`D34`). Koi naya URL / citation / commit hash invent nahi kiya gaya.
- **VERIFICATION:** `python -W error::ResourceWarning -m unittest discover -s tests -p "test_*.py" -v` → `Ran 101 tests in 77.621s — OK`, zero `ResourceWarning`; `PY_COMPILE_OK`; `NODE_CHECK_OK`; `agent.md` verbatim prefix SHA-256 `1de53535942d8e7f1b31b3d9b55c9ae4854e85fd667e14e02f314a62010fd840` MATCH, size `37314`, `CRLF False`; docs `9/9`; `git diff --check` clean; `git remote -v` empty; `core.autocrlf=false`; loopback smoke `/api/status` 200 + `/api/knowledge` 200 + `/index.html` / `/style.css` / `/app.js` 200 with CSP.
- **RESULT:** P11 `READY` — **project complete**. 12 gates sab `READY`, P5 / P10 N/A justified, 13/13 QA closed, 101 tests green, koi incomplete phase item nahi (C15).
- **Deliverables:** [x] `docs/PRD.md` · [x] `docs/architecture.md` · [x] `docs/design.md` · [x] `docs/rules.md` · [x] `docs/phases.md` · [x] `docs/decisions.md` · [x] `docs/progress.md` · [x] `docs/changelog.md` · [x] `docs/memory.md` · [x] `MobileLab/server.py` (`_log`).
- **N/A items + justification:** P5 / P10 N/A `D30` / `D31` se justified; is phase par koi naya N/A nahi.
- **Security review:** Sahulat & Safe Service Policy boundary **unchanged** — koi bypass automation / step-by-step tareeqa, koi device write / erase / flash / IMEI operation; app sirf read / validate / plan / record karta hai.
- **Documentation status:** 9/9 docs final, Roman Urdu prose + English surface, `date checked` conventions barqarar; koi banawati citation nahi.
- **Tests passed:** 101/101. **Tests failed:** koi nahi.
- **Definition of done:** met (§7 checked checklist) · **Gate:** READY.
- **Open questions:** O1 / O2 / O3 / O4 / O5 / O6 / O7 / O8 / O11 / O13 deferred with reason (`D34`); O10 / O12 resolved. Koi jhootha resolution nahi.
- **Commit:** Final review commit: pending central commit.
- **Next:** project complete; naye kaam par phase-by-phase approval wapas lagu (N7). Central coordinator final commit karega.
