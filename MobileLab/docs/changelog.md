# changelog.md — User-Visible Changes

**Format:** `YYYY-MM-DD` · type · khulasa · files. Types: `feat / fix / refactor / test / docs / chore / security`.

---

## 2026-11-08

### `chore:` — Local git + verbatim line-ending guard (P0 verification)
- Commit `c25c3c6` — `chore: adopt agent.md governance + project docs` (38 files, `.git` 502K, **koi remote nahi**, `git status` clean).
- Repo-local `core.autocrlf=false` taake checkout par `agent.md` ka verbatim block CRLF na ho jaye (R1). Raw-byte check: `CRLF present: False`, sha256 `1de53535…` barqarar.
- Commit `docs: record PHASE 0 verification and PHASE REVIEW` — progress / changelog / decisions / memory / phases update.
- **User-visible app behavior:** koi badlao nahi.

### `chore:` — Governance adoption (PHASE 0)
**User-visible app behavior:** koi badlao nahi. Is entry ka matlab sirf documentation / repo setup hai.
- `J:\Ai Agent\agent.md` — governing prompt **verbatim** (22 sections, 17,816 chars) + alag `## Project Addendum — MobileLab`.
- 9 docs naye: `PRD.md`, `architecture.md`, `design.md`, `rules.md`, `phases.md`, `memory.md`, `progress.md`, `decisions.md`, `changelog.md`.
- `J:\Ai Agent\.gitignore` + local-only git repo + aik `chore:` commit.
- Naye rules darj: **Roman Urdu hamesha (C9)**, **sab files `J:\Ai Agent` mein (C10)**, local-only git (C7), 12 adapted gates (C3), HARD POLICY (D10).

### `docs:` — QA register (read-only, abhi fix nahi)
13 findings `phases.md` aur `rules.md` mein darj. In mein se koi abhi fix nahi hua — fixes P6/P9 ke gates mein aayenge:
`llm_key` plaintext leak · invalid query params → 500 · `/api/reveal` prefix bypass · unsafe feed URL · XML DTD/entity · `llm_endpoint` SSRF · missing security headers / body cap · f-string SQL identifier · a11y gaps · perf issues · minor bugs · swallowed LLM errors · zero automated tests.

### `feat:` — MobileLab v1.0.0 (retroactive, is se pichhla turn)
- Local Windows app @ `127.0.0.1:8765`, Python stdlib only, SQLite WAL.
- MTK `scatter` / `preloader` / DA aur Qualcomm Firehose / `rawprogram` / `patch` validator, health score, sensitive-partition flagging, duplicate detection.
- Live research agent (RSS/Atom + Google News + HN Algolia + GitHub Releases), filters, Roman Urdu `khulasa`, optional LLM rewrite.
- 7-view light-theme UI, package catalog, model brief, job register, knowledge base, settings.
- `run.bat` launcher + 2 synthetic demo packages.

### `fix:` — v1.0.0 ke andar kiye gaye fixes (retroactive)
- `flask` / `feedparser` missing → poora stdlib redesign.
- Vendor RSS 404 → verified feeds.
- Chipset regex overmatch → lookaround patterns.
- Qualcomm storage inference → mixed UFS/eMMC detection.
- Research latency 33.8s → `TIMEOUT=10` + 8–16 workers.
- Short query noise → `_has()` word-boundary check.
- Demo binary duplicate false positives → per-file `sha256(path)` pattern + DB reseed.
- Package detail empty state → first package auto-select.
- Nested `.res-results` → wrapper `res-wrap`.
- `ExitPlanMode` tool is session mein maujood nahi → approval seedha user se liya gaya (koi jhootha "plan exit" claim nahi).

---

## Upcoming (gates ke mutabiq, abhi nahi hua)

- **P4** `run.bat` Python ≥3.10 guard.
- **P6** bad query params → `400`, minor bugs, stack trace hatana.
- **P8** stdlib `unittest` suite.
- **P9** 13 security / perf / a11y fixes + regression tests; scan ka explicit opt-in checkbox.
- **P11** local logging + final docs audit.

**Koi breaking change / DB migration / deployment change abhi nahi hua.**
