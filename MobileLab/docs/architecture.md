# architecture.md — MobileLab System Architecture

**Date:** 2026-11-08 · **Updated:** 2026-11-09 · **Status:** PHASE 2 `READY` + P3–P11 final doc-vs-code sync — project `READY` · **Document version:** 2.1.0
**Root:** `J:\Ai Agent` · **App:** `J:\Ai Agent\MobileLab` · **App `VERSION`:** `1.1.0` (P2 ne code nahi badla)
**Language (C19 / D22):** information / report / plan / prose = **Roman Urdu**; headings, labels, code, identifiers, paths, API routes, commits aur technical terms = **English**.

> **Research honesty:** P0 mein koi web browse nahi tha. P1 ne 16 official / verified sources `PRD.md` §5.3 (S1–S16) mein `URL + date checked = 2026-11-08` ke sath darj kiye. P2 ne 12 official technology / security sources `P2-01…P2-12` directly check kiye, sab ka `date checked = 2026-11-08` hai. Python docs pages `3.13.18 documentation` hain jabke local runtime `Python 3.13.14` hai — ye patch-level farq §19.3 mein darj hai. Telegram ka P2 anchor re-check juzwi raha; baqi Telegram facts P1 `S9` se retained hain, koi naya dawa nahi. **Facts** aur **Recommendations** alag hain; koi citation banawati nahi, koi speculation fact nahi.

---

## 1. System architecture

```
Browser (localhost)
   |  static: /, /index.html, /app.js, /style.css, /favicon.svg
   |  JSON  : /api/*
   v
server.py  — BaseHTTPRequestHandler + ThreadingHTTPServer, 127.0.0.1:8765
   |-- static allowlist + four security headers + CSP + MAX_BODY 1 MiB
   |-- handlers: GET / POST / DELETE
   |
   +--> firmware.py   (scan_folder, parse_scatter, parse_program_xml, validate)
   +--> research.py   (fetch RSS/Atom/JSON, score, filter, Roman Urdu khulasa, optional LLM)
   +--> knowledge.py  (static KB: boundaries, official routes, glossary)
   +--> sahulat.py    (official-route policy data, checklist, consent, letters, classifier)
   +--> db.py         (SQLite WAL, 7 tables, 4 indexes, settings)
                          |
                          v
                    data\mobilelab.db   (local only, gitignored)

tests\ — 8 files / 101 unittest methods (P8); _harness.py in-process loopback, fixed throwaway data\_p8_test.db
```

**Boundaries:** frontend / backend / DB / business logic / integrations alag files mein. Koi cloud service nahi. Koi auth layer nahi (single-user loopback, P5 N/A — `D30`). P2 sirf architecture documentation aur ADR gate tha; us phase mein koi Python, JS, CSS ya DB code nahi badla. **P3–P11 final sync:** P9 ne security baseline, P8 ne suite aur P11 ne doc-vs-code audit deliver kiya — tafseel `§23` aur `decisions.md` D32 / D33 / D34. 15 governing numbered headings (`§1`–`§15`) barqarar hain.

## 2. Technology stack (selection record)

### 2.1 Verified technology-selection table

| Area | Selected option | Alternatives considered | Why selected | Main trade-offs | Upgrade / replacement strategy | Verified evidence |
|---|---|---|---|---|---|---|
| Runtime / language | `Python 3.13.14` standard library only | Node.js, .NET, bundled PyInstaller runtime | Existing app chal raha hai; zero `pip install`; local Windows Python maujood; D4 / C11 | Windows Python version dependency; koi project-level linter / type config nahi; patch-level docs aur runtime alag ho sakte hain | Modules ko stdlib-compatible rakhein; agar kabhi embedded runtime chahiye to P4/P10 me naya ADR, koi P2 rewrite nahi | Local `python --version`; `P2-01…P2-07`; `D4`, `C20` |
| HTTP server | `http.server.ThreadingHTTPServer` + custom `BaseHTTPRequestHandler` | Flask `3.1.x`, FastAPI, aiohttp | Stdlib, zero dependency, loopback-only, manual route control; app ko WSGI server stack ki zarurat nahi | Official docs ke mutabiq `http.server` production ke liye recommended nahi aur sirf basic security checks karta hai; koi router/middleware/auth nahi; `send_header()` / `send_response_only()` CRLF validate nahi karte | Pehle `server.py` handlers ko `routes.py` style registry me nikaalein, phir zarurat par WSGI/ASGI framework; tab auth aur production server bhi lazmi honge | `P2-01`, `P2-11`, `P2-12`; `server.py` lines 12 / 32 / 353 |
| Database | `sqlite3` + WAL | JSON files, PostgreSQL, DuckDB | Single-file, transactional, serverless, stdlib, offline; 7-table schema already code me hai | Single writer; WAL network filesystem par kaam nahi karta; `-wal` / `-shm` DB state ka hissa hain; lambi read transaction checkpoint rok sakti hai; `check_same_thread=False` par writes serialize karne padte hain | `db.py` ke `rows` / `one` / `execute` functions ko repository adapter ke peeche rakhein; doosre DB par SQL dobara likhna padega | `P2-02`, `P2-08`; local `sqlite 3.53.1`; `db.py` lines 125–139 |
| Outbound HTTP client | `urllib.request.urlopen` | `requests`, `httpx`, `aiohttp` | Stdlib; feeds aur optional LLM / Telegram ke liye aik hi adapter point (`research.fetch`) | `FileHandler` / `DataHandler` / `FTPHandler` bhi maujood; proxy env vars ya Windows registry se auto-detect ho sakta hai; pooling / retry manually; timeout sirf HTTP/HTTPS/FTP par; arbitrary URL allow karne par SSRF risk | `research.fetch()` ke andar client adapter: scheme/host allowlist, resolved-IP validation, redirects off, connection-time enforcement (`P9`, `O10`) | `P2-03`, `P2-09`; `research.py` line 20 |
| Feed / XML parsing | `xml.etree.ElementTree` + `json` + `html` | `feedparser`, `defusedxml`, `lxml` | Stdlib; `parse_feed()` / `parse_github()` / `parse_hn()` pehle se alag hain | Untrusted XML par official warning; Expat `< 2.7.2` billion laughs / quadratic blowup / large tokens ka risk; `xmlrpc` decompression bomb; local Expat `expat_2.8.1` hai phir bhi input size / DTD / entity hardening chahiye | Parser adapter me pre-validation + bounded size; `defusedxml` sirf tab jab dependency policy user approve kare | `P2-04`, `P2-05`, `P2-09`; local `pyexpat.EXPAT_VERSION` |
| Concurrency | `concurrent.futures.ThreadPoolExecutor`, explicit `8–16` workers | `asyncio`, `multiprocessing`, sequential fetch | I/O-bound feed fetch ko overlap karna docs me recommended pattern hai; code default worker formula par depend nahi karta | GIL; thread count cap; default `max_workers` 3.5 / 3.8 / 3.13 me badla; cleanup aur timeout discipline chahiye | `_build_jobs()` / `_run_job()` ke around executor adapter; strategy badalne par route handlers na badlein | `P2-06`; `research.py` `max_workers=max(8, min(16, len(jobs)))` |
| Frontend | Vanilla JS + CSS, no build step | React, Vue, Tailwind, CDN component kit | Zero npm / bundler / external font / CDN; offline local UI; light theme; 8 views pehle se chal rahe hain | Manual state management; framework-level a11y tooling nahi; `innerHTML` aur external URL par escaping / allowlist lazmi | `app.js` ko modules me baant kar upar framework layer; CSP aur `esc()` / `safe_url()` pehle enforce karein | `P2-12`; `web\index.html`, `web\app.js`, `web\style.css` |
| Tests | stdlib `unittest` | `pytest`, Playwright, browser E2E runner | Stdlib; `pytest` PATH par nahi; `tests\` **8 files / 101 tests** green, 32/32 named regression tests maujood (`D33`) | Fixtures kam, verbose; browser E2E nahi; `-W error::ResourceWarning` par zero warning | Test names aur assertions portable rakhein; runner badalna aasan rahe | `P2-07`; `Ran 101 tests in 77.621s — OK` |
| Packaging | `run.bat` + `python server.py` | PyInstaller, MSI installer, Windows service | Zero install, local-only Git, user PC par Python maujood; C7 ke mutabiq koi remote / cloud nahi | Python version dependency; `run.bat` me Python `>=3.10` guard P4 me add ho chuka; service / daemon nahi | Optional installer sirf user ki nai manzoori aur naye ADR ke sath (`D31`) | Local `run.bat`, `server.py` lines 351–353; `D4`, `C7` |
| External integration transport (P7 planned) | Optional OpenAI-compatible LLM + official Telegram Bot API, dono `urllib.request` se | MTProto / TDLib / Telethon, vendor SDKs | Stdlib; official HTTPS template `https://api.telegram.org/bot<token>/METHOD_NAME`; core features ke liye koi token lazmi nahi | Token storage `O2/O4`; updates max 24h; webhook aur `getUpdates` mutually exclusive; arbitrary endpoint SSRF risk; LLM hallucination / prompt injection | `telegram.py` aur `llm_client.py` adapters; common allowlist `O10`; offline graceful degradation; koi historical public-channel scrape claim nahi | `P2-09`, `P2-10`, `S9`; `D14`, `D27` |

### 2.2 Selection criteria matrix (11 governing criteria)

| Criterion | Project-specific judgment | Evidence / project impact |
|---|---|---|
| Project requirements | Local, offline, zero-dependency MTK/QCOM package validation + Roman Urdu research + provenance + official-route records. | Stdlib stack barqarar; koi cloud / paid subscription / API key core features ke liye lazmi nahi (`C11`, `D4`). |
| Team skill level | Single technician / current maintainer; plain Python + vanilla JS samajhna aur debug karna aasan. | Koi build toolchain, framework training ya package manager nahi; `run.bat` direct launcher. |
| Long-term maintenance | Chhote modules, official stdlib APIs, 9 docs, local commits, `date checked` provenance. | P11 doc-vs-code audit; Python `3.13.18` docs vs local `3.13.14` patch drift `A12` / `R14` me tracked. |
| Ecosystem maturity | Python stdlib, SQLite WAL, Flask, MDN CSP, OWASP sab documented ecosystems hain. | Migration ke raaste maujood, lekin P2 me dependency add nahi ki; Flask `3.1.x` sirf alternative evidence ke liye (`P2-11`). |
| Security | Loopback-only; `http.server` production warning; SQL placeholders; untrusted XML warning; SSRF allowlist; CSP baseline. | **P9 fixes delivered (`D32`):** four security headers + CSP, `MAX_BODY` 1 MiB, `_authorize_path` (`realpath`/`commonpath`), `_xml_precheck`, `validate_url` / `validate_llm_endpoint`, `_mask_settings`, article action allowlist, `_log` (`P2-01`, `P2-02`, `P2-05`, `P2-09`, `P2-12`). |
| Documentation quality | Official Python 3.13 docs, SQLite WAL, OWASP, Flask, MDN CSP, Telegram Bot API directly checked. | Har major row ka source `§19` me `URL + date checked = 2026-11-08` ke sath; koi banawati citation nahi. |
| Community support | Stdlib aur upar wale official projects ke docs / extensions maujood; community frameworks migration option hain. | **Recommendation / project judgment, fact nahi:** abhi zero-dependency surface chhota rakhna behtar hai; community support ka fayda sirf zarurat par migration me lena. |
| Performance | `MAX_FILES=4000`, `MAX_DEPTH=6`, `TIMEOUT=10`, pool `8–16`; WAL readers/writer concurrency; ThreadPoolExecutor I/O overlap. | Single-user local scale; koi horizontal scaling / load balancer nahi (`P2-06`, `P2-08`, `§13`). |
| Hosting cost | `127.0.0.1` par aik Windows PC; koi cloud deploy, hosted CI/CD, container ya paid runtime nahi. | `PHASE 10` N/A + wajah; core features offline; optional LLM / Telegram user-configured (`C7`, `C11`). |
| Ease of testing | `unittest discover`, in-process loopback server, throwaway gitignored DB, SQL reset, mocked/offline design. | **101 tests / 8 files green (P8 delivered, `D33`);** production DB aur live internet tests kabhi touch nahi karte (`P2-07`, `A3`). |
| Ease of migration | Adapter boundaries: `server.py` routes, `db.py` repository, `research.fetch` HTTP client, `parse_*` parsers, `sahulat.py` policy data, `app.js` UI modules. | Har row ki replacement strategy upar table me; P2 koi rewrite nahi karta (`D24`, `§21`). |

**P2 status:** pehle wala pending research note ab band hai. Har major technology ke 5 required fields aur 11 selection criteria upar darj hain.

## 3. Folder structure (verified on disk)

```
J:\Ai Agent\
  agent.md                      <- governance (verbatim + addendum)
  .gitignore
  .git\                         <- local only
  .workbuddy-ai\memory\         <- assistant workspace memory (gitignored)
  MobileLab\
    server.py  db.py  firmware.py  research.py  knowledge.py  sahulat.py
    run.bat
    web\        index.html  app.js  style.css  favicon.svg
    samples\    MTK_Demo_MT6899_UFS\  QCOM_Demo_SM8650_UFS\
    data\       mobilelab.db (+ WAL/SHM), _p1b_test.db  <- gitignored
    docs\       PRD.md architecture.md design.md rules.md phases.md
                memory.md progress.md decisions.md changelog.md
    tests\      _harness.py + 7 test_*.py  (8 files total, 101 tests; P8)
```

P2 ne koi naya source file nahi banaya. `tests\test_sahulat.py` PHASE 1B me ban chuka tha; purana `tests\ (P8 mein banega)` note ab ghalat tha, is liye theek kiya gaya. **P8 final:** `tests\` ab **8 files** (`_harness.py`, `test_sahulat.py`, `test_security.py`, `test_firmware.py`, `test_db.py`, `test_research.py`, `test_server_api.py`, `test_static_governance.py`) / **101 tests** — fixed throwaway `data\_p8_test.db` SQL-only reset, sab network mocked (`D33`).

## 4. Frontend architecture

- Single page, 8 `.view` sections, hash routing (`location.hash`, `hashchange`, `nav(view)`). 8th view = `Sahulat / Official Route` (PHASE 1B).
- `state` object + `api()` / `post()` wrappers; `esc()` output encoding; `safe_url()` / `linkHtml()` external links ko `http/https` tak seemit rakhte hain.
- `TITLES` map, `refreshCounts()`, view-specific loaders (`loadPackages`, `fetchResearch`, `loadDashNews`, `loadSahulat`, …).
- Static allowlist server par; koi bundler / CDN / external font nahi.
- **Security baseline:** MDN ke mutabiq CSP response header resource loading control karta hai aur XSS se bachane me madad karta hai; Baseline widely available since August 2016 (`P2-12`). **P9 me CSP add ho chuka** — `_send()` ka `CSP` constant: `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'`. Sath mein four security headers (`Content-Security-Policy`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `X-Content-Type-Options: nosniff`) aur `MAX_BODY` 1 MiB → `413` (`D32`). Static assets zero inline `<script>` ke sath.
- **Language:** content strings Roman Urdu; professional surface English. **`O12` resolved (`D34`)** — English UI chrome migration done, `lang="en"`, 8 nav items / 8 `role="tabpanel"`, `aria-live`, `:focus-visible`, `prefers-reduced-motion`; Roman Urdu content (letters, reasons, hints, consent, `khulasa`, help) barqarar. P2 ne UI strings nahi badle the (historical snapshot).

## 5. Backend architecture

- `ThreadingHTTPServer`, loopback bind `127.0.0.1`, custom `BaseHTTPRequestHandler` (`do_GET` / `do_POST` / `do_DELETE`). Custom handler `SimpleHTTPRequestHandler` nahi hai, is liye us class ka symlink-follow warning directly apply nahi hota; phir bhi static allowlist `realpath` / `commonpath` hardening P9 me chahiye (`P2-01`).
- `_send()` headers: `Content-Type`, `Content-Length`, `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Content-Security-Policy` (four security headers + CSP). `_json()` / `_err()` JSON return karte hain. **P9 delivered:** `MAX_BODY` 1 MiB body cap → `413`, article action allowlist, `_parse_num`, `_authorize_path`, `validate_llm_endpoint`, `_mask_settings`, `_prune_research_cache`, pagination aur `_log` (`D32`).
- `_body()` `Content-Length` par `json.loads` karta hai; `_query()` `parse_qs` se first value leti hai.
- P2 snapshot me `do_GET` / `do_POST` ke top-level `except` me `traceback.print_exc()` aur `Server error: {e}` `500` response tha (QA #7 / #11). **P6/P9 me fix ho gaya:** `_log(context, exc)` local-only failure logging, safe JSON error, koi stack trace / internal message client ko nahi; ghalat input par `400`, LLM failure par rule-based fallback (`D32`).
- Static assets exact allowlist: `/`, `/index.html`, `/app.js`, `/style.css`, `/favicon.svg`.
- `os.startfile()` sirf `/api/reveal` (Windows Explorer) — Windows guard aur path authz P9.
- Official `http.server` docs production ke liye recommend nahi karte; is liye architecture boundary **sirf loopback** hai. LAN / Internet exposure ke liye naya framework, auth, TLS aur deployment ADR zaroori hoga (`P2-01`, `R13`).

## 6. Database design (verified in `db.py`)

`PRAGMA journal_mode=WAL`, `PRAGMA foreign_keys=ON`, `row_factory=sqlite3.Row`, `check_same_thread=False`, `_LOCK` around writes. Local runtime `sqlite 3.53.1`; `sqlite3.apilevel = 2.0`, `paramstyle = qmark`.

| Table | Purpose |
|---|---|
| `packages` | scanned package meta, health, report_json, tags/notes, created_at |
| `package_files` | per-file classification + fingerprint, FK → packages |
| `articles` | saved/live research items, `fetched_at`, flags |
| `models` | model cards |
| `jobs` | IMEI / model / customer / proof_ok / route / notes |
| `cases` | PHASE 1B Sahulat case / asset register (`case_no UNIQUE`, proof flags, consent, status) |
| `settings` | key-value config (`DEFAULT_SETTINGS`) |

**Indexes (exact, 4):** `idx_pf_package ON package_files(package_id)` · `idx_pf_hash ON package_files(fingerprint)` · `idx_articles_fetched ON articles(fetched_at)` · `idx_cases_created ON cases(created_at)`.

**Fingerprint:** size + first/last 512 KiB chunks (`FINGERPRINT_CHUNK`), duplicate detection ke liye.
**SQL safety:** official `sqlite3` docs string-formatted SQL ko SQL-injection vulnerable kehti hain aur `?` placeholders lazmi kehti hain (`P2-02`). P2 snapshot me `/api/article` me f-string SQL identifier `col` tha — **P9 me `server.py` article action allowlist se fix ho gaya** (`test_article_action_allowlist`, `D32`).
**WAL facts:** readers writer ko block nahi karte aur writer readers ko block nahi karta; `-wal` / `-shm` files DB state ka hissa hain; WAL network filesystem par kaam nahi karta; default auto-checkpoint ~1000 pages; lambi read transaction checkpoint progress rok sakti hai (`P2-08`). Is liye DB aur WAL files aik hi local folder me rehne chahiye.
**Migration status:** aaj `CREATE TABLE IF NOT EXISTS` hai; `cases` additive auto-create hoti hai (`D20`). Proper versioned migration strategy P6 ADR (`A7`).
**P9 delivered (QA #10 / `D32`):** `db._session()` context manager har connection ko close karta hai — isi se `-W error::ResourceWarning` par zero warning aaya; `save_package` single transaction, `/api/packages` pagination aur `_prune_research_cache` bounded cache bhi code me hain. Production DB tests kabhi touch nahi karte (`D33`).

## 7. API design

**GET:** `/api/status` · `/api/knowledge` · `/api/sources` · `/api/research` · `/api/articles` · `/api/packages` · `/api/packages/<id>` · `/api/models` · `/api/model-brief` · `/api/jobs` · `/api/settings` · `/api/sahulat/overview` · `/api/sahulat/cases` · `/api/sahulat/check`
**POST:** `/api/scan` · `/api/article` · `/api/models` · `/api/jobs` · `/api/settings` · `/api/sahulat/letter` · `/api/sahulat/case` · `/api/sahulat/check` · `/api/reveal`
**DELETE:** `/api/packages/<id>` (regex `^/api/packages/(\d+)$`)

Response: `{"ok":true,...}` / `{"error":"..."}`. Static: `/`, `/index.html`, `/app.js`, `/style.css`, `/favicon.svg`.
`/api/status` ab `policy`, `policy_id` aur `counts.cases` bhi return karta hai. Sahulat routes ki validation chain §18.3 me hai; 6 naye endpoints PHASE 1B ka code hain aur P2 ne unhe main API list me sync kiya.
**P6/P9 delivered (`D32`):** bad query params → `400` via `_parse_num` (QA #2), koi stack trace / internal error client ko nahi, `413` `MAX_BODY` cap, four security headers, article action allowlist (QA #8), `/api/status` path leak band — `db` basename-only + `_mask_settings` se `llm_key` `***` masked (QA #1 / QA #7). Loopback smoke: `/api/status` 200 (`version 1.1.0`, `policy_id SAHULAT-SAFE-SERVICE-v1`), `/api/knowledge` 200.

## 8. Authentication architecture — N/A (PHASE 5 gate)

`127.0.0.1` single-user offline app; koi account, session, password, token ya multi-user role nahi. Is liye auth layer **N/A + wajah** ke saath P5 gate pass hua, **skip nahi** (`D30`, `C25`). `llm_key` ka secret handling P9 ka security task hai (`_mask_settings`), authentication nahi. Agar kabhi app loopback se bahar expose ho to `http.server` production warning ki wajah se naya ADR + auth + TLS + framework review lazmi hoga (`D30`, `P2-01`, `R13`, `O13`).

## 9. Authorization model

- Har API design-level sirf loopback se accessible.
- Static authorization: exact path allowlist, custom `_static()`.
- P2 snapshot me `/api/reveal` `os.path.abspath(target).lower().startswith(BASE.lower())` prefix check karta tha (QA #3). **P9 me `server.py` `_authorize_path` (`realpath` + `commonpath`) se fix** — sibling-prefix bypass, symlink/junction/UNC escape reject, authz `exists()` se pehle, Windows guard (`os.startfile`).
- P2 snapshot me `/api/scan` path directly `firmware.scan_folder(raw)` ko deta tha; **P9 me C6 default workspace restriction + explicit `allow_outside` opt-in implement ho gaya**, `firmware.py` `MAX_FILES=4000` / `MAX_DEPTH=6` caps ke sath. P2 ne code fix ka dawa nahi kiya tha — wo ab P9 ka verified deliverable hai.
- **P9 hardening delivered:** upar wala `_authorize_path`, `firmware._xml_precheck` (DTD / entity reject), four security headers, `MAX_BODY`, `validate_llm_endpoint`, `_mask_settings`, article action allowlist, pagination (`D32`).
- **Outbound authorization:** OWASP allowlist, scheme/host/IP validation, resolved-IP connection binding, redirects off, parser-disagreement reject, private/loopback/link-local/metadata ranges block (`P2-09`, `O10`). `urllib.request` ke `file://`, `data://`, FTP handlers aur proxy autodetection is ko aur zaruri banate hain (`P2-03`).

## 10. External services

`research.py` me 7 RSS sources: GSMArena · XDA Developers · Android Authority · Android Police · 9to5Google · SamMobile · Apple Newsroom. Query sources: Google News RSS · Hacker News Algolia API · GitHub Releases API (`bkerler/mtkclient`, `bkerler/edl`, `blacktop/ipsw`). Optional OpenAI-compatible LLM endpoint user-configured. Telegram Bot API P7 ka planned adapter hai, P2 me code nahi.
Core features ke liye koi API key lazmi nahi. Offline par graceful degradation. Vendor RSS endpoints jo 404 dete the (Huawei / Qualcomm / MediaTek candidates) hata diye gaye.
`urllib.request` proxy env vars ya Windows registry se `ProxyHandler` auto-install kar sakta hai (`P2-03`); is liye P9 allowlist sirf hostname string par nahi, connection-time validated IP par lagni chahiye. Telegram endpoint template `https://api.telegram.org/bot<token>/METHOD_NAME` (`P2-10` / `S9`).

## 11. Data flow

**Scan:** UI path → `POST /api/scan` → `firmware.scan_folder()` (classify, fingerprint, parse scatter/XML) → `firmware.validate()` → `db.save_package()` → JSON report → UI render + auto-select.
**Research:** UI params → `GET /api/research` → `_build_jobs()` → parallel `fetch()` → `parse_*()` → `score_item()` / filters → `make_khulasa()` (Roman Urdu) → optional `llm_rewrite()` → JSON → cards. P9 me har outbound request allowlist + resolved-IP gate se guzaregi.
**Sahulat:** `web/app.js` → `GET /api/sahulat/overview` → 8th view → checklist + form → `POST /api/sahulat/letter` (preview) ya `POST /api/sahulat/case` (save + letter) → `db.cases` → `GET /api/sahulat/cases` table. Letter `<pre>` me `textContent`; har `<a>` `safe_url()` se.
**Reveal:** UI path → authz → `os.startfile()` → Explorer.
**Planned P7:** Telegram `getUpdates` → bot command → safe research / alert → `sendMessage`; LLM rewrite sirf configured endpoint par; dono `urllib.request` adapter ke through.

## 12. Error handling

`_err()` JSON errors; feed failures per-source diagnostics. P2 snapshot me `traceback.print_exc()` + `Server error: {e}` `500` aur `llm_rewrite()` ka silent swallow tha (QA #7 / #11 / #12). **P6/P9 delivered:** `server._log(context, exc)` local-only failure logging, koi silent swallow nahi, koi stack trace / internal message client ko nahi, ghalat input par `400`, `_parse_num` se safe numeric parse, LLM failure par rule-based fallback + local log, `research.py` offline graceful degradation (`D32`).

## 13. Scalability plan

Single-user local tool — scale ka matlab **bade firmware folders aur zyada feeds** hai: `MAX_FILES=4000`, `MAX_DEPTH=6`, `TIMEOUT=10`, pool `8–16`, `limit` 5–200, bounded cache (`_prune_research_cache`) + pagination (P9 delivered, `D32`). `ThreadPoolExecutor` I/O overlap ke liye munasib hai; explicit `max_workers` code ko Python 3.5/3.8/3.13 default-formula drift se bachata hai (`P2-06`). WAL concurrency achhi hai, lekin lambi readers checkpoint rok sakti hain aur network filesystem supported nahi (`P2-08`). Koi horizontal scaling / load balancer nahi; P2 N/A justification `phases.md` §2 me hai.

## 14. Deployment architecture — N/A (PHASE 10 gate)

Distribution = `run.bat` aik Windows PC par (Python `>=3.10` guard P4 se). Koi cloud deploy, hosted CI/CD, container ya remote nahi (C7); `git remote -v` empty. PortableGit sirf local commits ke liye. Official `http.server` docs production ke liye recommend nahi karte, is liye ye N/A sirf tab qabool hai jab app `127.0.0.1` par hi rahe (`P2-01`). P10 gate "N/A + wajah" ke saath pass hua, **skip nahi** (`D31`, `C25`). Online distribution kabhi chahiye to pehle naya ADR.

## 15. Architecture boundaries

- **Sahulat & Safe Service Policy:** koi bypass automation / steps; sensitive partitions sirf flag. Policy ka naam badla hai, qaida nahi (`D19`).
- Koi cloud / telemetry / paid service / naya dependency.
- Frontend kabhi DB ko directly touch nahi karta.
- `firmware.py` sirf **padhta / validate** karta hai — kabhi device ya partition ko write nahi karta.
- Outbound internet sirf research agent, firmware/provenance aur Telegram tak (`C11`); arbitrary URL default `OFF`.
- `http.server` sirf loopback; production / LAN exposure ke liye naya ADR (`P2-01`, `R13`).
- Docs ↔ code consistency P11 audit; P2 ne apni doc drift theek ki.

## 16. 12-gate mapping

P0 Bootstrap `READY` → P1 PRD `READY` → **P2 Architecture + research `READY`** → P3 Design `READY` → P4 Setup `READY` → P5 Auth `READY — N/A justified` (`D30`) → P6 Core fixes `READY` → P7 Integrations `READY` → P8 Tests `READY` → P9 Security/Perf/A11y `READY` → P10 Deploy `READY — N/A justified` (`D31`) → P11 Docs/Monitoring `READY`. Tafseel `phases.md` §8–§20. **Project complete**; naye kaam par phase-by-phase approval wapas (N7).

---

## 17. PHASE 1 research snapshot — external boundaries (retained)

**Source register:** `PRD.md` §5.3, S1–S16, `date checked = 2026-11-08`. Ye section unhi ka architecture impact hai; P2 ne isay replace nahi kiya, sirf §19–§22 se complete kiya.

| Area | P1 finding | Architecture impact |
|---|---|---|
| Runtime | App local `127.0.0.1`; internet scoped to research/firmware/Telegram (C11). | `research.py`, Telegram adapter aur provenance fetch alag adapter layer mein; core `firmware.py` / `db.py` offline rehte hain. |
| Telegram | Official Bot API HTTPS template; `getUpdates` 1–100, 24h retention, webhook mutually exclusive, `message` / `channel_post` alag; historical channel fetch documented nahi (S9). | P7: `telegram.py` adapter with `urllib.request`; `getUpdates` pehle; `sendMessage` alert; koi MTProto/TDLib/Telethon dependency nahi; token O2/O4. |
| Deep/dark web | BSI: deep web ~90% non-indexed; dark net subset needs Tor; browsing alone illegal nahi, illegal content/download/goods/services illegal; malware risk zyada (S10). | P7: policy gate **before** fetch; legal/public/authorized allowlist; koi default Tor automation, executable download ya private data nahi. |
| Competitors | Paid suites subscription/loader coverage; open-source low-level read/write; OEM tools narrow; enterprise SBOM/vulnerability platforms (S1–S8). | MobileLab ka boundary **read/validate/provenance/plan** hai — koi device write/erase ya bypass integration nahi. |
| Platform security | AOSP Verified Boot + rollback protection; Play Integrity genuine-device check; Apple Activation Lock server-side (S11–S13). | Firmware mismatch/downgrade ko high-risk flag; official-route job records; koi rollback/integrity spoofing nahi. |
| Regulatory | EU 2024/1799 applies from 31 July 2026 (S15). | Future demand assumption; local record/provenance features ko justify karta hai, koi cloud compliance claim nahi. |
| Security | OWASP SSRF allowlist, scheme/host validation, private/loopback/link-local/metadata block, redirects off (S16). | `llm_endpoint`, research URL aur Telegram endpoint ke liye common allowlist P9; connection-time validation. |

**P2 closure:** technology table §2, adapter contracts §21 aur source register §19 is snapshot ko verified citations se jor chuke hain. `O9` resolved hai (`D21`). P2 ke mutabiq `O4/O5/O10` apne P7/P9 gates par khulne wale the — P2 ne band hone ka jhootha dawa nahi diya. **P11 final:** `O10` resolved (`D34`: `research.validate_url` + `server.validate_llm_endpoint` + `app.js safe_url()`), `O12` resolved (`D34`: English chrome / Roman Urdu content); `O4/O5` deferred (`D34`).

## 18. PHASE 1B — Sahulat toolkit (code change, 2026-11-08)

> **Boundary:** is section ki har capability documentation / read-only guidance hai. `Sahulat & Safe Service Policy` ka naam badla hai, **qaida nahi** (`D19`). Koi naya outbound service, koi naya dependency, koi device operation nahi.

### 18.1 Naya module
| Module | Zimmedari | Dependency |
|---|---|---|
| `sahulat.py` | `POLICY`, `ROUTES` (6), `CHECKLIST` (8), `CONSENT_TEXT`, `letter_roman()` / `letter_english()`, `validate_case()` / `validate_letter()`, `check_request()`, `overview()` | stdlib `os`, `re`, `time` only |

`check_request()` regex-only classifier hai — koi network call, koi LLM, koi file I/O nahi. Banned request par `reason + official_route + official_links[] + documents[] + safe_next_steps[] + refusal_line` return karta hai; **kabhi bypass step nahi**.

### 18.2 Database (additive — D20)
`cases` table: `case_no UNIQUE`, `technician`, `shop`, `customer`, `contact`, `brand`, `model`, `device_id`, `issue_type`, `route_id`, `proof_json`, `proof_ok`, `consent`, `status`, `notes`, `created_at`. Index `idx_cases_created`. Purani DB par `db.init()` ke `CREATE TABLE IF NOT EXISTS` se auto-create; koi destructive migration nahi. `counts()` me `cases` add hua.

### 18.3 API
| Method | Route | Input | Output |
|---|---|---|---|
| GET | `/api/sahulat/overview` | — | policy, routes, checklist, consent text, letter languages |
| GET | `/api/sahulat/cases` | `limit` (1–500, invalid→200) | case list, newest first |
| GET | `/api/sahulat/check` | `q` | classification + reason + official links + safe steps |
| POST | `/api/sahulat/check` | `{q}` | same |
| POST | `/api/sahulat/letter` | case payload + `lang` | letter text ya `400` with reason |
| POST | `/api/sahulat/case` | case payload + `lang` | saved case + letter (+ `letter_error` if proof incomplete) |
| GET | `/api/status` | — | ab `policy`, `policy_id` aur `counts.cases` bhi |

**Validation chain:** `validate_case()` → field caps / unknown id drop / consent required → `validate_letter()` → required proof set → `db.add_case()` parameterized insert. Ghalat `lang`, `limit`, `route_id` ya `proof` kabhi `500` nahi dete.

`make_letter()` `validate_letter()` (na ke `validate_case()`) call karta hai: letter sirf 4/4 required proof + consent par banta hai; `/api/sahulat/case` incomplete proof par case `draft` save kar ke `letter_error` wapas karta hai (AC-15 / AC-16). `check_request()` ka `MAX_QUERY_CHARS = 4000` hard-bounded classification window hai — UI 500-char field se pehle truncate karne par aakhir wala banned phrase cut off ho jata tha; ab nahi. Har blocked response mein kam-az-kam aik official `https://` link `GENERIC_LINKS` fallback se guaranteed hai; generic wording par `route_id = ""` (koi jhootha brand diagnosis nahi).

### 18.3b Tests (targeted, PHASE 1B)
`tests/test_sahulat.py` — stdlib `unittest`, 47 tests: routes/policy, request classifier, validation + letters, `cases` round-trip + additive migration (pre-1B schema simulation), live loopback HTTP endpoints, static assets / 8-view wiring, `agent.md` verbatim hash aur 9-doc consistency. Throwaway DB `MobileLab/data/_p1b_test.db` (gitignored), SQL `DELETE FROM cases` se deterministic; production DB aur live internet kabhi touch nahi. **P1B snapshot me full project suite P8 ka deliverable tha; P8 me wo deliver ho chuka** — `tests/` 8 files / 101 tests, fixed `data/_p8_test.db`, SQL-only reset (`D33`).

### 18.4 Data flow
`web/app.js` → `GET /api/sahulat/overview` → 8th view render → user checklist + form → `POST /api/sahulat/letter` (preview) ya `POST /api/sahulat/case` (save + letter) → `db.cases` → `GET /api/sahulat/cases` table. Letter `<pre>` me `textContent` se render (koi `innerHTML`). Har `<a>` `safe_url()` se guzarta hai (`http/https` only, QA #4 partial fix).

### 18.5 Deployment / security impact
- Koi naya port, koi cloud, koi remote, koi `pip install`; `VERSION` `1.0.0` → `1.1.0`.
- Naya attack surface: 5 local JSON endpoints — sab input-validated, read-only ya local validated write; koi arbitrary URL fetch nahi.
- `data/` gitignored; koi token, credential ya full IMEI zaroori nahi. Case retention/export = `O11` (P11).
- **P2 closure:** is section ne technology-selection table finalize nahi kiya tha; wo ab §2 / §19–§22 me user ki P2 ijazat se complete hai. P2 ne koi code nahi badla.

---

## 19. PHASE 2 verified source register

### 19.1 P2 sources directly checked

| ID | Source | URL | Date checked | Used for / status |
|---|---|---|---|---|
| P2-01 | Python 3.13 `http.server` | `https://docs.python.org/3.13/library/http.server.html` | 2026-11-08 | `ThreadingHTTPServer`, production warning, symlink / CRLF warnings |
| P2-02 | Python 3.13 `sqlite3` | `https://docs.python.org/3.13/library/sqlite3.html` | 2026-11-08 | DB-API 2.0, placeholders, `check_same_thread`, transactions |
| P2-03 | Python 3.13 `urllib.request` | `https://docs.python.org/3.13/library/urllib.request.html` | 2026-11-08 | `urlopen`, handlers, proxy autodetection, redirects, timeout |
| P2-04 | Python 3.13 `xml.etree.ElementTree` | `https://docs.python.org/3.13/library/xml.etree.elementtree.html` | 2026-11-08 | parser purpose, untrusted-data warning |
| P2-05 | Python 3.13 XML security | `https://docs.python.org/3.13/library/xml.html` | 2026-11-08 | Expat, DoS / local-file / network risks, `xmlrpc` bombs |
| P2-06 | Python 3.13 `concurrent.futures` | `https://docs.python.org/3.13/library/concurrent.futures.html` | 2026-11-08 | `ThreadPoolExecutor`, `Future`, `max_workers`, I/O overlap |
| P2-07 | Python 3.13 `unittest` | `https://docs.python.org/3.13/library/unittest.html` | 2026-11-08 | JUnit-inspired framework, discovery, core concepts |
| P2-08 | SQLite Write-Ahead Logging | `https://www.sqlite.org/wal.html` | 2026-11-08 | WAL concurrency, `-wal` / `-shm`, checkpoint, network FS limit |
| P2-09 | OWASP SSRF Prevention | `https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html` | 2026-11-08 | allowlist, redirects, DNS rebinding, parser disagreement, network controls; P1 `S16` ka direct re-check |
| P2-10 | Telegram Bot API | `https://core.telegram.org/bots/api` | 2026-11-08 | P2 anchor re-check: endpoint template + `getUpdates` `1–100` + 24h retention verify hue; broader facts P1 `S9` se retained; kuch anchor fetches transient fail hue |
| P2-11 | Flask Documentation `3.1.x` | `https://flask.palletsprojects.com/en/stable/` | 2026-11-08 | alternative framework: lightweight WSGI, dependencies, extensions, security/deploy links |
| P2-12 | MDN `Content-Security-Policy` | `https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy` | 2026-11-08 | CSP header, XSS guard, Baseline since Aug 2016, fetch / document / navigation directives |

### 19.2 P1 sources reused for landscape / future outlook

| ID | URL | Date checked | Area |
|---|---|---|---|
| S1 | `https://chimeratool.com/` | 2026-11-08 | commercial suite |
| S2 | `https://chimeratool.com/en/` | 2026-11-08 | commercial suite |
| S3 | `https://unlocktool.org/` | 2026-11-08 | distributor / licence |
| S4 | `https://flash.android.com/` | 2026-11-08 | OEM flashing boundary |
| S5 | `https://api.github.com/repos/bkerler/edl` | 2026-11-08 | open-source Qualcomm tooling |
| S6 | `https://api.github.com/repos/bkerler/mtkclient` | 2026-11-08 | open-source MediaTek tooling |
| S7 | `https://www.binarly.io/` | 2026-11-08 | firmware security platform |
| S8 | `https://www.netrise.io/` | 2026-11-08 | supply-chain visibility |
| S9 | `https://core.telegram.org/bots/api` | 2026-11-08 | Telegram Bot API model |
| S10 | `https://www.bsi.bund.de/EN/Themen/Verbraucherinnen-und-Verbraucher/Informationen-und-Empfehlungen/Darknet-und-Deep-Web/darknet-und-deep-web_node.html` | 2026-11-08 | deep/dark web definitions + legality |
| S11 | `https://source.android.com/docs/security/features/verifiedboot` | 2026-11-08 | Verified Boot / rollback |
| S12 | `https://developer.android.com/google/play/integrity` | 2026-11-08 | Play Integrity |
| S13 | `https://support.apple.com/en-us/108794` | 2026-11-08 | Activation Lock server-side |
| S14 | `https://www.samsung.com/ca/support/mobile-devices/google-device-protection-on-your-galaxy-device/` | 2026-11-08 | FRP official route |
| S15 | `https://eur-lex.europa.eu/eli/dir/2024/1799/oj/eng` | 2026-11-08 | right-to-repair application date |
| S16 | `https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html` | 2026-11-08 | SSRF expectations |

### 19.3 Version / availability nuance

- Python docs pages `Python 3.13.18 documentation` hain; local runtime `Python 3.13.14`, SQLite `3.53.1`, Expat `expat_2.8.1`. P2 docs version ko local patch version ke barabar nahi kehta; runtime-specific claims local command se verify kiye gaye (`§22`).
- Earlier generic `/3/` fetches `3.15.2 documentation` dikhate the. P2 final register `3.13`-specific official URLs use karta hai; purane generic result ko local behavior ka saboot nahi mana gaya.
- Telegram ka P2 re-check juzwi tha: endpoint template aur `getUpdates` limit / 24h retention directly mile; webhook mutual-exclusivity, `message` vs `channel_post` aur "no documented arbitrary public-channel history" P1 `S9` se retained hain. Transient fetch failures ko chhupaya nahi gaya.
- Koi bhi low-authority reseller price / market-size claim P2 architecture facts me shamil nahi.

## 20. PHASE 2 research — facts / recommendations / impact

### 20.1 Verified facts

| Source | Fact | Project impact |
|---|---|---|
| P2-01 | `ThreadingHTTPServer` `HTTPServer` jaisa hai lekin `ThreadingMixIn` use karta hai; 3.7 me add hua. `http.server` production ke liye recommended nahi aur sirf basic security checks karta hai. `SimpleHTTPRequestHandler` symlinks follow karta hai; `send_header()` / `send_response_only()` CRLF reject nahi karte. | Loopback-only boundary pakka; custom `BaseHTTPRequestHandler` par bhi headers sanitized hone chahiye; LAN exposure ke liye naya ADR (`R13`). |
| P2-02 | `sqlite3` DB-API 2.0 / PEP 249 interface hai; string-formatted SQL injection vulnerable hai, `?` placeholders recommended hain; `check_same_thread=False` multi-thread access deta hai par writes serialize karne padte hain; `autocommit=False` recommended hai. | `db.py` ka `_LOCK` aur parameterized queries justified; `/api/article` f-string identifier QA #8 me allowlist se fix hoga. |
| P2-03 | `urlopen()` string ya `Request` accept karta hai, context-manager object with `url` / `headers` / `status` return karta hai; HTTP/1.1 + `Connection: close`; timeout HTTP/HTTPS/FTP; Windows registry / env proxy autodetect; non-HTTP(S)/FTP redirect par `HTTPError`; `FileHandler` / `DataHandler` / `FTPHandler` maujood. | Outbound adapter me scheme allowlist aur resolved-IP validation sirf hostname par nahi, connection par lagni chahiye. |
| P2-04 / P2-05 | `ElementTree` "simple and efficient" API hai aur untrusted XML ke liye XML security dekhne ko kehta hai. Attacker-controlled XML DoS, local file access, network connections ya firewall circumvention kar sakta hai; Expat default local files / network access nahi karta, par `< 2.7.2` versions me billion laughs / quadratic blowup / large tokens / memory risk; `xmlrpc` decompression bomb vulnerable hai; `pyexpat.EXPAT_VERSION` check karne ko kaha gaya hai. | Local Expat `2.8.1` hai, phir bhi P9 me DTD/entity reject, size cap aur decompression safety chahiye. `defusedxml` ka recommendation is page par nahi tha — is liye wo claim nahi likha. |
| P2-06 | `ThreadPoolExecutor` at most `max_workers` threads use karta hai; `submit()` `Future`, `map()` iterator return karta hai; default 3.5 / 3.8 / 3.13 me badla; I/O overlap ke liye aksar use hota hai. | `research.py` explicit `8–16` workers formula drift se bachata hai; executor adapter replaceable hai. |
| P2-07 | `unittest` JUnit-inspired hai; fixture / test case / suite / runner concepts; `python -m unittest discover` aur `python -m unittest` shortcut documented hain; supplied page me `unittest.mock` ka exact zikr nahi tha. | Targeted suite stdlib runner se green; P8 full suite bhi isi par banegi; `unittest.mock` ka dawa is page se nahi jora gaya. |
| P2-08 | WAL me readers writer ko aur writer readers ko block nahi karta; `-wal` / `-shm` files aati hain; WAL network filesystem par kaam nahi karta; auto-checkpoint ~1000 pages; WAL file persistent DB state hai aur DB ke sath copy/move honi chahiye; lambi reader checkpoint rok sakti hai. | DB local folder me rehna chahiye; backup / copy policy P11 me WAL state ka khayal rakhe; P9 pagination aur connection reuse. |
| P2-09 | SSRF sirf HTTP tak seemit nahi; allowlists deny-lists se behtar; redirects off; IP / domain strict validation; domain allowlist DNS rebinding nahi rokti; resolved IP validate kar ke connection usi IP se band karein; doosri unchecked DNS lookup bypass hai; `Host` / SNI / cert verification preserve karein; complete user URL accept na karein; parser disagreement reject; network firewall / segmentation. | `llm_endpoint`, research sources aur Telegram endpoint ke liye common P9 gate; `O10` open rehta hai. |
| P2-10 / S9 | Official Bot API template `https://api.telegram.org/bot<token>/METHOD_NAME`; `getUpdates.limit` 1–100; incoming updates 24h se zyada nahi rakhe jate. P1 `S9`: webhook aur `getUpdates` mutually exclusive; `message` / `channel_post` alag; arbitrary historical public-channel fetch documented nahi. | P7 `telegram.py` adapter; token storage / rotation `O2/O4`; koi history scrape claim nahi. |
| P2-11 | Flask `3.1.x` "lightweight WSGI web application framework" hai; quick start + complex applications tak scale; Werkzeug / Jinja / Click par depend karta hai; community extensions; Security Considerations / Security Headers / Deploying to Production / SQLite pattern links. | Mature alternative maujood hai, lekin stdlib-only, local-only requirement ki wajah se P2 me select nahi hua; migration path documented. |
| P2-12 | CSP response header resource loading control karta hai, XSS se bachane me madad karta hai; Baseline widely available since August 2016; violations Reporting API / `report-to` / `Reporting-Endpoints` se report; `default-src` fallback, `script-src` / `style-src` / `connect-src` / `img-src` / `font-src` / `frame-src` / `worker-src` / `object-src` fetch directives; `base-uri` document, `form-action` / `frame-ancestors` navigation directives. | P9 headers hardening ka verified reference; koi external script / font / CDN nahi hone se strict CSP practical hai. |
| S1–S8 | Commercial suites subscription / coverage par, open-source tools low-level read/write par, OEM tools narrow device support par, enterprise platforms SBOM / firmware security par focus karte hain. | MobileLab differentiation read/validate/provenance/explainability/local records hai; device-write ya bypass race nahi (`D17`). |
| S11–S15 | Verified Boot / rollback protection, Play Integrity genuine-device check, Activation Lock server-side, FRP official route, EU 2024/1799 application from 31 July 2026. | Ownership / integrity controls aur repair-record demand architecture boundaries ko justify karte hain; koi compliance certification claim nahi. |
| S16 / P2-09 | OWASP allowlist / scheme-host-IP / redirects-off guidance P1 aur P2 dono me verify hui. | P9 SSRF regression tests ka mustanad reference; `R2` banawati citation risk band. |

### 20.2 Assumptions (fact nahi)

- **A12:** Python `3.13.18` docs local `3.13.14` ke liye relevant hain, lekin patch-level behavior barabar hone ka dawa nahi; runtime-specific behavior local command / P8 tests se verify hoga.
- **A13:** Telegram ke P1 `S9` facts abhi bhi sahih hain; P2 ne unme se endpoint / limit / 24h directly dobara dekhe, baqi facts ko "P1 verified, P2 re-check nahi" ke tor par rakha gaya hai.
- **A14:** agle 2–5 saal me hardware-backed integrity, anti-rollback, provenance aur official-route record keeping ki ahmiyat barhegi; ye trend assumption hai, revenue ya market-share fact nahi (P1 §6 se retained).
- **A15:** feed schemas, Bot API aur optional LLM endpoints badal sakte hain; adapter layer aur offline degradation is liye zaruri hai.

### 20.3 Recommendations (project decisions, fact nahi)

- **R-01:** stdlib-only stack aur `VERSION 1.1.0` barqarar; P2 me koi dependency, framework ya code migration nahi.
- **R-02:** `http.server` sirf `127.0.0.1` par rakhein; production / LAN exposure ke liye framework + auth + deployment ka naya ADR aur user ki ijazat chahiye.
- **R-03:** P9 me common outbound allowlist: user se complete URL na lein, sirf validated host / IP, application-fixed scheme / port / path, redirects off, resolved-IP connection binding, private / loopback / link-local / metadata block.
- **R-04:** P9 me XML pre-validation, DTD / entity reject, size cap, CSP headers, `realpath` / `commonpath`, body cap, SQL identifier allowlist aur secret masking.
- **R-05:** P7 me `telegram.py` / `llm_client.py` adapters; P8 me full `unittest` suite; P11 me WAL-aware backup / copy policy aur doc-vs-code audit.
- **R-06:** har research fact ka `source URL + date checked` aur `fact` / `recommendation` label; koi speculation ko fact na likhein; low-authority price / market claims exclude.

### 20.4 Current landscape / future outlook coverage

| Governing research area | P2 coverage |
|---|---|
| Similar products + strengths / weaknesses | `PRD.md` §5.1 S1–S8; `architecture.md` §17 / §20.1 |
| Open-source alternatives | S5 / S6 (`bkerler/edl`, `bkerler/mtkclient`), plus Flask / MDN / OWASP docs for framework/security alternatives |
| Current recommended frameworks / libraries | Flask `3.1.x` as considered alternative; selected stack remains Python 3.13 stdlib (`P2-01…P2-07`, `P2-11`) |
| Security / compliance expectations | Verified Boot, Play Integrity, Activation Lock, FRP, EU 2024/1799, OWASP SSRF, MDN CSP (`S11–S16`, `P2-09`, `P2-12`) |
| Common implementation mistakes | string SQL, untrusted XML, CRLF headers, complete user URLs, redirects / DNS rebinding, production `http.server`, WAL copy without `-wal` |
| Pricing / infrastructure | Local Windows PC, no cloud / hosted CI/CD / paid runtime; optional LLM / Telegram user-configured; koi market-size claim nahi |
| Trends 2–5 years / stability / outdated risk | A14 / A15; Python stdlib + SQLite stable, feed / Bot API / LLM schemas drift-prone; patch-level docs `A12` |
| Upgrade / migration risks | §2.1 replacement strategy + §21 adapters; SQL rewrite, framework auth, WAL state, schema changes |
| AI risks | hallucination, prompt injection, SSRF, secret leakage; provenance + policy gate + `O2/O6/O10` |
| Platform / regulation risks | S11–S15; server-side ownership controls, rollback protection, right-to-repair signal |
| Modular / replaceable architecture | §21 adapter contracts; P2 koi rewrite nahi karta |

## 21. Adapter boundaries and replacement contracts

| Boundary | Aaj ka code | Contract | Replacement path |
|---|---|---|---|
| HTTP routing | `server.py` `_api_get()` / `_api_post()` / `do_DELETE()` | `path + body + query -> JSON dict` | Route registry module; phir WSGI/ASGI framework, auth aur production server ke sath |
| Repository | `db.py` `rows()` / `one()` / `execute()` / `counts()` | parameterized SQL, `dict` rows, `_LOCK`, WAL local | Doosra DB adapter; SQL aur transaction semantics dobara likhne padenge |
| Outbound client | `research.fetch()` / `llm_rewrite()` | timeout, allowed scheme/host, bounded body, no silent failure | `http_client.py` with allowlist, resolved-IP binding, redirects off, retry policy |
| Feed parsers | `parse_feed()` / `parse_github()` / `parse_hn()` | XML/JSON -> normalized item dict | Parser adapter; optional hardened library only with new ADR |
| Policy data | `sahulat.py` `POLICY` / `ROUTES` / `CHECKLIST` | read-only official-route data, no network / device operation | Static data module ya localized data files; boundary immutable |
| UI modules | `web/app.js` `state` / `api()` / `nav()` | hash routing, escaped output, `safe_url()` | ES modules, then optional framework layer; CSP pehle |
| Secrets | `db.settings` (`llm_key`, future bot token) | never return plaintext in API / log / toast | Windows DPAPI / Credential Manager adapter (`O2`, P9 ADR) |
| External services | Telegram / LLM planned P7 | stdlib HTTPS, user-supplied config, offline degrade | `telegram.py` + `llm_client.py`; koi MTProto/TDLib/Telethon |

## 22. PHASE 2 acceptance criteria

| ID | Criterion | Expected evidence |
|---|---|---|
| AC-P2-01 | `agent.md` ke 15 required architecture headings preserved | §1–§15 headings read-back |
| AC-P2-02 | 11 governing selection criteria explicitly covered | §2.2 matrix |
| AC-P2-03 | Har major technology ke 5 required fields | §2.1 table |
| AC-P2-04 | Har P2 research source ka URL + `date checked = 2026-11-08` | §19.1 / §19.2 |
| AC-P2-05 | Facts, assumptions aur recommendations alag | §20.1 / §20.2 / §20.3 |
| AC-P2-06 | Koi banawati citation / version claim na ho | §19.3 + P2 verification log |
| AC-P2-07 | Docs ↔ code match | 7 tables / 4 indexes, `cases`, 6 `/api/sahulat/*` routes, `tests\test_sahulat.py`, 8 views, `VERSION 1.1.0` |
| AC-P2-08 | ADRs + classification update | `decisions.md` D23–D28 / C20–C22 / A12–A15 / R13–R15 |
| AC-P2-09 | `agent.md` verbatim prefix untouched | SHA-256 `1de53535942d8e7f1b31b3d9b55c9ae4854e85fd667e14e02f314a62010fd840` MATCH |
| AC-P2-10 | Gate hygiene | 9 docs, clean Git, no remote, `core.autocrlf=false`, `py_compile`, `node --check`, 47 targeted tests green |
| AC-P2-11 | No scope creep | P2 docs-only; koi app code, dependency, DB migration ya deployment change nahi |

**P2 result:** upar wale criteria `phases.md` §11 ke `PHASE REVIEW` me verify ho kar `READY` darj hue. **P11 final:** P3–P11 bhi `READY` (`phases.md` §12–§20, `D30`–`D34`); project complete, `2.1.0` doc-vs-code sync §23 mein. N7 ke mutabiq naye kaam par phase-by-phase approval wapas lagu hogi.

---

## 23. P3–P11 final doc-vs-code sync (2026-11-09)

> **Document-only.** Koi naya source URL / citation add nahi kiya gaya. Ye 15 governing numbered headings (`§1`–`§15`) ke baad ka final audit hai; un headings ko chheda nahi gaya. App `VERSION` `1.1.0` barqarar; koi breaking change / destructive DB migration / deployment change / naya dependency / remote nahi. Sahulat & Safe Service Policy bilkul unchanged.

| Area | Verified code fact (2026-11-09) | Doc / test linkage |
|---|---|---|
| Loopback-only | `ThreadingHTTPServer` bind `127.0.0.1:8765`; P5 / P10 `N/A + wajah`, gates **passed not skipped** | `D30`, `D31`, `C25`, `R13`, `O13` |
| Four security headers | `_send()`: `Content-Security-Policy`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `X-Content-Type-Options: nosniff` (+ `Cache-Control: no-store`) | `test_security_headers_present`, `D32` QA #7 |
| `MAX_BODY` | `1024 * 1024` (1 MiB) request cap → `413` | `test_body_size_cap_413`, `D32` |
| `_authorize_path` | `realpath` + `commonpath`, authz `exists()` se pehle, symlink / junction / UNC reject, Windows guard | `test_reveal_rejects_sibling_prefix`, `test_scan_outside_*`, `D32` QA #3 |
| `validate_llm_endpoint` | `server.py` SSRF gate; `research.py` `validate_url` + feed host allowlist = common allowlist (`O10` resolved) | `test_llm_endpoint_rejects_internal`, `D34` |
| `_xml_precheck` | `firmware.py` DTD / `<!ENTITY` reject; `MAX_FILES=4000`, `MAX_DEPTH=6` | `test_dtd_entity_rejected`, `test_file_count_boundary_4000`, `D32` |
| Masked settings | `_mask_settings` → `POST /api/settings` kabhi plaintext `llm_key` na return kare; `/api/status` `db` basename-only, `llm_key` `***` | `test_settings_no_secret_leak`, `test_status_no_abs_db_path` |
| `db._session()` | context manager har connection close karta hai → `-W error::ResourceWarning` par zero `ResourceWarning` | `D33`, QA #10 fix |
| Offline degradation | `research.py` feed timeout / 404 par graceful degrade, LLM error logging, rule-based fallback; `server._log` local-only logging (koi telemetry / off-site export) | `test_research_source_timeout_degrades_gracefully`, `test_llm_failure_logged_not_swallowed`, `D34` |
| `tests/` folder | **8 files / 101 tests / 32 named regression-characterization tests**; `_harness.py` fixed throwaway `data/_p8_test.db`, SQL `DELETE FROM` reset, sab outbound network mocked | `D33`, `phases.md` §6 |
| In-app KB | `knowledge.py` 5 naye glossary + 4 naye help entries + extended `SECURITY_NOTE`; `/api/knowledge` 200 (`glossary 18`, `help 14`, `official_routes 5`, `security_note`, `tool_arch 5`) | `AC-06`, `D34` |
| UI chrome / O12 | `lang="en"`, 8 views / 8 nav items / 8 `role="tabpanel"` / 27 `sah*` IDs, zero inline `<script>`, `aria-live`, `:focus-visible`, `prefers-reduced-motion`; Roman Urdu content retained | `test_a11y_markup`, `D34` |

**Central verification (2026-11-09):** `python -W error::ResourceWarning -m unittest discover -s tests -p "test_*.py" -v` → `Ran 101 tests in 77.621s — OK` (zero `ResourceWarning`) · `python -m py_compile db.py server.py firmware.py research.py sahulat.py knowledge.py tests/*.py` → `PY_COMPILE_OK` · `node --check web/app.js` → `NODE_CHECK_OK` · `agent.md` verbatim prefix SHA-256 `1de53535942d8e7f1b31b3d9b55c9ae4854e85fd667e14e02f314a62010fd840` MATCH (`size 37314`, `CRLF False`) · docs `9/9` · `git diff --check` clean · `git remote -v` empty · `core.autocrlf=false`.

**13 QA findings:** sab closed with passing regression tests (`D32`, `phases.md` §6). **Koi bypass capability add nahi hui** — app sirf read / validate / plan / record karta hai. **Deferred open questions:** O1, O2, O3, O4, O5, O6, O7, O8, O11, O13 (`D34`) — inmein se koi resolution invent nahi kiya gaya.
