# JIN Agent 2.0.0

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
| `schedule [--live]` | Background job scheduler (Ctrl+C se band) |
| `serve [--port] [--open]` | Agent Console |
| `selftest` | Offline `unittest` suite |
| `classify <text>` | Safe-service gate ka natija |
| `llm` | Local model probe |

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

## Boundaries

- Sahulat & Safe Service Policy (`SAHULAT-SAFE-SERVICE-v1`) barqarar: koi Huawei ID / Google FRP / Samsung Knox / MDM / carrier / iCloud bypass automation ya step-by-step tareeqa nahi; koi device write / erase / flash / IMEI operation nahi.
- Deep / dark web sirf legal, public ya authorized. Onion links **sirf display** ke liye; kabhi fetch ya crawl nahi.
- Telegram sirf public `t.me/s/` preview aur official Bot API (opt-in token). Koi MTProto / userbot / private data / historical channel scrape nahi.
- Har fact ke sath `URL + date checked`. Facts aur recommendations alag. Koi banawati citation nahi. Offline fixtures ko report mein wazeh taur par "NOT a real citation" likha jata hai.
- Token aur API key local `data/config.json` mein rehte hain, kabhi log ya API response mein nahi aate. Is file ko private rakhein (open question O-TOKEN).

## Layout

| Path | Zimmedari |
|---|---|
| `config.py`, `util.py`, `policy.py` | Config, helpers, legal source register, SSRF guard |
| `store.py` | SQLite WAL + FTS5, dedupe, jobs, watchlist, retention, backup |
| `adapters.py` | 16 adapters, one fetch contract, parallel diagnostics |
| `normalizer.py`, `verifier.py`, `ranker.py` | Canonical record, provenance, smart ranking |
| `planner.py`, `llm.py` | Tool layer + optional local LLM |
| `briefer.py`, `evaluator.py` | Roman Urdu report, 25-query harness |
| `scheduler.py`, `alerts.py` | Job queue, firehose, watchlist, Bot API alerts |
| `orchestrator.py` | End-to-end pipeline |
| `server.py`, `web/` | Loopback Agent Console |
| `tests/` | 116 offline tests |
| `PHASES.md` | P13–P22 `PHASE REVIEW` record |

Assumptions, N/A justifications aur verification numbers `PHASES.md` mein hain.
