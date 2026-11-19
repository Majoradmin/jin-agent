# Competitors — Short Recon (replica-recon)

**Date checked:** 19 Nov 2026. **Sources:** GitHub repo READMEs + GitHub API metadata (public). Jo cheez README me nahi mili wahan "unverified" likha hai. Ye recon JIN Agent `PHASES.md` P30 me mention ki gayi 3 repos par hai.

---

## 1. `maddness/tg-deep-research`

**URL:** https://github.com/maddness/tg-deep-research
**Repo metadata (GitHub API, 19 Nov 2026):** created `2026-01-10`, pushed `2026-01-10`, 18 stars, 5 forks, Python, default branch `main`, koi license nahi.

**Kya karta hai:** Telegram channel deep-research agent. Claude Agent SDK + Query Fan-Out. Natural-language sawal → keywords → channels ke andar parallel search → dedupe → Claude se structured Roman Urdu/Ukrainian-style report.

**Features (README verify):**
- Query Fan-Out (Claude Haiku se NL → keywords)
- Multi-channel parallel search + dedupe by `(channel_username, message_id)`
- Conversational context (follow-up yaad rakhta hai; `session_manager.py`)
- Source links: `t.me/channel/message_id`
- 6-month time filter
- **No local database** — stateless, live search only

**Live step messages?** **Haan** — README example me emoji steps: `💬 Запрос → 🧠 Анализирую → 🔑 Ключевые слова → 🔍 Ищу → 📊 Найдено 33 → 🤖 Генерирую → ✅ Готово`.

**Citations?** **Haan** — har result me `t.me/channel/message_id` link.

**File/PDF export?** README me mention nahi → **unverified / missing**.

**Memory?** Conversational context TTL `session_timeout_minutes: 30`; persistent DB nahi.

**Channel explore/discovery?** **Nahi** — `config/channels.yaml` me manual channel list; `/channels` sirf configured list.

**Dark web?** **Nahi** (mention nahi).

**Trace?** README me mention nahi → **unverified**.

**Limits (settings.yaml):** `max_messages_per_channel: 10`, `parallel_limit: 5`, `flood_sleep_threshold: 60`, `months_back: 6`, session TTL 30 min.

**Commands:** sawal matn, `/channels`, `/new`, `/help`.

**Tech/boundary:** Telethon **user API** (login + `TG_API_ID/HASH/PHONE`), aiogram 3, Anthropic API key lazmi. Ye JIN se **alag legal boundary** hai (JIN sirf public `t.me/s/` preview + Bot API).

---

## 2. `tsukeno/hermes-research`

**URL:** https://github.com/tsukeno/hermes-research
**Repo metadata (GitHub API, 19 Nov 2026):** created `2026-05-10`, pushed `2026-05-10`, 4 stars, 0 forks, Python, MIT, default `main`.

**Kya karta hai:** Telegram-native **web** research agent. Sawal → DuckDuckGo search → top pages fetch → facts extract → cited markdown report. Backend Hermes (Nous) via OpenRouter; OpenAI/Anthropic/dry-run alternatives. CLI + Telegram dono.

**Features (README verify):**
- Live DuckDuckGo web search (no API key)
- Real HTTP fetch with polite User-Agent
- Focused fact extraction (LLM-guided ya deterministic heuristic dry-run)
- Markdown report + numbered citations
- **Persistent JSON traces** with prompt/completion token accounting
- Stdlib-only runtime
- CLI + Telegram front-ends

**Live step messages?** README me step-by-step message nahi dikhaya (sirf final report) → **unverified**.

**Citations?** **Haan** — numbered `## Sources` list.

**File/PDF export?** **Nahi** — markdown chat message.

**Memory?** Persistent memory nahi; `runs/*.json` traces + `manifest.json` (audit trail, conversation memory nahi).

**Channel explore?** **Nahi** — web research, Telegram channels se kuch nahi.

**Dark web?** **Nahi** (mention nahi).

**Trace?** **Haan** — `runs/` JSON + manifest, token accounting.

**Limits:** token accounting documented; koi hard message/time cap README me nahi → **unverified**.

**Commands:** `/start` + free-text sawal.

**Tests:** 4 pytest cases (network monkeypatched).

---

## 3. `ashishki/telegram-research-agent`

**URL:** https://github.com/ashishki/telegram-research-agent
**Repo metadata (GitHub API, 19 Nov 2026):** created `2026-03-16`, pushed `2026-10-25`, 0 stars, 0 forks, Python, default `master`, license nahi.
**Stage (README/PRODUCT_STATUS, 24 Oct 2026):** local prototype; 398 active tests pass; real model generation; **real Telegram ingress/send, production cutover, human acceptance unconfirmed**.

**Kya karta hai:** Ek owner ka personal Telegram assistant: **Chat, Search, Brief, Watch, Act**. Durable state (PostgreSQL runtime + SQLite canonical Telegram archive), confirmed actions, receipts.

**Features (README + PRODUCT_STATUS verify):**
- **Chat:** shared ingress, bounded/expiring context, topic change, abbreviation, recipient edit
- **Search:** canonical FTS archive, bounded deep research, fact/citation/number/URL verifier, honest fallback
- **Brief:** immutable `BriefDocument` (ID/version/digest), sources, **HTML/PDF/Markdown export**, private reader, mobile light/dark; 5-page PDF verified
- **Watch:** preview/confirm, durable schedule, quiet hours, caps, pause/revoke
- **Act:** exact preview, expiring one-use confirmation, executor, receipts, separate reconcile
- **Memory:** versioned, explicit confirmation, provenance, forget/derived deletion
- **Connections:** OAuth/PKCE adapters (mail/calendar) — implemented, real accounts unselected
- **Ops:** leases/recovery, cost accounting, backup/restore, migration rehearsal

**Live step messages?** **Haan** — PRODUCT_STATUS: "explicitly shown checked steps, found/cited materials, query limit".

**Citations?** **Haan** — exact URL + supporting quote; strict verifier (numbers/entity/negation/source integrity).

**File/PDF export?** **Haan** — HTML/PDF/Markdown + private reader.

**Memory?** **Haan** — versioned memory + explicit confirm + forget.

**Channel explore?** Telegram archive FTS hai, magar channel **discovery/explore** feature mention nahi → **unverified / missing**.

**Dark web?** **Nahi** (mention nahi).

**Trace?** **Haan** — receipts, evidence lineage, verification reports (69 requirements/10 scenarios).

**Limits:** bounded research, caps, quiet hours, expiring confirmation; 398 tests; token/cost accounting.

**Unconfirmed (khud likha hai):** real Telegram send/HTML/files, real mail/calendar, Brave discovery, private/production storage, multi-week operator pilot.

---

## 4. Cross-competitor note

| Dimension | maddness | tsukeno | ashishki |
|---|---|---|---|
| Core | Telegram channel search | Web research | Personal assistant (Chat/Search/Brief/Watch/Act) |
| LLM | Claude (required) | Hermes/OpenAI/Anthropic/dryrun | DeepSeek + others |
| DB | none (stateless) | JSON traces | SQLite + PostgreSQL |
| Export | unverified | markdown only | HTML/PDF/MD |
| Telegram boundary | Telethon user API (login) | Bot API | Bot/ingress (real unconfirmed) |
| Live steps | yes (emoji) | unverified | yes (checked steps) |
| Citations | t.me links | numbered URLs | URL + quote |
| Channel discovery | nahi | nahi | unverified |
| Dark web | nahi | nahi | nahi |
