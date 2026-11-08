# phases.md — 12 Phases, Gates aur PHASE REVIEW

**Date:** 2026-11-08 · **Current phase:** PHASE 0 (Bootstrap)
**Rule:** koi phase skip nahi. Jin items ka is app par matlab nahi, unhein **"N/A + wajah"** likh kar gate pass kiya jaye ga. Har `READY` ke baad **user ki ijazat** zaroori; khud aage na barhna.

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
| **P9 Security / Perf / A11y** | 13 QA findings band | fixes + `safe_url`, realpath, XML hardening, SSRF, headers, pagination, a11y | P8 READY (red tests) | poora suite green + `run.bat` 7-view smoke + `node --check` + `py_compile` | R3 workflow tootna | bara |
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

`agent.md` verbatim + addendum · 9 docs consistent, Roman Urdu, HARD POLICY encoded · 12 `PHASE REVIEW` sab READY · suite fully green bina live internet / production DB · 13 QA findings band with passing tests · default scan workspace-restricted + explicit opt-in · `run.bat` Python ≥3.10 guard · local git, koi remote nahi · skills/MCP `Open question` (O1) · stdlib-only, local, light theme, koi cloud / paid / secret exposure nahi · **sab files `J:\Ai Agent` mein (C10)**.

---

## 8. PHASE REVIEW — PHASE 0 — Discovery / Bootstrap — 2026-11-08

- **Confirmed:** C1–C10 (khaas kar C9 Roman Urdu, C10 `J:\Ai Agent` root). **Assumptions:** A1–A7. **Open questions:** O1–O3 (critical nahi). **Risks:** R1 mitigated (byte-compare + `core.autocrlf=false`), R2 (P2 mein asli browsing due), R3 / R4 / R5 tracked.
- **Deliverables:** [x] `J:\Ai Agent\agent.md` · [x] 9 `MobileLab\docs\*.md` · [x] `J:\Ai Agent\.gitignore` · [x] local `.git` + conventional commit.
- **Verification evidence:** `agent.md` byte-identical `True` · 22 sections · sha256 `1de53535942d8e7f1b31b3d9b55c9ae4854e85fd667e14e02f314a62010fd840` · `CRLF present: False` · docs count `9` · staged files `38` · `git log -1` → `c25c3c6 chore: adopt agent.md governance + project docs` · `git status --short` → empty · `git remote -v` → empty · `git check-ignore` → 3/3.
- **N/A items + justification:** is phase par koi N/A nahi.
- **Security review:** secrets / runtime DB / logs / workspace-memory `.gitignore` se bahar; plaintext `llm_key` leak ka fix **P9 pending** (acknowledged, is phase ka scope nahi); koi remote / cloud / credentials nahi; HARD POLICY 3 jagah encoded.
- **Documentation status:** 9/9 docs maujood, Roman Urdu, HARD POLICY `rules.md` + `PRD.md` + `agent.md` addendum mein.
- **Tests passed:** verbatim read-back, 22-section count, Windows-path check, design-token / media-query / DB-schema source checks, toolchain, git checks. **Tests failed:** koi nahi. **Automated `unittest` suite:** P8 deliverable hai — abhi nahi bana, is ka koi jhootha claim nahi.
- **Definition of done:** **met**.
- **Gate:** **READY**
- **Next:** PHASE 1 (PRD finalize) — **user ki ijazat ke baghair shuru nahi**.
