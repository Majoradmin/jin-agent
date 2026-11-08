# progress.md — Current Progress

**Date:** 2026-11-08 · **Current phase:** `PHASE 1B — Sahulat & Safe Service Toolkit` — ✅ **READY**
**Current task:** koi nahi. PHASE 1B mukammal; PHASE 2 ke liye user ki ijazat ka intezar.
**Gate status:** `READY` — `PHASE REVIEW — PHASE 1B` `phases.md` §10 mein darj hai.
**Previous gates:** `PHASE 0` ✅ `READY` (§8) · `PHASE 1` ✅ `READY` (§9).
**Language:** content Roman Urdu, surface English (C19 / D22).

---

## 1. Task Board (PHASE 1B)

| Task | Status | Files | Verification |
|---|---|---|---|
| P1B-1 Existing code + docs ka pattern inspect | ✅ completed | `db.py`, `server.py`, `knowledge.py`, `web\*`, 9 docs | read-back; 7 views → 8 views ka scope pakka |
| P1B-2 `sahulat.py` — routes, checklist, consent, letters, refusal | ✅ completed | `MobileLab\sahulat.py` (new) | 6 routes, 8 checklist items (4 required), 2 letter languages, regex-only classifier |
| P1B-3 `cases` table + API endpoints | ✅ completed | `db.py`, `server.py` | additive `CREATE TABLE IF NOT EXISTS`; 6 naye `/api/sahulat/*` routes; `/api/status` me policy + cases count |
| P1B-4 8th view UI | ✅ completed | `web\index.html`, `web\app.js`, `web\style.css` | 8 `view` sections / 8 nav items; `safe_url()` + `linkHtml()`; `.sah-*` CSS; `VERSION` `1.1.0` |
| P1B-5 Policy reframe (name + tone only) | ✅ completed | `knowledge.py`, `agent.md` addendum, 9 docs | canonical note har policy section; `HARD POLICY` sirf canonical note / ADR me; boundary list unchanged |
| P1B-6 QA fixes found during verification | ✅ completed | `sahulat.py`, `PRD.md` | `make_letter()` → `validate_letter()`; `MAX_QUERY_CHARS=4000`; `GENERIC_LINKS` fallback; generic wording par `route_id=""` |
| P1B-7 Targeted test suite | ✅ completed | `MobileLab\tests\test_sahulat.py` (new) | **47/47 green**, stdlib `unittest`, koi live internet / production DB nahi |
| P1B-8 Docs sync + C19 + commit + PHASE REVIEW | ✅ completed | `progress.md`, `memory.md`, `changelog.md`, `phases.md`, `decisions.md`, `PRD.md`, `architecture.md`, `rules.md`, `agent.md` | §10 review `READY`; verbatim hash MATCH; local commit |

**Internal task records:** #14–#19 sab completed.

## 2. Completed Work (Full Project Context)

- **v1.0.0 app** (P0 se pehle): `server.py`, `db.py`, `firmware.py`, `research.py`, `knowledge.py`, `web\*`, `run.bat`, `samples\*`, `data\mobilelab.db`. MTK + QCOM scanners, research agent, local preview @ `127.0.0.1:8765`.
- **Read-only QA:** 13 findings; do high-risk source par dobara verify.
- **PHASE 0:** 12 adapted gates, classification, `agent.md` verbatim + addendum, 9 docs, `.gitignore`, local-only git, `PHASE REVIEW` `READY`.
- **PHASE 1:** 16 official / verified sources S1–S16 (`URL + date checked = 2026-11-08`), competitor map, `PRD.md` 1.1.0, C11–C16, D13–D18, `PHASE REVIEW` `READY`.
- **PHASE 1B:** user ne `HARD POLICY` ko "easy policy" banane ko kaha. Boundary **nahi** hatayi; sirf naam / andaaz `Sahulat & Safe Service Policy` kiya aur sahulat-first toolkit banaya. User ne `"Sab kuch upar wala (Behtar)"` manzoor kiya (`bypass wali line waisi hi rehti hai`). C17 / C18 / D19–D21.
- **PHASE 1B decisions:** C17 policy reframe (boundary unchanged) · C18 toolkit scope · **C19 language split** (D22): information / report / plan = Roman Urdu, baqi sab = English. O9 resolved, O11 + O12 naye open questions, R11 tracked.
- **PHASE 1B fixes:** letter ab 4/4 required proof + consent ke baghair `400` deta hai; incomplete proof par case `draft` + `letter_error`; classification window 4000 (padding evasion band); har blocked answer me official `https://` link guaranteed; generic bypass par jhootha brand diagnosis nahi.
- **Commits (local only, koi remote nahi):** `c25c3c6` · `d84aff4` · `94ae743` · `93f73dd` + PHASE 1B commits.

## 3. In-progress / Blocked

- **In-progress:** koi nahi — PHASE 1B ke saare 8 tasks mukammal.
- **Blocked:** koi nahi.
- **Code changes:** haan, PHASE 1B ek scoped code sub-phase tha (P1 sirf documentation tha). 16 modified + 2 new files.
- **Known deferred (apne apne gates par, P1B ka incomplete item nahi):** full project `unittest` suite (P8), 13 QA findings ke baqi fixes (P9), `run.bat` Python ≥3.10 guard (P4), Telegram / task-plan / provenance integrations (P7), UI chrome English migration O12 (P3/P11), case retention O11 (P11).
- **Waiting on:** user ki PHASE 2 (Architecture / Tech Stack) ki ijazat.

## 4. Tests / Verification Completed

| Check | Method | Result |
|---|---|---|
| Python syntax | `python -m py_compile` (6 modules + test file) | ✅ `PY_COMPILE_OK` |
| JavaScript syntax | `node --check web/app.js` | ✅ `NODE_CHECK_OK` |
| Targeted suite | `python -m unittest discover -s tests -p "test_*.py" -v` | ✅ **Ran 47 tests — OK** (1.845s) |
| Suite determinism | SQL `DELETE FROM cases` reset, koi file delete nahi | ✅ hook noise `0`, repeatable |
| API endpoints | in-process loopback `ThreadingHTTPServer` | ✅ overview / cases / check (GET+POST) / letter / case / status / 404 |
| Validation errors | letter + case payloads | ✅ missing consent / proof / bad lang → `400` JSON, kabhi `500` nahi |
| Draft + letter_error | incomplete proof case | ✅ `status=draft`, `letter=""`, `letter_error` present |
| Additive migration | pre-1B schema simulation (`DROP TABLE cases` → `db.init()`) | ✅ table auto-create |
| Static assets | `/`, `/index.html`, `/app.js`, `/style.css` | ✅ 200; 8 views / 8 nav; 27 `sah*` IDs |
| URL safety | `safe_url()` + `linkHtml()` | ✅ `http/https` only; QA #4 partial fix |
| Boundary unchanged | `test_policy_boundary_unchanged`, `test_routes_no_bypass_steps`, `test_check_output_has_no_bypass_steps`, `test_letter_no_bypass_wording` | ✅ 0 bypass instructions |
| Every refusal has a link | `test_check_all_blocked_have_official_links` (9 queries) | ✅ 100% official `https://` links |
| `agent.md` verbatim | SHA-256 prefix compare | ✅ `1de53535942d8e7f1b31b3d9b55c9ae4854e85fd667e14e02f314a62010fd840` MATCH |
| Line endings | raw bytes | ✅ `CRLF present: False` |
| Docs count | `glob('*.md')` | ✅ 9 |
| No remote | `git remote -v` | ✅ empty |
| Local git | conventional commits, `git status --short` | ✅ clean after P1B commit |

**Full automated project suite:** abhi **P8** ka deliverable hai. 47 tests sirf PHASE 1B ka targeted regression suite hain — inhe poora project suite keh kar jhootha green claim nahi kiya gaya.

## 5. Remaining Work

**Is phase:** koi nahi — `READY`.
**Agle phases (sab gates, user ki ijazat ke saath):** P2 Architecture + S1–S16 technology citations · P3 Design (O12) · P4 Setup (Python guard) · P5 Auth N/A · P6 Core fixes · P7 Integrations · P8 Full test suite · P9 Security/Perf/A11y (O2/O4/O10) · P10 Deploy N/A · P11 Docs/Monitoring (O3/O8/O11).

## 6. Known Risks

R1 verbatim drift (mitigated: hash + `core.autocrlf=false`) · R2 banawati citations (S1–S16 se mitigated; P2 final) · R3 security fixes workflow tod dein · R4 doc drift · R5 default scan restriction · R6 Telegram token/update loss · R7 illegal research/malware · R8 planner policy se bahar · R9 competitor claims outdated · R10 AI hallucination ko fact samajhna · R11 policy ke naam badalne ko "boundary hata di" samajhna (D19 canonical note + tests se mitigated) · R12 C19 language split ko C9 ki mansookhi samajhna (D22 ne clarify kiya).

## 7. Next Action

PHASE 1B `READY` hai. **Ab rukna hai** — user se PHASE 2 (Architecture / Tech Stack) ki ijazat maango. Khud aage na barho. `status` bole to `progress.md` + `phases.md` §10 parho; `review` bole to §10 ka PHASE REVIEW dikhao.
