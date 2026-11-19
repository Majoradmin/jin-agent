# Parity Baseline — JIN Agent vs 3 competitors (19 Nov 2026)

**JIN:** 2.9.0, Python stdlib-only, local-only, offline deterministic.
**Competitors:** `maddness/tg-deep-research`, `tsukeno/hermes-research`, `ashishki/telegram-research-agent` (details: `competitors.md`).

---

## 1. JIN ke paas jo competitors ko nahi (ya kamzor)

| Capability | JIN | maddness | tsukeno | ashishki |
|---|---|---|---|---|
| Stdlib-only / koi API key lazmi nahi | ✅ (offline fixtures) | ❌ Claude key | ❌ LLM key (dry-run bhi web chalata hai) | ❌ model provider |
| Offline deterministic tests | ✅ 480 tests, ci-gate | unverified | 4 tests | 398 tests |
| Policy gate + legal source register | ✅ 45 sources, block patterns | ❌ | ❌ | partial (grants) |
| SSRF/host allowlist | ✅ | unverified | partial (polite fetch) | partial |
| Local FTS5 archive + search | ✅ | ❌ stateless | ❌ | ✅ |
| Canonical dedup + cross-verification | ✅ | dedupe by msg id | ❌ | partial (verifier) |
| Confidence caps + citation audit | ✅ | ❌ | ❌ | partial (verifier) |
| Telegram channel auto-discovery | ✅ public preview + scoring | ❌ manual yaml | ❌ | unverified |
| Channel health / dead TTL / stale | ✅ | ❌ | ❌ | unverified |
| Explore cards + ✅/❌ memory gate | ✅ | ❌ | ❌ | ❌ |
| Scheduler 8 jobs + retention + backup | ✅ | ❌ | ❌ | Watch scheduler (local) |
| Per-run trace + token accounting | ✅ | ❌ | ✅ traces | ✅ receipts |
| Redacted logs + metrics + health | ✅ | ❌ | ❌ | ✅ ops |
| Roman Urdu report + BLUF + report file | ✅ | Ukrainian/Russian report | English markdown | English brief |
| Hosted supervisor/watchdog | ✅ | ❌ | ❌ | unverified |

## 2. Jo competitors ke paas hai, JIN me missing (honest gaps)

| Gap | Competitor source | JIN status |
|---|---|---|
| PDF / HTML report export + private reader | ashishki | ❌ sirf `.md` file (`briefer.save`:347) |
| Multi-turn conversation context (chat memory) | maddness (session 30 min), ashishki (bounded turns) | ❌ sirf per-query `search_memory` |
| Real LLM se report/synthesis | sab (Claude/Hermes/DeepSeek) | ⚠️ LLM `off` default; sirf local/custom endpoint optional — report rule-based Roman Urdu |
| Confirmed external actions (mail/calendar/Act) | ashishki | ❌ |
| Media / OCR / speech inputs | ashishki | ❌ |
| Immutable versioned BriefDocument (ID/version/digest) | ashishki | ❌ reports table hai, magar versioned document model nahi |
| User-API channel reach (Telethon login) | maddness | ❌ JIN sirf public `t.me/s/` preview (policy) |
| Channel post search ke andar message-id citations | maddness | ⚠️ JIN channel search result URL deta hai, message id nahi |
| Web-search breadth (Brave/Bing keyed) | tsukeno (DDG), ashishki (Brave) | ⚠️ JIN me Brave/Bing adapters hain magar default **off**, key chahiye |

## 3. JIN behtar karta hai (un 3 ke against)

1. **Legal/policy boundary + source provenance:** JIN ka `SAHULAT-SAFE-SERVICE-v1` gate, 45-entry legal register, SSRF allowlist aur `url_fetched=False` honesty competitors me nahi. maddness Telethon user-API login use karta hai (broader reach, lekin zyada legal/ToS risk).
2. **Offline reproducibility:** JIN 480 tests + deterministic fixtures + ci-gate; tsukeno 4 tests; maddness tests unverified.
3. **Channel lifecycle:** discovery + liveness score + dead/stale/archive + TTL + health digest + failed-channel negative memory — kisi competitor me nahi.
4. **Archive intelligence:** FTS5 + canonical dedup + near-dup collapse + cross-verification + repeated-claim labels + confidence caps + citation audit — tsukeno/maddness se aage.
5. **Ops:** scheduler 8 jobs, retention, SQLite backup, redaction, metrics, health, supervisor/watchdog, web console + CLI.
6. **Honest absence:** `ok/no_results/fetch_failed/partial/blocked` alag payam — maddness/tsukeno me ye distinction nahi.
7. **Cost/key independence:** JIN bina API key chalta hai; competitors ke LLM keys lazymi.

## 4. Honest risks / kamzoriyan

- **LLM off** hone se JIN ki synthesis/ranking rule-based hai; real-language summarization competitors ke samne kamzor.
- **PDF/HTML export** nahi — report sirf `.md`.
- **Multi-turn chat context** nahi — har sawal modular research hai.
- **Telegram channel search** sirf public preview server-side `?q=`; private/invite-only channels ya message-id citations nahi.
- **`is_owner` default allow-all** (code-verified, `telegram_bot.py`:1947) — production me `TELEGRAM_CHAT_ID` lazmi.
- **Koi real external action** (mail/calendar/write) nahi.
- **Koi mobile app** nahi.

## 5. Top 5 gaps (priority order)

1. **PDF/HTML export + versioned brief** (ashishki parity) — must.
2. **Multi-turn conversation memory** (maddness/ashishki) — should.
3. **LLM synthesis default on / local model bundle** — should (quality gap).
4. **Keyed web search (Brave/Bing) default readiness** — could.
5. **Message-id level channel citations** — could.

---

## 6. Parity score (19 Nov 2026)

`replica/parity.csv` + `replica-diff/parity.py` se: **overall parity 88.5 / 100** (21 scored features; must-haves 11/11 done). Iska matlab competitor-verified capabilities ka zyada tar hissa JIN me mojood hai; 51 features JIN ki apni additions hain (score se bahar).

**Sab se bada gap:** `reporting` area — **PDF/HTML export** (sirf `.md`). Uske baad `memory` (multi-turn chat context) aur `actions` (confirmed external actions). Missing list me koi **must-have nahi** — sirf 3 should-haves. Detail: `replica/parity.md`.
