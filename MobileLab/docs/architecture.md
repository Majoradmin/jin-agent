# architecture.md — MobileLab System Architecture

**Date:** 2026-11-08 · **Status:** PHASE 0 baseline + PHASE 1 research snapshot; PHASE 2 finalize karega.
**Root:** `J:\Ai Agent` · **App:** `J:\Ai Agent\MobileLab`

> **Research honesty:** P0 mein koi naya web browse nahi tha. P1 mein 16 official / verified sources `PRD.md` §5.3 (S1–S16) mein `URL + date checked = 2026-11-08` ke sath darj hain. Is file ka technology table abhi P0 baseline hai; P2 usay S1–S16 se jor kar final karega. Koi citation banawati nahi.

---

## 1. System architecture

```
Browser (localhost)
   |  static: /, /index.html, /app.js, /style.css, /favicon.svg
   |  JSON  : /api/*
   v
server.py  — ThreadingHTTPServer, 127.0.0.1:8765
   |-- static allowlist + security headers
   |-- handlers: GET / POST / DELETE
   |
   +--> firmware.py   (scan_folder, parse_scatter, parse_program_xml, validate)
   +--> research.py   (fetch RSS/Atom/JSON, score, filter, Roman Urdu khulasa, optional LLM)
   +--> knowledge.py  (static KB: boundaries, official routes, glossary)
   +--> db.py         (SQLite WAL, 6 tables, 3 indexes, settings)
                          |
                          v
                    data\mobilelab.db   (local only)
```

**Boundaries:** frontend / backend / DB / business logic / integrations alag files mein. Koi cloud service nahi. Koi auth layer nahi (single-user loopback, P5 N/A).

## 2. Technology stack (selection record)

| Area | Selected | Alternatives considered | Why selected | Trade-offs | Replacement strategy |
|---|---|---|---|---|---|
| HTTP server | `http.server.ThreadingHTTPServer` (stdlib) | Flask, FastAPI, aiohttp | `flask` import fail hua tha; zero-dependency policy | koi middleware/router nahi, manual handler | `server.py` ke handlers ko ek chhote router module mein nikaal kar kisi bhi WSGI/ASGI framework se replace karna |
| DB | `sqlite3` + WAL | JSON files, PostgreSQL, DuckDB | single-file, transactional, stdlib, offline | single-writer, koi server nahi | `db.py` functions (execute/rows/one) ek adapter ke peeche; SQL dobara likhna parhe ga |
| Feed parsing | `xml.etree.ElementTree` + `json` | `feedparser`, `defusedxml` | stdlib; `feedparser` maujood nahi | DTD/entity hardening khud karni parhti hai (QA #5, P9) | parser functions alag hain (`parse_feed`, `parse_github`, `parse_hn`) |
| HTTP client | `urllib.request` | `requests`, `httpx` | stdlib | pooling / retry manually | `research.fetch()` ek hi jagah — wahin badalna |
| Concurrency | `concurrent.futures.ThreadPoolExecutor` | asyncio, multiprocessing | I/O-bound feeds, stdlib, simple | GIL, threads count capped 8–16 | `_build_jobs` / `_run_job` replaceable |
| Frontend | Vanilla JS + CSS (no build) | React, Vue, Tailwind | koi npm/build step nahi, offline | manual state management | `app.js` ko modules mein baant kar koi bhi framework layer upar lagana |
| Tests | `unittest` + `unittest.mock` | `pytest`, Playwright | stdlib; `pytest` PATH par nahi | fixtures kam, verbose | tests portable; runner badalna aasan |
| Packaging | `run.bat` + `python server.py` | PyInstaller, MSI | zero install, user PC par Python maujood | Python version dependency | P4 mein version guard add |

**Research due (P2):** har row ke liye official docs + security guidance asli browse se verify karna, `source URL` + `date checked = YYYY-MM-DD` ke saath, facts aur recommendations alag. Is table mein abhi koi verified citation nahi hai.

## 3. Folder structure (verified on disk)

```
J:\Ai Agent\
  agent.md                      <- governance (verbatim + addendum)
  .gitignore
  .git\                         <- local only
  .workbuddy-ai\memory\         <- assistant workspace memory (git ignored)
  MobileLab\
    server.py  db.py  firmware.py  research.py  knowledge.py
    run.bat
    web\        index.html  app.js  style.css  favicon.svg
    samples\    MTK_Demo_MT6899_UFS\  QCOM_Demo_SM8650_UFS\
    data\       mobilelab.db (+ WAL/SHM)  <- git ignored
    docs\       PRD.md architecture.md design.md rules.md phases.md
                memory.md progress.md decisions.md changelog.md
    tests\      (P8 mein banega)
```

## 4. Frontend architecture

- Single page, 7 `.view` sections, hash routing (`location.hash`, `hashchange`, `nav(view)`).
- `state` object + `api()` / `post()` wrappers; `esc()` output encoding.
- `TITLES` map, `refreshCounts()`, view-specific loaders (`loadPackages`, `fetchResearch`, `loadDashNews`, …).
- Static allowlist server par; koi bundler / CDN / external font nahi.

## 5. Backend architecture

- `ThreadingHTTPServer`, loopback bind, `do_GET` / `do_POST` / `do_DELETE`.
- `_send()` (Content-Type, Content-Length, `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`), `_json()`, `_err()`.
- Static assets allowlist; JSON body parse; handlers per route.
- `os.startfile()` sirf `/api/reveal` (Windows Explorer) — Windows guard P9.

## 6. Database design (verified in `db.py`)

`PRAGMA journal_mode=WAL`, `PRAGMA foreign_keys=ON`, `row_factory=sqlite3.Row`, `_LOCK` around writes.

| Table | Purpose |
|---|---|
| `packages` | scanned package meta, health, report_json, tags/notes, created_at |
| `package_files` | per-file classification + fingerprint, FK → packages |
| `articles` | saved/live research items, `fetched_at`, flags |
| `models` | model cards |
| `jobs` | IMEI / model / customer / proof_ok / route / notes |
| `settings` | key-value config (`DEFAULT_SETTINGS`) |

**Indexes (exact):** `idx_pf_package ON package_files(package_id)` · `idx_pf_hash ON package_files(fingerprint)` · `idx_articles_fetched ON articles(fetched_at)`.

**Fingerprint:** size + first/last 512 KiB chunks (`FINGERPRINT_CHUNK`), duplicate detection ke liye.
**Migration status:** aaj `CREATE TABLE IF NOT EXISTS` hai; proper migration strategy P6 ADR (Assumed A7).
**Pending (QA #10):** connection reuse, `save_package` single transaction, `/api/packages` pagination.

## 7. API design

**GET:** `/api/status` · `/api/knowledge` · `/api/sources` · `/api/research` · `/api/articles` · `/api/packages` · `/api/packages/<id>` · `/api/models` · `/api/model-brief` · `/api/jobs` · `/api/settings`
**POST:** `/api/scan` · `/api/article` · `/api/models` · `/api/jobs` · `/api/settings` · `/api/reveal`
**DELETE:** `/api/packages/<id>`

Response: `{"ok":true,...}` / `{"error":"..."}`. Static: `/`, `/index.html`, `/app.js`, `/style.css`, `/favicon.svg`.
**Pending:** bad query params → `400` (QA #2), no stack traces, `413` body cap, security headers, identifier allowlist (QA #8), `/api/status` path leak (QA #7).

## 8. Authentication architecture — N/A (PHASE 5 gate)

`127.0.0.1` single-user offline app; koi account, session, password, token ya multi-user role nahi. Is liye auth layer **N/A + wajah** ke saath P5 gate pass hoga, skip nahi. `llm_key` ka secret handling P9 ka security task hai, authentication nahi.

## 9. Authorization model

- Har API sirf loopback se accessible (design-level).
- Path authorization: static allowlist + `/api/reveal` allowlist + scan path policy (C6: default workspace, explicit `allow_outside`).
- **Hardening due (P9):** `realpath` + `commonpath`, authz pehle / `exists()` baad, symlink/junction/UNC reject, Windows guard.
- Authorization matrix per endpoint P9 mein darj hogi.

## 10. External services

Google News RSS · GSMArena · XDA Developers · Android Authority · Android Police · 9to5Google · SamMobile · Apple Newsroom · Hacker News Algolia API · GitHub Releases API · optional OpenAI-compatible LLM endpoint (user-configured).
Core features ke liye koi API key lazmi nahi. Offline par graceful degradation. Vendor RSS endpoints jo 404 dete the (Huawei / Qualcomm / MediaTek candidates) hata diye gaye.

## 11. Data flow

**Scan:** UI path → `POST /api/scan` → `firmware.scan_folder()` (classify, fingerprint, parse scatter/XML) → `firmware.validate()` → `db.save_package()` → JSON report → UI render + auto-select.
**Research:** UI params → `GET /api/research` → `_build_jobs()` → parallel `fetch()` → `parse_*()` → `score_item()` / filters → `make_khulasa()` (Roman Urdu) → optional `llm_rewrite()` → JSON → cards.
**Reveal:** UI path → authz → `os.startfile()` → Explorer.

## 12. Error handling

`_err()` JSON errors; feed failures per-source diagnostics; `except Exception` LLM failure aaj chup kar deta hai (QA #12) → P9 mein log + rule-based fallback. Goal: koi silent swallow nahi, koi stack trace client ko nahi, ghalat input par `400` na ke `500`.

## 13. Scalability plan

Single-user local tool — scale ka matlab **bade firmware folders aur zyada feeds** hai: `MAX_FILES=4000`, `MAX_DEPTH=6`, `TIMEOUT=10`, pool 8–16, `limit` 5–200, bounded cache + pagination (P9). Koi horizontal scaling / load balancer nahi.

## 14. Deployment architecture — N/A (PHASE 10 gate)

Distribution = `run.bat` aik Windows PC par. Koi cloud deploy, hosted CI/CD, container ya remote nahi (C7). PortableGit sirf local commits ke liye. P10 gate "N/A + wajah" ke saath pass hoga.

## 15. Architecture boundaries

- **HARD POLICY:** koi bypass automation / steps; sensitive partitions sirf flag.
- Koi cloud / telemetry / paid service / naya dependency.
- Frontend kabhi DB ko directly touch nahi karta.
- `firmware.py` sirf **padhta / validate** karta hai — kabhi device ya partition ko write nahi karta.
- Docs ↔ code consistency P11 audit.

## 16. 12-gate mapping

P0 Bootstrap → P1 PRD → P2 Architecture+research → P3 Design → P4 Setup → P5 Auth (N/A+why) → P6 Core fixes → P7 Integrations → P8 Tests → P9 Security/Perf/A11y → P10 Deploy (N/A+why) → P11 Docs/Monitoring. Tafseel `phases.md`.

---

## 17. PHASE 1 research snapshot — external boundaries (P2 final karega)

**Source register:** `PRD.md` §5.3, S1–S16, `date checked = 2026-11-08`. Ye section unhi ka architecture impact hai; koi naya citation nahi.

| Area | P1 finding | Architecture impact |
|---|---|---|
| Runtime | App local `127.0.0.1`; internet scoped to research/firmware/Telegram (C11). | `research.py`, Telegram adapter aur provenance fetch alag adapter layer mein; core `firmware.py` / `db.py` offline rehte hain. |
| Telegram | Official Bot API HTTPS template; `getUpdates` 1–100, 24h retention, webhook mutually exclusive, `message` / `channel_post` alag; historical channel fetch documented nahi (S9). | P7: `telegram.py` adapter with `urllib.request`; `getUpdates` pehle; `sendMessage` alert; koi MTProto/TDLib/Telethon dependency nahi; token O2/O4. |
| Deep/dark web | BSI: deep web ~90% non-indexed; dark net subset needs Tor; browsing alone illegal nahi, illegal content/download/goods/services illegal; malware risk zyada (S10). | P7: policy gate **before** fetch; legal/public/authorized allowlist; koi default Tor automation, executable download ya private data nahi. |
| Competitors | Paid suites subscription/loader coverage; open-source low-level read/write; OEM tools narrow; enterprise SBOM/vulnerability platforms (S1–S8). | MobileLab ka boundary **read/validate/provenance/plan** hai — koi device write/erase ya bypass integration nahi. |
| Platform security | AOSP Verified Boot + rollback protection; Play Integrity genuine-device check; Apple Activation Lock server-side (S11–S13). | Firmware mismatch/downgrade ko high-risk flag; official-route job records; koi rollback/integrity spoofing nahi. |
| Regulatory | EU 2024/1799 applies from 31 July 2026 (S15). | Future demand assumption; local record/provenance features ko justify karta hai, koi cloud compliance claim nahi. |
| Security | OWASP SSRF allowlist, scheme/host validation, private/loopback/link-local/metadata block, redirects off (S16). | `llm_endpoint`, research URL aur Telegram endpoint ke liye common allowlist P9; connection-time validation. |

**P2 due:** technology table ki har row ko S1–S16 se jorna, adapter interfaces finalize karna, evidence/provenance DB schema ADR likhna, aur O4/O5/O9/O10 band karna. P1 ne koi code nahi badla.
