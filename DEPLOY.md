# JIN Agent — Deployment (FadeHost / Render / Railway)

Bot akele **long polling** karta hai aur TCP port nahi kholta — is liye hosted
reverse proxy ko `502 Bad Gateway` milta tha. Ab `supervisor` do cheezein ek
saath chalata hai:

1. **Agent Console** — HTTP server, `GET /api/health` (health check + version).
2. **Telegram bot** — long polling.

Koi bhi child exit ho to supervisor use backoff ke saath dobara start karta hai.
Koi nayi dependency nahi (sirf Python stdlib).

---

## FadeHost (asaani se)

FadeHost panel me app banate waqt:

**Start command** (koi bhi ek):

```
python -m jin_agent supervisor
```

ya default `python bot.py` (yeh shim ab wahi supervisor chalata hai).

**Environment variables** (panel → Environment / Variables):

| Variable | Majboori | Misal / tafseel |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | haan | `@BotFather` se token (kabhi public commit na karein) |
| `TELEGRAM_CHAT_ID` | haan | aap ka numeric chat id (unset = allow-all, production me na chodein) |
| `JIN_AGENT_HOST` | hosted par haan | `0.0.0.0` — reverse proxy ko dene ke liye **explicit opt-in** |
| `PORT` | haan | FadeHost jo port deta hai use set karein (default `8766`) |
| `JIN_AGENT_UPDATE_WORKERS` | na | per-update thread pool, default `2` |
| `JIN_AGENT_MAX_POLL_FAILURES` | na | lagataar poll failures ki cap; `0` = unlimited (default) |
| `JIN_AGENT_SEND_DELAY` | na | Telegram chunks ke darmiyan intezar (second), default `1.0` (429 flood rokne ke liye) |
| `JIN_AGENT_LOG_LEVEL` | na | `DEBUG` / `INFO` / `WARNING` / `ERROR`, default `INFO` |
| `JIN_AGENT_DATA` | na | data dir (DB / reports / backups / logs), default `jin_agent/data` |
| `JIN_AGENT_VERBOSE` | na | set karne par HTTP access log bhi dikhta hai (default off) |
| `JIN_AGENT_SCHEDULER` | na | `serve` par scheduler auto-start; `off` / `0` / `false` par band (default on) |
| `JIN_AGENT_RETENTION_DAYS` | na | retention window (din), default `90` — items + events/runs/reports/jobs/search_memory/tg_candidates/chat_context/feedback/tg_sites/tg_discovery_state/schedule_state/page_snapshots |
| `JIN_AGENT_BACKUP_KEEP` | na | `data/backups/` me rakhne wale backups, default `7` |
| `JIN_AGENT_REPORT_DAYS` | na | `data/reports/` retention (din), default `90` |
| `JIN_AGENT_MAX_ROUNDS` | na | research rounds ki cap, default `5` |
| `JIN_AGENT_CHANNEL_NEGATIVE_TTL_DAYS` | na | failed channel ki negative memory TTL (din), default `7` — agla round unhe skip karega |
| `JIN_AGENT_CHANNEL_DEAD_TTL_DAYS` | na | dead `tg_channels` registry TTL (din), default `30` — purani dead rows retention delete karta hai |
| `JIN_AGENT_REPORT_CONFIDENCE` | na | report confidence gate (0–1), default `0.6` — is se niche "bharosemand nahi" payam, file nahi |
| `JIN_AGENT_REQUIRE_CHAT_ID` | production par haan | `1` par unset `TELEGRAM_CHAT_ID` reject (default off = allow-all). `1` ke waqt chat id khaali/ghalat ho to bot **start nahi hoga** (allow-all silent mode rokne ke liye) |
| `JIN_AGENT_ADMIN_TOKEN` | public bind par haan | Console bearer token (`Authorization: Bearer <token>`). Khaali par console sirf loopback (default `127.0.0.1`); `JIN_AGENT_HOST=0.0.0.0` par lazmi set karein. `/api/health` public rehta hai |
| `JIN_AGENT_SCHEDULER_OFFLINE` | na | `serve` scheduler mode: `0` = live (default), `1` = offline; band karne ke liye `JIN_AGENT_SCHEDULER=off` |
| `JIN_AGENT_SOURCE_STALE_DAYS` | na | source `stale` mark karne ki window (din), default `30` |
| `JIN_AGENT_CHANNEL_STALE_DAYS` | na | active channel `stale` (khamosh) window (din), default `30` |
| `JIN_AGENT_TRACE_DAYS` | na | `data/runs/` per-run trace retention (din), default `30` |
| `JIN_AGENT_MEMORY_STALE_DAYS` | na | memory audit ka stale window (din), default `30` |
| `JIN_AGENT_TOKEN_BUDGET` | na | per-run token budget, default `100000` (meter + `budget_exceeded`) |
| `JIN_AGENT_COST_PER_1M` | na | USD per 1M tokens (cost meter), default `0` |
| `GROQ_API_KEY` | na | Roman Urdu translation / related search ke liye |
| `LLM_PROVIDER` | na | `custom` |
| `LLM_ENDPOINT` | na | `https://api.groq.com/openai/v1` |
| `LLM_MODEL` | na | `llama-3.3-70b-versatile` |
| `ALL_PROXY` / `HTTPS_PROXY` / `HTTP_PROXY` | region-block par | proxy URL (socks5/http), jaise `socks5://127.0.0.1:1080` |

> **Security:** `JIN_AGENT_HOST` ke baghair console **sirf loopback**
> (`127.0.0.1`) par rehta hai. `0.0.0.0` sirf tab set karein jab trusted hosted
> reverse proxy ke peeche ho.

**Verify:**

```bash
curl https://aapka-app-domain/api/health
```

Jawab (HTTP 200):

```json
{"ok": true, "version": "2.9.0", "db": {"ok": true}, "data_writable": true}
```

Telegram se `/status` bhejo — bot ko jawab milna chahiye. Log:
`jin_agent/data/logs/supervisor.log`.

Pehle startup par bot Telegram ke `/` menu me 6 commands bhi set karta hai
(Bot API `setMyCommands`, best-effort): `/research`, `/search`, `/channels`,
`/explore`, `/status`, `/help`. `/explore` ke cards par ✅/❌ se channel/site
memory me rakhna ya skip karna hota hai; `/status` me explore block dikhta hai.

---

## Render

`render.yaml` me `type: web` + `healthCheckPath: /api/health` set hai. `PORT`
Render khud inject karta hai. `JIN_AGENT_HOST=0.0.0.0` envVars me likha hai.

## Railway

`railway.json` me `healthcheckPath: /api/health` set hai. Dashboard → Variables me
`JIN_AGENT_HOST=0.0.0.0` aur `PORT` (Railway inject karta hai) set karein.

---

## Local / Docker

```bash
python -m jin_agent supervisor          # console (loopback) + bot
python -m jin_agent serve --open        # sirf console
python -m jin_agent bot                 # sirf bot
```

Docker:

```bash
docker build -t jin-agent .
docker run -p 8766:8766 -e TELEGRAM_BOT_TOKEN=... -e TELEGRAM_CHAT_ID=... \
  -e JIN_AGENT_HOST=0.0.0.0 -e JIN_AGENT_ADMIN_TOKEN=... jin-agent
```

`Dockerfile` me `VOLUME /app/jin_agent/data` hai — DB, reports aur backups container
rebuild/restart ke baad bhi barqarar rehte hain. Data dir `0700` (owner-only) aur
DB `0600` set hoti hai (sirf process ke hone par).

### DB backup / restore

Backup: `POST /api/backup` (admin token) ya `store.backup()` — `data/backups/` me
`jin_agent-<UTC>.db`, rolling retention `JIN_AGENT_BACKUP_KEEP` (default 7).

Restore (DB overwrite — **confirm lazmi**):

```bash
python -m jin_agent restore --from data/backups/jin_agent-<stamp>.db --confirm
```

Console: `POST /api/restore` body `{"path": "...", "confirm": true}`.
`--confirm` / `confirm:true` ke baghair CLI `1` return karta hai aur server `400`
detā hai. Restore se pehle current DB ka safety backup apne aap banta hai; source
par `PRAGMA integrity_check` + required tables ki tasdeeq hoti hai, replace
atomic (`os.replace`) hai.
