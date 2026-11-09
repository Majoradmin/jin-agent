# changelog.md — User-Visible Changes

**Format:** `YYYY-MM-DD` · type · khulasa · files. Types: `feat / fix / refactor / test / docs / chore / security`.

---

## 2026-11-09

### `feat:` — PHASE 3–P11 completion / project `READY`
**User-visible app behavior:** koi naya feature ya bypass capability nahi; app sirf read / validate / plan / record karta hai (Sahulat & Safe Service Policy barqarar). P3–P11 delivered: design tokens / a11y plan (`design.md` P3 final `READY`, **O12 resolved** — English UI chrome, Roman Urdu content retained), `run.bat` Python `>=3.10` guard, 13 QA hardening fixes, offline graceful degradation + LLM error logging, poora 101-test suite, P5 / P10 `N/A` justified gates (D30 / D31 — **passed not skipped**), aur in-app knowledge base (`/api/knowledge`: `glossary 18`, `help 14`, `official_routes 5`, `tool_arch 5`, `security_note`). `phases.md` §12–§20 mein 9 final `PHASE REVIEW`s `READY` darj.

### `security:` — 13 QA findings closed
13/13 QA findings `phases.md` §6 mein `CLOSED` — har aik ka asli code-fix + named passing regression test (`decisions.md` D32). Delivered baseline: four security headers (`X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `X-Content-Type-Options: nosniff`) + `Content-Security-Policy` + `Cache-Control: no-store`, `MAX_BODY` 1 MiB, `_authorize_path` (realpath/commonpath), `validate_llm_endpoint` SSRF allowlist, `app.js safe_url()` http/https allowlist, `_xml_precheck` + `MAX_FILES=4000` / `MAX_DEPTH=6`, `_mask_settings` (`llm_key` masked `***`), article action allowlist, `_prune_research_cache` + pagination, `_log` local-only logging. **Koi bypass capability add nahi hui.**

### `test:` — full project `unittest` suite
`python -W error::ResourceWarning -m unittest discover -s tests -p "test_*.py" -v` → **`Ran 101 tests in 77.621s — OK`**, **zero `ResourceWarning`**. `tests/` exactly **8 files** (`_harness.py`, `test_sahulat.py`, `test_security.py`, `test_firmware.py`, `test_db.py`, `test_research.py`, `test_server_api.py`, `test_static_governance.py`), **101** methods, **32/32** named regression / characterization tests. Sab outbound network mocked, production DB never touched, fixed throwaway `data/_p8_test.db` sirf SQL `DELETE FROM` se reset. `PY_COMPILE_OK` · `NODE_CHECK_OK`.

### `docs:` — P3–P11 final documentation + governance sync
`decisions.md` ADRs **D30–D34** + Classification Register **C24 / C25**, `~~O10~~` / `~~O12~~` resolved, R3 / R15 mitigated with regression tests, R4 final doc-vs-code audit completed P11 · `PRD.md` `1.3.0` → **`1.4.0`** + `§17 PHASE 3–P11 delivered state` · `architecture.md` `2.0.0` → **`2.1.0`** (15 governing headings intact) + `§23 P3–P11 final doc-vs-code sync` · `design.md` P3 final `READY` + `§12` · `rules.md` `§18 Security regression rules` + `§19 Testing rules` · `phases.md` §1 matrix, §2 N/A justifications, §6 QA closure, §7 checked DoD, **9 `PHASE REVIEW`s §12–§20** · `progress.md` / `changelog.md` / `memory.md` sync. `agent.md` addendum me **§O P3–P11 completion record** append hua (sirf verbatim prefix ke baad; prefix khud untouched) · verbatim prefix SHA-256 `1de53535942d8e7f1b31b3d9b55c9ae4854e85fd667e14e02f314a62010fd840` MATCH (`37314 bytes`, `CRLF False`), docs `9/9`, `git diff --check` clean, `git remote -v` empty, `core.autocrlf=false`. **Is assistant ne koi git commit nahi kiya** — `Final review commit: pending central commit`.

### `fix:` — `db._session()` connection leak
`db._session()` ab har connection close karta hai → zero `ResourceWarning` under `-W error::ResourceWarning` (P8 / D33). Koi destructive DB migration nahi.

### `fix:` — stale `7-view` / pending wording
`phases.md` P9 gate ka purana `7-view smoke` → `8-view smoke`; `progress.md` / `memory.md` / `changelog.md` se `P2 pending`, `Waiting on: user ki PHASE 3 ijazat`, `Ab rukna hai`, aur purana `## Upcoming` (P4/P6/P8/P9/P11 pending) hata kar delivered state darj. `design.md` O12 resolved note.

**Koi breaking change / destructive DB migration / deployment change / naya dependency / remote nahi.** P5 / P10 `N/A` justified hain (D30 / D31), koi phase skip nahi hua. C23 / D29 auto-continue is run me consume hua; N7 ke mutabiq naye kaam par phase-by-phase approval wapas.

---

## 2026-11-08

### `docs:` — PHASE 2 Architecture / Tech Stack final (documentation-only)
**User-visible app behavior:** koi badlao nahi. P2 ne na Python/JS/CSS code, na dependency, na DB schema, na deployment, na `VERSION 1.1.0` chheda. Ye sirf architecture aur governance documentation ka gate tha.
- `architecture.md` `1.x` → **2.0.0**: 15 governing headings preserve, 10-row technology-selection table (har row me selected option / alternatives / why / trade-offs / replacement strategy / evidence), 11/11 selection-criteria matrix, validated system diagram, frontend / backend / DB / API design ko asli code se match, adapter boundaries aur replacement contracts §21, aur `AC-P2-01…AC-P2-11`.
- **12 naye verified sources** `P2-01…P2-12` — official Python `3.13` docs (`http.server`, `sqlite3`, `urllib.request`, `xml.etree.ElementTree`, `xml.html`, `concurrent.futures`, `unittest`), SQLite WAL, OWASP SSRF Cheat Sheet, Telegram Bot API anchors, Flask docs, MDN CSP. P1 ke `S1–S16` bhi reuse. Har source ka full URL + `date checked = 2026-11-08`; facts §20.1, assumptions §20.2, recommendations §20.3 alag.
- **Research honesty:** Python docs `3.13.18 documentation` vs local runtime `3.13.14` ka patch farq darj; Telegram ka P2 anchor re-check juzwi raha aur kuch fetches transient fail hue — P1 `S9` retained, koi naya unverified claim nahi; low-authority price / market-size claims exclude.
- **Doc-vs-code drift theek:** `6 tables, 3 indexes` → `7 tables, 4 indexes`; `cases` table main DB design mein; 6 `/api/sahulat/*` routes API design mein; `tests\test_sahulat.py` folder structure mein; `phases.md` P9 gate ka stale `7-view smoke` → `8-view smoke`; purana `P2 pending` / `Research due` wording hataya.
- **Decisions:** `decisions.md` D23–D28 (verified stdlib stack, adapter contracts, WAL/schema, loopback security baseline, Bot API + stdlib HTTP integrations, provenance/version honesty) · C20–C22 · A12–A15 · O13 · R12–R16. `agent.md` addendum §M (verbatim prefix untouched) · `PRD.md` `1.2.0` → `1.3.0` + §16 architecture linkage · `rules.md` §17 research-honesty rule · `phases.md` §11 `PHASE REVIEW — PHASE 2` `READY` · `progress.md` / `memory.md` sync.
- **Verification:** headings `15/15`, criteria `11/11`, `P2-01…P2-12` + `S1–S16`, `AC-P2-01…11`, docs `9/9`, `agent.md` verbatim SHA-256 `1de53535…0840` MATCH (`CRLF False`), `PY_COMPILE_OK`, `NODE_CHECK_OK`, `Ran 47 tests — OK` (`2.059s`, final re-run `1.752s`), `git diff --check` clean, koi remote nahi, `core.autocrlf=false`.
- **Koi breaking change / destructive DB migration / deployment change nahi hua.** Security hardening P9, integrations P7, full project suite P8 aur `run.bat` guard P4 apne apne gates par pending hain — P2 ne unhe fix hone ka jhootha dawa nahi kiya.

### `feat:` — Sahulat & Safe Service Toolkit `v1.1.0` (PHASE 1B)
**User-visible app behavior:** naya 8th view `Sahulat / Official Route`, `VERSION` `1.0.0` → `1.1.0`. Koi bypass capability nahi; boundary bilkul barqarar.
- **Naya module** `MobileLab/sahulat.py`: 6 brand-wise official routes (Huawei, Google FRP, Samsung, Apple, Carrier, Department), 8-item proof-of-ownership checklist (4 required), printable Roman Urdu customer consent, Roman Urdu + English official service-request letters, aur request classifier jo blocked request par **sirf "nahi" nahi — wajah + official link + documents + 4 safe next steps** deta hai.
- **Naye API:** `GET /api/sahulat/overview`, `GET /api/sahulat/cases`, `GET|POST /api/sahulat/check`, `POST /api/sahulat/letter`, `POST /api/sahulat/case`. `GET /api/status` me ab `policy`, `policy_id` aur `counts.cases`.
- **Naya DB table** `cases` (additive): `case_no UNIQUE`, proof flags, consent, `status` (`ready` / `draft`), timestamp, `idx_cases_created`. Purani DB `db.init()` par auto-migrate — koi destructive migration nahi.
- **UI:** 8 views / 8 nav items, 27 `sah*` element IDs, `.sah-*` CSS, dashboard par `Sahulat cases` stat. `safe_url()` + `linkHtml()` har external href ko `http/https` allowlist se guzarte hain (QA #4 ka partial fix, XSS band).
- **Policy reframe (C17 / D19):** internal naam `HARD POLICY` → `Sahulat & Safe Service Policy`, pehli line "hum kya madad karte hain". **Sirf naam aur andaaz; har qaida waisa ka waisa**, koi role-based / sarkari-mulazim exception nahi. Canonical note har policy section mein.

### `fix:` — PHASE 1B verification me mile do gaps
- `make_letter()` `validate_case()` ki jagah `validate_letter()` call karta tha → required proof items enforce na hona (AC-15 / AC-16 toot rahe the). Ab letter sirf 4/4 proof + consent par banta hai; incomplete proof par case `draft` save + `letter_error`, aur `/api/sahulat/letter` `400`.
- `check_request()` 500 chars par truncate kar ke classify karta tha → lambi request ke aakhir me likha banned phrase cut off ho kar "ye kaam app ke andar hai" wajah se bach jata tha. Ab `MAX_QUERY_CHARS = 4000` hard-bounded window. Sath mein `GENERIC_LINKS` fallback se **har** blocked answer me kam-az-kam aik official `https://` link guaranteed; generic "bypass" wording par jhootha brand diagnosis band (`route_id = ""`).

### `test:` — Targeted regression suite (PHASE 1B)
- Naya `MobileLab/tests/test_sahulat.py` — stdlib `unittest`, **47/47 green**: routes / policy, classifier (9 banned queries), validation + dono letter languages, `cases` round-trip + pre-1B schema migration, live loopback HTTP endpoints, static assets / 8-view wiring, `agent.md` verbatim hash, 9-doc consistency.
- Production DB aur live internet kabhi touch nahi; throwaway `data/_p1b_test.db` (gitignored), SQL `DELETE FROM cases` se deterministic. **Full project suite abhi P8 ka deliverable hai** — ye targeted suite hai, koi jhootha "poora suite green" claim nahi.

### `docs:` — PHASE 1B governance sync + language split (C19 / D22)
- `PRD.md` `1.1.0` → `1.2.0` (J12–J15, FR-21…FR-26, AC-12…AC-17, canonical note) · `decisions.md` D19–D22 / C17–C19 / A11 / O11–O12 / R11 · `agent.md` addendum C1–C19 + §K / §L · `architecture.md` §18 · `design.md` §13 · `rules.md` §15–§16 · `phases.md` §10 `PHASE REVIEW — PHASE 1B` `READY` · `progress.md` / `memory.md` sync.
- **C19 (user ki nai hidayat):** information / report / plan / user communication = **Roman Urdu**; headings, labels, code, identifiers, paths, API routes, commits, technical terms = **English** (professional surface). C9 refined, mansookh nahi; koi bulk rewrite nahi.
- `agent.md` verbatim prefix SHA-256 `1de53535…0840` MATCH, `CRLF present: False`, koi remote nahi.
- **Koi breaking change / destructive DB migration / deployment change nahi hua.**

### `docs:` — PHASE 1 PRD + verified research (P1)
**User-visible app behavior:** koi badlao nahi. Is entry ka matlab sirf requirements / documentation hai; koi Python, JS, CSS ya DB code nahi badla.
- `PRD.md` `1.0.0` → `1.1.0`: product vision, competitor map, future outlook, C11–C16, FR-01…FR-20, AC-01…AC-11, edge cases aur success metrics mukammal.
- 16 sources S1–S16 `URL + date checked = 2026-11-08` ke sath darj: ChimeraTool, UnlockTool distributor, Android Flash Tool, GitHub API `edl` / `mtkclient`, Binarly, NetRise, Telegram Bot API, BSI, AOSP Verified Boot, Play Integrity, Apple, Samsung, EUR-Lex, OWASP. Facts aur recommendations alag; low-authority price/market claims exclude.
- Naye confirmed decisions: C11 scoped internet · C12 Telegram Bot command/alert · C13 legal/authorized deep/dark web · C14 safe task plan/report · C15 phase completeness · C16 provenance.
- `decisions.md` D13–D18 · `agent.md` addendum C1–C16 (verbatim block untouched) · `architecture.md` §17 · `design.md` §12 · `rules.md` §14 · `memory.md` / `progress.md` P1 update.
- Open questions O4–O10 aur risks R6–R10 register mein darj; P1 ko nahi rokte, implementation se pehle band honge.
- Verification: `agent.md` verbatim sha256 MATCH, `CRLF present: False`, docs `9/9`, PRD checks `8/8 True`, diff docs-only, `git remote -v` empty.
- Commits: `94ae743 docs: finalize PHASE 1 PRD and decisions` · `docs: record PHASE 1 verification and PHASE REVIEW`. Dono local-only.
- **Koi breaking change / DB migration / deployment change nahi hua.**

### `chore:` — Local git + verbatim line-ending guard (P0 verification)
- Commit `c25c3c6` — `chore: adopt agent.md governance + project docs` (38 files, `.git` 502K, **koi remote nahi**, `git status` clean).
- Repo-local `core.autocrlf=false` taake checkout par `agent.md` ka verbatim block CRLF na ho jaye (R1). Raw-byte check: `CRLF present: False`, sha256 `1de53535…` barqarar.
- Commit `docs: record PHASE 0 verification and PHASE REVIEW` — progress / changelog / decisions / memory / phases update.
- **User-visible app behavior:** koi badlao nahi.

### `chore:` — Governance adoption (PHASE 0)
**User-visible app behavior:** koi badlao nahi. Is entry ka matlab sirf documentation / repo setup hai.
- `J:\Ai Agent\agent.md` — governing prompt **verbatim** (22 sections, 17,844-byte prefix) + alag `## Project Addendum — MobileLab`.
- 9 docs naye: `PRD.md`, `architecture.md`, `design.md`, `rules.md`, `phases.md`, `memory.md`, `progress.md`, `decisions.md`, `changelog.md`.
- `J:\Ai Agent\.gitignore` + local-only git repo + aik `chore:` commit.
- Naye rules darj: **Roman Urdu hamesha (C9)**, **sab files `J:\Ai Agent` mein (C10)**, local-only git (C7), 12 adapted gates (C3), Sahulat & Safe Service Policy (D10).

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

## Upcoming (updated 2026-11-09)

P4 / P6 / P8 / P9 / P11 ab **delivered** hain (upar `## 2026-11-09` dekho); koi pending gate nahi. Project complete hai. Sirf **honestly deferred open questions** baqi hain — O1, O2, O3, O4, O5, O6, O7, O8, O11, O13 (`decisions.md` D34) — inka koi invented resolution nahi; naye kaam par N7 ke mutabiq phase-by-phase approval ke sath khulenge.

**Koi breaking change / DB migration / deployment change / naya dependency / remote abhi nahi hua.**
