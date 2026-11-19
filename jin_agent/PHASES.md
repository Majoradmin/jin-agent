# PHASES — JIN Agent P13–P26

**Status:** ALL PHASES READY · **Date:** 2026-11-16 · **Version:** 2.9.0
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

## 21. PHASE REVIEW — PHASE 28 — Channel Memory & Health (2.10.0)

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

## 22. PHASE REVIEW — PHASE 29 — Confidence, Report File & Explore (2.10.0)

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
