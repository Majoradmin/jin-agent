# phases.md — 12 Phases, Gates aur PHASE REVIEW

**Date:** 2026-11-08 · **Current phase:** PHASE 2 (Architecture / Tech Stack) — ✅ **READY** · **Next:** PHASE 3 (user ki ijazat ke baghair shuru nahi)
**Rule:** koi phase skip nahi. Jin items ka is app par matlab nahi, unhein **"N/A + wajah"** likh kar gate pass kiya jaye ga. Har `READY` ke baad **user ki ijazat** zaroori; khud aage na barhna. C15: har phase mukammal, kuch incomplete na chhorhein.

---

## 1. Phase matrix

| Phase | Objective | Deliverables | Dependencies | Verification gate | Risks | Effort |
|---|---|---|---|---|---|---|
| **P0 Discovery / Bootstrap** | governance ko source of truth banana | `agent.md` verbatim + addendum, 9 docs, `.gitignore`, local `git init` + `chore:` commit | user ki manzoori (mili) | 22-section read-back, 10 governance files + `.gitignore`, clean `git status`, conventional `git log -1` | R1 drift, R5 scan policy | chhota |
| **P1 Requirements / PRD** | PRD finalize | `PRD.md` poora, har feature ka AC block, route checklist | P0 READY | PRD vs `server.py` route-by-route; criterion "`min_score=x` → 400" darj | requirements invent hona | chhota |
| **P2 Architecture / Tech** | architecture + research | `architecture.md` final, `decisions.md` ADRs, **asli URLs + date checked** | P1 READY | doc vs `db.py`/`server.py`; koi banawati citation na ho | R2 banawati citations | darmiyana |
| **P3 Design / UX** | design system finalize | `design.md` final, tokens audit, a11y plan | P2 READY | doc vs `style.css`/`index.html` | doc drift | chhota |
| **P4 Project setup** | launcher harden | `run.bat` Python ≥3.10 guard, zero installs | P3 READY | clean shell se `run.bat`, `python --version`, `git status` | version mismatch | chhota |
| **P5 Auth / Authorization** | N/A justify | `phases.md` + `decisions.md` mein N/A + wajah | P4 READY | justification signed | koi auth zaroori na ho | bohot chhota |
| **P6 Core features / CRUD** | core gaps band | QA #2 safe numeric parse, #11 minor bugs, `_err` stack trace hatana, CRUD audit | P5 READY | bad-param checks + P8 suite; zero `500` | filter behavior badalna | darmiyana |
| **P7 Integrations** | research integrations document + offline | `research.py` docs, offline graceful degradation, mocked tests | P6 READY | network mocked offline run | feed schema drift | darmiyana |
| **P8 Testing / QA** | suite banana | `tests\` 8 files, helpers, regression + characterization tests | P7 READY | `python -m unittest discover -s tests -v` | DB/internet contamination | bara |
| **P9 Security / Perf / A11y** | 13 QA findings band | fixes + `safe_url`, realpath, XML hardening, SSRF, headers, pagination, a11y | P8 READY (red tests) | poora suite green + `run.bat` 8-view smoke + `node --check` + `py_compile` | R3 workflow tootna | bara |
| **P10 Deploy / CI-CD** | N/A justify | `decisions.md` mein local-only distribution | P9 READY | justification signed, koi remote na ho | — | bohot chhota |
| **P11 Docs / Monitoring** | final consistency | 9 docs final, in-app KB, local logging, final `status`, doc-vs-code audit | P10 READY | suite final green, docs checklist, `status` output | R4 doc drift | darmiyana |

## 2. N/A items (pehle se tay, gate pass — skip nahi)

| Phase | N/A item | Wajah |
|---|---|---|
| P5 | multi-user auth, sessions, password/token, tenant isolation, cross-origin CORS | `127.0.0.1` single-user offline app; koi account / cloud / doosra user nahi |
| P10 | cloud deploy, hosted CI/CD, containers, remote git | distribution `run.bat` aik Windows PC par; C7 = sirf local git, koi remote/cloud/credentials |
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

| QA # | Fix phase | Regression test |
|---|---|---|
| 1 `llm_key` plaintext leak | P9 | `test_settings_no_secret_leak` |
| 2 invalid query params → 500 | P6 / P9 | `test_invalid_query_params_return_400`, `test_no_stacktrace_on_bad_input` |
| 3 `/api/reveal` prefix bypass + C6 | P9 | `test_reveal_rejects_sibling_prefix`, `test_scan_outside_denied_by_default`, `test_scan_outside_allowed_with_flag`, `test_scan_rejects_symlink_escape`, `test_scan_rejects_unc_path` |
| 4 unsafe feed URL | P9 | `test_javascript_url_rejected` |
| 5 XML DTD/entity | P9 | `test_dtd_entity_rejected` |
| 6 `llm_endpoint` SSRF | P9 | `test_llm_endpoint_rejects_internal` |
| 7 headers / body cap / path leak | P9 | `test_security_headers_present`, `test_body_size_cap_413`, `test_status_no_abs_db_path` |
| 8 f-string SQL identifier | P9 | `test_article_action_allowlist` |
| 9 a11y markup | P9 | `test_a11y_markup` |
| 10 perf | P9 | `test_save_package_single_txn`, `test_cache_bounded`, `test_packages_paginated` |
| 11 minor bugs / version guard | P4 / P6 | characterization tests |
| 12 swallowed LLM errors | P9 | `test_llm_failure_logged_not_swallowed` |
| 13 zero automated tests | P8 | poora suite |

Baqi named cases: `test_scan_valid_mtk_package_happy_path`, `test_scan_valid_qcom_package_happy_path`, `test_unknown_api_returns_404`, `test_list_packages_empty_db`, `test_research_source_timeout_degrades_gracefully`, `test_duplicate_guid_is_idempotent`, `test_limit_clamped_to_5_200`, `test_min_score_boundary`, `test_file_count_boundary_4000`, `test_model_upsert`, `test_job_validation_failure`, `test_package_delete_not_found`.

## 7. Definition of Done (poora project)

`agent.md` verbatim + addendum · 9 docs consistent, Roman Urdu, Sahulat & Safe Service Policy encoded · 12 `PHASE REVIEW` sab READY · suite fully green bina live internet / production DB · 13 QA findings band with passing tests · default scan workspace-restricted + explicit opt-in · `run.bat` Python ≥3.10 guard · local git, koi remote nahi · skills/MCP `Open question` (O1) · stdlib-only, local, light theme, koi cloud / paid / secret exposure nahi · **sab files `J:\Ai Agent` mein (C10)**.

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
