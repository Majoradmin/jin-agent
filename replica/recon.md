# JIN Agent — Recon Map (replica-recon)

- **Repo:** `/Users/mac/Documents/jin-agent` (JIN Agent 2.9.0, Python stdlib-only)
- **Code checked:** 19 Nov 2026, `main` @ `c5fe4f2` (working tree clean)
- **Method:** sirf source code + README/PHASES/docs parhna. Koi live bot/network test nahi chalaya.
- **Scope note:** Telegram front-end + pipeline + data layer. MobileLab alag product hai, is recon me nahi.

---

## 1. Screens / Surfaces

### 1.1 Telegram (primary surface) — `jin_agent/telegram_bot.py`

| Surface | Trigger | Message type | Source |
|---|---|---|---|
| Welcome / menu | `/start`, `/help` | Plain text, 6 commands + misaal (example) | `HELP_TEXT` :108; dispatch :1270/:1273 |
| Bot "/" menu | startup | `setMyCommands` (best-effort, 6 commands) | `BOT_COMMANDS` :132; `register_commands` :341; `run` :1912 |
| Research start | `/research <sawal>` ya seedha matn | Header message, phir **edit-in-place** stages | `_send_research` :1602; `route_plain_text` :316 |
| Progress stages | research ke dauran | Wahi message edit: `⏳ Plan/Sources/Fetch/Verify/Brief` (3s throttle) | `_stage_status` :1522; `on_stage` :1647 |
| BLUF | report ke baad, high confidence | ≤1000 char TL;DR + 3-5 findings + confidence + trace path | `_bluf_text` :1550; send :1759 |
| Report file | high confidence + report `.md` | `sendDocument` (multipart, caption ≤1024) | `_API.send_document` :966; call :1766 |
| Report chunks (fallback) | low confidence ya file fail | 4096-char HTML chunks, query terms `<b>` | `send_chunks` :421; `highlight.split_html` :236; call :1780 |
| "Mil gaya?" gate | report ke baad | Inline buttons: ✅ Mil gaya / 🔁 Nahi mila | `after_report_buttons` :1165; `ask_after_report` :1189 |
| Retry round | 🔁 dabaya | Naya research, purane sources/channels skip | `handle_callback` :1876; `_send_research` :1626 |
| Deep engines | `/research ... --deep` ya `/deep` | Dark/deep engine links (onion sirf display) | `split_deep_flag` :332; `format_deep` :556; dispatch :1449/:1365 |
| Channel search | `/search <kw>`, `/tgsearch` | "🔍 search..." + results / empty hint | `_do_channel_search` :1242; `format_tg_results` :514 |
| Channels list | `/channels` | Active channels + `t.me` links (max 20) | `format_channels` :479; dispatch :1335 |
| Channel add gate | `/channels add <link>`, `/addchannel` | ✅ Confirm / ❌ Cancel buttons | `_ask_add_channel` :1231; callback :1845 |
| Channel added | ✅ dabaya | Save + probe + title/subs/posts | `_addchannel_now` :1202 |
| Channel remove | `/channels rm @h`, `/rmchannel` | "🗄️ archive (delete nahi)" | dispatch :1322/:1350; `channels.remove_channel` :198 |
| Explore digest | `/explore [topic]` | Discovery counts + top scored archive items | `format_explore` :592; dispatch :1430 |
| Explore cards + gate | `/explore` ke baad | Cards (naam, @handle, score, subs, link) + har item ✅/❌ + bulk | `format_explore_cards` :617; `_send_explore_gate` :716 |
| Explore confirm | ✅/❌ buttons | "✅ … memory me rakh liya" / "❌ … skip" | `_handle_explore_callback` :683 |
| Status | `/status` | Policy, poll failures, channels active/dead/archived/stale, sites, sources ok/fail, last explore, pending candidates | `format_status_text` :784; dispatch :1283 |
| Channel health | `/channelhealth` | Active/dead/archived/stale + "alive magar khamosh" (>30 din) | `format_channel_health` :1458 |
| Memory | `/memory` | Recent research memory (6) | `format_memory` :575; dispatch :1368 |
| Memory audit | `/memoryaudit` | duplicates / conflicts / stale | `format_memory_audit` :1480 |
| Digest | `/digest` | Daily digest + local report path | dispatch :1384 |
| Reports | `/reports` | Recent reports list | dispatch :1405 |
| Alerts | `/alerts` | Recent alert events | dispatch :1397 |
| Schedule | `/schedule` | Schedule minutes table | dispatch :1414 |
| Selftest | `/selftest` | Parser selftest PASS/FAIL | `format_selftest` :1497; `channels.parser_selftest` :421 |
| Stop | `/stop` | "🛑 Research rok di gayi" (foran, busy workers ke peeche nahi atka) | dispatch :1276; `_cancel_research` :284 |
| New context | `/new` | Purani memory band + pending gates clear | dispatch :1372 |
| Engines | `/engines` | Telegram search engines (bots + web) | `format_engines` :540 |
| Errors | har command | Named Roman Urdu error text (query required, not found, fail, timeout, unknown) | dispatch :1454 + per-branch |

**Purane aliases** (HELP_TEXT :124): `/addchannel`, `/rmchannel`, `/tgsearch`, `/deep`, `/engines`, `/memory`, `/stop`, `/new`, `/digest`, `/reports`, `/alerts`, `/schedule`, `/channelhealth`, `/memoryaudit`, `/selftest`.

**Callback data shapes** (:180-189, :1172, :1180):
- `mem:<row_id>:done|more|reset` — report gate
- `add:ok:<handle>` / `add:no` — channel add gate
- `exp:keep|skip:(all|ch:<handle>|st:<idx>)` — explore gate

### 1.2 Web console (secondary) — `jin_agent/web/` + `server.py`
7 tabs (`web/index.html` :25-32): **Console, Archive, Sources, Watchlist, Reports, Evaluation, Settings**.
HTTP API (`server.py`): GET `/api/status|health|metrics|changes|sources|archive|watchlist|reports|report|overview|events|jobs|runs|channels|settings|scheduler|tools`; POST `/api/run|eval/run|watchlist|watchlist/remove|feedback|settings|llm/test|scheduler|digest|alert/test|retention|backup|channels|classify` (:131-320).
Loopback default `127.0.0.1:8766`; `0.0.0.0` sirf explicit `JIN_AGENT_HOST`/`--host` (README :124).

### 1.3 CLI — `__main__.py`
`status, run, search, sources, digest, eval, batch, schedule, serve, supervisor, selftest, ci-gate, changes, classify, llm, channels` (README :31-48).

---

## 2. Flows (with states)

### (a) Plain text → research
1. User matn bhejta hai (bina `/`). `route_plain_text` (:316): agar poore matn me sirf link/`@handle` hai → `/addchannel`; warna `/research <matn>`. Channel post forward → `/addchannel @<forwarded>` (:461 `forwarded_handle`).
2. `dispatch` → `research` (:1443) → `split_deep_flag` (:332).
3. `_send_research` (:1602): `_research_lock` ke andar naya session; header message bhejo; `on_stage` callback se stages edit.
4. `research_full` (:1091): **parallel** web (`orchestrator.run`) + saved-channel search (`channels.search_posts`), pool 2 workers; web timeout 180s, channel 60s.
5. `orchestrator.run` (:40): policy gate → planner → adapters → normalizer → `store.upsert_items` → verify/cross-check → rank → collapse → on-topic filter → briefer.
6. Report: confidence ≥ threshold (:1734) → BLUF + `sendDocument`; warna chunks; `absence_kind` ke mutabiq honest message.
7. Memory: `searchmemory.begin/remember/remember_failed/note_source_stat` (:1793-1819).

**States:** loading (header + stage edits) · empty (`no_results` → "Koi result nahi mila", :1742) · error (`fetch_failed` :1747, timeout :1699, exception :1680) · partial (:1550 note) · blocked (:1064) · success (BLUF + file/chunks).

### (b) `/research --deep`
`split_deep_flag` (:332) query se `--deep` nikalta hai; research ke baad `format_deep(query)` (:556) links bhejta hai. Onion links **sirf display**, kabhi fetch nahi (`policy.DARK_WEB_RULE` :18). `/deep` alias bhi (:1365).

**States:** loading/empty/error/success wahi; deep links hamesha "links-only" note ke saath.

### (c) `/explore [topic]` → scope → cards → ✅/❌ gate → memory
1. `dispatch` :1430 → `scheduler.run_job("explore", {"query": topic}, cfg, offline=False)` (:1434).
2. `scheduler.explore` (:45): `channels.run_discovery` (web search + archive/preview harvest + probe + score) + `store.search_archive` top 10 + `orchestrator.digest` + `store.add_event("explore")`.
3. `format_explore` (:592) digest bhejo.
4. `_send_explore_gate` (:716): naye channels (max 10) + scored sites (max 8) → `_EXPLORE_PENDING[chat_id]`; cards + per-item ✅/❌ + bulk "✅ Sab rakho / ❌ Kuch nahi".
5. Callback `_handle_explore_callback` (:683): keep → `channels.add_channel`/`add_site`; skip → `channels.remove_channel` (archive, delete nahi).

**States:** loading (discovery probes) · empty ("Koi naya channel/site nahi mila", :752) · error ("❌ Explore fail", :1436) · expired gate ("Purana explore gate hai", :703) · success (✅/❌ confirm messages).

### (d) `/channels add/rm/list`
- list: active channels + links; khali ya sab dead/archived ho to alternate hint (:479-497); `--all` sab (:1328).
- add: `clean_handle` (:288) → `_ask_add_channel` confirm gate (:1231) → callback `add:ok` → `_addchannel_now` (:1202) save + `check_channel` probe → ✅/⚠️ message.
- rm: `remove_channel` (:198) `status='archived'`, score=0; hard delete nahi.

**States:** loading (probe) · empty (list empty, :492) · error (add fail :1209, not found :1325) · success (✅ save / 🗄️ archive).

### (e) `/search`
`_do_channel_search` (:1242) → `channels.search_posts` (:732): `t.me/s/<ch>?q=` public preview, max 8 channels × 6 posts, 4 workers, dedupe by URL; report me `channel` + `matched_in='channel-search'`.
**States:** loading ("🔍 Channels ke andar search…") · empty ("nah mila" + agla step hints, :519) · error ("❌ Channel search fail", :1256) · partial (failed channels list, :533) · success (numbered results + URLs).

### (f) Scheduler auto jobs
`Scheduler` thread (:149) har 20s `tick` (:116): due jobs enqueue → claim → `run_job` (:70).
8 kinds (`JOB_MINUTES` :15, defaults `config.py` :68):
| Kind | Kaam | Default |
|---|---|---|
| feeds | firehose sab adapters | 15 min |
| telegram | firehose Telegram adapter | 30 min |
| papers | firehose openalex/crossref/arxiv | 360 min |
| digest | orchestrator.digest + Telegram alert | 1440 min |
| watchlist | archive search per term → alert | 5 min |
| retention | `store.retention` + backup | 1440 min |
| discovery | `channels.run_discovery` | 720 min |
| explore | `scheduler.explore` | 1440 min |

`--offline` me web probes skip (harvest-only). `schedule_state` table last-run ts. Job errors `events(kind='job_error')`.
**States:** running (jobs table status pending/running/done/failed) · empty (koi due job nahi) · error (per-job, isolation) · success (processed list).

### (g) `/stop`, retry/rounds
- `/stop` :1276 → `_cancel_research` (:284): `_stop_research=True` + session invalidate + threads join (1s). `_send_research` loop turant wake (:1690-1697).
- Retry: report ke "🔁 Nahi mila" → `handle_callback` :1876 → `memory.reset` (agar kuch use nahi hua) → `_send_research(advance=True, related=True)` → `llm.related_queries` (:203) 3 queries, pehla non-empty report.
- Round cap: `max_rounds()` (:67, env `JIN_AGENT_MAX_ROUNDS`, default 5); limit par "🛑 Round limit" (:1628).
- Purane sources/channels + failed channels skip (:1655).
**States:** loading (round header) · stopped ("stopped by user" :1697) · error (max rounds :1630, timeout :1699) · success.

### (h) Error / partial / empty states (cross-cutting)
- Policy block: `⛔ Request block hua` (:1064) + gate JSON.
- `absence_kind`: `ok` / `no_results` / `fetch_failed` / `partial` / `blocked` (:1148-1153).
- Channel search fail → report me ⚠️ section (:1083).
- Report khali → "❌ Report khali rahi" (:1719).
- Low confidence → "⚠️ Report bharosemand nahi" + local console (:1773).
- Poll failure → `/status` me `poll_failures` (:811), exponential backoff + optional exit cap (:1971).
- Unknown command → "Maaf kijiye… /help" (:1454).

---

## 3. Components (1-line role + key functions)

| File | Role | Key functions (file:line) |
|---|---|---|
| `telegram_bot.py` | Telegram front-end: long polling, commands, gates, report delivery | `route_plain_text`:316, `dispatch`:1264, `_send_research`:1602, `research_full`:1091, `_send_explore_gate`:716, `handle_callback`:1833, `run`:1896 |
| `channels.py` | Channel registry, discovery, liveness scoring, saved-channel search | `add_channel`:181, `remove_channel`:198, `run_discovery`:614, `check_channel`:550, `score`:465, `search_posts`:732 |
| `orchestrator.py` | End-to-end pipeline: gate→plan→fetch→normalize→verify→rank→brief | `run`:40, `run_many`:230, `digest`:258, `_write_trace`:25 |
| `scheduler.py` | SQLite job queue + 8 auto jobs | `tick`:116, `run_job`:70, `firehose`:27, `explore`:45, `Scheduler`:149 |
| `store.py` | SQLite WAL + FTS5 archive, dedupe, jobs, watchlist, retention, backup | `init_db`:206, `upsert_items`:249, `search_archive`:317, `retention`:599, `backup`:736 |
| `briefer.py` | Roman Urdu report builder (facts/recommendations/not-verified) | `_markdown`:89, `build`:282, `save`:347, `bucket_for`:61 |
| `policy.py` | Legal source register, policy gate, SSRF/allowlist, dark-web rule | `classify`:201, `check_url`:136, `register`:237, `SOURCE_REGISTER`:58 |
| `highlight.py` | Query-term HTML highlight + entity-safe chunking | `terms`:29, `highlight_html`:180, `split_html`:236 |
| `adapters.py` | 27 adapters + RSS, one fetch contract, offline fixtures, diagnostics | `fetch`:45, `run`:1321, `ADAPTERS`:1182 |
| `verifier.py` | Provenance, cross-verification, confidence, citation audit | `verify`:21, `cross_check`:84, `collapse`:115, `aggregate_confidence`:194, `citation_audit`:255 |
| `planner.py` | Tool plan (LLM JSON tool calls + deterministic fallback), validate/scrub | `plan`, `execute`, `validate`, `scrub` |
| `llm.py` | Optional local/OpenAI-compatible LLM; token budget; translation; related queries | `resolve`:43, `token_usage`:93, `related_queries`:203, `translate_text`:237 |
| `searchmemory.py` | Per-query search memory (used sources/channels, negative TTL) | `begin`, `remember`, `remember_failed`, `audit`, `reset_chat` |
| `snapshots.py` | Page change detection (`page_snapshots`) | `record`, `changes_since`, `recent_changes` |
| `canonical.py` | URL canonicalization, near-dup title clustering | `canonicalize`, `dedupe_key`, `near_duplicate_titles` |
| `ratelimit.py` | Per-host interval + exponential backoff | `wait`, `note_success`, `note_failure` |
| `alerts.py` | Telegram Bot API alerts (opt-in) + local alert log | `send_telegram`:29, `get_updates`:53 |
| `server.py` | Loopback HTTP console/API | `do_GET`:131, `do_POST`:215, `make_server`:359 |
| `config.py` | Local config + defaults (schedule, topics, source flags) | `DEFAULT`:33, `load`, `public` |
| `metrics.py` / `logging_setup.py` | In-memory metrics; redacted JSON-lines logs | `inc`, `snapshot`; `redact`:92, `get_logger`:204 |
| `evaluator.py` | 25-query offline eval harness | `run`:132 |
| `ci_gate.py` | Offline release gate (compile+import+tests+eval) | `run` |
| `supervisor.py` / `watchdog.py` | Hosted console+bot auto-restart; watchdog | — |

---

## 4. Inferred Data Model (code se verify)

**16 tables** (15 physical + 1 FTS virtual). Note: task gawah ne `channels` kaha tha, asli naam `tg_channels` hai.

### store.py — `SCHEMA_MAIN` (:21) / `SCHEMA_FTS` (:155)
| Table | Columns | Indexes / constraints |
|---|---|---|
| `items` | id PK, guid UNIQUE, url, canonical, title, source, source_key, tier, trust, trust_label, category, published, date_checked, fetched_at, excerpt, body, fingerprint, content_hash, entities(JSON), score, reasons(JSON), confidence, verified, cross_verified, link_only, useful, meta(JSON) | idx_items_fingerprint, idx_items_fetched, idx_items_category, idx_items_source; UNIQUE(guid) |
| `items_fts` | FTS5(title, excerpt, body, source) external content → `items` | triggers items_ai/ad/au |
| `runs` | id PK, query, mode, started_at, finished_at, status, items_count, sources_ok, sources_failed, metrics(JSON) | — |
| `sources` | key PK, name, tier, trust, enabled, ok_count, fail_count, last_ok, last_error, status, last_verified_at, stale_days | — |
| `watchlist` | id PK, term UNIQUE, category, active, created_at, last_hit | — |
| `entities` | id PK, item_id, kind, value | UNIQUE(item_id, kind, value) |
| `jobs` | id PK, kind, payload(JSON), status, run_at, attempts, last_error, created_at, finished_at | idx_jobs_status(status, run_at) |
| `schedule_state` | key PK, last_ts | — |
| `reports` | id PK, title, query, fmt, path, created_at, metrics(JSON) | — |
| `feedback` | id PK, guid, useful, note, created_at | — |
| `events` | id PK, ts, kind, detail | — |
| `page_snapshots` | id PK, source_key, url, canonical, ts, first_seen, content_hash, size, text, changed, added_lines, removed_lines, diff(JSON) | idx_page_snapshots_ts, idx_page_snapshots_source; UNIQUE(source_key, canonical) |

### channels.py — `SCHEMA` (:43)
| Table | Columns | Notes |
|---|---|---|
| `tg_channels` | channel PK, status(active/dead/archived/stale), origin(manual/auto), added_at, last_checked, last_post_at, post_count, subscribers, title, score, note | archive-not-delete |
| `tg_candidates` | handle PK, found_at, probed_at | discovery pool |
| `tg_sites` | url PK, title, source, topic, added_at | explore ✅ memory |

### searchmemory.py — `SCHEMA` (:33)
| Table | Columns | Indexes |
|---|---|---|
| `search_memory` | id PK, chat_id, query_key, query, round_no, used_sources(JSON), used_channels(JSON), failed_channels(JSON), rejected_ideas(JSON), source_stats(JSON), status, created_at, updated_at | idx_search_memory_chat(chat_id, query_key) |

**Migrations:** `init_db` sources me `status`/`last_verified_at`/`stale_days` ALTER; `searchmemory.ensure_table` `failed_channels`/`rejected_ideas`/`source_stats` ALTER. Sab tables `IF NOT EXISTS` + WAL + `foreign_keys=ON` (:186-188).

**Retention:** `store.retention` (:599) items + events/runs/reports/jobs/search_memory/tg_candidates prune; dead `tg_channels` TTL; traces 30 din; backups keep 7.

---

## 5. Verification notes (code se)

- `VERSION = "2.9.0"` (`__init__.py`:10); `POLICY_ID = "SAHULAT-SAFE-SERVICE-v1"` (:11).
- `policy.SOURCE_REGISTER` = **45** entries (grep count, 19 Nov 2026). README "19 adapters" stale; `ADAPTERS` = **27** (7 RSS + 20 class adapters, `adapters.py`:1182).
- Tests: **480** `def test_` functions across 32 files (grep). README "311" aur PHASES "475" stale hain.
- `is_owner` default **allow-all** agar `telegram_chat_id` unset (:1947 warning) — production risk, code-verified.
- Report file = `.md` hi (`briefer.save` :347); PDF/HTML export nahi.
- Koi MTProto/userbot/private scrape nahi; Telegram sirf `t.me/s/` public preview + Bot API (README :131, channels.py :8-11).
