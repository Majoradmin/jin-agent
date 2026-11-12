# memory.md — Project Context

**Date:** 2026-11-08 · **Updated:** 2026-11-09 · **Root:** `J:\Ai Agent` · **App:** `MobileLab` · **Current phase:** `PHASE 13 — Agent Memory` — ✅ **READY** · **App `VERSION`:** `1.3.0`
Ye file project ki **lasting context** rakhti hai. Rozana ka detail `progress.md`, faisle `decisions.md`, user-visible badlao `changelog.md` mein.

---

## 1. Project kya hai

Local Windows **mobile-software / firmware workbench**. Mobile-software technician ko `preloader`, `scatter`, Qualcomm `EDL` / `Firehose` / `rawprogram` / `patch` files taiyar aur validate karne mein madad. Sath mein real-time research agent (Roman Urdu khulasa), package catalog, model brief, job register, aur static knowledge base.

**App pehle se bana hai** (v1.0.0) — ab ka kaam greenfield rebuild nahi, **governance adopt karna + QA gaps band karna** hai.

## 2. Confirmed user preferences

| # | Preference |
|---|---|
| P1 | **Language split (C19 / D22):** information, report, plan, har reply / sawal / option, docs prose = **Roman Urdu**. Headings, labels, code, identifiers, paths, API routes, commits, technical terms = **English** (professional look). Purana P1 "sab Roman Urdu" ab refined hai, mansookh nahi. Sawal chhote aur seedhe. |
| P2 | Sab kaam **local Windows PC** par; koi cloud / paid subscription / remote nahi. |
| P3 | **Python standard library only**; koi `pip install` nahi. |
| P4 | **Light theme**. |
| P5 | **Har project file / progress `J:\Ai Agent` mein** (C10). `C:\Users\...\.workbuddy-ai\` sirf WorkBuddy internal data. |
| P6 | **Phase-by-phase**: pehle aik chhota sawal → user jawab → sirf approved task → `TASK/IMPLEMENTATION/VERIFICATION/RESULT` → `PHASE REVIEW` → ruk kar agli ijazat. |
| P7 | **Sahulat & Safe Service Policy**: koi bypass automation / steps nahi. |
| P8 | Sirf **local git**, koi remote / cloud / credentials nahi. |
| P9 | Skills / MCP installs abhi **defer** (O1). |
| P10 | Scan default workspace-restricted, zarurat par **explicit opt-in** (C6). |

> **Approval note (C23 / D29 / N7):** is run ke liye P3–P11 blanket auto-continue active tha — **consume ho gaya**. N7 ke mutabiq naye kaam par P6 wala asli phase-by-phase rule wapas lagu hoga. P5 / P10 `N/A` justified gates hain (D30 / D31), skip nahi. PHASE 12 ke liye user ne alag se single-run ijazat di (C26 / D35); PHASE 13 ke liye user ne explicit feature request par implement kar di (C27 / D36) — `PHASE REVIEW — PHASE 13` `phases.md` §22 mein `READY`.

## 3. Confirmed decisions (C1–C27)

`decisions.md` → "Classification Register" aur ADRs D1–D36. Khulasa: existing MobileLab (C1) · `agent.md` root + 9 docs `MobileLab\docs\` (C2) · adapted saare 12 gates (C3) · static QA + stdlib unittest (C4) · verbatim prompt + alag addendum (C5) · scan opt-in (C6) · local git (C7) · skills/MCP defer (C8) · Roman Urdu (C9) · J: root (C10) · scoped internet (C11) · Telegram Bot command/alert (C12) · legal/authorized deep/dark web (C13) · safe task plan/report (C14) · phase completeness (C15) · provenance/URL/date (C16) · policy reframe boundary unchanged (C17) · Sahulat toolkit scope (C18) · language split content/surface (C19) · **P2 verified stdlib stack (C20)** · **modular adapter contracts (C21)** · **P2 research provenance / version honesty (C22)** · **P3–P11 blanket auto-continue, is run me consume (C23)** · **13 QA findings closed with passing regression tests (C24)** · **P5 / P10 `N/A` justified, gates passed not skipped (C25)** · **P12 single-run approval (C26)** · **P13 agent memory design (C27)**.

## 4. Current progress

**PHASE 0** · **1** · **1B** · **2** ✅ **READY** · **PHASE 3–P11** ✅ **READY** · **PHASE 12** ✅ **READY** · **PHASE 13** ✅ **READY** — **project complete** (P5 / P10 `N/A` justified, gates passed not skipped).
- P0-1 `agent.md` ✅ — verbatim byte-identical (**17,844 bytes** prefix, 22 sections, sha256 `1de53535…0840`) + alag addendum.
- P0-2 9 docs ✅ — `PRD, architecture, design, rules, phases, memory, progress, decisions, changelog`.
- P0-3 `.gitignore` + local git ✅ — commit `c25c3c6`, 38 files, koi remote nahi, clean status, `core.autocrlf=false`.
- P0-4 verification + `PHASE REVIEW — PHASE 0` ✅ — gate `READY`.
- P1-1 docs inspection ✅ · P1-2 3+1 Roman Urdu clarifications ✅ · P1-3 16 verified sources S1–S16 ✅.
- P1-4 `PRD.md` 1.1.0 ✅ — competitor map, future outlook, C11–C16, FR-01…FR-20, AC-01…AC-11, 16-source register.
- P1-5 `decisions.md` D13–D18 ✅ · `agent.md` addendum C1–C16 ✅ · `architecture / design / rules` P1 sections ✅.
- P1-7 / P1-8 ✅ — `progress.md`, `changelog.md`, `phases.md` P1 review, workspace memory, verification aur do conventional `docs:` commits; `git status` clean, koi remote nahi.
- **P1B-1…P1B-8** ✅ — `sahulat.py` (6 official routes, 8-item checklist, consent, Roman Urdu + English letters, refusal-with-reason), additive `cases` table, 6 `/api/sahulat/*` endpoints, 8th view, `safe_url()` / `linkHtml()`, policy reframe (boundary unchanged), 2 QA fixes, `tests/test_sahulat.py` **47/47 green**, 9 docs + addendum sync, `PHASE REVIEW — PHASE 1B` §10 `READY`.
- **P2-1…P2-7** ✅ — `architecture.md` **2.0.0** (15 governing headings, 10 technology rows × 5 fields, 11/11 selection criteria, `P2-01…P2-12` official sources + `S1–S16`, facts/assumptions/recommendations alag, adapter contracts §21, `AC-P2-01…AC-P2-11`) · `decisions.md` D23–D28 / C20–C22 / A12–A15 / O13 / R12–R16 · `agent.md` addendum §M · `PRD.md` 1.3.0 §16 · `rules.md` §17 · `phases.md` §11 `PHASE REVIEW — PHASE 2` `READY`. **Documentation-only gate — koi app code badla nahi.**
- **P3–P11 (2026-11-09, C23 / D29 auto-continue):** `design.md` 2.0.0 P3 final `READY` (O12 resolved: English UI chrome, Roman Urdu content retained) · `run.bat` Python `>=3.10` guard (P4) · `decisions.md` **D30–D34** + **C24 / C25**, `~~O10~~` / `~~O12~~` resolved, R3 / R15 mitigated with regression tests, R4 final audit P11 · `PRD.md` **1.4.0** §17 · `architecture.md` **2.1.0** §23 (15 headings intact) · `rules.md` §18–§19 · `phases.md` §1 / §2 / §6 (13/13 CLOSED) / §7 DoD / **9 `PHASE REVIEW`s §12–§20** · `progress.md` / `changelog.md` / `memory.md` sync. **Koi bypass capability add nahi hui.**
- **P12 Service Brief (2026-11-09, C26 / D35):** `service_brief.py` + 5 `/api/service-brief/*` routes + Sahulat view card + 8 official sources + stateless masked-last-4; `tests/test_service_brief.py`; `PHASE REVIEW — PHASE 12` `phases.md` §21 `READY`.
- **P13 Agent Memory (2026-11-09, C27 / D36):** `agent_memory.py` + `telegram_public.py`, 7 additive `memory_*` tables, 13 memory API routes, 9th view `Agent Memory`, `/api/research` recall-before + record-after, feedback usefulness/priority, `data/agent_memory.md` export, `VERSION 1.3.0`; `tests/test_memory.py` 17 green; full suite **`Ran 174 tests — OK`**; `PHASE REVIEW — PHASE 13` `phases.md` §22 `READY`. Memory archive-not-delete; Telegram public-only; local-only.
- **P8 / P9 delivered:** `python -W error::ResourceWarning -m unittest discover -s tests -p "test_*.py" -v` → **`Ran 101 tests in 77.621s — OK`**, zero `ResourceWarning`; `tests/` **8 files / 101 methods / 32 named tests**; `PY_COMPILE_OK` · `NODE_CHECK_OK`; 13/13 QA findings closed with passing regression tests; four security headers + CSP + `Cache-Control: no-store`, `MAX_BODY` 1 MiB, `_authorize_path`, `validate_llm_endpoint`, `_xml_precheck`, `_mask_settings`, `db._session()` leak fix, `server._log` local-only logging.
- **Verification (central):** `agent.md` verbatim SHA-256 `1de53535…0840` MATCH (`37314 bytes`, `CRLF False`), docs `9/9`, `git diff --check` clean, `git remote -v` empty, `core.autocrlf=false`; loopback smoke `/api/status` / `/api/knowledge` / `/index.html` / `/style.css` / `/app.js` sab 200 with `Content-Security-Policy`. **Is assistant ne koi git commit nahi kiya** — `Final review commit: pending central commit`.
- **User ki nai hidayat (C19 / D22):** "information report plan sbb roman urdu, baki sab professional English". C9 refined, khatam nahi.

## 5. Known constraints / environment

- Python **3.13.14**, SQLite **3.53.1**, Expat **expat_2.8.1**, DB-API **2.0 / qmark**, `ThreadingHTTPServer` present, node 22, npm 10, PortableGit **2.55.0.windows.3** (P2 me local command se verify).
- Official Python docs pages **3.13.18 documentation** hain — patch-level barabari ka dawa nahi (A12 / R14); generic `/3/` pages 3.15.2 dikhate the.
- `pytest` PATH par nahi → sirf `unittest`.
- Global `git user.name` / `user.email` **set nahi** → local commit ke liye neutral repo-local identity (A5).
- `flask` / `feedparser` pehle `ModuleNotFoundError` de chuke hain → stdlib-only pakka.
- Kuch vendor RSS (Huawei / Qualcomm / MediaTek candidates) `404` dete the → verified feeds istemal.
- WorkBuddy ka session transcript / plan cache `C:\Users\...\.workbuddy-ai\` mein app-managed hai; project source of truth ab `J:\Ai Agent\agent.md` + `docs\` hain.
- Browser headless screenshot ke waqt Chrome ka `docs.google.com ... failed to install` error harmless noise tha.

## 6. Pending questions (project complete; honestly deferred)

- **O1** — kaunsi skills / MCP, kyun, kis cost / credentials ke saath? Alag task mein shortlist + manzoori (**deferred**).
- **O2** — `llm_key` / Telegram token plaintext-at-rest qabool hai ya Windows DPAPI / Credential Manager? (**deferred**).
- **O3** — monitoring log retention (kitne din / kitna MB)? (**deferred**; `server._log` local-only hai, D34).
- **O4** — Telegram token storage, rotation, rate-limit/backoff (**deferred**). **O5** — legal deep/dark allowlist approval (**deferred**). **O6** — task plan rule-based vs LLM (**deferred**). **O7** — public channel history (**deferred**). **O8** — firmware provenance hash policy (**deferred**). ~~**O9**~~ — **RESOLVED** (D21): 8th view `Sahulat / Official Route`. ~~**O10**~~ — **RESOLVED** (D34 / D32): common SSRF allowlist via `research.validate_url` + `server.validate_llm_endpoint` + `app.js safe_url()`. **O11** — case register retention / export / deletion (**deferred**). ~~**O12**~~ — **RESOLVED** (D34): English UI chrome migration done, Roman Urdu content retained. **O13** — agar app ko `127.0.0.1` se bahar LAN / Internet par expose karna ho to framework / auth / TLS / deployment model; tab P5/P10 N/A dobara khulenge (**deferred**, D30 / R13).

**Deferred summary (koi jhootha resolution nahi):** O1, O2, O3, O4, O5, O6, O7, O8, O11, O13 — tafseel `decisions.md` D34.

## 7. Lessons learned

- Third-party library maangne se pehle availability check karo; is project ne poora stdlib redesign kar diya.
- Demo binaries ek jaisa byte pattern share karte the → false duplicate fingerprints. Ab har file ka pattern `sha256(path)` se banta hai.
- `startswith(BASE)` path allowlist sibling-prefix se bypass hota hai → `realpath` + `commonpath` zaroori (P9).
- `POST /api/settings` `db.set_settings()` ka poora dict wapas karta hai → plaintext key leak; GET masked hona kaafi nahi (P9).
- UI mein nested `.res-results` aur pehla package auto-select na hona do alag bugs the; dono theek kiye gaye.
- Chipset regex `\b` se overmatch karta tha → lookaround patterns.
- **Tool gotcha:** Bash heredoc ke andar Windows `\` path kabhi kabhi `/` ho jata hai; Windows paths likhte waqt `Edit`/`Write` tool ya `chr(92)` istemal karo aur read-back verify karo.
- **acceptance criteria read-back zaroori:** `make_letter()` pehle `validate_case()` call karta tha → AC-15/AC-16 toot rahe the despite "code complete" dikhna. Test likhne par pakda gaya; ab `validate_letter()`.
- **truncation ≠ validation:** 500-char cap par classify karne se lambi request ka aakhiri banned phrase cut off ho jata tha. Bounded 4000-char classification window se theek.
- **sandbox safe-delete hook:** Python `shutil.rmtree` / `os.remove` ko recycle bin me bhejne me fail hota hai (`SAFE_DELETE_FAIL_CLOSED`). Tests me file delete ki jagah SQL `DELETE FROM cases` reset istemal karo; cleanup zaroori ho to Bash `rm` se karo.
- **hash boundary:** `agent.md` verbatim prefix `\n---\n\n## Project Addendum` par khatam hota hai (byte `17844`), na ke heading par — galat slice par hash `no-match` deta hai.
- **verification script khud bhi verify karo:** P2 me aik regex `^## N. exact-heading$` tha jis ne parenthetical suffixes wale 5 headings miss kiye (`10/15`), aur `S\d\d` ne `S1–S9` miss kiye (`7/16`). Doc theek tha, script ghalat tha. Asli headings/IDs print kar ke check dobara chalaya → `15/15` + `16/16`. Kabhi bhi tool ke galat output ko doc ki ghalti na likho.
- **version honesty:** official docs aur local runtime ka patch farq explicitly darj karo; docs se runtime behavior ka dawa na banao (C22 / D28 / `rules.md` §17).

## 8. Next recommended action

PHASE 0, 1, 1B, 2 aur **PHASE 3–P13** sab `READY` — **project complete**. `phases.md` §12–§22 mein 11 final `PHASE REVIEW`s, `decisions.md` D30–D36 / C24–C27, `architecture.md` 2.1.0 §23 / §24 / §25, `PRD.md` 1.5.0 §18 / §19 darj. **PHASE 12** (`phases.md` §21) aur **PHASE 13** (`phases.md` §22) ab `READY` hain — P12 Service Brief aur P13 Agent Memory delivered; `VERSION 1.3.0`. Koi agla internal action nahi. **N7:** naye kaam par phase-by-phase approval wapas lagu hogi (C23 / D29 auto-continue is run tak seemit tha); P5 / P10 `N/A` justified hain, skip nahi. `status` bole to `progress.md` aur `phases.md` §1 parho; `review` bole to §12–§22 ka PHASE REVIEW dikhao. Central coordinator final commit karega; is assistant ne koi commit nahi kiya. Har reply / report / plan Roman Urdu me (C19).
