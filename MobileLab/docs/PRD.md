# PRD — MobileLab

**Version:** 1.1.0 (PHASE 1 final draft) · **Date:** 2026-11-08 · **Root:** `J:\Ai Agent`
**Status:** PHASE 1 documentation complete; `PHASE REVIEW — PHASE 1` aur final gate `phases.md` mein darj hai.
**Language:** Roman Urdu prose; code, paths, API routes aur technical terms English (C9).

> **Research honesty:** is file mein sirf wo sources hain jo 2026-11-08 ko directly fetch ya official search result se verify kiye gaye. Har fact ke saath URL aur `date checked` hai. **Facts** aur **Recommendations** alag sections mein hain. Market-size ya reseller ke ghair-tasdeeq numbers PRD mein shamil nahi kiye gaye. Koi citation banawati nahi.

---

## 1. Product vision

MobileLab aik **bilkul local** Windows workbench hai jo mobile-software technician ko firmware package flash se pehle atakne se bachata hai — khaas kar MediaTek `preloader` / `scatter` / `DA` aur Qualcomm `EDL` / `Sahara` / `Firehose` / `rawprogram` / `patch` files. Is ke sath aik **research aur task-planning agent** hai jo internet se legal aur verified maloomat la kar **Roman Urdu** mein khulasa, safe plan aur report deta hai. App khud `127.0.0.1` par chalti hai; internet sirf research agent, firmware maloomat aur Telegram Bot API ke liye allowed hai (C11).

**Competitor se aage jane ka matlab:** zyada models ka bypass karna nahi; balkay **pehle se ghalat package pakadna**, har result ka **source/date/hash** ke sath saboot rakhna, aur technician ko **safe, explainable, local** faisla dena — bina paid subscription, cloud lock-in ya device-write automation ke.

## 2. Problem statement

- Technician aksar adhuri ya ghalat firmware package ki wajah se atak jata hai: missing image, chipset se mismatched `preloader`, `UFS` / `eMMC` ka ghalat loader, partition sector overlap, GPT / LUN coverage, ghalat `DA` / auth file.
- Paid suites subscription, account activation aur loader/model database par chalte hain; unki asli value coverage aur update speed hai, na ke local explainability.
- Har model ki latest maloomat kai sites par bikhri hoti hai; zurori information chhaantna aur uska source yaad rakhna mushkil.
- Account / activation locks server-side ownership controls hain. Local tools ya paid tools un server records ko badal nahi sakte; sirf official route + proof-of-ownership kaam karta hai.
- Research agent ko "koi bhi mobile-software task" diya jaye to usay **safe plan/report** dena chahiye, lekin HARD POLICY ke andar: koi device write/erase command aur koi lock bypass steps nahi (C14).

## 3. Target users / personas

**Primary — Mobile software technician**
Windows PC · local firmware folders · ROM / model files banata ya validate karta hai · Roman Urdu mein baat karta hai, technical terms English · paid tools se bachna chahta hai · sab kaam apni PC par chahiye · Telegram se chhote command aur alert chahta hai.

**Secondary — Record keeper**
Model brief, job register, proof-of-ownership aur official route note karta hai; har research item ka source aur date checked chahiye.

**Tertiary — QA / reviewer**
Har phase ka gate, acceptance criteria, regression test aur source register dekhna chahta hai; koi incomplete item nahi chhorhna.

## 4. User journeys

| # | Journey | Aaj / Proposed |
|---|---|---|
| J1 | Dashboard kholte hi counts, health aur tez live news | Aaj (7 views) |
| J2 | Folder path → scan → health report + issues → detail → duplicate check → Explorer | Aaj |
| J3 | Query + filters + sources → live results → Roman Urdu khulasa → article save | Aaj |
| J4 | Model card + sirf official routes | Aaj |
| J5 | IMEI / model / customer / proof / route / notes | Aaj |
| J6 | Boundaries, glossary, official routes, security note | Aaj |
| J7 | Sources, optional LLM endpoint/key/model, scan behavior | Aaj |
| J8 | Research result par URL + `date checked` + fact/recommendation label + local evidence hash | Proposed (P7) |
| J9 | Telegram bot ko command bhejo → local agent result / alert wapas de | Confirmed (C12), proposed P7 |
| J10 | Koi bhi mobile-software task likho → Roman Urdu safe plan + report → HARD POLICY gate | Confirmed (C14), proposed P7 |
| J11 | Legal/authorized deep/dark web source → policy gate → provenance ke sath khulasa | Confirmed (C13), proposed P7 |

> **P3 decision pending:** J8–J11 ke liye naya 8th view ya existing views mein panels — ye `design.md` aur Open question O9 mein hai. P1 code nahi badalta.

## 5. Research — CURRENT LANDSCAPE (facts)

**Method:** `domain_search` se broad synthesis liya gaya, lekin uske low-authority reseller / aggregator price aur market-size claims PRD mein istemal nahi kiye. Neeche sirf official ya directly verified sources hain. Sab ka `date checked = 2026-11-08`.

### 5.1 Competitor / tooling map

| Category | Verified example | Public fact | MobileLab se farq |
|---|---|---|---|
| Commercial all-in-one repair suite | ChimeraTool | Official site claims `15,000+` models, `270+` manufacturers, `10+` modes, `1,520` test points for `29` brands, new models/features every `2 weeks`, **`no hardware box needed`**, subscription/licence tiers. Site publicly advertises FRP-related procedures; is PRD mein unka koi step nahi likha. | Paid, account/licence based, device-operation focused; MobileLab free, local, pre-flash validation + explainability focused. |
| Commercial servicing suite / distributor | UnlockTool distributor | Public distributor page states account-based activation, 3/6/12-month licences, no dongle/box, no per-operation credits, latest listed build `v2026.10.31.0`, multi-brand MTK/QCOM/Unisoc support. Ye vendor-independent verification nahi, public distributor claim hai. | Same category; MobileLab koi activation, credit ya device-operation workflow nahi rakhta. |
| OEM flashing tool | Android Flash Tool (Google) | Official page: installs Android builds on recent Pixel devices and some development devices; needs `10GB` free storage, USB, and extra Windows USB driver. | Authorized but device/chipset narrow; MobileLab cross-vendor package QA karta hai, flash nahi karta. |
| Open-source low-level Qualcomm | `bkerler/edl` | GitHub API description: `Inofficial Qualcomm Firehose / Sahara / Streaming / Diag Tools :)`; Python; GPL-3.0; `2,692` stars; `pushed_at 2026-09-19`; default branch `master`. | Low-level read/write capable; MobileLab stdlib-only, read/validate only, koi device write nahi. |
| Open-source low-level MediaTek | `bkerler/mtkclient` | GitHub API description: `Mediatek Flash and Repair Utility`; Python; GPL-3.0; `1,456` stars; `pushed_at 2026-10-26`; default branch `main`. | Same boundary; MobileLab isko dependency ke taur par import nahi karta. |
| Enterprise firmware / supply-chain security | Binarly | Official positioning: binary-level product security for firmware; inspects built binary, validates SBOM/CBOM, detects tampering/secrets/malicious code, CI/CD release gates. | Enterprise vulnerability platform; MobileLab technician ki pre-flash readiness aur local case record par focus karta hai. |
| Enterprise software supply-chain visibility | NetRise | Official positioning: software asset inventory, compiled-artifact analysis, SBOM/CBOM, vulnerability and supplier risk, policy/incident response. | Enterprise SBOM/risk platform; MobileLab chhota local workbench hai. |

**Result:** koi bhi verified tool aik hi jagah **local + zero-dependency + MTK/QCOM pre-flash validation + Roman Urdu research + provenance + safe task plan + official-route records** nahi deta. Ye gap MobileLab ka target hai. Ye **recommendation / positioning** hai, koi independent market-share claim nahi.

### 5.2 Platform, legal aur integration facts

| Topic | Verified fact | Project par asar |
|---|---|---|
| Verified Boot | AOSP: chain of trust from hardware root to bootloader and verified partitions; rollback protection ensures devices only update to newer Android versions. | Firmware downgrade / mismatched package ko high-risk flag karna chahiye; koi rollback bypass nahi. |
| Play Integrity | Google: API checks that actions come from unmodified app binary installed by Google Play and running on a genuine Android device. | "Genuine device / integrity" claims ko sirf read-only verification tak rakho; koi spoofing nahi. |
| Activation Lock | Apple: device contacts Apple activation servers; Apple Account securely stored and linked to device; password required to turn off Find My, erase or reactivate. | Server-side ownership control; local tool isay badal nahi sakta. |
| FRP / Google Device Protection | Samsung official support: unauthorized factory reset demands most recently used Google account; official routes are account recovery, password reset, service center with proof of purchase. | Job register mein proof-of-ownership aur official route note lazmi. |
| Telegram Bot API | HTTPS `https://api.telegram.org/bot<token>/METHOD_NAME`; `getUpdates` long polling; `limit` 1–100; updates retained no longer than 24 hours; `getUpdates` aur webhook mutually exclusive; `message` aur `channel_post` alag fields; supplied excerpt mein historical public-channel-post fetch documented nahi. | C12: bot command + alert; purani public channel history ka dawa nahi; P7 mein adapter layer. |
| Deep web / dark net | BSI: clear web chhota hissa; deep web approx. `90%` non-indexed, password/paid/company content; dark net chhota subset requiring special software such as Tor; browsing dark net alone illegal nahi, lekin illegal content/download/goods/services illegal; malware risk zyada. | C13: sirf legal, public/authorized sources; koi illegal marketplace, stolen credential, leaked firmware ya bypass service nahi. |
| Right to Repair | EUR-Lex: Directive (EU) 2024/1799 dated 13 June 2024; Member States apply measures from `31 July 2026`; goal promote repair of goods and sustainable consumption. | Independent repair demand ka regulatory signal; future outlook mein assumption ke taur par likha hai, revenue claim nahi. |
| SSRF | OWASP: prefer allowlists; validate scheme/host/IP; block private, loopback, link-local, metadata ranges; disable redirects; bind connection to validated IP. | `llm_endpoint`, Telegram endpoint aur research URL fetch par P9 security gate lazmi. |

### 5.3 Source register

| ID | Source | URL | Date checked | Used for |
|---|---|---|---|---|
| S1 | ChimeraTool official homepage | `https://chimeratool.com/` | 2026-11-08 | coverage, update cadence, no-box, licence model |
| S2 | ChimeraTool English page | `https://chimeratool.com/en/` | 2026-11-08 | public product update claims; no procedure copied |
| S3 | UnlockTool public distributor page | `https://unlocktool.org/` | 2026-11-08 | account-based licence, durations, no dongle |
| S4 | Android Flash Tool | `https://flash.android.com/` | 2026-11-08 | OEM flashing boundary |
| S5 | GitHub API `bkerler/edl` | `https://api.github.com/repos/bkerler/edl` | 2026-11-08 | open-source Qualcomm tooling metadata |
| S6 | GitHub API `bkerler/mtkclient` | `https://api.github.com/repos/bkerler/mtkclient` | 2026-11-08 | open-source MediaTek tooling metadata |
| S7 | Binarly official | `https://www.binarly.io/` | 2026-11-08 | enterprise firmware security category |
| S8 | NetRise official | `https://www.netrise.io/` | 2026-11-08 | enterprise supply-chain visibility category |
| S9 | Telegram Bot API | `https://core.telegram.org/bots/api` | 2026-11-08 | Bot API limits and update model |
| S10 | BSI dark net / deep web | `https://www.bsi.bund.de/EN/Themen/Verbraucherinnen-und-Verbraucher/Informationen-und-Empfehlungen/Darknet-und-Deep-Web/darknet-und-deep-web_node.html` | 2026-11-08 | definitions, legality, malware risk |
| S11 | AOSP Verified Boot | `https://source.android.com/docs/security/features/verifiedboot` | 2026-11-08 | rollback protection, chain of trust |
| S12 | Play Integrity API | `https://developer.android.com/google/play/integrity` | 2026-11-08 | genuine-device integrity check |
| S13 | Apple Activation Lock | `https://support.apple.com/en-us/108794` | 2026-11-08 | server-side ownership control |
| S14 | Samsung Google Device Protection | `https://www.samsung.com/ca/support/mobile-devices/google-device-protection-on-your-galaxy-device/` | 2026-11-08 | FRP official route |
| S15 | EUR-Lex Directive 2024/1799 | `https://eur-lex.europa.eu/eli/dir/2024/1799/oj/eng` | 2026-11-08 | right-to-repair application date |
| S16 | OWASP SSRF Prevention | `https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html` | 2026-11-08 | outbound endpoint security expectations |

## 6. Research — FUTURE OUTLOOK (2–5 saal)

**Facts (upar S9–S16 se):** hardware-backed Verified Boot / rollback protection aaj maujood hai; Play Integrity genuine-device check karta hai; Activation Lock server-side linked hai; EU repair rules 31 July 2026 se apply hote hain; Telegram updates 24 ghante se zyada nahi rakhe jate; dark net par malware aur illegal-content risk zyada hai.

**Assumptions (fact nahi):**
- A1: hardware-backed integrity aur anti-rollback aane wale 2–5 saal mein aur zyada models par phailenge; is liye "bypass" par based products ka legal/technical scope aur chhota hoga.
- A2: right-to-repair aur second-hand/refurbish workflow independent technicians ke liye **verification, provenance aur record keeping** ki demand barhayenge; ye revenue forecast nahi.
- A3: paid suites apna subscription + loader/model database model jari rakhenge; update speed unki moat rahegi.
- A4: Bot API ya feed schemas badal sakte hain; is liye adapter layer aur offline degradation chahiye.
- A5: LLM/agent se hallucination, prompt injection, SSRF aur secret leakage ka risk rahega; is liye source provenance aur policy gate chahiye.

**Recommendations (Decision, fact nahi):**
- MobileLab ko **bypass / device-write race** mein nahi jana; HARD POLICY kabhi na todein.
- Differentiation: pre-flash validation, explainable checks, hash/provenance, Roman Urdu, local-only, official-route job records, Telegram alerts, safe task plan/report.
- Stdlib-only rakhein; Telegram ke liye `urllib.request` + Bot API, koi MTProto/TDLib/Telethon dependency nahi.
- Har research item mein `source_url`, `date_checked`, `fact_or_recommendation`, `confidence` aur local `sha256` evidence ho.
- Deep/dark web sirf legal/authorized allowlist se; koi download execute na ho; koi credential, leaked firmware ya bypass service na ho.
- P2/P7/P9 mein adapter, threat model aur regression tests pehle likhein, code baad mein.

## 7. Classification

**Confirmed:** C1–C10 `decisions.md` mein · C11 local runtime + internet sirf agent/firmware · C12 Telegram Bot command/alert · C13 legal/authorized deep/dark web only · C14 any mobile task → safe plan/report under HARD POLICY · C15 step-by-step phases, kuch incomplete na chhorhein · C16 har fact ke saath URL + `date checked`, facts vs recommendations alag.

**Assumptions:** P1 A1 docs Roman Urdu + English headings · A2 verbatim block P0 se · A3 tests production DB/live internet na chhuyein · A4 `.gitignore` secrets/DB/logs ignore · A5 neutral local git identity · A6 responsive single-column fallback · A7 migration strategy P6 · A8 Bot API `getUpdates` pehle, webhook baad mein agar user maange · A9 research sources user-editable allowlist se, arbitrary URL nahi.

**Open questions (critical implementation se pehle, P1 ko nahi rokte):**
- O1 skills/MCP shortlist · O2 `llm_key` / bot token at-rest encryption · O3 log retention · O4 Telegram token storage/rotation aur rate-limit policy · O5 legal deep/dark web source allowlist kaun approve kare · O6 task plan rule-based vs optional LLM rewrite · O7 public channel history chahiye to Bot API se bahar ka legal/technical faisla · O8 firmware provenance hash policy · O9 J8–J11 ke liye naya view ya existing panels · O10 optional LLM endpoint aur Telegram endpoint ke liye common SSRF allowlist.

**Risks:** R1 verbatim drift (mitigated) · R2 banawati citations (P1 source register se mitigated; P2 final) · R3 security fixes workflow tod dein · R4 doc drift · R5 default scan restriction · R6 Telegram token leak / 24h update loss · R7 illegal research source / malware · R8 task planner HARD POLICY se bahar step de de · R9 competitor claims outdated ho jayein · R10 AI hallucination ko fact mana jaye.

## 8. Functional requirements

| ID | Requirement | Status | Source / phase |
|---|---|---|---|
| FR-01 | MTK `scatter` parse + `preloader` / chipset / storage / DA / partition checks | Aaj | `firmware.py` |
| FR-02 | Qualcomm Firehose, `rawprogram*.xml`, `patch*.xml`, GPT, LUN, sector overlap, image-size checks | Aaj | `firmware.py` |
| FR-03 | `SENSITIVE_PARTITIONS` sirf flag, kabhi write/erase nahi | Aaj / HARD POLICY | `firmware.py` |
| FR-04 | Package health score + issues + checks | Aaj | `firmware.py:validate()` |
| FR-05 | Package catalog, file fingerprint, duplicate detection, delete | Aaj | `db.py`, `server.py` |
| FR-06 | Live research: RSS/Atom, Google News, HN Algolia, GitHub Releases + filters | Aaj | `research.py` |
| FR-07 | Rule-based Roman Urdu `khulasa`; optional OpenAI-compatible rewrite | Aaj | `research.py` |
| FR-08 | Saved articles, model cards, job register, settings | Aaj | `db.py`, `server.py` |
| FR-09 | Static knowledge base: boundaries, official routes, glossary | Aaj | `knowledge.py` |
| FR-10 | `/api/reveal` se scanned folder Explorer mein kholna | Aaj | `server.py` |
| FR-11 | 7-view light-theme UI, hash routing, loading/empty/error/success states | Aaj | `web/*` |
| FR-12 | One-click launcher | Aaj | `run.bat` |
| FR-13 | Internet research with provenance: URL, `date checked`, fact/recommendation label, source diagnostics | Proposed | C16 / S1–S16 / P7 |
| FR-14 | Telegram Bot API: user-supplied token, command intake, local result/alert, no historical channel scrape | Confirmed / Proposed | C12 / S9 / P7 |
| FR-15 | Legal/authorized deep/dark web research gate; illegal sources reject; no download execution | Confirmed / Proposed | C13 / S10 / P7 |
| FR-16 | Any mobile-software task → Roman Urdu safe plan + report; HARD POLICY gate; no device write/erase | Confirmed / Proposed | C14 / P7 |
| FR-17 | Official-route + proof-of-ownership job workflow | Aaj / Expand | S13, S14 / P6 |
| FR-18 | Local evidence log: `sha256`, timestamp, source type, saved article link | Proposed | C16 / P7 |
| FR-19 | Offline-first core: app local; internet sirf research/firmware/Telegram; graceful degradation | Confirmed | C11 / P7 |
| FR-20 | Security/QA gates: 13 QA findings, stdlib `unittest`, 12 phase reviews | Aaj docs / Pending code | `phases.md` |

## 9. Non-functional requirements

- **Local-only runtime:** `127.0.0.1:8765`, `ThreadingHTTPServer`, koi cloud deploy / telemetry / remote nahi (C11).
- **Internet boundary:** sirf research agent, firmware/provenance information aur Telegram Bot API; arbitrary outbound URL default `OFF`.
- **Zero dependency:** sirf Python standard library; koi `pip install` nahi. Telegram ke liye bhi stdlib `urllib.request`.
- **Storage:** SQLite WAL, `foreign_keys=ON`, 6 tables aaj; evidence/provenance tables P7 ADR.
- **Zaban:** Roman Urdu prose; code / paths / API terms English (C9).
- **Jagah:** har project file `J:\Ai Agent` mein (C10).
- **Limits:** `MAX_FILES=4000`, `MAX_DEPTH=6`, feed `TIMEOUT=10`, pool 8–16, `limit` 5–200; Telegram `getUpdates.limit` 1–100.
- **Theme:** light; `lang="ur-PK-Latn"` re-evaluate P9 ADR.
- **Security:** loopback, static allowlist, `nosniff`, `no-store`; baqi 13 QA findings P6/P9.
- **Provenance:** har research fact ka URL + `date checked`; har recommendation ka label; koi speculation ko fact na likha jaye.
- **Legal research:** BSI boundary; koi illegal content, stolen credential, leaked firmware, bypass marketplace ya malware nahi.

## 10. Must-have / Nice-to-have / Out-of-scope

**Must-have:** FR-01…FR-20, HARD POLICY, official-route KB, C11–C16, 12 phase gates, source register, full acceptance criteria.

**Nice-to-have (P7+):** optional LLM rewrite, Telegram webhook, export/report share, offline cache tuning, model-coverage matrix UI, research confidence score.

**Out-of-scope — HARD POLICY:**
- Huawei ID, Google FRP, Samsung Account / Knox Guard, MDM, carrier lock, iCloud Activation Lock ka **koi bypass automation ya step-by-step tareeqa**.
- Koi script / command jo `frp`, `persistent`, `config`, `devinfo`, `modemst1/2`, `nvram`, `nvdata`, `nvcfg`, `seccfg`, `proinfo`, `metadata` jaise identity / ownership / anti-theft partitions ko erase ya write kare.
- Device flashing, bootloader unlock/relock, IMEI repair, screen-lock removal, firmware patching ya low-level read/write automation.
- Illegal deep/dark web marketplaces, stolen credentials, leaked/proprietary firmware, bypass services, malware, private databases, ya koi bhi unauthorized access.
- Cloud deploy, multi-user auth, tenant isolation, paid-tool integration, naya third-party dependency, MTProto/TDLib/Telethon.

## 11. User stories

- **US-01** — Technician ke tor par main ek firmware folder scan karna chahta hoon taake flash se pehle missing / mismatched files ka pata chal jaye.
- **US-02** — Technician ke tor par main Qualcomm `rawprogram` mein sector overlap aur image-size ghalti dekhna chahta hoon.
- **US-03** — Technician ke tor par main latest mobile-software news Roman Urdu mein chhaantna chahta hoon.
- **US-04** — Technician ke tor par main kisi locked device ke liye **sirf official** route aur proof-of-ownership note karna chahta hoon.
- **US-05** — Technician ke tor par main apne scans ka local catalog aur duplicate check rakhna chahta hoon.
- **US-06** — Technician ke tor par main har research result ka URL, `date checked` aur fact/recommendation label dekhna chahta hoon.
- **US-07** — Technician ke tor par main Telegram se command bhej kar result ya alert lena chahta hoon.
- **US-08** — Technician ke tor par main koi bhi mobile-software task likh kar safe Roman Urdu plan/report lena chahta hoon.
- **US-09** — Reviewer ke tor par main dekhna chahta hoon ke koi bhi dark/deep web source legal aur authorized allowlist se bahar na jaye.
- **US-10** — QA ke tor par main chahta hoon ke har feature ka acceptance criteria aur passing regression test ho.

## 12. Acceptance criteria

> Har block mein `Feature / User story / Preconditions / Expected behavior / Validation rules / Error cases / Empty state / Loading state / Success state / A11y / Security / Performance / Test cases / Definition of done` milta hai. Proposed features ke tests P8/P9 mein banenge; P1 sirf criteria finalize karta hai.

### AC-01 — Firmware package scan / validation (F-01: FR-01…FR-04)
- Feature: `POST /api/scan` + `firmware.validate()`.
- User story: US-01, US-02.
- Preconditions: local folder maujood, `MAX_FILES`/`MAX_DEPTH` ke andar, Python 3.10+.
- Expected: `health` 0–100, `issues`, `checks`, `counts`, package DB mein save; sensitive partitions sirf flagged.
- Validation: `path` lazmi; default workspace; bahar ke liye explicit `allow_outside: true`; XML `DOCTYPE`/`ENTITY` reject; numeric params safe parse.
- Error cases: ghalat path `400` JSON; kharab XML `400`/safe issue; timeout/cap `413`/`429` policy; kabhi `500` ya stack trace nahi.
- Empty: khali folder → valid report + `health` + info issue.
- Loading: UI `busy()` spinner.
- Success: toast + list mein naya package + auto-select.
- A11y: labels, keyboard submit, `aria-live` toast (P9).
- Security: `realpath` + `commonpath`, symlink/junction/UNC reject, authz pehle `exists()` baad; koi write/erase nahi.
- Performance: 4000 files / depth 6 cap; fingerprint 512 KiB chunks.
- Tests: `test_scan_valid_mtk_package_happy_path`, `test_scan_valid_qcom_package_happy_path`, `test_scan_outside_denied_by_default`, `test_scan_outside_allowed_with_flag`, `test_file_count_boundary_4000`, `test_dtd_entity_rejected`.
- DoD: sab tests green + `run.bat` manual smoke.

### AC-02 — Catalog, duplicate, reveal, delete (F-02: FR-05, FR-10)
- Feature: `/api/packages`, `/api/packages/<id>`, `DELETE`, `/api/reveal`.
- User story: US-05.
- Preconditions: kam az kam aik scanned package; Explorer Windows par.
- Expected: list, detail, duplicate matches, delete, scanned folder reveal.
- Validation: numeric `id`; `path` allowlist; delete confirmation.
- Error cases: not-found `404`; unauthorized path `403`; non-Windows `os.startfile` guard; DB busy → safe JSON error.
- Empty: `Koi package nahi; pehle scan chalayein.`
- Loading: list/detail skeleton.
- Success: toast + counts refresh.
- A11y: buttons keyboard reachable, destructive confirm dialog.
- Security: `commonpath` sibling-prefix bypass block; koi absolute DB path client ko nahi.
- Performance: `/api/packages` paginated `limit`/`offset`; `save_package` aik transaction.
- Tests: `test_packages_paginated`, `test_package_delete_not_found`, `test_reveal_rejects_sibling_prefix`, `test_duplicate_guid_is_idempotent`, `test_save_package_single_txn`.
- DoD: regression green + Explorer smoke.

### AC-03 — Research agent + filters + Roman Urdu khulasa (F-03: FR-06, FR-07)
- Feature: `GET /api/research`, `/api/sources`, saved articles.
- User story: US-03.
- Preconditions: selected sources reachable ya offline mode.
- Expected: filtered/scored items + Roman Urdu `khulasa` + source diagnostics; optional LLM rewrite.
- Validation: `days`, `min_score`, `limit` numeric; ghalat value `400`; `limit` 5–200 clamp; sirf `http`/`https` links render.
- Error cases: feed `404`/timeout → graceful degradation; LLM failure log + rule-based fallback; koi swallowed exception nahi.
- Empty: koi match na ho → saaf empty state.
- Loading: skeleton + per-source status.
- Success: cards + count + save button.
- A11y: links readable, focus styles, `aria-live` for result count.
- Security: XML hardening, `safe_url`, `llm_endpoint` SSRF block, no raw feed URL in `href` without validation.
- Performance: `TIMEOUT=10`, pool 8–16, bounded cache.
- Tests: `test_invalid_query_params_return_400`, `test_limit_clamped_to_5_200`, `test_research_source_timeout_degrades_gracefully`, `test_javascript_url_rejected`, `test_llm_failure_logged_not_swallowed`.
- DoD: mocked offline suite green.

### AC-04 — Articles, model brief, jobs, settings, knowledge (F-04: FR-08, FR-09)
- Feature: CRUD endpoints + static KB.
- User story: US-04, US-05.
- Preconditions: DB initialized.
- Expected: saved articles, model cards, job records, masked settings, boundary/official-route KB.
- Validation: required fields; `llm_key="***"` round-trip preserve; SQL identifier allowlist.
- Error cases: validation `400`, not-found `404`, duplicate article idempotent, no stack trace.
- Empty: har list ka Roman Urdu empty state.
- Loading: form busy + list skeleton.
- Success: toast + refresh.
- A11y: labels, error text associated, keyboard forms.
- Security: `POST /api/settings` kabhi plaintext `llm_key` return na kare; no secret in logs; HARD POLICY KB read-only.
- Performance: indexes on `articles.fetched_at`, `package_files.fingerprint`.
- Tests: `test_settings_no_secret_leak`, `test_article_action_allowlist`, `test_model_upsert`, `test_job_validation_failure`, `test_list_packages_empty_db`.
- DoD: regression green + docs match.

### AC-05 — 7-view UI + launcher (F-05: FR-11, FR-12)
- Feature: `web/*`, `run.bat`.
- User story: US-01…US-05.
- Preconditions: Python 3.10+ on PATH; `run.bat` from `J:\Ai Agent\MobileLab`.
- Expected: 7 views, hash routing, responsive single-column fallback, app `127.0.0.1:8765`.
- Validation: Python version guard P4; static allowlist; `node --check web/app.js`.
- Error cases: missing Python → clear message; missing asset `404`; API down → error state.
- Empty / Loading / Success: har view par documented states.
- A11y: `aria-current`, `aria-live`, tab/tabpanel roles, decorative `aria-hidden`, focus-visible (P9).
- Security: CSP, `X-Frame-Options`, `Referrer-Policy`, `nosniff`, `no-store`, body cap `413`.
- Performance: no CDN/external font; light theme; `prefers-reduced-motion`.
- Tests: `test_a11y_markup`, `test_security_headers_present`, `test_body_size_cap_413`, `test_unknown_api_returns_404`.
- DoD: `run.bat` smoke + 7-view screenshot/manual check.

### AC-06 — Research provenance / evidence log (F-06: FR-13, FR-18)
- Feature: source register in PRD + proposed local evidence records in P7.
- User story: US-06, US-10.
- Preconditions: research item fetch hua ho; allowed source URL.
- Expected: har item ke sath `source_url`, `date_checked`, `fact_or_recommendation`, `source_type`, `sha256`, `fetched_at`; PRD source register S1–S16.
- Validation: URL scheme `http`/`https` only; missing URL/date → item `unverified` label; recommendations kabhi `fact` label na paayein.
- Error cases: source deleted/redirect → old evidence retain + new status; hash mismatch → warn.
- Empty: `Koi verified source nahi; offline result ko verified na samjhein.`
- Loading: provenance badge `checking`.
- Success: badge `verified 2026-11-08` + copyable citation.
- A11y: badge text, not color-only; keyboard-copy.
- Security: no private data in evidence; SSRF allowlist; no arbitrary redirect follow.
- Performance: one hash per item; bounded evidence table.
- Tests: `test_research_item_has_source_and_date`, `test_recommendation_not_labeled_fact`, `test_unverified_item_empty_state`, `test_evidence_hash_mismatch_warns`.
- DoD: S1–S16 docs ↔ evidence UI audit clean.

### AC-07 — Telegram Bot command / alert (F-07: FR-14)
- Feature: Bot API adapter, `getUpdates`, `sendMessage`, local command handler, alert toggle.
- User story: US-07.
- Preconditions: user ne apna bot token local settings mein diya ho; internet available; webhook `OFF`.
- Expected: command → local safe action → Roman Urdu result; scheduled/manual alert → `sendMessage`; token kabhi plain text return/log na ho.
- Validation: HTTPS `api.telegram.org/bot<token>/METHOD_NAME` only; `getUpdates.limit` 1–100; `offset` recalculated; `message` vs `channel_post` alag; command allowlist.
- Error cases: invalid token `401` → safe message; webhook set → `getUpdates` conflict clear; 24h update loss → no false history claim; network down → local queue + retry; unknown command → help.
- Empty: `Koi naya update nahi.`
- Loading: `Bot se update la rahe hain...`.
- Success: `Result bhej diya gaya` + local log.
- A11y: settings labels, token masked, status text.
- Security: token encrypted/protected per O2; no token in URL logs; no arbitrary URL; SSRF allowlist; rate-limit/backoff; no public-channel history scrape.
- Performance: long-poll timeout bounded; batch 1–100; no busy loop.
- Tests: `test_telegram_token_never_returned`, `test_getupdates_webhook_conflict`, `test_channel_post_not_history`, `test_telegram_invalid_token_401`, `test_telegram_unknown_command_help`.
- DoD: mocked Bot API suite green + one live token-free dry run.

### AC-08 — Legal/authorized deep/dark web research gate (F-08: FR-15)
- Feature: research source policy engine + allowlist + legal warning.
- User story: US-09.
- Preconditions: source URL, purpose, authorization note.
- Expected: legal/public/authorized source allowlist se hi fetch; BSI definitions aur warning UI mein; illegal content kabhi fetch/store na ho.
- Validation: scheme, host, allowlist, category; `illegal`, `stolen-credential`, `leaked-firmware`, `bypass-service`, `malware`, `private-db` tags reject.
- Error cases: unauthorized source `403` + reason; Tor-only URL without approved adapter → `not configured`; malware download → blocked before write.
- Empty: `Koi approved deep/dark source nahi.`
- Loading: policy-check spinner.
- Success: `Legal/authorized` badge + provenance.
- A11y: warning text readable, not icon-only.
- Security: no credentials, no downloaded executable, no arbitrary Tor automation, no private data, no bypass marketplace.
- Performance: policy check before network; no bulk crawl.
- Tests: `test_illegal_source_rejected`, `test_unauthorized_source_403`, `test_tor_url_requires_approved_adapter`, `test_policy_check_before_fetch`, `test_no_executable_download`.
- DoD: policy tests green + BSI boundary doc review.

### AC-09 — Any mobile-software task → safe plan/report (F-09: FR-16)
- Feature: task intake, HARD POLICY classifier, Roman Urdu plan/report renderer.
- User story: US-08.
- Preconditions: user ne task text diya; optional model/firmware context.
- Expected: task summary, known facts with sources, assumptions, open questions, risks, safe next steps, official-route pointer; **koi device write/erase ya bypass step nahi**.
- Validation: input length cap; HARD POLICY keyword + semantic gate; every fact sourced; recommendations labeled; Roman Urdu output.
- Error cases: prohibited request → refusal + official route; missing context → open questions; LLM failure → rule-based plan; source unavailable → `unverified`.
- Empty: `Task likhein; abhi koi plan nahi.`
- Loading: `Plan bana rahe hain...`.
- Success: copyable plan + evidence list + `HARD POLICY: safe` badge.
- A11y: headings, copy button keyboard, status text.
- Security: no command execution from plan; no credential request; no SSRF; no private data in logs.
- Performance: rule-based plan under bounded time; optional LLM timeout.
- Tests: `test_task_plan_is_roman_urdu`, `test_bypass_request_refused`, `test_plan_has_fact_assumption_risk_sections`, `test_plan_never_emits_write_command`, `test_llm_failure_rule_based_fallback`.
- DoD: policy suite green + sample 10 tasks manual review.

### AC-10 — Official-route / proof-of-ownership workflow (F-10: FR-17)
- Feature: job register + model brief + knowledge base.
- User story: US-04.
- Preconditions: model/IMEI/customer fields; proof-of-ownership checkbox.
- Expected: job record, official route note, no bypass instruction; Apple / Samsung / carrier / manufacturer route pointer.
- Validation: proof flag required for lock-related job; `route` enum official only; no free-text bypass steps stored.
- Error cases: missing proof → validation; unknown model → open question; banned route → `403` + HARD POLICY.
- Empty: `Koi job nahi; naya record banayein.`
- Loading: form busy + table skeleton.
- Success: toast + record + official route summary.
- A11y: required markers, error text, keyboard table.
- Security: no IMEI/customer data in logs; local DB only; `.gitignore` data ignore.
- Performance: indexed jobs; paginated list.
- Tests: `test_job_validation_failure`, `test_unofficial_route_rejected`, `test_proof_required_for_lock_job`, `test_no_imei_in_logs`.
- DoD: regression green + S13/S14 route review.

### AC-11 — Offline/local-only + security/QA (F-11: FR-19, FR-20)
- Feature: runtime boundary, 13 QA fixes, stdlib `unittest`, 12 gates.
- User story: US-10.
- Preconditions: clean local checkout; no network for tests.
- Expected: core scan/catalog/KB/settings offline; research/Telegram gracefully degraded; 13 QA findings closed; 12 `PHASE REVIEW` `READY`.
- Validation: no remote, no cloud, no `pip install`, no live internet in tests, all files under `J:\Ai Agent`.
- Error cases: network down → local core still works; bad input → `400` not `500`; secret leaks → regression fails.
- Empty: fresh DB empty states.
- Loading: documented per view.
- Success: `python -m unittest discover -s tests -v` green + `git status` clean.
- A11y: P9 checklist green.
- Security: OWASP SSRF, CSP, path allowlist, secret masking, XML hardening, no stack traces.
- Performance: bounded cache/pagination; feed timeout; scan caps.
- Tests: poora `tests\*` suite + `py_compile` + `node --check` + `run.bat` smoke.
- DoD: P11 final audit clean, no incomplete phase item.

## 13. Edge cases

Khali folder · 4000+ files · depth > 6 · symlink / junction / UNC / remote path · mixed UFS+eMMC loaders · single-LUN UFS · missing image · sector overlap · image > partition · ghalat/tukda XML · feed 404 / timeout · ghalat query param · duplicate GUID · `llm_key="***"` round-trip · LLM failure · `os.startfile` non-Windows · Telegram token missing/invalid · webhook already set · 24h update expiry · `channel_post` ko history samajhna · unknown bot command · offline queue · illegal deep/dark URL · Tor-only URL without approved adapter · malicious download · task plan me prohibited request · source URL missing · recommendation ko fact likhna · hash mismatch · competitor page language/region change · PRD source outdated.

## 14. Success metrics

- S1–S16 ke 100% facts ka URL + `date checked = 2026-11-08` maujood; facts aur recommendations 100% alag.
- HARD POLICY violations: `0` — koi bypass step, write/erase command ya illegal source PRD/docs/code mein nahi.
- 12/12 `PHASE REVIEW` gates `READY`; koi phase incomplete nahi (C15).
- 13/13 QA findings band, har aik ka named passing regression test.
- `python -m unittest discover -s tests -v` bina internet / production DB green.
- 7 views + proposed J8–J11 flows load hon; `run.bat` se app chal jaye.
- Telegram token kabhi plaintext API response, log ya doc mein na ho.
- Core scan/catalog/KB/settings offline bhi kaam karein; research/Telegram offline par safe degrade.
- Docs ↔ code audit clean (P11); sab project files `J:\Ai Agent` mein (C10).

## 15. Open items / next gate

O1–O10 upar `decisions.md` mein. **PHASE 2** ka kaam: in sources ko technology-selection table se jorna, adapter boundaries finalize karna, aur `architecture.md` ko verified citations ke sath final karna. P1 ka code koi change nahi karta.
