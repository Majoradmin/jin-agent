# JIN Agent — Production Readiness Audit Report

- **Bot:** `@jin_agent101_bot`
- **Repository:** https://github.com/Majoradmin/jin-agent (`origin` confirmed)
- **Commit audited:** `eb6e83e` (`fix(status): /status aur /channelhealth me spam/blocked channels ki ginti bhi dikhao`)
- **Branch:** `main` (only branch; `origin/main` = `eb6e83ee52d3f8901848f5e5175d352d3ee2763d`)
- **Audit date:** 2026-11-21
- **Working tree:** clean (`git status --porcelain` empty)
- **Auditor method:** static code review + executed test suite + live Telegram user journey (real browser session, logged-in Telegram Web)
- **Rules honoured:** read-only audit; no production config/secret changed; no deploy/start; no secrets reproduced.

> **Evidence rule:** Every PASS below was produced by an executed command or a code reference. Items that could not be executed are marked **NOT TESTED** / **NOT VERIFIABLE**. README/commit-message claims were not treated as proof.

---

## 1. Executive verdict

**Production readiness: CONDITIONALLY READY.**

**Can a real user rely on `@jin_agent101_bot` today?**

> **Yes, with conditions.** A real user can send `/start`, `/help`, `/status`, `/explore <keyword>` (English, Urdu, Roman Urdu), `/research <sawal>`, `/channels`, `/search`, `/dork`, `/report [md|html]` and receive a working, non-fabricated, multi-source response. The core research pipeline and the new discovery pipeline are **real and verified live**. The conditions are:
>
> 1. **The unauthenticated management console on port 8766 must not be publicly reachable.** In the deployed configuration (`render.yaml` sets `JIN_AGENT_HOST=0.0.0.0`) the HTTP control server has **no authentication** on `POST /api/settings`, `/api/run`, `/api/retention`, `/api/backup`. This is a **P0 security blocker** for public hosting.
> 2. **Telegram authorization defaults to allow-all** when `TELEGRAM_CHAT_ID` is unset. This is acceptable for a single-owner personal bot but is **not acceptable if the bot is opened to the public**.
> 3. **Discovery breadth is limited by third-party providers**, not by this codebase. `/explore android` returned **0 Telegram candidates** on the live bot; `/explore موبائل سیکیورٹی` returned 9; `/explore mobail security` returned 9. This is honest, not fabricated — but it is not "Telegram-wide".

**Overall confidence: HIGH** in the code-level findings (749 tests executed, static review of 164 tracked files, live Telegram verification). **MEDIUM** in the live-journey completeness (Telegram Web DOM reads were flaky for 5 of the paths; see §4).

### Live verification summary (real bot, 2026-11-21)

| Check | Result |
|---|---|
| Bot reachable by Telegram | **YES** — real replies received in chat `Jin->Agent` |
| Deployed commit | **`eb6e83e`** (latest) — Phase-5 card format live |
| `/start` | PASS — 6 commands + "Baqi commands:" (18) |
| `/help` | PASS — same menu |
| `/status` | PASS — 131 sources (58 auto / 73 registry-only), 30 active / 110 dead / 3 archived Telegram, Dork 1 working / 5 blocked, failed-source names + reasons |
| `/explore android` | PARTIAL — Open web (5) + Deep links (4); **Telegram section empty (0 candidates)** |
| `/explore موبائل سیکیورٹی` | PASS — 9 Telegram items, card format correct, 3 post cards, `🎯 موبائل`, language labels |
| `/explore mobail security` | PASS — 9 Telegram items, `Roman Urdu` language detected, `🎯 mobail` |
| `example.org` (synthetic) leakage | **0 occurrences** in all three live `/explore` results |
| Latency | 2–15 s depending on provider |

---

## 2. Truth table

| Area | Claimed / assumed status | Verified status | Evidence | Risk | Blocker |
|---|---|---|---|---|---|
| Repository accessible | assumed | **PASS** — `origin https://github.com/Majoradmin/jin-agent.git`, HEAD `eb6e83e` | `git remote -v`; `git rev-parse --is-inside-work-tree` | Low | No |
| Language / framework | Python bot | **PASS** — Python 3.11-slim (Dockerfile), stdlib-only core, `PySocks==1.7.1` optional | `Dockerfile`, `requirements.txt` | Low | No |
| Entry point | `python -m jin_agent supervisor` | **PASS** — `bot.py` → `jin_agent.__main__.main(['supervisor'])`; `Dockerfile:23`; `render.yaml:9` | code + deploy files | Low | No |
| Test suite | 749 tests claimed | **PASS** — `Ran 749 tests — OK (skipped=1)` | executed command, §6.1 | Low | No |
| compileall | — | **PASS** — rc 0 | `python3 -m compileall -q .` | Low | No |
| Long polling (no webhook) | — | **PASS** — `grep setWebhook\|secret_token` → 0 hits | code grep | Low | No |
| Synthetic-item guard | claimed fixed | **PASS** — live `/explore` ×3 showed 0 `example.org`; `search_archive` filters `synthetic=0` | `store.py`, live Telegram | Low | No |
| Scheduler live by default | claimed fixed | **PASS** — `JIN_AGENT_SCHEDULER_OFFLINE` default `0` | `server.py`, live `/status` real sources | Low | No |
| Per-source diversity cap | claimed | **PASS** — 5 sources in one local report; live BLUF 5 findings from 5 sources | `orchestrator._diversify`, live | Low | No |
| Multilingual query pipeline | implemented | **PARTIAL** — language detect/transliteration/synonyms verified live; **translation requires LLM or builtin table** | live `/explore` Urdu/Roman Urdu | Medium | No |
| Telegram-wide discovery | "scalable Telegram-wide" | **PARTIAL** — RightDAO + Lyzem (10 results/query) + own DB; **no MTProto**; `/explore android` → 0 candidates | live `/status`, `/explore` | **High** | No |
| Channel ranking (relevance/activity/subs) | implemented | **PARTIAL** — relevance 0–10 substring; 30-day recency; subscribers from preview; no ML | `discovery_rank.py`, live cards | Medium | No |
| Spam/scam filter | implemented | **PARTIAL** — small keyword list, title/descr/note only | `discovery_rank.spam_reason` | Medium | No |
| Unsafe-content filter | implemented | **PARTIAL** — reuses `policy.BLOCK_PATTERNS`; not applied to every content field | `discovery_rank.blocked_reason` | Medium | No |
| Admin authorization | assumed safe | **FAIL** — `is_owner()` allow-all when `TELEGRAM_CHAT_ID` unset | `telegram_bot.py:541-555` | **High** | **YES** |
| Management console auth | assumed safe | **FAIL** — `POST /api/settings|run|retention|backup` unauthenticated; bound to `0.0.0.0` in deployed config | `server.py:215-318`, `render.yaml:13-14` | **Critical** | **YES** |
| SSRF protection | assumed | **PARTIAL** — allowlist + redirect re-validation, but `trusted_public_endpoint()` does **not** resolve DNS | `policy.py:319-341` | Medium | No |
| Secrets in repo / git history | assumed none | **PASS** — 0 hits in `git grep` and `git log --all -p` | executed greps | Low | No |
| SQL injection | assumed safe | **PASS** — all `execute()` parameterized | `store.py` | Low | No |
| Prompt injection | assumed safe | **PASS** — `planner.validate` + `INJECTION` scrub | `planner.py` | Low | No |
| TLS verification | assumed on | **PASS** — 0 hits `CERT_NONE`/`verify=False` | code grep | Low | No |
| Database durability | assumed | **PARTIAL** — WAL + `foreign_keys=ON`; **no VOLUME**, DB file mode `0644`, no encryption, no restore test | `store.py:189-196`, `Dockerfile` | **High** | **YES** |
| Retention correctness | claimed | **PARTIAL** — effective 90 days; `DEPLOY.md:42` says 180; `chat_context`/`feedback`/`page_snapshots`/`tg_sites` unbounded | `store.py:686-741`, `config.py:78` | Medium | No |
| Data deletion / export | assumed | **NOT IMPLEMENTED** — no `/delete`, `/export`, `/forget`; `/new` only resets status | `searchmemory.py:288-295` | Medium | No |
| Observability | assumed | **PARTIAL** — `logs/agent.log` (2 MB × 3), `/api/status`, `/api/runs`, `/api/jobs`, `/api/events`; no metrics/alerting/APM | code | Medium | No |
| Health check | assumed | **PASS** — `render.yaml` `healthCheckPath: /api/health`; `GET /api/health` exists | `render.yaml` | Low | No |
| Rollback | assumed | **PASS** — git history + FadeHost "Redeploy (pull latest)" | FadeHost console | Low | No |

---

## 3. Critical blockers (P0)

### P0-1 — Unauthenticated management console (CRITICAL)
- **Problem:** `server.py` `do_POST` exposes state-changing endpoints with **no authentication**. `POST /api/settings` can rewrite the bot token / chat id / LLM key; `POST /api/run` triggers outbound network work; `POST /api/retention` deletes data; `POST /api/backup` reads the database.
- **Affected files:** `jin_agent/server.py:215-318`, `jin_agent/server.py:380-383`, `render.yaml:13-14`, `Dockerfile:19`
- **Evidence:** static review; `render.yaml` sets `JIN_AGENT_HOST=0.0.0.0`; `server.py` `do_POST` has no auth check.
- **Reproduction:** start the server with `JIN_AGENT_HOST=0.0.0.0`, then `curl -X POST http://<host>:8766/api/settings -d '...'` from any network.
- **Fix:** bind to loopback by default in production, **or** require a shared secret (`JIN_AGENT_ADMIN_TOKEN`) checked on every `/api/*` mutating route, **or** disable the console entirely in hosted mode.
- **Acceptance test:** unauthenticated `POST /api/settings` returns 401/403; with the correct token it succeeds; a test asserts both.
- **Risk:** Critical. **Blocker:** Yes.

### P0-2 — Telegram authorization allow-all (HIGH)
- **Problem:** `is_owner()` returns `True` for everyone when `TELEGRAM_CHAT_ID` is unset. Admin/owner-only behaviour (settings, channels, exploration, research) is then available to any Telegram user who finds the bot.
- **Affected files:** `jin_agent/telegram_bot.py:541-555`, `jin_agent/telegram_bot.py:76-83`, gates at `:2965` and `:2984`
- **Evidence:** code reference; live bot logs `[bot] KHABARDAAR: telegram_chat_id unset — allow-all mode`.
- **Reproduction:** deploy without `TELEGRAM_CHAT_ID`; message the bot from a second account; it responds.
- **Fix:** fail fast on startup when `TELEGRAM_CHAT_ID` is unset in a hosted environment (`JIN_AGENT_REQUIRE_CHAT_ID=1` already exists but defaults off), and set the env var in production.
- **Acceptance test:** with the flag on and no chat id, the bot exits with a clear error; with a chat id, a non-owner message is rejected.
- **Risk:** High. **Blocker:** Yes for public hosting; No for single-owner private use.

### P0-3 — No persistent volume for the database (HIGH)
- **Problem:** `Dockerfile` creates `jin_agent/data` but declares no `VOLUME`; the container filesystem is ephemeral. A redeploy/restart can lose the SQLite DB (research memory, channel index, reports, runs).
- **Affected files:** `Dockerfile:15`, `render.yaml`, `jin_agent/config.py` (`data_dir()`)
- **Evidence:** static review; `stat` shows `jin_agent.db` mode `0644`, no encryption.
- **Reproduction:** restart the container and compare `jin_agent/data/jin_agent.db` before/after.
- **Fix:** mount a persistent volume at the data dir (Render Disk / host path), and set file mode `0600`.
- **Acceptance test:** documented restart procedure; DB row count unchanged across restart; `stat -c %a` = 600.
- **Risk:** High. **Blocker:** Yes for data durability.

### P0-4 — No restore path for backups (MEDIUM-HIGH)
- **Problem:** `store.backup()` + `_prune_backups()` exist and keep 7 rolling backups, but **there is no restore function and no restore test** (`grep restore jin_agent/tests` → 0).
- **Affected files:** `jin_agent/store.py:823-838`, `jin_agent/store.py:770-793`
- **Fix:** add `store.restore(path)` + a test that backs up, mutates, restores, and compares row counts.
- **Acceptance test:** round-trip test passes.
- **Risk:** High (data loss). **Blocker:** Yes for durability claims.

---

## 4. Complete test matrix

### 4.1 Commands (live Telegram, chat `Jin->Agent`, 2026-11-21)

| Command | Expected | Actual | Status | Evidence |
|---|---|---|---|---|
| `/start` | welcome + command menu | 6 commands + "Baqi commands:" (18) | **PASS** | live, 15:15:37 → 15:15:39 (2 s) |
| `/help` | same menu | same | **PASS** | live |
| `/status` | agent + explore status | full status incl. 131 sources, 30/110/3 channels, 4 failed sources with reasons | **PASS** | live, 15:16:17 → 15:16:19 |
| `/explore android` | cards | Open web (5) + Deep (4); Telegram empty | **PARTIAL** | live, 15:16:52 → 15:16:59 |
| `/explore موبائل سیکیورٹی` | cards + language | 9 items, 3 post cards, `🎯 موبائل`, language labels | **PASS** | live, 15:17:36 → 15:17:48 |
| `/explore mobail security` | cards + Roman Urdu detect | 9 items, `Roman Urdu`, `🎯 mobail` | **PASS** | live, 15:18:19 → 15:18:34 |
| `/research free api key` | report | query-pollution fixed; relevant items; 5 sources | **PASS** | live, earlier session |
| `/report html` | HTML file | delivered | **PASS** | live, earlier session |
| `/report md` | Markdown file | delivered | **PASS** | live, earlier session |
| `/dork <query>` | dork links + live results | Bing results + presets | **PASS** | live, earlier session |
| `/channels` | saved channels list | `📡 Aap ke channels (30)` | **PASS** | live, 14:49 |
| `/search`, `/tgsearch` | channel search | results with `t.me/s/...` links | **PASS** | live, earlier session |
| `/memory`, `/new` | memory list / clear | worked | **PASS** | live, earlier session |
| `/digest`, `/alerts`, `/reports`, `/schedule`, `/channelhealth`, `/memoryaudit`, `/selftest` | status outputs | worked | **PASS** | live, earlier session |
| unknown command | polite fallback | "Maaf kijiye… /help use kijiye." | **PASS** | earlier session; **re-test flaky** (§4.4) |
| empty message | graceful handling | **NOT VERIFIED** | **NOT TESTED** | flaky read |
| very long message | graceful handling | **NOT VERIFIED** | **NOT TESTED** | flaky read |
| emoji / mixed Urdu-English | handled | emoji message sent; read stale | **NOT TESTED** | flaky read |

### 4.2 Inline buttons / callbacks

| Callback | Expected | Actual | Status |
|---|---|---|---|
| `exp:keep:ch:<h>` / `exp:skip:ch:<h>` | memory gate | implemented; gate observed live in earlier sessions | **PASS** |
| `exp:keep:all` / `exp:skip:all` | bulk gate | implemented; live "✅ Bulk explore: 13 memory me" | **PASS** |
| `exp:topic:<hash>` | topic picker | implemented; live picker observed | **PASS** |
| `exp:scope:*` | scope filter | implemented; live scope buttons observed | **PASS** |
| `exp:more:<topic>` | "Aur explore karo" | implemented (`1c3cf73`); live observed | **PASS** |
| `add:ok` / `add:cancel` | channel confirm gate | implemented; live observed | **PASS** |
| `mem:<id>:done/more` | report feedback / round 2 | implemented; live observed | **PASS** |
| `tr:<hash>` | translate card | implemented (`2dad49c`); not live-tested | **PARTIAL** |
| `refine:<hash>` | refine search | implemented (`2dad49c`); not live-tested | **PARTIAL** |
| `rm:`, `dork:`, `ytn:` | — | **DO NOT EXIST** (grep 0) | **N/A — dead assumption** |

### 4.3 Failure modes

| Failure | Expected | Actual | Status |
|---|---|---|---|
| Telegram 429 | retry with `retry_after` | implemented, 3 attempts | **PASS** (code) |
| Poll failure | backoff 5/10/20/40/60 s + `MAX_POLL_FAILURES` | implemented | **PASS** (code) |
| Provider HTTP error | named in `/status` | live showed 429/403/SSL with reasons | **PASS** (live) |
| Empty provider results | honest "no results" | live: `/explore android` Telegram empty, no fake items | **PASS** (live) |
| LLM provider off | rule-based fallback | `llm.provider=off` default; `llm_mode=rule_based` | **PASS** (code + local run) |
| LLM timeout | fallback, no crash | `llm.chat` guarded; rule-based path | **PASS** (code) |
| DB missing | auto-create + migrate | `init_db()` creates schema | **PASS** (code + tests) |
| Duplicate update | no duplicate side effects | offset = last_id + 1; research serialized by `_research_lock` | **PASS** (code) |
| Concurrent same-user messages | no duplicate replies | `_research_lock` + per-chat rate limit 20/min | **PASS** (code) |
| Process restart mid-task | graceful | supervisor restarts children; in-flight work lost (no job queue) | **PARTIAL** |
| Malformed webhook payload | — | **N/A** — no webhook | **N/A** |

### 4.4 NOT VERIFIED (honest gaps)

Telegram Web DOM reads were flaky at ~15:20; five paths (`/dork android security`, `/report html`, `/report md`, `/xyzzy123`, emoji message) returned stale DOM and could not be confirmed in that pass. Earlier sessions did verify `/dork`, `/report html`, `/report md`, and unknown-command handling, so the risk is low but the evidence is not from this pass.

---

## 5. Feature classification (REAL / PARTIAL / MOCK / STUB / NOT IMPLEMENTED)

| Feature | Class | Basis |
|---|---|---|
| Telegram long-polling bot | **REAL** | live replies |
| Command dispatch (21 commands) | **REAL** | live + code |
| Research pipeline (planner → adapters → store → briefer) | **REAL** | live reports, 749 tests |
| Multilingual detect / transliteration / synonyms | **REAL** | live language labels |
| Machine translation | **PARTIAL** | builtin ~35 terms + optional LLM; not a real MT engine |
| Telegram-wide search | **PARTIAL** | RightDAO + Lyzem only; no Bot-API search method exists |
| MTProto user-client discovery | **NOT IMPLEMENTED** | deliberately out of scope (ToS risk) |
| Channel ranking | **PARTIAL** | substring relevance + 30-day recency + subscribers; no ML |
| Spam/scam filter | **PARTIAL** | small keyword list |
| Unsafe-content filter | **PARTIAL** | reuses `policy.BLOCK_PATTERNS`; coverage incomplete |
| "100–200 channels per keyword" | **NOT IMPLEMENTED / NOT POSSIBLE with current providers** | Lyzem returns 10/query; RightDAO rate-limits |
| Management console | **REAL but UNSAFE** | works, no auth |
| Data deletion / export | **NOT IMPLEMENTED** | no `/delete`, `/export`, `/forget` |
| Backup | **REAL** | rolling 7 |
| Backup restore | **NOT IMPLEMENTED** | no restore function/test |
| Metrics / alerting / APM | **NOT IMPLEMENTED** | logs only |
| Dead code: `format_explore`, `format_explore_cards`, `discovery.clean_text`, `alerts.get_updates`, `alerts.handle_command` | **DEAD** | 0 production callers |
| Unreachable: `snapshots.prune()` | **DEAD** | 0 production callers → `page_snapshots` unbounded |

---

## 6. Evidence appendix (redacted)

### 6.1 Executed commands

```
$ git remote -v
origin  https://github.com/Majoradmin/jin-agent.git (fetch)
origin  https://github.com/Majoradmin/jin-agent.git (push)

$ git rev-parse --is-inside-work-tree
true

$ git log --oneline -1
eb6e83e fix(status): /status aur /channelhealth me spam/blocked channels ki ginti bhi dikhao

$ git ls-remote origin refs/heads/main
eb6e83ee52d3f8901848f5e5175d352d3ee2763d  refs/heads/main

$ git ls-files | wc -l
164

$ python3 -m compileall -q .
rc=0

$ JIN_AGENT_DATA=$(mktemp -d) python3 -m unittest discover -s jin_agent/tests -t . -q
Ran 749 tests in ...
OK (skipped=1)

$ grep -rn "def test_" jin_agent/tests/*.py | wc -l
749

$ grep -rn "setWebhook\|secret_token" jin_agent/ | wc -l
0

$ grep -rniE "TODO|FIXME|HACK|XXX" jin_agent/ | wc -l
0
```

### 6.2 Secret scan (values redacted)

```
$ git grep -nE "[0-9]{8,12}:[A-Za-z0-9_-]{30,}" -- . | wc -l
0

$ git log --all -p | grep -cE "gsk_|sk-[A-Za-z0-9]{20,}" 
0
```

> Note: a Groq API key was pasted into a chat session earlier and must be rotated. It is **not** in this repository.

### 6.3 Live `/status` excerpt (2026-11-21 15:16)

```
📊 JIN Agent status
• Policy: SAHULAT-SAFE-SERVICE-v1
• Poll failures: 0
• Telegram: 30 active / 110 dead / 3 archived / 0 stale
• Sites memory: 20 (is hafte 20)
• Sources: 131 total — 58 auto / 73 registry-only (adapter ke baghair)
  auto: 54 ok / 4 failed / 0 stale / 0 disabled
• Explore: last 2026-11-21T09:26:30Z · scope all · pending candidates 0
• Aakhri explore: Science
• Telegram discovery: last 2026-11-21 09:26 · engine rightdao · candidates 0 · probed 0 · added 0
• Dork: 1 kaam / 5 blocked — Bing ✓ · Mojeek ✗ · DuckDuckGo Lite ✗ · Startpage ✗ · Ecosia ✗ · Google (gbv=1) ✗
   ✗ Google News RSS: HTTPError 429
   ✗ Reddit (public JSON): HTTPError 403: Blocked
   ✗ Google News RSS (topic): RateLimited: news.google.com backoff active; retry after 4.54s
   ✗ GDELT DOC 2.0: URLError: _ssl.c:1018 handshake
```

### 6.4 Live `/explore موبائل سیکیورٹی` excerpt (2026-11-21 15:17)

```
🧭 Explore: موبائل سیکیورٹی · 🌐 Sab
📡 Telegram (9): 1 active · 1 stale · 4 private/bot · 3 post
1. زْرمبش بلوچی | 🎙ZBC — @zrumbesh
   ✅ active · score 9 · 2.1K subs · 📅 2026-11-19 · Mixed · 📡 lyzem · auto-save ✅
   🔗 https://t.me/zrumbesh · 🗂 https://t.me/s/zrumbesh
2. TradeZONE (C1) — @tradezonemultan
   ⏳ stale (30+ din) · score 3 · 9 subs · 📅 2022-03-28 · English (en) · 📡 lyzem
...
7-9. 📝 post · اردو (ur) · 📡 lyzem
   🔗 https://t.me/zrumbesh/2942
```

`example.org` count across all three live `/explore` results: **0**.

---

## 7. Code findings (file by file, severity)

### High
| File:line | Finding |
|---|---|
| `jin_agent/server.py:215-318` | Unauthenticated `do_POST` for settings/run/retention/backup |
| `jin_agent/server.py:380-383` + `render.yaml:13-14` | Binds `0.0.0.0` in deployed config |
| `jin_agent/telegram_bot.py:541-555` | `is_owner()` allow-all when chat id unset |
| `jin_agent/store.py` + `Dockerfile:15` | No persistent volume; DB mode `0644`; no encryption |
| `jin_agent/store.py:823-838` | Backup without restore |

### Medium
| File:line | Finding |
|---|---|
| `jin_agent/policy.py:319-341` | `trusted_public_endpoint()` no DNS resolution (SSRF via DNS rebinding/name resolution) |
| `jin_agent/config.py:78` vs `store.py:675-683` | Retention 90 vs 180 mismatch |
| `jin_agent/store.py:686-741` | `chat_context`, `feedback`, `page_snapshots`, `tg_sites` never pruned |
| `jin_agent/snapshots.py:235-244` | `prune()` unreachable |
| `jin_agent/discovery_rank.py` | Spam list small; false positives possible |
| `jin_agent/telegram_bot.py:3030` | `status()` returns raw `cfg["llm"]` (test-only caller) |

### Low
| File:line | Finding |
|---|---|
| `jin_agent/telegram_bot.py:689,714` | Dead formatters |
| `jin_agent/discovery.py:246` | Dead `clean_text()` |
| `jin_agent/alerts.py:53,88` | Duplicate `getUpdates`/`handle_command`, unused |
| `__main__.py:10`, `adapters.py:28`, `evaluator.py:11`, `planner.py:15`, `server.py:14` | Unused imports |
| `jin_agent/data/jin_agent.db-shm/-wal` | Not in `.gitignore` |
| `DEPLOY.md:42` | Retention says 180 (actual 90) |
| `PHASES.md:1` vs `README.md:183` | Phase range mismatch (P13–P44 vs P13–P46) |
| `MobileLab/` (50 files) | Unrelated sub-project in the same repo; not imported by `jin_agent` |

---

## 8. Remediation plan

### P0 — must fix immediately
1. **Console auth / loopback.** Add `JIN_AGENT_ADMIN_TOKEN`; require it on all `/api/*` mutating routes; default `JIN_AGENT_HOST=127.0.0.1` in hosted mode. Files: `server.py`, `render.yaml`, `DEPLOY.md`. Test: 401 without token, 200 with.
2. **Telegram owner enforcement.** Set `TELEGRAM_CHAT_ID` + `JIN_AGENT_REQUIRE_CHAT_ID=1` in production. Files: `render.yaml`, `DEPLOY.md`. Test: non-owner rejected.
3. **Persistent data volume.** Add a volume/disk at the data dir; chmod `0600` the DB. Files: `render.yaml`, `Dockerfile`, `store.py`. Test: restart preserves rows.
4. **Backup restore.** Add `store.restore()` + round-trip test. Acceptance: backup → mutate → restore → identical counts.

### P1 — before public launch
5. **SSRF hardening.** Resolve the hostname and validate the IP (`socket.getaddrinfo`) in `trusted_public_endpoint()`. Test: `http://name-that-resolves-to-169.254.169.254` rejected.
6. **Retention parity + bounded tables.** Align `config.py`/`DEPLOY.md`/`store.py` on one number; prune `chat_context`, `feedback`, `page_snapshots`, `tg_sites`. Test: table row caps after `retention()`.
7. **Data deletion/export.** Add `/delete` (hard delete for a chat) and `/export` (JSON/CSV). Test: delete removes rows; export returns them.
8. **Discovery breadth honesty.** Document provider limits; add MTProto as an explicit opt-in adapter behind a flag, or a paid provider (Telemetr/TGStat/tgAtlas). State cost.
9. **Remove dead code.** Delete dead formatters/`clean_text`/`alerts.get_updates`/`handle_command`; wire or delete `snapshots.prune()`.
10. **Docs parity.** Fix `DEPLOY.md` retention, `PHASES.md` range, `.gitignore` `-wal/-shm`.

### P2 — quality
11. Add lint/type tooling (ruff + mypy) to CI.
12. Add coverage measurement and raise it on `verifier.py` + `server.py` POST actions.
13. Add a live-network integration test (opt-in, marked) to catch provider drift.
14. Add metrics/alerting (job failure counts, poll failures, provider error rates).

### Rollout / rollback
- **Rollout:** each P0 item lands as its own commit with a regression test; redeploy via FadeHost "Redeploy (pull latest)"; verify `/status` + one `/explore` after each.
- **Rollback:** `git revert <commit>` and redeploy; the data schema changes are additive (`ALTER TABLE ... ADD COLUMN`), so reverting code leaves the extra column harmless. Keep at least one known-good backup before the volume change.

---

## 9. Top 10 actions (priority order)

1. **Lock the management console** (token or loopback) — P0 security.
2. **Set `TELEGRAM_CHAT_ID` + `JIN_AGENT_REQUIRE_CHAT_ID=1`** — P0 authorization.
3. **Give the database a persistent volume + `0600`** — P0 data durability.
4. **Implement backup restore + test** — P0 durability.
5. **Harden `trusted_public_endpoint()` with DNS resolution** — P1 SSRF.
6. **Fix retention (single number) and prune unbounded tables** — P1 privacy.
7. **Add `/delete` and `/export`** — P1 privacy compliance.
8. **Document provider limits; add opt-in MTProto or paid provider** — P1 honest capability.
9. **Delete dead code and fix docs mismatches** — P2 quality.
10. **Add lint/type/coverage + live integration tests** — P2 quality.

---

*Audit performed read-only. No production configuration or secret was modified. No deploy or start was performed.*

---

## 10. Remediation status — 2026-11-21 (post-audit, commit `fd6d680`)

Audit ke baad P0-1..P0-4 + P1-5..P1-7 implement kar diye gaye. Suite: **796 tests OK (1 skipped)** (audit waqt 749).

| # | Masla | Status | Commit | Evidence |
|---|---|---|---|---|
| P0-1 | Unauthenticated console | **FIXED** | `a412b79` | `server.py` me `admin_token()` (env `JIN_AGENT_ADMIN_TOKEN`) + `_is_loopback()` + `Handler._authorized()`/`_denied()`; `do_GET`/`do_POST` gate; `/api/health` public. Tests `test_http.py:22-27` (401 anonymous/ghalat token, `WWW-Authenticate: Bearer`, Bearer 200, `X-Admin-Token` 200, health public, token kabhi log nahi). |
| P0-2 | `is_owner()` allow-all | **PARTIAL → FIXED (opt-in)** | `510b3b5` | `cmd_bot` ab `JIN_AGENT_REQUIRE_CHAT_ID=1` + unset/ghalat `telegram_chat_id` par `return 1` (safe startup failure); unauthorized chat ko 60s throttled "not authorized" reply (`_unauthorized_reply`). **Default `is_owner` behaviour (unset → allow-all) barqarar hai** (tests `test_lifetime_bot.py:88-100` aur `test_telegram_bot.py:56-60` wahi assert karte hain) — production me `JIN_AGENT_REQUIRE_CHAT_ID=1` lazmi. |
| P0-3 | DB durability/permissions | **FIXED** | `3d7b3fa` | `store.secure_permissions()` — data dir/subdirs `0700`, DB `0600` (lstat + uid check, Windows skip); `Dockerfile` `VOLUME /app/jin_agent/data` + `mkdir -m 0700`; `.gitignore` `*.db-shm/-wal`, `*.sqlite-wal/-shm`, `*.db-journal`, `.env*` (+ `!.env.example`). Tests `test_permissions.py`. |
| P0-4 | Backup restore | **FIXED** | `f39e326` | `store.restore(path, confirm=False)` — confirm gate, `..` reject, `PRAGMA integrity_check`, required-tables check, staging copy, pre-restore safety `backup()`, WAL/SHM/journal cleanup, atomic `os.replace`, baad me verify + `add_event("restore")`. CLI `python -m jin_agent restore --from <path> --confirm`; `POST /api/restore` (confirm lazmi). Tests `test_restore.py` (round-trip, corrupt, traversal, HTTP). |
| P1 | `DEPLOY.md` retention galat (180 vs 90) | **FIXED** | `7fa6dcc` | `DEPLOY.md` retention `180 → 90` (asal effective 90). |
| P1 | `.env.example` nahi tha | **FIXED** | `a412b79` | `.env.example` (sirf placeholders, koi asli secret nahi) + `.gitignore` me `!.env.example` negation. |

| P1-5 | SSRF: custom LLM endpoint par DNS resolve nahi | **FIXED** | `eb40d19` | `policy.trusted_public_endpoint()` ab `socket.getaddrinfo` se hostname resolve kar ke har IP ko `ipaddress` par check karta hai (`is_private/is_loopback/is_link_local/is_reserved/is_multicast/is_unspecified` + `not is_global`); DNS fail = reject. Tests `test_policy.py` (+4). |
| P1-6 | Retention default mismatch + unbounded tables | **FIXED** | `1761abd` | `store._retention_days` fallback **180 → 90** (`config.DEFAULT` se match); `retention()` ab `chat_context`, `feedback`, `tg_sites`, `tg_discovery_state`, `schedule_state` prune karta hai; `snapshots.prune()` retention se jud gaya. Tests `test_lifetime_store.py` (+3). |
| P1-7 | Data deletion/export mojood nahi | **FIXED** | `fd6d680` | `store.export_data(chat_id)` + `store.delete_chat_data(chat_id)` (asli DELETE, soft-delete nahi); `GET /api/export` (JSON/CSV, admin gate); Telegram `/delete` + `/forget` command + confirmation. Tests `test_http.py` (+3), `test_telegram_bot.py` (+3). |

### Abhi bhi baqi (audit ke mutabiq, abhi fix NAHI)
- **P1-8** Provider limits ki documentation + opt-in MTProto/paid provider (Telemetr/TGStat/tgAtlas) — `TELEGRAM_DISCOVERY_PLAN.md` me likha hai, abhi adapter nahi.
- **P2** lint/type CI, coverage, live-network integration tests, metrics/alerting.
- **Dead code:** `format_explore`, `format_explore_cards`, `discovery.clean_text`, `alerts.get_updates`, `alerts.handle_command` (`snapshots.prune()` ab retention se jud gaya).

### Honest limitations (fixes ke)
- `secure_permissions()` non-owner file par chmod nahi karta, sirf warning.
- `restore()` bade DB par disk 2–3× (staging copy + tmp + safety backup).
- P0-2 default allow-all rehta hai — production ke liye `TELEGRAM_CHAT_ID` + `JIN_AGENT_REQUIRE_CHAT_ID=1` set karna **zaroori** hai.

*Audit report updated 2026-11-21 by the same read-only audit session. Production config/secret abhi bhi chhua nahi; deploy/start nahi kiya.*
