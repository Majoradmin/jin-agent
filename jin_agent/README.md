# JIN Agent 2.9.0

Local, stdlib-only research and intelligence agent. `MobileLab` se alag, khud ka
package, khud ka SQLite archive aur khud ka loopback console. Koi cloud, koi pip
install, koi lazmi API key nahi.

## Quick Start

```bat
jin_agent\run.bat
```

Ya terminal se:

```bat
python -m jin_agent status
python -m jin_agent run "MediaTek preloader scatter DA" --live
python -m jin_agent eval
python -m jin_agent serve --open
python -m jin_agent selftest
python -m jin_agent ci-gate
python -m jin_agent channels --discover
python -m jin_agent channels --check *
```

Console default `http://127.0.0.1:8766` par khulta hai (light theme). MobileLab
ka server `8765` par alag rehta hai; dono aik saath chal sakte hain.

## Commands

| Command | Kaam |
|---|---|
| `status` | Version, FTS5, LLM mode, DB counts, source register |
| `run <query> [--live] [--no-save]` | Aik poora research run + Roman Urdu brief |
| `search <query>` | Local FTS5 archive search |
| `sources` | Legal source register (URL + date checked) |
| `digest` | Archive se daily brief |
| `eval [--live]` | 25-query harness + report |
| `batch <q...> [--live] [--limit]` | Parallel agents: N simultaneous research runs |
| `schedule [--live]` | Background job scheduler (Ctrl+C se band) |
| `serve [--port] [--open]` | Agent Console |
| `supervisor [--port] [--host]` | Console + Telegram bot ek saath (hosted deploy, auto-restart) |
| `selftest` | Offline `unittest` suite |
| `ci-gate [--queries N] [--skip-tests]` | Offline release gate: compile/import + poora suite + evaluator quick check; exit 0 sirf all-pass |
| `changes [--limit N]` | Snapshot change-detection: recent "naya kya aaya" + counts |
| `classify <text>` | Safe-service gate ka natija |
| `llm` | Local model probe |
| `channels` | Telegram channel registry: list / `--add <handle>` / `--remove <handle>` (archive, delete nahi) / `--check *` (liveness) / `--discover` (ek cycle) |

### Telegram Bot Commands (P32)

6 canonical commands — Telegram ke `/` menu me bhi (Bot API `setMyCommands`,
startup par ek dafa, best-effort):

| Command | Kaam |
|---|---|
| `/research <sawal> [--deep]` | Research + Roman Urdu report; `--deep` dark/deep engines links jodta hai |
| `/search <keyword>` | Saved channels ke andar search |
| `/channels` | Saved channels ki list + clickable `t.me` links |
| `/channels add <link>` | Channel memory me rakho (✅/❌ confirm gate) |
| `/channels rm <@handle>` | Channel archive (delete nahi) |
| `/explore [topic]` | Channels + sites discovery, scored cards, har item par ✅ rakhna / ❌ skip gate |
| `/status` | Agent + explore block: channels active/dead/archived/stale, sites, sources health breakdown, Telegram discovery (engine + candidates/probed/added + fail wajah), last explore, pending candidates |
| `/report [md\|html]` | Aakhri report dobara bhejo (default `md`; HTML stdlib-only template) |
| `/help` | Yeh menu |

Sources register: **130** legal/public sources — **57 auto** (adapter wired,
automatic fetch) + **73 registry-only** (verified manually; koi stable feed ya
adapter nahi). P40/P41 key-free engine list (web/regional/academic/patents/OSS/
archive/news/social/TG dirs) ka har engine yahan hai; jo block (captcha/429/
Cloudflare/JS) ya key maange us par `auto=False` + wajah note hai (jhoota auto
nahi). `/dork <query>` Google-dork (site:t.me/s, intitle, filetype:pdf, ...)
banata hai — backend Bing kaam karta hai, baqi block (auto=False). `/status` is
breakdown ke saath non-overlapping health buckets bhi dikhta hai: ok / failed /
stale / disabled (fail/stale ka naam + wajah), aur **Dork** block.

Multi-turn: chhota follow-up (`aur`, `iske baare me`, `phir`, `more`) pichhle
sawal ke context se jurre hota hai; `/new` context saaf karta hai.

Seedha matn (bina `/`) bhi `/research` ban jata hai; link ya `@handle` ya channel
post forward `/addchannel` hi rakha jata hai. Purane commands (`/addchannel`,
`/rmchannel`, `/tgsearch`, `/deep`, `/engines`, `/memory`, `/stop`, `/new`,
`/digest`, `/reports`, `/alerts`, `/schedule`, `/channelhealth`, `/memoryaudit`,
`/selftest`) aliases ki tarah chalte hain. Research ke dauran Plan → Sources →
Fetch → Verify → Brief → Deliver stages wahi status message edit hote hain
(3s throttle, Telegram 20/min ke andar), aur BLUF/caption me local trace path
`data/runs/<id>.json` dikhta hai.

### Channel Auto-Discovery (P23)

Agent khud informative Telegram channels dhoondta hai — user ke channel naam
nai zaroori. Sources: public search engine (pehle **Bing** `t.me/s <topic>`,
phir DDG html/lite fallback — anti-bot anomaly par agla engine) + preview
harvest (`t.me/<handle>` mentions) + archive harvest. Har candidate ko liveness
probe se tasdeeq hota hai; informative wale (`score >= channel_min_score`,
default 4) khud `auto` add hote hain, dead channels `status='dead'` archive
hote hain (delete nahi). Daily discovery job scheduler me hai
(`channel_discovery_minutes`, default 720). `--offline` me sirf harvest hota hai.
Koi private group / userbot / MTProto / login scrape — koi wohi (P13 policy).

`mobile & firmware | gsm repair | osint | ai tools | tech news` jaise topics
se search discovery rotate hoti hai; koi bhi language channel add allowed.
Search fail (anti-bot) par `/explore` wajah batata hai aur `/status` me
**Telegram discovery** block (engine, candidates/probed/added, fail wajah) hota hai.

`--live` na lagane par sab kuch offline deterministic fixture corpus par chalta
hai — tests aur demos mein kabhi live internet zaroori nahi.

## Design

```
Query -> Policy gate -> Tool plan (LLM optional) -> Agent validates every call
      -> Adapters fetch (allowlist, timeout, size cap) -> Normalizer
      -> SQLite FTS5 firehose archive -> Verifier / trust / cross-check
      -> Ranker -> Roman Urdu brief (Facts | Recommendations | Not Verified)
```

**"LLM ko internet mat do — usay tools do."** Model sirf JSON tool request
bhejta hai; `planner.validate()` har call check karta hai; `planner.scrub()`
tool output se prompt-injection hata kar plain text deta hai. Model OFF ho to
deterministic rule-based plan aur Roman Urdu khulasa chalata hai — ye bug nahi,
by-design fallback hai.

## Observability (P26)

- **Logs:** `data/logs/agent.log` — aik line = aik JSON object; `RotatingFileHandler`
  (2 MB × 3 backups, stdlib). Telegram bot token aur LLM key `logging_setup.redact()`
  se `***` ho jate hain, disk par kabhi nahi jate. Level: `JIN_AGENT_LOG_LEVEL`.
- **Metrics:** in-memory counters (`queries_total`, `runs_ok`, `runs_blocked`,
  `fetch_errors`, `reports_total`) + gauges + latency p50/p95. `GET /api/metrics`
  se JSON snapshot; summary `data/metrics.json` mein best-effort likhi jati hai.
- **Health:** `GET /api/health` — DB connectivity, data dir writable, version,
  uptime seconds aur `llm_enabled` (key kabhi return nahi hoti).

## Hosted Deploy (FadeHost / Render / Railway)

Bot akele long polling karta hai aur port nahi kholta — hosted par `supervisor`
console (HTTP `/api/health`) aur bot ko ek saath, auto-restart ke saath chalata
hai. Exact steps aur env vars (`JIN_AGENT_HOST`, `PORT`,
`JIN_AGENT_UPDATE_WORKERS`, proxy vars) ke liye [`DEPLOY.md`](../DEPLOY.md)
parh lein. Console ka default hamesha loopback rehta hai; `0.0.0.0` sirf
`JIN_AGENT_HOST` env / `--host` se (explicit opt-in).

## Boundaries

- Sahulat & Safe Service Policy (`SAHULAT-SAFE-SERVICE-v1`) barqarar: koi Huawei ID / Google FRP / Samsung Knox / MDM / carrier / iCloud bypass automation ya step-by-step tareeqa nahi; koi device write / erase / flash / IMEI operation nahi.
- Deep / dark web sirf legal, public ya authorized. Onion links **sirf display** ke liye; kabhi fetch ya crawl nahi.
- Telegram sirf public `t.me/s/` preview aur official Bot API (opt-in token). Koi MTProto / userbot / private data / historical channel scrape nahi.
- Har fact ke sath `URL + date checked`. Facts aur recommendations alag. Koi banawati citation nahi. Offline fixtures ko report mein wazeh taur par "NOT a real citation" likha jata hai. **2.1.0:** offline fixtures ko kabhi `cross-verified` nahi kaha jata; duplicate source records aik story mein merge hote hain; zero-relevance records brief se nikaale jaate hain.
- Token aur API key local `data/config.json` mein rehte hain, kabhi log ya API response mein nahi aate. Is file ko private rakhein (open question O-TOKEN).

## Layout

| Path | Zimmedari |
|---|---|
| `config.py`, `util.py`, `policy.py` | Config, helpers, legal source register, SSRF guard |
| `store.py` | SQLite WAL + FTS5, dedupe, jobs, watchlist, retention, backup |
| `adapters.py` | 57 adapters + RSS feeds, one fetch contract, parallel diagnostics |
| `normalizer.py`, `verifier.py`, `ranker.py` | Canonical record, provenance, smart ranking |
| `planner.py`, `llm.py` | Tool layer + optional local LLM |
| `briefer.py`, `evaluator.py` | Roman Urdu report, 25-query harness |
| `scheduler.py`, `alerts.py` | Job queue, firehose, watchlist, Bot API alerts |
| `orchestrator.py` | End-to-end pipeline |
| `logging_setup.py`, `metrics.py`, `ci_gate.py` | JSON-lines logs (redacted), in-memory metrics, offline CI gate |
| `server.py`, `web/` | Loopback Agent Console |
| `canonical.py`, `snapshots.py`, `ratelimit.py` | URL canonical dedup, page change detection, per-host rate limits |
| `tests/` | 580 offline tests (1 skipped) |
| `PHASES.md` | P13–P41 `PHASE REVIEW` record |

Assumptions, N/A justifications aur verification numbers `PHASES.md` mein hain.

## Boundaries (2.2.0)

- **Telegram channel auto-discovery:** public `t.me/s/` preview se only
  (`t.me` / `telegram.me` allowlist, timeout, 2 MB cap, SSRF guard). Koi
  private group / userbot / MTProto / login scrape. Dead channel archive
  (`status='dead'`), hard delete nahi. Any language allowed; discovery scoring
  content + health based (score 0-10, `channel_min_score` 4, cap
  `channel_discovery_max_auto` 60 channels per cycle budget).
- **Deep / dark web:** links-only (`Ahmia`), kabhi fetch/crawl nahi.
- **LLM:** OFF until local model install; `custom` OpenAI-compatible endpoint
  (e.g. Groq free tier) supported via settings — cloud LLM layer ready for the
  anywhere-access Telegram bot plan.
