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
  -e JIN_AGENT_HOST=0.0.0.0 jin-agent
```
