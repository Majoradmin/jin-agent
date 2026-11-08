# PRD — MobileLab

**Version:** 1.0.0 (governance baseline) · **Date:** 2026-11-08 · **Root:** `J:\Ai Agent`
**Status:** PHASE 0 scaffold. PHASE 1 ka gate is file ko user ke saath finalize karega.

> Jo kuch yahan likha hai wo **maujooda code** se verify kiya gaya hai. Koi nayi requirement, API ya user data nahi gharhi gayi. Har `Assumed` ya `Open` item alag se nishan-zada hai.

---

## 1. Product vision

Aik **bilkul local** Windows workbench jo mobile-software technician ko firmware package taiyar karte waqt atakne se bachaye — khaas kar MediaTek `preloader` / `scatter` aur Qualcomm `EDL` / `Firehose` / `rawprogram` / `patch` files. Sath mein aik research agent jo mobile-software ki nayi maloomat real time mein la kar **Roman Urdu** mein khulasa de, aur technician khud important cheez chhaant sake.

## 2. Problem statement

- Technician aksar adhuri ya ghalat firmware package ki wajah se atak jata hai: missing image, chipset se mismatched `preloader`, `UFS` / `eMMC` ka ghalat loader, partition sector overlap, GPT / LUN coverage, ghalat `DA` / auth file.
- Paid tools (Chimera Tool, UnlockTool) Windows client + cloud authorization + subscription / credits par chalte hain. Un par depend karna mehnga aur bandha hua hai.
- Har model ki latest maloomat kai sites par bikhri hoti hai; zurori information chhaantna mushkil.
- **Aham haqeeqat:** account / activation locks server-side ownership controls hain. Koi bhi local tool un server records ko badal nahi sakta — paid tools bhi nahi.

## 3. Target users / persona

**Primary — "Mobile software technician"**
Windows PC · local firmware folders · ROM / model files banata ya validate karta hai · Roman Urdu mein baat karta hai, technical terms English · paid tools se bachna chahta hai · sab kaam apni PC par chahiye.

**Secondary — "Record keeper"**
Model brief aur job register maintain karta hai, proof-of-ownership aur official route note karta hai.

## 4. User journeys (7 views)

| # | View | Journey |
|---|---|---|
| J1 | Dashboard | kholte hi counts, health aur tez live news nazar aaye |
| J2 | Firmware Packages | folder path → scan → health report + issues → detail → duplicate check → Explorer mein kholna |
| J3 | Research Agent | query + filters + sources → live results → Roman Urdu khulasa → article save |
| J4 | Model Brief | model ka card + sirf official routes |
| J5 | Job Register | IMEI / model / customer / proof / route / notes darj karna |
| J6 | Knowledge / Help | boundaries, glossary, official routes, security note |
| J7 | Settings | sources, optional LLM endpoint/key/model, scan behavior |

## 5. Functional requirements (maujooda code se)

| ID | Requirement | Source |
|---|---|---|
| FR-01 | MTK `scatter` parse + `preloader` / chipset / storage / DA / partition checks | `firmware.py` |
| FR-02 | Qualcomm Firehose, `rawprogram*.xml`, `patch*.xml`, GPT, LUN, sector overlap, image-size checks | `firmware.py` |
| FR-03 | `SENSITIVE_PARTITIONS` sirf flag, kabhi write/erase nahi | `firmware.py` |
| FR-04 | Package health score + issues + checks | `firmware.py:validate()` |
| FR-05 | Package catalog, file fingerprint, duplicate detection, delete | `db.py`, `server.py` |
| FR-06 | Live research: RSS/Atom, Google News, HN Algolia, GitHub Releases + filters | `research.py` |
| FR-07 | Rule-based Roman Urdu `khulasa`; optional OpenAI-compatible rewrite | `research.py` |
| FR-08 | Saved articles, model cards, job register, settings | `db.py`, `server.py` |
| FR-09 | Static knowledge base (boundaries + official routes + glossary) | `knowledge.py` |
| FR-10 | `/api/reveal` se scanned folder Explorer mein kholna | `server.py` |
| FR-11 | 7-view light-theme UI, hash routing, loading/empty/error/success states | `web/*` |
| FR-12 | One-click launcher | `run.bat` |

## 6. Non-functional requirements

- **Local-only:** `127.0.0.1:8765`, `ThreadingHTTPServer`, koi cloud / telemetry / remote nahi.
- **Zero dependency:** sirf Python standard library; koi `pip install` nahi (`flask`, `feedparser`, `requests` reject kiye gaye the).
- **Storage:** SQLite, `PRAGMA journal_mode=WAL`, `foreign_keys=ON`, 6 tables, indexes.
- **Zaban:** Roman Urdu prose; code / paths / API terms English (C9).
- **Jagah:** har project file `J:\Ai Agent` mein (C10).
- **Limits:** `MAX_FILES=4000`, `MAX_DEPTH=6`, feed `TIMEOUT=10`, research pool 8–16 workers, `limit` 5–200.
- **Theme:** light; `lang="ur-PK-Latn"`.
- **Security:** loopback binding, static allowlist, `nosniff`, `no-store`. Baqi 13 QA findings P6/P9 mein band honge.

## 7. Must-have / Nice-to-have / Out-of-scope

**Must-have:** FR-01…FR-12 (upar), official-route KB, HARD POLICY.
**Nice-to-have (P7+):** optional LLM rewrite, model cards, duplicate detection, export/report share, offline cache tuning.
**Out-of-scope — HARD POLICY:**
- Huawei ID, Google FRP, Samsung Account / Knox Guard, MDM, carrier lock, iCloud Activation Lock ka **koi bypass automation ya step-by-step tareeqa**.
- Koi bhi script / command jo `frp`, `persistent`, `config`, `devinfo`, `modemst1/2`, `nvram`, `nvdata`, `nvcfg`, `seccfg`, `proinfo`, `metadata` jaise identity / ownership / anti-theft partitions ko erase ya write kare.
- Cloud deploy, multi-user auth, tenant isolation, paid-tool integration, koi naya dependency.

## 8. User stories

- **US-01** — Technician ke tor par main ek firmware folder scan karna chahta hoon taake flash se pehle missing / mismatched files ka pata chal jaye.
- **US-02** — Technician ke tor par main Qualcomm `rawprogram` mein sector overlap aur image-size ghalti dekhna chahta hoon.
- **US-03** — Technician ke tor par main latest mobile-software news Roman Urdu mein chhaantna chahta hoon.
- **US-04** — Technician ke tor par main kisi locked device ke liye **sirf official** route aur proof-of-ownership note karna chahta hoon.
- **US-05** — Technician ke tor par main apne scans ka local catalog aur duplicate check rakhna chahta hoon.

## 9. Acceptance criteria

**Template (har feature ke liye PHASE 1 mein poora bhara jayega):**
`Feature / User story / Preconditions / Expected behavior / Validation rules / Error cases / Empty state / Loading state / Success state / A11y / Security / Performance / Test cases / Definition of done`

**AC-01 — Firmware scan (filled example)**
- Feature: `POST /api/scan`
- User story: US-01
- Preconditions: local folder maujood, `MAX_FILES`/`MAX_DEPTH` ke andar
- Expected: `health` 0–100, `issues`, `checks`, `counts`, package DB mein save
- Validation: `path` lazmi; default sirf workspace; bahar ke liye explicit `allow_outside: true` (C6)
- Error: ghalat path → `400` JSON; kabhi `500` / stack trace nahi
- Empty: khali folder → valid report + `health` + info issue
- Loading: UI `busy()` spinner
- Success: toast + list mein naya package + auto-select
- A11y: form label, keyboard submit, toast `aria-live` (P9)
- Security: `realpath` + `commonpath`, symlink/junction/UNC reject (P9)
- Performance: 4000 files / depth 6 cap
- Tests: `test_scan_valid_mtk_package_happy_path`, `test_scan_valid_qcom_package_happy_path`, `test_scan_outside_denied_by_default`, `test_scan_outside_allowed_with_flag`, `test_file_count_boundary_4000`
- DoD: sab tests green + manual `run.bat` smoke

**AC-02 — Research (filled example)**
- Feature: `GET /api/research`
- Expected: filtered/scored items + Roman Urdu `khulasa` + source diagnostics
- Validation: `days`, `min_score`, `limit` numeric; ghalat value → `400` (QA #2, P6); `limit` 5–200 clamp
- Error: feed timeout / 404 → graceful degradation, baqi sources ke results aayein
- Empty: koi match na ho → saaf empty state
- Loading/Error/Success states UI mein
- Security: sirf `http`/`https` links render (QA #4, P9); XML DTD/entity reject (QA #5); `llm_endpoint` SSRF block (QA #6)
- Tests: `test_invalid_query_params_return_400`, `test_limit_clamped_to_5_200`, `test_research_source_timeout_degrades_gracefully`, `test_javascript_url_rejected`, `test_dtd_entity_rejected`
- DoD: mocked offline suite green

**AC-03 — Settings (filled example)**
- Feature: `GET|POST /api/settings`
- Critical: `POST` kabhi plaintext `llm_key` return na kare (QA #1, P9); GET masked `***` pehle se hai
- Tests: `test_settings_no_secret_leak`, `test_llm_endpoint_rejects_internal`, `test_llm_failure_logged_not_swallowed`
- DoD: regression green

Baari features (catalog, reveal, jobs, articles, models) ke poore AC blocks **PHASE 1** mein likhe jayenge — ye P0 scaffold unka dawa nahi karta.

## 10. Edge cases

Khali folder · 4000+ files · depth > 6 · symlink / junction / UNC / remote path · mixed UFS+eMMC loaders · single-LUN UFS · missing image · sector overlap · image > partition · ghalat/tukda XML · feed 404 / timeout · ghalat query param · duplicate GUID · `llm_key = "***"` round-trip · LLM failure · `os.startfile` non-Windows.

## 11. Success metrics

- 2 demo packages (MTK + QCOM) reproducible health report dein.
- Bad input par **zero 500**.
- 13 QA findings band, har aik ka named passing regression test.
- `python -m unittest discover -s tests -v` bina internet / production DB green.
- 7 views load hon, `run.bat` se app chal jaye.
- Docs ↔ code audit clean (P11).

## 12. Open items

O1 skills/MCP shortlist · O2 `llm_key` at-rest encryption · O3 log retention → `decisions.md`.
