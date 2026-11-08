# memory.md — Project Context

**Date:** 2026-11-08 · **Root:** `J:\Ai Agent` · **App:** `MobileLab`
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

## 3. Confirmed decisions (C1–C19)

`decisions.md` → "Classification Register" aur ADRs D1–D22. Khulasa: existing MobileLab (C1) · `agent.md` root + 9 docs `MobileLab\docs\` (C2) · adapted saare 12 gates (C3) · static QA + stdlib unittest (C4) · verbatim prompt + alag addendum (C5) · scan opt-in (C6) · local git (C7) · skills/MCP defer (C8) · Roman Urdu (C9) · J: root (C10) · scoped internet (C11) · Telegram Bot command/alert (C12) · legal/authorized deep/dark web (C13) · safe task plan/report (C14) · phase completeness (C15) · provenance/URL/date (C16) · **policy reframe boundary unchanged (C17)** · **Sahulat toolkit scope (C18)** · **language split content/surface (C19)**.

## 4. Current progress

**PHASE 0 — Bootstrap** ✅ **READY** · **PHASE 1 — Requirements / PRD** ✅ **READY** · **PHASE 1B — Sahulat Toolkit** ✅ **READY**.
- P0-1 `agent.md` ✅ — verbatim byte-identical (**17,844 bytes** prefix, 22 sections, sha256 `1de53535…0840`) + alag addendum.
- P0-2 9 docs ✅ — `PRD, architecture, design, rules, phases, memory, progress, decisions, changelog`.
- P0-3 `.gitignore` + local git ✅ — commit `c25c3c6`, 38 files, koi remote nahi, clean status, `core.autocrlf=false`.
- P0-4 verification + `PHASE REVIEW — PHASE 0` ✅ — gate `READY`.
- P1-1 docs inspection ✅ · P1-2 3+1 Roman Urdu clarifications ✅ · P1-3 16 verified sources S1–S16 ✅.
- P1-4 `PRD.md` 1.1.0 ✅ — competitor map, future outlook, C11–C16, FR-01…FR-20, AC-01…AC-11, 16-source register.
- P1-5 `decisions.md` D13–D18 ✅ · `agent.md` addendum C1–C16 ✅ · `architecture / design / rules` P1 sections ✅.
- P1-7 / P1-8 ✅ — `progress.md`, `changelog.md`, `phases.md` P1 review, workspace memory, verification aur do conventional `docs:` commits; `git status` clean, koi remote nahi.
- **P1B-1…P1B-8** ✅ — `sahulat.py` (6 official routes, 8-item checklist, consent, Roman Urdu + English letters, refusal-with-reason), additive `cases` table, 6 `/api/sahulat/*` endpoints, 8th view, `safe_url()` / `linkHtml()`, policy reframe (boundary unchanged), 2 QA fixes, `tests/test_sahulat.py` **47/47 green**, 9 docs + addendum sync, `PHASE REVIEW — PHASE 1B` §10 `READY`.
- **User ki nai hidayat (C19 / D22):** "information report plan sbb roman urdu, baki sab professional English". C9 refined, khatam nahi.

## 5. Known constraints / environment

- Python **3.13.14**, node 22, npm 10, PortableGit **2.55.0.windows.3**.
- `pytest` PATH par nahi → sirf `unittest`.
- Global `git user.name` / `user.email` **set nahi** → local commit ke liye neutral repo-local identity (A5).
- `flask` / `feedparser` pehle `ModuleNotFoundError` de chuke hain → stdlib-only pakka.
- Kuch vendor RSS (Huawei / Qualcomm / MediaTek candidates) `404` dete the → verified feeds istemal.
- WorkBuddy ka session transcript / plan cache `C:\Users\...\.workbuddy-ai\` mein app-managed hai; project source of truth ab `J:\Ai Agent\agent.md` + `docs\` hain.
- Browser headless screenshot ke waqt Chrome ka `docs.google.com ... failed to install` error harmless noise tha.

## 6. Pending questions (P1 ko nahi rokte; implementation se pehle band)

- **O1** — kaunsi skills / MCP, kyun, kis cost / credentials ke saath? Alag task mein shortlist + manzoori.
- **O2** — `llm_key` / Telegram token plaintext-at-rest qabool hai ya Windows DPAPI / Credential Manager? P9 ADR.
- **O3** — monitoring log retention (kitne din / kitna MB)? P11.
- **O4** — Telegram token storage, rotation, rate-limit/backoff. **O5** — legal deep/dark allowlist approval. **O6** — task plan rule-based vs LLM. **O7** — public channel history. **O8** — firmware provenance hash policy. ~~**O9**~~ — **RESOLVED** (D21): 8th view `Sahulat / Official Route`. **O10** — common SSRF allowlist. **O11** — case register retention / export / deletion (P11). **O12** — in-app Roman Urdu chrome ko English surface par migrate karne ka phase (P3/P11).

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

## 8. Next recommended action

PHASE 1 aur PHASE 1B dono `READY` hain. **Ab ruk kar user se PHASE 2 (Architecture / Tech Stack) ki ijazat maango** — S1–S16 ko technology-selection table se jorna, adapter boundaries finalize karna aur `architecture.md` final karna. Khud aage na barho. `status` bole to `progress.md` aur `phases.md` §9/§10 parho; `review` bole to §10 ka PHASE REVIEW dikhao. Har reply / report / plan Roman Urdu me (C19).
