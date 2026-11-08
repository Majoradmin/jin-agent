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
| P1 | **Hamesha Roman Urdu** — har reply, har sawal, har option, har doc prose, har toast. Technical terms / code / paths English. Sawal chhote aur seedhe. |
| P2 | Sab kaam **local Windows PC** par; koi cloud / paid subscription / remote nahi. |
| P3 | **Python standard library only**; koi `pip install` nahi. |
| P4 | **Light theme**. |
| P5 | **Har project file / progress `J:\Ai Agent` mein** (C10). `C:\Users\...\.workbuddy-ai\` sirf WorkBuddy internal data. |
| P6 | **Phase-by-phase**: pehle aik chhota sawal → user jawab → sirf approved task → `TASK/IMPLEMENTATION/VERIFICATION/RESULT` → `PHASE REVIEW` → ruk kar agli ijazat. |
| P7 | **HARD POLICY**: koi bypass automation / steps nahi. |
| P8 | Sirf **local git**, koi remote / cloud / credentials nahi. |
| P9 | Skills / MCP installs abhi **defer** (O1). |
| P10 | Scan default workspace-restricted, zarurat par **explicit opt-in** (C6). |

## 3. Confirmed decisions (C1–C16)

`decisions.md` → "Classification Register" aur ADRs D1–D18. Khulasa: existing MobileLab (C1) · `agent.md` root + 9 docs `MobileLab\docs\` (C2) · adapted saare 12 gates (C3) · static QA + stdlib unittest (C4) · verbatim prompt + alag addendum (C5) · scan opt-in (C6) · local git (C7) · skills/MCP defer (C8) · Roman Urdu (C9) · J: root (C10) · scoped internet (C11) · Telegram Bot command/alert (C12) · legal/authorized deep/dark web (C13) · safe task plan/report (C14) · phase completeness (C15) · provenance/URL/date (C16).

## 4. Current progress

**PHASE 0 — Bootstrap** ✅ **READY** · **PHASE 1 — Requirements / PRD** 🔄 documentation complete, final review due.
- P0-1 `agent.md` ✅ — verbatim byte-identical (17,816 chars, 22 sections, sha256 `1de53535…`) + alag addendum.
- P0-2 9 docs ✅ — `PRD, architecture, design, rules, phases, memory, progress, decisions, changelog`.
- P0-3 `.gitignore` + local git ✅ — commit `c25c3c6`, 38 files, koi remote nahi, clean status, `core.autocrlf=false`.
- P0-4 verification + `PHASE REVIEW — PHASE 0` ✅ — gate `READY`.
- P1-1 docs inspection ✅ · P1-2 3+1 Roman Urdu clarifications ✅ · P1-3 16 verified sources S1–S16 ✅.
- P1-4 `PRD.md` 1.1.0 ✅ — competitor map, future outlook, C11–C16, FR-01…FR-20, AC-01…AC-11, 16-source register.
- P1-5 `decisions.md` D13–D18 ✅ · `agent.md` addendum C1–C16 ✅ · `architecture / design / rules` P1 sections ✅.
- **Baaki:** `progress.md`, `changelog.md`, `phases.md` P1 review, workspace memory, verification + commit.

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
- **O4** — Telegram token storage, rotation, rate-limit/backoff. **O5** — legal deep/dark allowlist approval. **O6** — task plan rule-based vs LLM. **O7** — public channel history. **O8** — firmware provenance hash policy. **O9** — naya 8th view ya existing panels. **O10** — common SSRF allowlist.

## 7. Lessons learned

- Third-party library maangne se pehle availability check karo; is project ne poora stdlib redesign kar diya.
- Demo binaries ek jaisa byte pattern share karte the → false duplicate fingerprints. Ab har file ka pattern `sha256(path)` se banta hai.
- `startswith(BASE)` path allowlist sibling-prefix se bypass hota hai → `realpath` + `commonpath` zaroori (P9).
- `POST /api/settings` `db.set_settings()` ka poora dict wapas karta hai → plaintext key leak; GET masked hona kaafi nahi (P9).
- UI mein nested `.res-results` aur pehla package auto-select na hona do alag bugs the; dono theek kiye gaye.
- Chipset regex `\b` se overmatch karta tha → lookaround patterns.
- **Tool gotcha:** Bash heredoc ke andar Windows `\` path kabhi kabhi `/` ho jata hai; Windows paths likhte waqt `Edit`/`Write` tool ya `chr(92)` istemal karo aur read-back verify karo.

## 8. Next recommended action

PHASE 1 ka documentation mukammal hai; ab **verification + `PHASE REVIEW — PHASE 1` + commit** karna hai. Gate `READY` hone ke baad **ruk kar user se PHASE 2 (Architecture / Tech Stack) ki ijazat maango**. Khud aage na barho. `status` bole to `progress.md` aur `phases.md` ka PHASE REVIEW parho.
