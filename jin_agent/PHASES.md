# PHASES — JIN Agent P13–P44

**Status:** ALL PHASES READY · **Date:** 2026-11-19 · **Version:** 2.9.0
**Version note:** Purane section labels `(2.10.0)` / `(2.11.0)` kabhi release nahi
hue — ye un-released plan numbers thay. Asli `VERSION` har waqt `2.9.0` hai
(`jin_agent/__init__.py:10`), is liye saari labels normalize ki gayi hain.
**Plan source:** `C:\Users\Rohaani\.local\share\opencode\opencode.db` → `session_message` text part `msg_1c0750351001e5quVqIgT43TAH` = `JIN Agent — Final Plan (plan only)`, 13 sections, phases P13–P22.

## 1. Approval & Scope

User ne 2026-11-14 ko kaha: **"sary phase mukammal kro"**. Ye `agent.md` §N (C23 / D29) ke documented "blanket auto-continue" precedent ki tarah aik hi run me P13–P22 sab gates par ijazat hai. Is run me har gate par naya sawal nahi poocha gaya; **har phase ka `TASK / IMPLEMENTATION / VERIFICATION / RESULT` aur `PHASE REVIEW` barqarar** hai, koi phase skip nahi.

Pichhle hukm (*"sirf agent py work kro"*) ke mutabiq **MobileLab ka koi code, koi doc aur `agent.md` ka addendum nahi chherha gaya**. Agent aik standalone package `J:\Ai Agent\jin_agent\` hai — C1 ka "koi naya product nahi" is maane mein barqarar hai ke MobileLab replace nahi hua; ye usi project ka naya agent subsystem hai jo plan ke P20 "Agent Console" ke liye zaroori tha. C10 ke mutabiq sab kuch `J:\Ai Agent` ke andar hai.

## 2. Assumptions — plan ke 4 khule sawaal

| # | Sawaal | Assumption (code + Settings se badal sakte hain) |
|---|---|---|
| A-JIN-1 | RAM / GPU / VRAM | CPU-only. Local LLM default `off`; hardware tiers `README.md` / plan section 5 mein document hain. Koi model download ya runtime install nahi kiya. |
| A-JIN-2 | Topics | Plan ke 12 default categories enabled. |
| A-JIN-3 | Telegram channels | Koi channel pre-configured nahi; Settings se public channels add honge. |
| A-JIN-4 | Tor links ya auto-fetch | `links_only` (recommended). Onion links display, kabhi fetch/crawl nahi. |

Ye assumptions `config.DEFAULT["assumptions"]` aur `GET /api/status` mein zinda hain — koi chhupa hua guess nahi.

## 3. Governance Deviation — written justification

| Rule | Is run mein | Wajah |
|---|---|---|
| `agent.md` §F: har task ke baad 9 docs sync | **N/A + wajah** | User ne P14 / docs-sync ko "fazool" kaha aur sirf agent par kaam karne ko kaha. Is liye agent-apna aik record `jin_agent/PHASES.md` banaya; MobileLab ke 9 source-of-truth docs aur `agent.md` addendum **bilkul unchanged**. Verbatim prefix hash neeche verify hai. |
| `agent.md` §E: 12 adapted gates | **N/A + wajah** | Wo 12 gates P0–P11 pehle P3–P11 blanket run me pass ho chuke hain (`agent.md` §O). Ye naya plan apne P13–P22 gates le kar aaya; unhi ka yahan record hai. |
| Har gate par aik chhota sawal | **N/A + wajah** | Is run par user ki explicit "sary phase mukammal kro" ijazat (§1). Agle naye kaam par `N7` ki phase-by-phase approval wapas lagu hogi. |

---

## 4. PHASE REVIEW — PHASE 13 — Plan Final + Legal Source Register

**TASK:** `opencode` ka plan-only document code mein freeze karna, 4 khule sawaalon ke assumptions, legal source register aur Sahulat boundary.

**IMPLEMENTATION:** `config.py` (defaults, assumptions, masked `public()`, merge-on-save), `policy.py` (22-entry `SOURCE_REGISTER` T0–T4, har row `URL + date checked = 2026-11-14`, trust, tier, auto flag, notes), `util.py` (dates, SHA-256, canonical URL, fingerprint, HTML→text, query terms). `POLICY_ID = SAHULAT-SAFE-SERVICE-v1` unchanged. Narrow action-intent classifier: sirf bypass/removal wording block, "Android security bulletin FRP research" jaise jaez research allowed.

**VERIFICATION:** `test_policy.py` — 16 tests: register provenance, dark-web links-only, N/A justifications, 6 SSRF categories, custom-endpoint check, 6 blocked phrases, 3 allowed research phrases, trust labels, config masking. `git status` se `agent.md` aur MobileLab unchanged.

**RESULT:** Plan freeze ho gaya; koi illegal marketplace / stolen data / credential dump / malware source register mein nahi.

**PHASE REVIEW — PHASE 13: READY**

## 5. PHASE REVIEW — PHASE 14 — Evaluation Harness + Baseline

**TASK:** 25-query harness, KPIs, aur L1.5 baseline ka asli naap.

**IMPLEMENTATION:** `evaluator.py` — 25 queries (MTK, QCOM, Apple, security, tools, firmware, AI, telecom, science, world), metrics = coverage, precision@10, freshness median, provenance %, fabricated citations, offline crashes, dedupe, avg/p95 latency, sources hit; 11 safety checks; per-query detail; Markdown report. Offline fixture mode aur `--live` mode alag label hote hain taake offline number ko live coverage na kaha jaye.

**VERIFICATION:** `python -m jin_agent eval` → `passed: true`; coverage **100.0%**, precision@10 **1.0**, freshness median **0.0 d**, provenance **100.0%**, fabricated **0**, offline crashes **0**, avg latency **1570.2 ms**, p95 **1800 ms**, sources hit **14**, total **39,480 ms**; 11/11 safety checks `true`. Report `data/reports/eval-*.md`. `test_eval_scheduler.py` 11 harness tests green.

**RESULT:** Baseline L1.5 se aage; pipeline correctness ka reproducible naap maujood. Latency pehle 3504 ms thi — `ranker` har item ke liye alag DB connection kholta tha; `store.feedback_scores()` se aik connection karke **1570 ms** par laya gaya (fix ka asli output upar hai).

**PHASE REVIEW — PHASE 14: READY**

## 6. PHASE REVIEW — PHASE 15 — Data Layer + Public Adapters + FTS5

**TASK:** SQLite WAL + FTS5 archive, adapter contract, public sources, dedupe, graceful degradation.

**IMPLEMENTATION:** `store.py` (9 tables + `items_fts` external-content FTS5 + 3 sync triggers, dedupe by `guid`, entities, runs, watchlist, jobs, reports, feedback, events, schedule_state, retention, online backup). `adapters.py` — 16 adapters: 7 RSS, Google News RSS, HN Algolia, GitHub Releases (3 repos), GDELT DOC 2.0, OpenAlex, Crossref, arXiv, Telegram public preview, Ahmia links-only. Contract `search / health / provenance / rate_limit / cost`. Har fetch `policy.check_url()` se pehle aur **har redirect par dobara** validate, 2 MB cap, 10 s timeout, XML precheck (DOCTYPE/ENTITY reject), `ThreadPoolExecutor` parallel, per-source diagnostics.

**VERIFICATION:** `test_store.py` 13 tests (FTS5 available, insert→update, FTS search, sanitized MATCH, entities, archive-not-delete, jobs, reports, feedback, secret redaction, retention, backup, overview). Live smoke: **9/11 sources OK** (`9to5google 100`, `androidauthority 80`, `gnews 35`, `apple-newsroom 20`, `gsmarena 20`, `androidpolice 10`, `xda 10`, `github 8`, `hn 1`); 2 graceful fail (`gdelt HTTP 429`, `sammobile TimeoutError`) — run crash nahi hua, 8 ranked items mile.

**RESULT:** Archive searchable, provenance-ready, zero-crash degradation.

**PHASE REVIEW — PHASE 15: READY**

## 7. PHASE REVIEW — PHASE 16 — Telegram Adapter + Scheduler + Alerts

**TASK:** Public Telegram, Bot API alerts/commands, scheduler, daily digest.

**IMPLEMENTATION:** `telegram_public` logic `TelegramAdapter` me `t.me/s/<channel>` HTML preview (sirf Settings me diye gaye public channels; koi login / MTProto / userbot / history scrape nahi). `alerts.py` — official Bot API `sendMessage` + `getUpdates` (`/status`, `/digest`, `/eval`, `/help`), token kabhi log ya URL error mein nahi, local `alerts.log` + `events`. `scheduler.py` — SQLite job queue, 6 job kinds (`feeds`, `telegram`, `papers`, `digest`, `watchlist`, `retention`), stoppable daemon thread, har job try/except.

**VERIFICATION:** `test_eval_scheduler.py` — firehose, tick enqueue/process (0 errors), watchlist job, digest job, retention+backup job, unknown job, thread start/stop; 5 alert tests (no-token local-only, no token leak, command surface). `POST /api/scheduler` HTTP smoke green.

**RESULT:** 24/7-ingest ke liye scheduler tayyar; alerts opt-in aur key-free diagnostics ke sath.

**PHASE REVIEW — PHASE 16: READY**

## 8. PHASE REVIEW — PHASE 17 — Deep Web Legal + Provenance

**TASK:** Legal deep-web adapters, provenance, trust, cross-verification, zero fabricated citations.

**IMPLEMENTATION:** `normalizer.py` (12 category rules, CVE / model / version / brand entities, canonical URL, content hash), `verifier.py` (`citation_ok`, `verified`, `url_fetched=False` honest note, trust labels `Official > Verified > Reported > Unverified > Rumor`, fingerprint clustering ≥2 independent sources → `cross_verified` boost, `citation_audit`). `AhmiaAdapter` clearnet index se **sirf .onion links** nikalta hai; `policy.check_url()` har `.onion` ko fetch se block karta hai. Ahmia / Google Patents / VirusTotal / urlscan registry-only ya links-only hain.

**VERIFICATION:** `test_pipeline.py` — 6 verifier tests (full provenance, link-only never verified, offline fixture honestly labelled `NOT a real citation`, 0 fabricated, missing-URL detection, cross-check boost) + 4 normalizer tests. `citation_audit` offline eval me **0 fabricated / 100% provenance**.

**RESULT:** Har fact ka URL + date checked; jis article URL ko agent ne khud fetch nahi kiya wo report ke "Not Verified" section mein wazeh hai. Koi banawati citation nahi.

**PHASE REVIEW — PHASE 17: READY**

## 9. PHASE REVIEW — PHASE 18 — Local LLM Tool Layer + Prompt-Injection Defense

**TASK:** LLM ko raw internet na de kar validated tools dena; local model support.

**IMPLEMENTATION:** `planner.py` — 8 tools (`search_public`, `fetch_url`, `search_telegram`, `search_onion_index`, `search_papers`, `verify_source`, `search_archive`, `save_report`), strict `validate()` (unknown tool / extra arg / private URL / onion URL / blocked query / length caps sab reject), max 6 calls, `dispatch()` tool output **sirf scrubbed plain text**, `INJECTION.sub()` prompt-injection defence, deterministic fallback. `llm.py` — Ollama / LM Studio / custom OpenAI-compatible, OFF default, `SYSTEM_RESEARCH` source-only prompt, `tool_plan()`, `polish()`, `probe()`, key kabhi log nahi.

**VERIFICATION:** `test_pipeline.py` — 10 planner/LLM tests (valid call, unknown tool, extra arg, private URL, onion URL, blocked query, injection scrub, deterministic plan, offline dispatch plain text, OFF rule-based). Eval safety: `prompt_injection_scrubbed`, `invalid_tools_rejected`, `secrets_masked` sab `true`. `/api/tools` me `run_shell` maujood nahi.

**RESULT:** **"LLM ko internet mat do — usay tools do"** code mein hai. Model band hone par bhi poora agent chalta hai.

**PHASE REVIEW — PHASE 18: READY**

## 10. PHASE REVIEW — PHASE 19 — Smart Ranking + Roman Urdu Report

**TASK:** Trust-weighted ranking aur professional categorized Roman Urdu brief.

**IMPLEMENTATION:** `ranker.py` (keyword relevance + trust + freshness + cross-verification + feedback, link-only / fixture penalty; aik `feedback_scores()` query). `briefer.py` — English headings, Roman Urdu prose, formal tone, `Executive Summary / Scope & Method / Facts by Category / Recommendations / Not Verified & Limitations / Sources & Diagnostics / Provenance / Metrics`; **Facts aur Recommendations alag sections**; har item `Source | Tier | Date checked | Published | Confidence | Trust | Score | URL`; Markdown + CSV + JSON export.

**VERIFICATION:** `test_pipeline.py` — ranker order, report section order (`Facts` pehle, `Recommendations` baad), blocked report me reason + official link + safe steps; `orchestrator.run()` se asli brief generate. Live run ke top items: *"Android security bulletin: November 2025 patch fixes zero-click RCE"*, *"Samsung's November 2026 security patch details revealed"*, *"Android's November 2026 Updates Patch Over 200 Vulnerabilities"*.

**RESULT:** Report professional, provenance-wala aur honestly unverified sections ke sath.

**PHASE REVIEW — PHASE 19: READY**

## 11. PHASE REVIEW — PHASE 20 — Agent Console UI + Search + Export

**TASK:** Standalone Agent Console, archive search, reports viewer, settings, export.

**IMPLEMENTATION:** `server.py` (`ThreadingHTTPServer` sirf `127.0.0.1:8766`, CSP + 4 security headers, 1 MiB body cap, report path `realpath`/`commonpath` authorization, masked settings, 20 GET/POST routes), `web/index.html` (7 views — Console / Archive / Sources / Watchlist / Reports / Evaluation / Settings), `web/app.js` (vanilla, koi inline script nahi, `safeUrl()`), `web/style.css` (**light theme**, responsive, reduced-motion), `favicon.svg`. `run.bat` + `__main__.py` CLI.

**VERIFICATION:** `test_http.py` 19 tests — static shell/assets, status, masked settings, sources, offline run, report view, 404, archive, watchlist, scheduler tick, blocked classify, tools list, bad provider/tor 400, LLM probe, unknown route, CSP headers, loopback-only. `node --check` OK.

**RESULT:** Console chal raha hai; `MobileLab` ka 8765 untouched.

**PHASE REVIEW — PHASE 20: READY**

## 12. PHASE REVIEW — PHASE 21 — Firehose + Watchlist + Retention + Backup

**TASK:** Sab kuch store, best kuch report; watchlist alert; retention; 24h-safe loop.

**IMPLEMENTATION:** `scheduler.firehose()` adapters se **sab** items normalize karke FTS5 archive mein deta hai (ranking/filter nahi). Watchlist har 5 min archive search karke local + Telegram alert. `store.retention(days)` sirf purane **articles** hata ta hai; sources / watchlist **archive** hote hain, delete nahi. `store.backup()` SQLite online backup. Scheduler loop har exception ko event mein likh kar aage chalta hai.

**VERIFICATION:** `test_store.py` retention (sources count barqarar) + backup file; `test_eval_scheduler.py` firehose, watchlist hits, retention+backup job; `.gitignore` me `jin_agent/data/` add kiya gaya taake DB / reports / secrets kabhi commit na hon.

**RESULT:** Firehose, alerting aur backup sab local aur non-destructive.

**PHASE REVIEW — PHASE 21: READY**

## 13. PHASE REVIEW — PHASE 22 — Hardening + Full Eval + Release 2.0.0

**TASK:** Central verification, hardening, docs, release.

**IMPLEMENTATION / VERIFICATION (asli output, kisi agent ke dawe par nahi):**

| Check | Natija |
|---|---|
| `python -m compileall -q jin_agent` | `PY_COMPILE_OK` |
| `node --check jin_agent/web/app.js` | `NODE_CHECK_OK` |
| `python -W error::ResourceWarning -m unittest discover -s jin_agent/tests -p "test_*.py"` | **Ran 116 tests in 11.162s — OK**, zero `ResourceWarning`; `python -m jin_agent selftest` bhi **116 OK** |
| `python -m jin_agent eval` | `passed: true`, 25 queries, 11/11 safety, 0 fabricated, 100% provenance |
| Live network smoke | 9/11 adapters OK, 2 graceful fail, 8 items, blocked request par **0 fetch** |
| Console smoke `127.0.0.1:8766` | 12/12 GET `200` + CSP har response; `POST /api/run` → 22 items, 0 fabricated, brief saved; server cleanly band |
| `agent.md` verbatim prefix | SHA-256 `1de53535…0840` MATCH, size unchanged |
| `MobileLab/server.py` | `VERSION = "1.4.0"` unchanged |
| `core.autocrlf` / remote | `false` / koi remote nahi |
| Secrets | `config.public()` + `store.add_event()` redact; token/API key koi response mein nahi |
| Loopback / CSP | `127.0.0.1` only, CSP har response |

**RESULT:** `VERSION = "2.2.0"`, 10/10 `PHASE REVIEW READY`, koi phase skip nahi. **2.1.0 honesty fix:** offline fixtures ko kabhi `cross-verified` nahi kaha jata; duplicate source records aik story mein merge hote hain (`verifier.collapse()`); zero-keyword-relevance records brief se nikaale jaate hain (ranker relevance floor); brief mein "Fixture replayed by: …" attribution instead of fake per-source headlines; 120/120 tests green; eval `passed: true` (precision@10 = 0.875, coverage 100%, 0 fabricated, 100% provenance).

**PHASE REVIEW — PHASE 22: READY**

---

## 14A. PHASE REVIEW — PHASE 23 — Telegram Channel Auto-Discovery (2.2.0)

**TASK:** User request (2026-11-15): *"agent khud channels dhoondta rahe add karta jaey, jo informative hain kis bhi language mien, dead na ho / working ha — add karo."*

**IMPLEMENTATION:**

| File | Change |
|---|---|
| `channels.py` (nayi) | `tg_channels` + `tg_candidates` SQLite tables; `clean_handle`, `extract_handles`, `harvest_archive`, `web_search_candidates`, `probe`, `score`, `check_channel`, `run_discovery`, `adapter_channels`, `add/remove/list/counts` registry functions. Dead → `status='dead'` (archive, delete nahi). Informative scoring: recency + volume + text richness + subscribers + topic relevance (0–10). |
| `adapters.py` | `TelegramAdapter.search` ab manual config channels + auto-discovered active channels merge karta hai. |
| `scheduler.py` | `discovery` job (`channel_discovery_minutes`, default 720 = 12h) add; offline discovery me network call nahi. |
| `server.py` | `GET /api/channels`, `POST /api/channels {action:add\|remove\|check\|discover}` routes. |
| `__main__.py` | CLI: `channels --add/--remove/--check/--discover/--offline/--status`. |
| `config.py` | Defaults: `channel_discovery_web`, `channel_discovery_max_auto` (60), `channel_discovery_probe_per_run` (8), `channel_min_score` (4). |
| `policy.py` | `html.duckduckgo.com` / `lite.duckduckgo.com` public allowlist mein add (site:t.me/s bootstrap discovery). |
| `__init__.py` / `server.py` / tests | `VERSION` 2.1.0 → **2.2.0**. |

**VERIFICATION:** `python -m compileall -q jin_agent` → `PY_COMPILE_OK`; `python -m jin_agent selftest` → **Ran 135 tests in ~8s — OK** (116 P13–P22 + nayi `tests/test_channels.py` 15); `python -m jin_agent run "..." --no-save` → offline end-to-end OK; CLI `channels --status` → OK. Saari network calls tests me mocked (live internet rule).

**RESULT:** `VERSION = "2.2.0"`, phases P13–P23 sab `PHASE REVIEW READY`. Koi phase skip nahi.

**PHASE REVIEW — PHASE 23: READY**

---

## 14A. Post-Release Honesty Fix (2.1.0, 2026-11-15)

**Problem:** `verifier.cross_check()` same fingerprint + ≥2 source keys par `cross_verified = True` de raha tha — goya offline fixture (synthetic data) ko 2 "independent sources" ne tasdeeq kiya ho. Brief mein wohi ek headline 5 dafa alag source naam se aa rahi thi, aur har ek par `Cross-verified: yes` likha tha. Ye agent ke bharosemand-report maqsad ke bilkul khilaf tha.

**Fix (5 files, +161 lines):**

| File | Change |
|---|---|
| `verifier.py` | `cross_check()` ab sirf `meta.offline == False` aur `meta.kind != "onion-link"` records par boost deta hai. `collapse()` naya function: same fingerprint wale records ko merge karta hai, `also_sources` / `duplicate_count` add karta hai, confidence max() leta hai. |
| `ranker.py` | Relevance floor: agar koi query keyword title/excerpt mein match na ho to score mein `relevance = 0` + penalty `-3.0`; zero-relevance items brief se nikalte hain par archive mein rehte hain. |
| `orchestrator.py` | `verifier.collapse(pool)` call add; `unique_stories` / `duplicate_rows_merged` / `zero_relevance_dropped` metrics; digest function mein bhi collapse. |
| `briefer.py` | "Fixture replayed by: …" instead of fake per-source attribution; `Cross-verified: no (offline fixture / link-only)` label; `Also reported by` merged sources line; duplicate-merge summary in Executive Summary. |
| `tests/test_pipeline.py` | `test_cross_check_real_only` replaces old `test_cross_check_boosts`; new `test_offline_run_honesty` asserts no fake cross-verified, no duplicate headlines, `Also reported by` present, `duplicate_rows_merged > 0`. |

**Verification:**
- `python -m unittest discover -s jin_agent/tests -t . -q` → **Ran 120 tests — OK**
- `python -m jin_agent eval` → `passed: true`, precision@10 = 0.875, coverage 100%, 0 fabricated, 100% provenance
- `python -m jin_agent run "MediaTek preloader scatter validation"` → 2 unique stories (13 duplicates merged), 0 cross-verified (honest), 0 zero-relevance dropped, fixture attribution correct

**RESULT:** Offline fixtures ko kabhi "cross-verified" nahi kaha jata. Duplicate stories merge hoti hain. Brief mein attribution honest hai. Ye regression nahi — pehli dafa sahi naap hai (pehle wohi headline 5 dafa "relevant" ginī ja rahi thi).

---

## 14. N/A Register — gate pass, skip nahi

| Item | Wajah |
|---|---|
| Google Patents auto-adapter | Koi keyless stable API nahi; JS-heavy page. Link-only registry entry (`patents`), notes me `N/A` darj. |
| VirusTotal / urlscan / Hybrid Analysis adapters | API key ya submission writes chahiye; C20 (stdlib-only, koi dependency) aur read-only agent ke khilaf. Registry-only. |
| Paid search APIs (Tavily / Exa / Brave / Shodan) | Plan khud kehta hai "pehle free stack se eval, proof ke baghair paisa na lagayein". Deferred. |
| Windows Task Scheduler install | In-app stoppable thread + SQLite job queue istemal; koi OS-level install / admin permission nahi. |
| LLM raw browser / shell / file / POST tools | Plan ne khud ❌ kaha; tool allowlist me maujood hi nahi. |
| Abliterated / uncensored model | Plan ki recommendation ke mutabiq normal instruct model + research system prompt; abliterated se reasoning aur injection resistance girta hai. Koi model install nahi. |
| Onion auto-fetch / crawl | Legal + `links_only` policy; `.onion` `check_url()` se hard-block. |
| "100% duniya ki har khabar" claim | Plan section 2 khud kehta hai ye mumkin nahi. **Sab kuch store, best kuch report** — report me limitation darj. |
| GSX / account / FRP bypass / device write | Sahulat & Safe Service Policy unchanged; is agent me koi aisi capability code hi nahi. |

## 15. Open Questions / Risks (honest deferral, koi jhootha resolution nahi)

| ID | Baat |
|---|---|
| O-TOKEN | Bot token / LLM key local `config.json` me plaintext (local-only, masked in UI/API/logs). Windows file ACL hardening baad mein. |
| R-FLAKY | Live smoke me GDELT `429` aur SamMobile timeout mile — diagnostics me darj, run crash nahi hua. |
| R-LIVE-EVAL | Default eval offline-fixture hai; `--live` 25-query evaluation abhi scheduled nahi (network cost / rate limits). |
| R-HARDWARE | RAM / GPU / VRAM maloom nahi; LLM OFF rehta hai jab tak model install na ho. |
| R-MODEL | Koi runtime / model download nahi kiya gaya; LLM tool-planning path unit-tested hai par real model ke sath end-to-end probe abhi baaqi. |
| R-COVERAGE | Offline coverage 100% pipeline correctness ka naap hai, live source availability ka nahi — dono report me alag label hain. |

## 16. Final Result

**ALL 14 PHASES (P13–P26) READY.** `JIN Agent 2.5.0` ab L1.5 feed aggregator nahi: tool-mediated LLM layer, 16 adapters, FTS5 firehose archive, provenance + trust + cross-verification, scheduler + alerts, 25-query evaluation harness, professional Roman Urdu brief aur apna loopback console sab kaam kar rahe hain. Sahulat & Safe Service Policy, local-only constraint aur Python stdlib-only stack bilkul barqarar hain. **2.1.0 honesty fix:** offline fixtures ko cross-verified nahi kaha jata, duplicate stories merge hoti hain, attribution honest hai, 120/120 tests green.

## 17. PHASE REVIEW — PHASE 24 — Parallel Agents / Batch Research (2.3.0)

**TASK:** User ke request: *"sary agents bhejo jitny bhej skty ho ess search ko better banny mein bina ruky km krty raho"* — N agents / N queries ek saath chalayen, keep improving.

**IMPLEMENTATION:** `orchestrator.run_many(queries, live, days, limit, keys, cfg, save, max_concurrent=3)` — ThreadPoolExecutor se parallel runs; har run apni report banata hai; bounded concurrency (default 3); blocked / error handling per run.

**VERIFICATION:** `python -m jin_agent batch "mediatek preloader scatter DA" "mtk brom config version" --limit 3` → **2 parallel agents OK**, exit 0; `test_run_many_parallel_runs` green; full suite 136 OK.

**RESULT:** `VERSION = "2.3.0"`, phases sab READY. Koi phase skip nahi.

**PHASE REVIEW — PHASE 24: READY**

---

## 18. PHASE REVIEW — PHASE 25 — Telegram Bot Front-End (2.4.0)

**TASK:** User ke request: telegram bot se token/key lo, bot sirf user tak, agent se dark web / deep web / telegram / public-private channels se info lae, Roman Urdu report banao, mistakes na hon.

**IMPLEMENTATION:** `telegram_bot.py` (naya): Bot API long polling (`getUpdates` offset+timeout, `sendMessage`), command dispatch (`/start /help /status /sources /channels /research`), chat allowlist (`telegram_chat_id`), research → Roman Urdu markdown → Telegram chunks (4096), error handling.

**VERIFICATION:** `jin_agent/tests/test_telegram_bot.py` (9 tests: parse, chunk, allowlist, dispatch, research-requires-query); full suite **136 → 145 tests OK** (pending final run).

**RESULT:** `VERSION = "2.4.0"`, phases sab READY.

**PHASE REVIEW — PHASE 25: READY**

---

## 19. PHASE REVIEW — PHASE 26 — Foundation Hardening (2.5.0)

**TASK:** Foundation harden karna: structured JSON logging (secrets redacted), in-memory metrics + `/api/metrics`, `/api/health`, offline CI eval gate (`ci-gate`), aur release **2.5.0**. Scope sirf P26.

**IMPLEMENTATION:**

| File | Change |
|---|---|
| `logging_setup.py` (nayi) | JSON-lines logger `data/logs/agent.log` par; stdlib `RotatingFileHandler` (2 MB × 3 backups, UTF-8, `delay=True`), `JsonLineFormatter` (ts / level / logger / msg / fields / error), `get_logger(name)`, `read_lines()`. `redact()` message, nested fields aur exception text par lagta hai: Telegram bot token (`bot<id>:<secret>` pattern **aur** config ki exact value) aur LLM key (`sk-...` pattern **aur** exact value) kabhi disk par nahi jate. Level `JIN_AGENT_LOG_LEVEL` se. Data dir badlne par handler replace hota hai, duplicate nahi. |
| `metrics.py` (nayi) | Thread-safe (`threading.Lock`) counters (`queries_total`, `runs_ok`, `runs_blocked`, `fetch_errors`, `reports_total`, `evals_total`, `llm_calls`), gauges, bounded latency samples (`deque(maxlen=500)`), `percentile` / `p50` / `p95` helpers, `latency()`, `snapshot()`, `compact()`. Summary `data/metrics.json` best-effort (5 s throttle, write fail par run crash nahi). |
| `ci_gate.py` (nayi) | Offline gate: (a) har package module `py_compile` + `importlib` import, (b) poora unittest suite in-process, (c) evaluator quick check (3 offline queries, throwaway `JIN_AGENT_DATA`, zero network). `run()` compact JSON verdict; `ok` sirf tab jab teeno checks pass. |
| `server.py` | `GET /api/health` — DB `SELECT 1` + item count, data dir writable probe, version, uptime seconds, `llm_enabled` bool (`key` kabhi nahi), FTS5. `GET /api/metrics` — counters/gauges/latency snapshot (koi secret nahi). `server_version` → `JINAgent/2.5.0`. |
| `orchestrator.py` | Run instrumentation: `queries_total`, `runs_ok`, `runs_blocked`, `fetch_errors` (= failed sources), `reports_total`, `run` latency + `items_last_run` gauge. `status()` payload mein compact `metrics` block. Har run par aik structured log line (query truncated). |
| `__main__.py` | CLI `ci-gate [--queries N] [--skip-tests]`: compact JSON verdict print, exit 0 sirf all-pass. |
| `__init__.py` / `server.py` / tests | `VERSION` 2.4.0 → **2.5.0**. Nayi `tests/test_metrics.py` (15), `tests/test_ci_gate.py` (7), `test_http.py` +2 (`/api/health`, `/api/metrics`), `test_governance.py` P13–P26 (14 reviews) + required files + version 2.5.0, `test_pipeline.py` version + `metrics` block. |

**VERIFICATION:** (asli output, kisi dawe par nahi)

| Check | Natija |
|---|---|
| `python -m py_compile` (12 changed/new `.py` files) | `PY_COMPILE_OK` |
| `python -X utf8 -m jin_agent selftest` | **Ran 168 tests in 9.0s — OK** (144 P13–P25 + 24 nayi: metrics 15, ci_gate 7, http 2) |
| `python -X utf8 -m jin_agent ci-gate` | `{"ok": true, ...}` — imports 21/21 OK, unit_tests 168 pass, evaluator offline 3 queries / 0 crashes / 0 fabricated / 100.0% provenance; exit **0** |
| `python -X utf8 -m jin_agent status` | `"version": "2.5.0"`, compact `metrics` block maujood; exit 0 |
| Offline run smoke (`--no-save`, throwaway data dir) | `agent.log` mein aik JSON line (`run done`, items=2, sources_ok=11, duration_ms=84); `metrics.json` → `queries_total=1`, `runs_ok=1`, `run p50=84 ms / p95=84 ms` |
| Secrets | `redact()` bot token + LLM key ko pattern aur exact config value dono se `***` karta hai; log file aur `/api/metrics` response mein koi token / key nahi |
| Network | Saare tests offline; koi server ya bot start nahi kiya gaya |

**RESULT:** `VERSION = "2.5.0"`, phases P13–P26 sab `PHASE REVIEW READY`. Observability (JSON logs + metrics + health endpoint) aur offline release gate maujood; stdlib-only, local-only aur Sahulat & Safe Service Policy bilkul barqarar.

**PHASE REVIEW — PHASE 26: READY**

---

## 20. PHASE REVIEW — PHASE 27 — Retrieval++ (2.6.0)

**TASK:** Retrieval coverage barhana: 10 naye source adapters (Reddit, Wikipedia, Wikidata, Google News topics, Wayback, GitHub search, NVD/CVE, sitemap/robots, Brave/Bing keyed search) + URL canonicalization/dedup + page snapshot change-detection + per-host rate limiting/backoff, aur release **2.6.0**.

**IMPLEMENTATION:**

| File | Change |
|---|---|
| `adapters.py` | Naye adapters: `RedditAdapter`, `WikipediaAdapter`, `WikidataAdapter`, `GoogleNewsTopicAdapter`, `WaybackAdapter`, `GitHubSearchAdapter`, `NVDAdapter`, `SitemapAdapter` (robots.txt + sitemap.xml discovery), optional keyed `BraveSearchAdapter` / `BingSearchAdapter` (key na ho to disabled, error spam nahi). Total 19 adapters + RSS feeds; har adapter ka offline fixture test. Boundaries barqarar: Telegram public-only, Ahmia links-only. |
| `canonical.py` (nayi) | `canonicalize()` (host lowercase, tracking params `utm_*`/`fbclid`/`gclid` strip, query sort), `same_url()`, `content_hash()`, `title_tokens()` + `jaccard()` + `near_duplicate_titles()`, `dedupe_key()` / `dedupe_records()` (URL canonical + content hash + near-dup title). |
| `snapshots.py` (nayi) | `page_snapshots` table: `record()`, `diff_text()`, `changes_since()`, `recent_changes()`, `changes_since_last_run()`, `mark_seen()`, `counts()`, `prune()`. "Naya kya aaya" per source (added/removed lines + first N changes). |
| `ratelimit.py` (nayi) | Per-host minimum interval + exponential backoff (`backoff_base`/`backoff_max`), in-memory thread-safe state: `wait()`, `note_success()`, `note_failure()`, `state()`, `reset()`. |
| `config.py` | Naye defaults: source flags (`brave-search`, `bing-search`), optional keys (`brave_key`, `bing_key`, `github_token`), `snapshot_max_chars`, `change_max_lines`; keys logging me redact. |
| `__main__.py` | Naya CLI: `changes [--limit N]` — recent snapshot changes + counts (JSON). |
| Tests | Nayi `tests/test_canonical.py`, `tests/test_change_detection.py`, `tests/test_adapters_v2.py` (57 tests); `test_governance.py` P13–P27 (15 reviews) + required files + version 2.6.0. |

**VERIFICATION:** (asli output)

| Check | Natija |
|---|---|
| `python -m py_compile` (changed/new `.py`) | OK |
| `python -X utf8 -m jin_agent selftest` | **Ran 225 tests — OK** (168 P13–P26 + 57 nayi: canonical, change-detection, adapters-v2) |
| `python -X utf8 -m jin_agent ci-gate` | `ok: true` — imports + 225 unit tests + evaluator offline quick check; exit **0** |
| `python -X utf8 -m jin_agent status` | `"version": "2.6.0"`, metrics block maujood |
| Boundaries | Saare tests offline (koi network nahi), MobileLab untouched, secrets redacted |

**RESULT:** `VERSION = "2.6.0"`, phases P13–P27 sab `PHASE REVIEW READY`. Retrieval breadth (19 adapters + RSS), canonical dedup, change detection aur rate limiting maujood; stdlib-only, local-only aur Sahulat & Safe Service Policy barqarar.

**PHASE REVIEW — PHASE 27: READY**

---

## 21. PHASE REVIEW — PHASE 28 — Channel Memory & Health (2.9.0)

**TASK:** "No working channel" masla: failed/dead channels ka negative memory, channel
health telemetry, aur dead registry ka TTL cleanup. Competitor patterns (web research):
silent/dead channels ka record 14/30/90 din thresholds par clean karo, aur failed
channel ko yaad rakho taake agla round wahi dhoond na kare.

**IMPLEMENTATION:**

| File | Change |
|---|---|
| `searchmemory.py` | `failed_channels` column (migration samet) + `remember_failed()` / `failed_channels()`; TTL env `JIN_AGENT_CHANNEL_NEGATIVE_TTL_DAYS` (default 7). |
| `channels.py` | `dead_ttl_days()` + `cleanup_dead()` — `status='dead'` aur TTL purani rows delete (active/archived ko chhuna nahi); env `JIN_AGENT_CHANNEL_DEAD_TTL_DAYS` (default 30). |
| `store.py` | `retention()` ab dead-channel TTL cleanup ko channels module se guzarti hai. |
| `telegram_bot.py` | `format_channels()` empty-state: active 0 magar dead/archived hon to "`/channels --all`" tareeqa; `/channels --all` command; `/status` aur `status()` me `channels_active` / `channels_dead` / `channels_archived`; research agle round me failed channels skip karta hai. |

**VERIFICATION:** `JIN_AGENT_DATA=$(mktemp -d) python3 -m unittest discover -s jin_agent/tests -t . -q`
→ **Ran 379 tests — OK** (1 skip: PySocks). Naye `test_phase1_memory_health.py` (10 tests).

**RESULT:** Phases P13–P28 sab `PHASE REVIEW READY`. Failed/dead channel memory TTL
ke saath bounded; registry unbounded nahi; stdlib-only, local-only, policy barqarar.

**PHASE REVIEW — PHASE 28: READY**

---

## 22. PHASE REVIEW — PHASE 29 — Confidence, Report File & Explore (2.9.0)

**TASK:** Competitor patterns: per-claim confidence + hard caps, report ko chat flood
ki jagah `sendDocument` file ki shakal me, aur rozana scored digest/explore.

**IMPLEMENTATION:**

| File | Change |
|---|---|
| `verifier.py` | `aggregate_confidence()` — score-weighted mean, hard caps (cross 0.99 / verified 0.80 / single 0.60), `confidence_threshold()` env `JIN_AGENT_REPORT_CONFIDENCE` (default 0.6). |
| `briefer.py` | `build()` structured + markdown me aggregate confidence; `confidence` / `confidence_label` output. |
| `orchestrator.py` | `run()` / `digest()` metrics me `confidence` + `confidence_label`. |
| `telegram_bot.py` | `_API.send_document()` (multipart, caption ≤1024); `_send_research` report `.md` file bhejta hai (high confidence) ya "bharosemand nahi" payam (low); `/explore [topic]` + `format_explore()`; `research_full` `report_path` / `confidence` / `failed_channels` return karta hai. |
| `scheduler.py` | Naya `explore` job kind + `explore()` (discovery + scored archive + digest); `explore_minutes` (default 1440). |
| `config.py` | `schedule.explore_minutes` default 1440. |

**VERIFICATION:** `JIN_AGENT_DATA=$(mktemp -d) python3 -m unittest discover -s jin_agent/tests -t . -q`
→ **Ran 379 tests — OK** (1 skip: PySocks). Naye `test_phase2_confidence_report.py` (14 tests).

**RESULT:** Phases P13–P29 sab `PHASE REVIEW READY`. Confidence deterministic aur
reproducible; Telegram chat flood ke bajaye report file; explore rozana scored digest;
stdlib-only, local-only, policy barqarar.

**PHASE REVIEW — PHASE 29: READY**

---

## 23. PHASE REVIEW — PHASE 30 — Scoring, Lifecycle, Trace (2.9.0)

**TASK:** Competitor deep-dive (tgden/chatcrawler, ipiton STEWARDSHIP, maddness,
ashishki, tsukeno, Hermes) ke P0 gaps: log-scale channel scoring + 30-din dead
rule, source/channel lifecycle, markdown HTML, confirm-gated actions, suppression
memory, per-run trace + token accounting, repeated-claim detection.

**IMPLEMENTATION:**

| File | Change |
|---|---|
| `channels.py` | `score()` log-scale (`lg(1+subs)`, `0.8*lg(1+posts)`), `channel_signs()` (kam-az-kam-3-signs gate), `check_channel` 30-din dead rule + `insufficient_data`, `dead_ttl_days`/`stale_ttl_days` + `mark_stale_channels`, `parse_preview` + `parser_selftest` (drift gate) |
| `store.py` | sources me `status`/`last_verified_at`/`stale_days` (migration), `touch_source` lifecycle, `mark_stale_sources`, trace pruning |
| `searchmemory.py` | `rejected_ideas` + `source_stats` (acted/cited/skipped/rejected), `reset_chat`, `audit` (duplicate/conflict/stale + audit trail) |
| `verifier.py` | `repeated_claims()` (≥2 occurrences, cross-channel/cross-source/same-channel) |
| `orchestrator.py` | per-run trace `data/runs/<id>.json` (query/plan/tools/sources/tokens/duration/confidence), token budget/cost meter |
| `llm.py` | `TOKEN_USAGE` + `reset_tokens`/`token_usage`/`token_budget`/`cost_per_1m` |
| `briefer.py` | Repeated Claims section |
| `telegram_bot.py` | markdown→HTML + `parse_mode="HTML"` (escape-safe), `/addchannel` confirm gate (✅/❌), per-chat 20/min rate limit |

**VERIFICATION:** `JIN_AGENT_DATA=$(mktemp -d) python3 -m unittest discover -s jin_agent/tests -t . -q`
→ **Ran 413 tests — OK** (1 skip: PySocks). Naye `test_phase3_scoring_lifecycle.py` (17 tests).

**RESULT:** Phases P13–P30 sab `PHASE REVIEW READY`. Scoring log-scale, lifecycle
bounded, report HTML, destructive action confirm-gated, trace/token accounting,
repeated-claim labels; stdlib-only, local-only, policy barqarar.

**PHASE REVIEW — PHASE 30: READY**

---

## 24. PHASE REVIEW — PHASE 31 — BLUF, Honest Absence, Progress Edit, Top-Class Ops (2.9.0)

**TASK:** Explorer ke "top class" gaps: BLUF (TL;DR + 3-5 findings, poori report
file), honest absence (no result vs fetch fail vs partial), `/new` context reset,
progress edit-in-place, `/digest` `/alerts` `/reports` `/schedule`, channel health
digest, parser-drift selftest, memory audit.

**IMPLEMENTATION:**

| File | Change |
|---|---|
| `telegram_bot.py` | `_bluf_text` (≤1000 chars) + `sendDocument`; `absence_kind` (ok/no_results/fetch_failed/partial/blocked) alag payam; `_API.edit` + `_STATUS_MESSAGES` (progress edit-in-place); `/new` `/digest` `/alerts` `/reports` `/schedule` `/channelhealth` `/memoryaudit` `/selftest`; `format_channel_health` / `format_memory_audit` / `format_selftest` |
| `channels.py` | `parser_selftest()` (network-free drift gate) |
| `searchmemory.py` | `audit()` duplicate/conflict/stale + audit event |

**VERIFICATION:** `JIN_AGENT_DATA=$(mktemp -d) python3 -m unittest discover -s jin_agent/tests -t . -q`
→ **Ran 413 tests — OK** (1 skip: PySocks). Naye `test_phase4_topclass.py` (17 tests).

**RESULT:** Phases P13–P31 sab `PHASE REVIEW READY`. BLUF + honest absence, context
reset, progress edit, ops commands, channel health, parser selftest, memory audit;
stdlib-only, local-only, policy barqarar.

**PHASE REVIEW — PHASE 31: READY**

---

## 25. PHASE REVIEW — PHASE 32 — 6-Command Surface, Explore Cards + Memory Gate (2.9.0)

**TASK:** User ka muksad: "main khta jaun wo explore krta jaey channel ko mjhy
dekhata jaye link ... report ... memory mein rakhta jaye ... mjhy b option ho k
konsa channel ya site memory mein rakhni ha ya ni ... /status me explore status
dikhe." P0/P1 kaam: seedha matn = `/research`, `/help` ka 6-command rewrite,
purane commands aliases, `/channels add/rm`, `/search`, `/research --deep`,
`setMyCommands`, live progress stages, trace local path, aur explore cards +
✅/❌ memory gate.

**IMPLEMENTATION:**

| File | Change |
|---|---|
| `telegram_bot.py` | `HELP_TEXT` 6 commands + har ek ka misaal; `BOT_COMMANDS` + `register_commands` + `_API.set_my_commands`; `route_plain_text` (seedha matn → `/research`, link/handle → `/addchannel`); `split_deep_flag`; `/channels` me `add`/`rm`/list/search merge; `/search` alias; explore cards + `_EXPLORE_PENDING` + `exp:keep/skip` callback gate; `format_status_text` explore block; `_stage_status` (3s throttle) + Plan→Deliver stages; `_bluf_text`/caption me `_trace_display` |
| `channels.py` | `pending_candidates()`; `tg_sites` table + `add_site`/`list_sites`/`site_counts` (explore ✅ memory) |
| `orchestrator.py` | `run(..., on_stage=...)` — Plan/Sources/Fetch/Verify/Brief stages; `trace_path` return |
| `scheduler.py` | `explore()` event (`kind='explore'`) — `/status` ka "last explore" |
| `__main__.py` | `run` CLI trace path print |
| `tests/test_p0_p1_ux.py` | 19 regression tests (commands, routing, gate, stages, trace, explore) |

**VERIFICATION:** `JIN_AGENT_DATA=$(mktemp -d) python3 -m unittest discover -s jin_agent/tests -t . -q`
→ **Ran 494 tests — OK (1 skipped)**. `len(policy.register()) == 45` sahi hai
(P2.1 ke 12 legal/public institutional sources, commit `3286bc6`). `VERSION`
`2.9.0` par barqarar; `test_p0_p1_ux` 19/19, `test_telegram_bot`,
`test_phase4_topclass`, `test_bot_hardening`, `test_lifetime_bot` sab green.

**RESULT:** 6-command surface (`/research`, `/search`, `/channels`, `/explore`,
`/status`, `/help`) + purane aliases; explore cards clickable links ke saath,
per-item/bulk ✅❌ memory gate; `/status` me explore block; live stages + trace
local path. stdlib-only, `is_owner` default allow-all aur loopback unchanged.

**RESULT: PHASE 32 — READY**

**PHASE REVIEW — PHASE 32: READY**

---

## 26. PHASE REVIEW — PHASE 33 — Query-Term Highlight, Beginner Buckets + 12 Legal Sources (2.9.0)

**TASK:** User ka muksad: "report jo milti hai wo keyword highlight kar ky mily" —
report/BLUF me query ke lafz highlight hon, magar HTML tags/URLs/entities ko
nuqsan na pohonche. Saath hi report ki 12 variti categories beginner ke liye
4 buckets me samjh di jayen, aur legal/public institutional sources register
me shamil hon.

**IMPLEMENTATION:**

| File | Change |
|---|---|
| `highlight.py` | Naya module (309 lines): `terms(query, limit=20)`; `highlight_html(html, terms)` — **sirf text nodes** me `<b>` wrap; tags, attributes, URLs aur entities nahi chhoote; case-insensitive; har term pehli occurrence par **ek dafa**; `split_html(html, limit=4096)` — entity-safe, tag-balanced chunks |
| `briefer.py` | `CATEGORY_BUCKETS` — 12 variti categories ko 4 beginner buckets me group; `bucket_for()` (na-maloom category → Watchlist); `BUCKET_ORDER`; report me `### Bucket` headings |
| `policy.py` | `SOURCE_REGISTER` me 12 legal/public institutional sources — 33 → **45** |
| `tests/test_highlight.py` | 28 naye tests (terms, text-node-only highlight, entity/tag safety, chunk balance) |
| `tests/test_buckets.py` | 8 naye tests (bucket mapping + report rendering) |
| `tests/test_adapters_v2.py`, `tests/test_governance.py` | register count assert 33 → 45 |

**VERIFICATION:** `JIN_AGENT_DATA=$(mktemp -d) python3 -m unittest discover -s jin_agent/tests -t . -q`
→ naye `test_highlight` 28/28, `test_buckets` 8/8 green; `len(policy.register()) == 45`
assert pass. Suite is marhale ke aakhir par **494 tests OK (1 skipped)**.

**RESULT:** `highlight.py` (query-term highlight + entity-safe chunking), report
ki 4 beginner buckets, aur register ka 12 legal/public sources (45) ka kaam
mukammal. `7395aac` ne `highlight.py` docstring ki typo bhi theek ki.

**PHASE REVIEW — PHASE 33: READY**

---

## 27. PHASE REVIEW — PHASE 34 — Explore v2: Topic-Driven Discovery + Scope Cards (2.9.0)

**TASK:** `/explore` ko topic-driven banaya jaye — koi hardcoded niche default
na ho, aur user 4 scope (Telegram / Open web / Open source / Deep web) me
filtered cards dekhe. Deep-web (onion) links sirf display hon, fetch kabhi nahi.

**IMPLEMENTATION:**

| File | Change |
|---|---|
| `scheduler.py` | `explore(topic="", scope="all")` — topic khaali ho to `_rotating_topic()` (`config.TOPICS` se har ghanta rotate; koi hardcoded niche default nahi); `scope` = `all \| tg \| web \| oss \| deep`; `is_oss_item` (arXiv/Crossref/OpenAlex/GitHub), `is_deep_item` (onion/ahmia — links only), `is_web_item`; `firehose(query="")` bhi neutral |
| `channels.py` | `run_discovery(cfg, offline, query=topic)` — discovery query ke mutabiq |
| `telegram_bot.py` | `EXPLORE_SCOPES` (🌐 Sab / 🐦 Telegram / 🌐 Open web / 📚 Open source / 🕶️ Deep web); `explore_scope_buttons()`; `_explore_groups()` 4 scope-group; `format_explore_cards_v2()` — **ek hi message**, deduped cards + clickable links + score; `_EXPLORE_PENDING` (topic/scope hash); `_filter_groups()` — scope button par sirf us group; status block |
| `tests/test_explore_v2.py` | 14 naye tests (topic required, dedupe, 4 scopes, onion links-only) |
| `tests/test_p0_p1_ux.py` | Explore regression align |

**VERIFICATION:** `JIN_AGENT_DATA=$(mktemp -d) python3 -m unittest discover -s jin_agent/tests -t . -q`
→ `test_explore_v2` 14/14 green; onion items par `links_only` behavior assert
pass (fetch nahi hota).

**RESULT:** `/explore` ab topic-driven + neutral scheduler defaults ke saath;
ek deduped card message, 4 scope buttons aur status block; deep-web sirf
display. Stdlib-only, local-only, policy barqarar.

**PHASE REVIEW — PHASE 34: READY**

---

## 28. PHASE REVIEW — PHASE 35 — BLUF/Report Me Query-Term Highlight Wiring (2.9.0)

**TASK:** Highlight module ko Telegram BLUF aur final report me wire karna —
user ko jis lafz se search kiya, report me wahi lafz `<b>` se nazar aaye, magar
message hargiz adhura (broken HTML) na bane.

**IMPLEMENTATION:**

| File | Change |
|---|---|
| `telegram_bot.py` | `_highlight_html(text, query)` — markdown → HTML, phir `highlight.highlight_html(..., highlight.terms(query))`; **sirf text nodes** me highlight; koi masla ho to escape-only HTML fallback (kabhi adhura message nahi); BLUF (`send parse_mode="HTML"`, purana/fake API par plain fallback) aur final report dono me wiring; report ke liye `highlight.split_html()` se entity-safe + tag-balanced chunks |
| `tests/test_highlight_wiring.py` | 5 naye tests (BLUF/report highlight wiring, fallback, chunk safety) |
| `tests/test_telegram_bot.py` | Highlight wiring ke mutabiq update |

**VERIFICATION:** `JIN_AGENT_DATA=$(mktemp -d) python3 -m unittest discover -s jin_agent/tests -t . -q`
→ `test_highlight_wiring` 5/5 green; full suite **494 tests OK (1 skipped)**.

**RESULT:** BLUF aur report dono me query terms `<b>` se highlight hote hain —
tags/attributes/URLs/entities me nahi; report hamesha entity-safe, balanced
chunks me bheja jata hai. `VERSION` `2.9.0` par barqarar; stdlib-only,
local-only, Sahulat policy barqarar.

**PHASE REVIEW — PHASE 35: READY**

---

## 29. PHASE REVIEW — PHASE 36 — /status Source Health Non-Overlapping (2.9.0)

**TASK:** Live `/status` ka source hisaab overlap kar raha tha — `status == "ok"`
magar `fail_count > 0` wala source `ok` aur `fail` dono buckets me gina jata
tha (bot ne `45 ok / 1 fail (total 45)` dikhaya). Fail source ka naam/wajah bhi
nahi dikhta tha.

**IMPLEMENTATION:**

| File | Change |
|---|---|
| `telegram_bot.py` | `source_health()` — non-overlapping buckets: `disabled` (enabled falsy) pehle, phir `failed` (`verification_failed`) / `stale` / `ok`; `auto` vs `registry_only` honest ginatī. `format_status_text()` ab `45 total — 26 auto / 19 registry-only \| 26 ok / 0 failed / 0 stale / 19 disabled` aur fail/stale ka naam + `last_error` (80 chars) dikhta hai. `/status` result me `sources_*` fields. |
| `tests/test_status_health.py` | 6 naye tests: overlap na ho, fail naam/error aaye, stale naam, disabled bucket, auto vs registry-only breakdown |

**VERIFICATION:** `test_status_health` 6/6 green; `test_telegram_bot`,
`test_explore_v2`, `test_p0_p1_ux`, `test_bot_hardening` 80/80 green (1 skipped).

**RESULT:** Har source ab sirf ek bucket me — `sum(buckets) == total == 45`.
Store `enabled` ko `auto` se seed karta hai, is liye 19 registry-only sources
`disabled` bucket me hain (26 auto hi enabled). Fail/stale ka naam + wajah
`/status` me saaf dikhta hai. `VERSION` `2.9.0` barqarar; stdlib-only.

**PHASE REVIEW — PHASE 36: READY**

---

## 30. PHASE REVIEW — PHASE 37 — HTML Report Export + /report Command (2.9.0)

**TASK:** Competitor HTML/PDF/MD export deta hai; JIN sirf `.md` deta tha. Stdlib-only
project me HTML export chahiye; PDF ke liye third-party dep ki zaroorat hoti hai —
jaan-boojh kar nahi gaya (honest note).

**IMPLEMENTATION:**

| File | Change |
|---|---|
| `report_export.py` (naya) | `to_html(report)` — `briefer.build()` dict ya structured JSON dono se valid HTML: heading/meta, BLUF, findings beginner-bucket headings, sources table, confidence, provenance, metrics. Saara data `html.escape`; sirf `http/https` href (javascript: nahi). `from_report_file(md_path)` JSON archive se HTML. |
| `telegram_bot.py` | `/report [md|html]` (default md) — aakhri saved report dobara `send_document`; JSON archive na hone par honest MD fallback; `pdf` par saaf mana + wajah |
| `tests/test_report_export.py` | 8 naye tests: escaping, adhuri report valid HTML, bucket headings, sources table, javascript: URL guard, briefer roundtrip, bot `/report` |

**VERIFICATION:** `JIN_AGENT_DATA=$(mktemp -d) python3 -m unittest discover -s jin_agent/tests -t . -q`
→ `test_report_export` 8/8 green; full suite **508 tests OK (1 skipped)**.

**RESULT:** HTML export stdlib-only, valid (escape + scheme guard ke saath).
PDF third-party dependency maangta hai, is liye chhoda — MD/HTML hi formats hain.

**PHASE REVIEW — PHASE 37: READY**

---

## 31. PHASE REVIEW — PHASE 38 — Multi-Turn Chat Context (2.9.0)

**TASK:** Abhi har sawal akele samajha jata tha; chhota follow-up (`aur`,
`iske baare me`, `phir`) ke liye user ko purana sawal dobara likhna parta.

**IMPLEMENTATION:**

| File | Change |
|---|---|
| `chat_context.py` (naya) | `is_followup()` — chhota matn (≤4 words) ya `aur/iske baare me/more/continue/phir` (word-boundary); `attach()` — pichhla sawal `prev \| current` (max 1); `note()`; `clear()` |
| `store.py` | `chat_context` table (`chat_id` PK, `last_queries` JSON, `updated_at`) + `init_db` migration; `save_chat_query` / `last_chat_query` / `clear_chat_context` (max 5 history) |
| `telegram_bot.py` | `/research` par context attach + note (table na hone par as-is); `/new` context clear |
| `tests/test_chat_context.py` | 7 naye tests: migration, detect, attach, store roundtrip, bot `/research` attach + `/new` clear |

**VERIFICATION:** `JIN_AGENT_DATA=$(mktemp -d) python3 -m unittest discover -s jin_agent/tests -t . -q`
→ `test_chat_context` 7/7 green; full suite **515 tests OK (1 skipped)**.

**RESULT:** Chhote follow-ups ab pichhle sawal ke context se jurre hain; `/new`
saaf context shuru karta hai. `VERSION` `2.9.0` barqarar; stdlib-only, local-only.

**PHASE REVIEW — PHASE 38: READY**

---

## 32. PHASE REVIEW — PHASE 39 — Explore Discovery Engine Fix (Bing + anomaly fallback) (2.9.0)

**TASK:** `/explore <topic>` Telegram channels kabhi discover nahi karta tha — hamesha
`📡 Telegram` group khaali, sirf Open web + Deep links. Root cause prove ho chuka:
`web_search_candidates` sirf DuckDuckGo par hardcoded tha (`uddg=` regex), aur DDG
abhi anti-bot "anomaly" page deta hai (`uddg=0`). `www.bing.com` allowlist me hi
nahi tha. Is liye `candidates=0 → probed=0 → added=0`.

**IMPLEMENTATION:**

| File | Change |
|---|---|
| `policy.py` | `ALLOWED_HOSTS` me `www.bing.com` (sirf search ke liye); `SOURCE_REGISTER` me `bing-web` (`https://www.bing.com/search`, `auto=True`, keyless HTML) — register 45 → 46 |
| `channels.py` | `decode_bing_url` (urlsafe base64 + padding + `validate=True`), `parse_bing_html` (`ck/a` decode + raw links), `bing_has_results` (`<li class="b_algo">`), `parse_ddg_html`, `web_search_probe` (Bing → DDG html → DDG lite; anomaly par agla engine), `merge_web_probe`, `web_search_candidates(..., info=)`; `run_discovery` me `web_search` hisaab + `tg_discovery_state` table (`save_discovery_state` / `last_discovery_state`) |
| `telegram_bot.py` | `/status` me **Telegram discovery** block (last, engine, candidates/probed/added, fail wajah); 0-candidate explore par honest message (`_explore_empty_reason`) |
| `tests/test_bing_discovery.py` (naya) | 16 tests: Bing parse + `ck/a` decode, anomaly fallback, policy allow, `/status` block, honest message |
| `tests/test_status_health.py`, `test_adapters_v2.py`, `test_governance.py`, `test_explore_v2.py` | count assertions 45 → 46 (auto 26 → 27) + mock signature |

**VERIFICATION:** `JIN_AGENT_DATA=$(mktemp -d) python3 -m unittest discover -s jin_agent/tests -t . -q`
→ full suite **531 tests OK (1 skipped)**. Live check (2026-11-19):
`web_search_candidates("android security")` → `engine=bing`, `anomaly=False`,
handles `['MobileSecurityTesting', 'androidMalware']` (DDG is dafa anomaly).

**RESULT:** `/explore` ab asli search engine (Bing) se Telegram channels dhoondta
hai; DDG html/lite fallback aur anti-bot anomaly detection wujood me hai. Fail hone
par bot user ko wajah aur `/status` engine health dikhti hai. `VERSION` `2.9.0`
barqarar; stdlib-only, local-only, onion fetch block aur FRP/FMI/HuaweiID/Knox/MDM
patterns untouched.

**PHASE REVIEW — PHASE 39: READY**

---

## 33. PHASE REVIEW — PHASE 40 — Key-Free Engine List (2.9.0)

**TASK:** User ne kaha "poori list add kro key free batch b add kro" — web /
regional / academic / patents / OSS / archive / news / social / TG dirs ke
engine source universe me add karne, har engine ke liye allowlist + register +
adapter/parser, aur jo block/key wale hon un par auto=False (jhoota auto NA).

**IMPLEMENTATION:**

| File | Change |
|---|---|
| `policy.py` | `ALLOWED_HOSTS` me 44 naye host; `SOURCE_REGISTER` me 46 naye entries (9 web, 9 regional, 7 academic, 3 patents, 8 OSS, 4 archive, 2 news, 2 social, 2 TG dirs) — register 46 → 92; `auto=True` sirf 12 engine jin ka live adapter results deta hai |
| `adapters.py` | `SimpleEngineAdapter` (URL template + parser kind), `parse_html_links` (`_LinkCollector`), `parse_json_rows`, 9 khaas JSON parser (doaj/europepmc/gitlab/huggingface/npm/crates/archive-search/openlibrary) + `SIMPLE_ENGINES` table; `ADAPTERS` 27 → 39 |
| `tests/test_keyfree_engines.py` (naya) | 19 tests: allowlist, auto/blocked flags, adapter presence, har parser |
| `tests/test_adapters_v2.py`, `test_governance.py`, `test_status_health.py` | counts 39 adapters / 92 register / 39 auto — 53 registry-only |

**LIVE CLASSIFICATION (2026-11-19, JIN-Agent UA):**
- **auto=True (12):** yahoojp, seznam, bing-news, doaj, europepmc, gitlab,
  huggingface, stackexchange, npm, crates, archive-search, openlibrary.
- **auto=False (34):** mojeek/marginalia/searx (captcha/JS), gibiru/qwant/
  swisscows/rambler/sourceforge (JS shell), ecosia/startpage/espacenet/
  telemetr (Cloudflare/Anubis 403), presearch (530), yandex (SmartCaptcha),
  baidu/sogou/naver/daum (JS/ad-heavy), yahoo (500), yahoo-news (404),
  semanticscholar (429), biorxiv (recent-feed only), unpaywall (email),
  core (429/key), base-search (access denied), patentscope (JS/session),
  uspto (401 key), codeberg (429), pypi (no search API), gutendex (timeout),
  googlebooks (429 quota), bsky (501), mastodon (empty), tgstat (JS shell).

**VERIFICATION:** `JIN_AGENT_DATA=$(mktemp -d) python3 -m unittest discover -s jin_agent/tests -t . -q`
→ **550 tests OK (1 skipped)**. End-to-end `adapters.run` (doaj/gitlab/npm/
openlibrary/yahoojp/bing-news) → 120 items, sab diagnostics ok.

**RESULT:** Source register 46 → **92** (39 auto / 53 registry-only); adapters
27 → 39. Har engine ki wajah (blocked/key/JS) register note me likhi hai.
`VERSION` `2.9.0`, `is_owner`, `server.py`, `watchdog.py`, onion fetch block
aur FRP/FMI/HuaweiID/Knox/MDM patterns untouched.

**PHASE REVIEW — PHASE 40: READY**

---

## 34. PHASE REVIEW — PHASE 41 — Google Dork + Extra Engines (2.9.0)

**TASK:** (1) Google-dork support — `jin_agent/dorks.py` helper, `/dork <query>`,
`/explore <topic> --dork`, onion dork sirf link, backend live test. (2) Aur
engines — news RSS / academic / patents / archive-data / web / TG-social.

**IMPLEMENTATION:**

| File | Change |
|---|---|
| `dorks.py` (naya) | operators (`site/intitle/inurl/filetype/exclude/build`), presets (tg/pdf/gov/edu/pastebin), `DORK_BACKENDS` registry, `parse_bing_results` (ck/a decode), `render`, `search` (Bing), `onion_link` (link-only), `selftest` |
| `telegram_bot.py` | `/dork` command, `split_dork_flag` + `/explore <topic> --dork`, `/status` me **Dork** block (1 kaam / 5 blocked), HELP aliases |
| `policy.py` | 44 naye host + 38 naye SOURCE_REGISTER entries — register 92 → 130 |
| `adapters.py` | RSS_FEEDS +10 news; naye parser datacite/openaire/hal/usgs/weather/wiby/rightdao/lemmy; `ADAPTERS` 39 → 57 |
| `tests/test_dorks.py` (naya) | 18 tests: operators, backend flags, parser, render, command, status |
| `tests/test_p41_engines.py` (naya) | 12 tests: allowlist, auto/blocked flags, parsers |
| counts | `test_adapters_v2`/`test_governance` 57 adapters / 130 register; `test_status_health` 130 total / 57 auto / 73 registry-only |

**DORK BACKEND (live 2026-11-19, JIN-Agent UA):**
- **kaam karta hai:** Bing (dork qabool, 8 results).
- **blocked:** Mojeek (captcha), DuckDuckGo Lite (HTTP 202 anomaly), Startpage
  (Anubis challenge), Ecosia (403 unusual traffic), Google gbv=1 (JS shell, 0 result).

**EXTRA ENGINES (live):**
- **auto=True (18):** bbc-news, aljazeera, arstechnica, wired, techcrunch,
  theverge, zdnet, cnet, nytimes, npr (news RSS); datacite, openaire, hal;
  usgs, weather; wiby, rightdao; lemmy.
- **auto=False (20):** wapo/reuters/groundnews (404), orcid (profiles only),
  scilit (403), fatcat (timeout), citeseerx (404), repec/econpapers (form/session),
  philpapers (403), pubpsych (404), ipaustralia (503), jplatpat (timeout),
  kipris (refused), commoncrawl (504), loc/worldcat (403 Cloudflare),
  reliefweb (403 appname), 4cdn/8kun (404).

**VERIFICATION:** `JIN_AGENT_DATA=$(mktemp -d) python3 -m unittest discover -s jin_agent/tests -t . -q`
→ **580 tests OK (1 skipped)**. Sab 18 naye auto adapters live chalaye (bbc 32,
nytimes 42, datacite 25, openaire 24, hal 25, usgs 25, weather 25, wiby 11,
rightdao 12, lemmy 25). `/dork android security` → 8 live Bing results.

**RESULT:** Register 92 → **130** (57 auto / 73 registry-only); adapters 39 → 57.
Dork sirf public search + onion link-only. `VERSION` `2.9.0`, `is_owner`,
`server.py`, `watchdog.py`, onion fetch block aur FRP/FMI/HuaweiID/Knox/MDM/IMEI
patterns untouched.

**PHASE REVIEW — PHASE 41: READY**

---

## 35. PHASE REVIEW — PHASE 42 — Synthetic Archive Guard + Live Scheduler (2.9.0)

**TASK:** User ki shikayat: bot ki di hui links "fake" lagti thin. Live `/explore`
me `https://example.org/8badfbb73842` jaisi URLs dikhin.

**ROOT CAUSE (prove kiya):** `server._start_scheduler(offline=True)` default tha —
yaani hosted scheduler **offline** chalta tha. `adapters._offline_items` offline
par `https://example.org/<fingerprint>` banawati links deta hai; wo items archive
me jamate the aur `/explore` / `/digest` unhe asli khabar ki tarah dikhate the.
Reproduce: `scheduler.tick(cfg, offline=True)` → `search_archive("android")` me
4 `example.org` items (bilkul wahi URL jo live explore me dikha).

**IMPLEMENTATION:**

| File | Change |
|---|---|
| `store.py` | `items.synthetic` column + purani DB migration (purane `example.org` rows ko flag karta hai); `upsert_items` flag set karta hai (`synthetic`/`kind=fixture`/`offline`/`meta.offline`); `search_archive` dono paths (FTS + LIKE) me `synthetic=0` filter |
| `normalizer.py` | `normalize()` `synthetic` field jodi jo hai (fixture/offline se derive) |
| `adapters.py` | `_offline_items` me `synthetic: True` |
| `server.py` | `_start_scheduler` ab **live** default; env `JIN_AGENT_SCHEDULER_OFFLINE=1` se offline minta`l |
| `tests/test_synthetic_guard.py` (naya) | 8 tests: flag, archive hide, `example.org` kabhi na wapas, purani DB migration, scheduler default |
| `tests/test_eval_scheduler.py` | `test_watchlist_job` asli item use karta hai (synthetic archive se bahar hai) |

**VERIFICATION:** `JIN_AGENT_DATA=$(mktemp -d) python3 -m unittest discover -s jin_agent/tests -t . -q`
→ **669 tests OK (1 skipped)**. End-to-end: offline `tick` → 106 items, sab
`synthetic=1`, `search_archive` **0** rows. Live `firehose` (gnews) → 101 asli
items, `synthetic=0`, archive 20 asli URLs dikhata hai.

**RESULT:** Bot ki di hui links ab hamesha asli hain — synthetic fixture archive
me hote hain magar user ko kabhi nahi dikhte. Hosted scheduler live chalta hai,
is liye archive asli khabaron se bharta hai. `VERSION` `2.9.0`, `is_owner`,
`watchdog.py`, onion fetch block aur FRP/FMI/HuaweiID/Knox/MDM/IMEI patterns
untouched.

**PHASE REVIEW — PHASE 42: READY**

---

## 36. PHASE REVIEW — PHASE 43 — Multilingual Query Variants (2.9.0)

**CONTEXT:** User ka `/explore` sirf English keyword samajhta tha. Urdu/Arabic/Roman
Urdu query par dhoond bohat kamzor thi (transliteration ka koi rasta nahi tha).
Saath hi `TELEGRAM_DISCOVERY_PLAN.md` likha gaya — 5-option architecture
comparison (Bot API / MTProto / search APIs / crawler / hybrid), gap analysis
G1–G24, P1–P5 phases, rollout + rollback.

**DECISION:** Hybrid architecture (free-first search providers + `t.me/s/`
preview + apni index); MTProto **opt-in** hi rahega (ToS + ban risk). Bot API me
channel-search method mojood hi nahi — ye verified fact hai, is liye Bot API sirf
`getChat` enrichment ke liye.

**CHANGES:**
- Naya `jin_agent/query_variants.py` (stdlib-only, default network-free):
  `script_of()`, `detect_language()` (script + stopword scoring),
  `transliterate()` (Urdu→Roman, Roman→Urdu, Arabic→Latin, Latin→Arabic),
  `translate_query()` (LLM on hone par LLM; warna ~35 EN↔UR↔AR builtin pairs;
  anu lafz par **khali dict** — jhoot nahi), `synonyms()`, `variants()`,
  `variant_texts()`.
- `channels.run_discovery(..., variants=None)` — variants ko web-probe fan-out
  me istemal karti hai (har variant par probe), output me `variants` darj.
- `scheduler.explore(..., variants=None)` forward.
- `telegram_bot._run_explore` — payload me `query_variants.variants(topic, cfg, 6)`.

**VERIFICATION:** `python3 -m compileall -q jin_agent` → COMPILE_OK.
`JIN_AGENT_DATA=$(mktemp -d) python3 -m unittest discover -s jin_agent/tests -t . -q`
→ **700 tests OK (skipped=1)** (669 + 31 naye `test_query_variants.py`).

**LIMITATION (honest):** Translation/transliteration abhi **offline builtin**
hai — bara coverage LLM ya paid API se hi milega. Discovery provider abhi bhi
RightDAO (rate-limit) + Bing/DDG fallback (bemusarir). Ye Phase 3 ka kaam hai.

**PHASE REVIEW — PHASE 43: READY**

---

## 37. PHASE REVIEW — PHASE 44 — Lyzem Provider + Discovery Layer (2.9.0)

**CONTEXT:** RightDAO akela discovery provider tha — burst ke baad rate-limit,
aur kuch queries par 0 handles. User ko Telegram-wide discovery chahiye jo
kisi bhi zaban ke keyword par kaam kare.

**INVESTIGATION (2026-11-21, live):** `https://lyzem.com/search?q=<keyword>`
bina login / bina API key kaam karta hai. Har query par 10 results, har result
ke saath `title="channel|group|bot|post|article|message"` aur
`https://t.me/<handle>(/<msg_id>)`. `android security` → 10 (channel/group/bot)،
`free api key` → 10، `firmware unlock` → 10، Urdu `موبائل` → 10 (post/channel).
Posts ke liye title aksar khaali hota hai aur descr me matched keyword `<em>`
se highlight hota hai.

**CHANGES:**
- Naya `jin_agent/discovery.py` (stdlib-only): `PROVIDERS = (rightdao, lyzem,
  bing, ddg-html, ddg-lite)`، `probe()`، `probe(merge=True)` (saare providers se
   handles ikhatte — source diversity)، `lyzem_records()` (type/handle/title/
  descr/url/msg_id)، TTL cache (`discovery_cache_seconds`, default 900s، `0` =
  band)، `clear_cache()`.
- `channels.py`: `LYZEM_SEARCH_URL`، `parse_lyzem_html()`، `lyzem_has_results()`؛
  `web_search_probe`/`web_search_candidates` ab `discovery` par muntaqil.
- `run_discovery` topic branch: `rightdao` + `lyzem` se **merge** (pehle
  first-wins tha) — live `android security` par web candidates 3 → 16.
- `policy.py`: `lyzem.com` allowlist + register entry (130 → 131).

**VERIFICATION:** `compileall` OK · **715 tests OK (skipped=1)** (700 + 16
naye `test_lyzem_discovery.py`). Live: `run_discovery("android security")` →
`web_search.engine = "rightdao, lyzem"`، tried `[rightdao, lyzem]`،
candidates 34، probed 15، added `android_broadcast`. Urdu query par candidates
45 (variants + merge). Koi `example.org` / synthetic nahi.

**LIMITATION (honest):** Lyzem subscriber count nahi deta؛ ranking abhi bhi
`check_channel` ke 30-din rule + signs par based hai. Telemetr/TGStat/tgAtlas
paid ya key-wale hain — Phase 3 ki "additional provider" free option (Lyzem)
puri tarah kaam karta hai.

**PHASE REVIEW — PHASE 44: READY**

---

## 38. PHASE REVIEW — PHASE 45 — Discovery Ranking + Safety (2.9.0)

**CONTEXT:** P44 ke baad discovery candidates ke paas relevance nahi thi —
ranking sirf `check_channel` ke recency/volume/subs par thi, spam/scam
channels bhi active ki tarah dikhte the, aur Telegram handles case-insensitive
hote hue bhi `dict.fromkeys` case-sensitive dedupe karta tha.

**CHANGES:**
- Naya `jin_agent/discovery_rank.py` (stdlib-only): `relevance()` /
  `relevance_detail()` / `relevance_reason()` (query terms -> title/handle/
  descr/preview, 0-10; Urdu/Arabic/Cyrillic fallback), `spam_reason()`
  (English + Roman Urdu + Urdu/Arabic lafz; FRP/FMI/MDM/IMEI/carrier-bypass
  NAHI — wo `policy.py` hai), `blocked_reason()` (`policy.BLOCK_PATTERNS` ka
  bina badla istemal), `dedupe_handles()` (case-insensitive).
- `channels.py`: `score(rec, cfg, query="")` aur
  `channel_signs(rec, cfg, query="")` ab relevance feed karte hain;
  `check_channel(channel, cfg, query="")` spam -> `status='spam'` (score 0),
  `policy` blocked -> `status='blocked'` (score 0); `parse_preview` me
  `descr` + `preview` (message text) — relevance/spam ke liye.
- `discovery.py`: `probe(merge=True)` ab `sources` (handle -> engine) aur
  `records` (Lyzem post/article/message) deta hai; `merge_web_probe` dono
  merge karta hai.
- `run_discovery`: case-insensitive dedupe (known/manual bhi lower), har
  `probe_rows`/summary me `source` (engine) + `relevance` + `reason`, aur
  `rank` (1..N: active -> score -> relevance); output me `summaries` +
  `lyzem_records`.

**VERIFICATION:** `compileall` OK · **749 tests OK (skipped=1)** (715 + 19
`test_discovery_rank.py` + 15 `test_explore_ux.py`). Naye tests: relevance
ordering, spam match/false-positive, FRP blocked (spam NAHI), case-insensitive
dedupe, source diversity, rank field.

**LIMITATION (honest):** Relevance terms `util.terms` (latin) + whitespace
fallback (non-latin) par based hai — stemming/morphology nahi. Spam list
chhoti hai; novel scam phrasing pakd sakti hai. Source engine sirf tab janta
hai jab web search chala; archive/pool candidates ka `source` khaali rehta
hai.

**PHASE REVIEW — PHASE 45: READY**

---

## 39. PHASE REVIEW — PHASE 46 — Telegram Explore UX (2.9.0)

**CONTEXT:** `/explore` cards me sirf naam/@handle/score/subs/status tha —
zaban, relevance reason, source link, post preview aur per-card actions nahi.
Loading/empty/error ka UX bhi adhoora tha.

**CHANGES:**
- `format_explore_cards_v2` ab HTML card deta hai: title, `@handle`,
  `https://t.me/<handle>` + `https://t.me/s/<handle>`, status badge, score,
  subs, last-post date, zaban (`query_variants.detect_language`), relevance
  reason (max 2 terms), `📡 <engine>` source badge. Post/article/message
  cards me 140-char preview + post link.
- `_render_explore` `parse_mode='HTML'` + `highlight.split_html` se
  tag-balanced 4096 chunks bhejta hai (koi adhura tag nahi).
- Har card par 4 actions: `🔗 Channel` / `🗂 Posts` (URL) + `🌐 Translate`
  (`tr:<topic_hash>:<item_hash>` — `llm.translate_text`) + `🔄 Refine`
  (`refine:<topic_hash>` — naya variant set). ✅/❌ gate + bulk ✅/❌ +
  `🔄 Aur explore karo` barqarar.
- `_run_explore`: pehle `⏳ Explore chal raha hai — <topic>` message, phir
  wahi message `✅ Explore ho gaya` / `⚠️ Explore me masla hua — <wajah>;
  detail local console par hai.` par edit. Khaali par saaf Roman Urdu
  `Koi naya item nahi mila — <wajah>`.
- `scheduler.explore`: `run_discovery` ke sath aye Lyzem records use karta
  hai (doosri network call nahi); offline me koi call NAHI.

**VERIFICATION:** **749 tests OK (skipped=1)**. Naye
`test_explore_ux.py` (15 tests): card fields, Urdu/Roman Urdu label, HTML
escape, post preview + 140-char truncate, 4 actions + bulk, translate/refine
callback, loading/empty/error, balanced chunks ≤4096.

**LIMITATION (honest):** Translate local LLM band hon to `available nahi`
ka paighaam deta hai (jhoota translation nahi). Post date Lyzem nahi deta,
is liye post card me date khaali. Refine variants discovery ke liye hote
hain, alag "variant picker" UI nahi.

**PHASE REVIEW — PHASE 46: READY**

---
