# Telegram-Wide Discovery & Search — Architecture + Implementation Plan

**Bot:** `@jin_agent101_bot` (JIN Agent)
**Repo:** `Majoradmin/jin-agent` · **Branch:** `main` · **HEAD:** `f93403c`
**Document date:** 2026-11-21
**Status:** Phase 1 verified ✅ · Phase 2 implemented ✅ · Phase 3–5 planned

---

## 0. Reading guide — facts vs assumptions

| Marker | Meaning |
|---|---|
| **[FACT]** | Verified against code, live network, or the provider's own docs on the date shown |
| **[ASSUMPTION]** | Reasoned estimate, not yet measured |
| **[PLAN]** | Design intent — no code yet |

Every provider claim below carries a source + check date. Where a provider could not be
verified, it is marked **[UNVERIFIED]** and is never used as a basis for a claim.

---

## 1. Phase 1 — Verification of the previous fix (DONE)

### 1.1 Commits present

| Check | Command | Result |
|---|---|---|
| `6ac37ba` exists | `git cat-file -t 6ac37ba` | `commit` ✅ |
| `f93403c` exists | `git cat-file -t f93403c` | `commit` ✅ |
| Compile | `python3 -m compileall -q .` | rc=0 ✅ |
| Tests | `JIN_AGENT_DATA=$(mktemp -d) python3 -m unittest discover -s jin_agent/tests -t . -q` | **669 tests, OK (1 skipped)** ✅ |
| Remote | `git ls-remote origin refs/heads/main` | `f93403c92636239c03ae4ceb656346511980fa3e` ✅ |
| Tree | `git status --porcelain` | clean ✅ |

### 1.2 Live `/explore` results (real Telegram, chat `Jin->Agent`, 21 Nov 2026 12:42–12:43)

| Query | Language | Telegram section | `example.org` | Sources seen |
|---|---|---|---|---|
| `android` | English | — (0 TG, 3 probed all stale) | **0** ✅ | Stack Exchange API, Google News RSS, 9to5Google, Hacker News |
| `موبائل سیکیورٹی` | Urdu | `📡 Telegram (6): 1 active · 3 stale · 2 private/bot` | **0** ✅ | RightDAO + web |
| `mobail security` | Roman Urdu | `📡 Telegram (9): 4 active · 5 stale` | **0** ✅ | RightDAO + Google News RSS |

**Roman Urdu sample (live, verbatim):**
`Daily_Writeups @Daily_Writeups 10 · 4.23K · ✅ active` ·
`TNJOKERSEC | Cybersecurity @tnjokersecurity 9 · 7.47K · ✅ active` ·
`RLXTECH @RLXTECHX 7 · 12.8K · ✅ active` ·
`Eset NOD32 keys @esetnodkeys 7 · 11K · ✅ active`

### 1.3 Verification verdict

- ✅ **Synthetic guard works** — `example.org` = **0** in `/explore` (local + live, all three queries).
- ✅ **Live results are `synthetic=0`.**
- ✅ **Multi-source** — results come from ≥4 distinct providers, not one.
- ✅ **Urdu + Roman Urdu both produce Telegram results**, or a clear empty reason.
- ⚠️ **Real gap** — no language detection, no translation, no transliteration, no synonym
  expansion exists. `grep -rni "transliter|langdetect|detect_lang|arabic|script" jin_agent/*.py`
  returns name-only matches, no implementation. Urdu/Roman-Urdu results work only because
  RightDAO happens to match Latin/Arabic strings; relevance is weak (e.g. a *health* channel
  surfaced for "موبائل سیکیورٹی").
- ⚠️ **Discovery is RightDAO-only in practice.** Bing ignores `site:t.me`, DDG/Mojeek/Startpage/
  Ecosia are anti-bot blocked, Brave 429s.

---

## 2. Architecture investigation — 5 options

### 2.0 Headline finding [FACT]

> **The Telegram Bot API has no channel-search method.**
> The complete Bot API method list (core.telegram.org/bots/api, fetched 2026-11-21) contains
> `getChat`, `getChatMemberCount`, `exportChatInviteLink`, `getUpdates`, … and **no**
> `searchPublicChats`, no keyword search, no directory. A bot can only read a chat it is
> already a member of.
>
> Therefore **"Bot API only" cannot discover new channels by keyword.** It can only enrich
> handles already known (via `getChat @username` → title/description/member count).

### 2.1 Option comparison

| # | Approach | Can discover | Cannot discover | Credentials / infra | Rate limits & scaling | ToS / legal risk | Cost [ASSUMPTION] | Best use |
|---|---|---|---|---|---|---|---|---|
| **1** | **Bot API only** | Enrich a **known** @username (`getChat`, member count, invite link); read channels the bot admin added | Any keyword → channel search; any new channel | Bot token only | ~30 msg/s send; `getChat` cheap but per-call | Low — fully sanctioned | Free | Enrichment layer only. **Not a discovery engine.** |
| **2** | **MTProto user client** (Telethon/Pyrogram/GramJS) | `contacts.Search` (public directory), global `messages.search`, read any **public** channel by id, join by username, channel recommendations | Private channels/groups; content behind `t.me/+…` invite links | A **user account** + `api_id`/`api_api_hash` (my.telegram.org), phone verification, session file | Aggressive server-side flood waits; ~seconds between ops; session bans on abuse | **High** — automated user accounts violate Telegram ToS §"Bots"/automation; mass-read = account ban risk; GDPR on personal data | Free infra, **account-risk cost** | Recommended **only** as an optional, opt-in, rate-limited adapter — never the default |
| **3** | **Third-party search APIs** (Telemetr.io, TGStat, tgAtlas, Lyzem, RightDAO, Apify actors) | Keyword → channel catalogue, subscriber counts, post search, categories/languages/countries, recommendations | Coverage is a **slice**, never complete; each provider indexes differently; paid tiers gate depth | Provider API key (Telemetr/TGStat/tgAtlas); Apify account for actors; RightDAO/Lyzem none | Per-plan quotas; RightDAO rate-limits after bursts (observed) | Low–medium — public data, but respect each provider's ToS; no Telegram account risk | Free tier → ~$23–500/mo | **Primary discovery layer.** |
| **4** | **Self-hosted crawler / indexer** of public channels | Whatever you crawl: full history of channels you seed, own ranking, no third-party quota | Anything not reachable from your seed graph; channels with no inbound links; groups | Server + storage + proxy pool; seed list | Self-imposed politeness limits; storage grows fast | Medium — `t.me/s/` is public by design, but bulk crawling at scale is hostile and may draw blocks | Infra only | Useful as the **own index** layer (Phase 3), not as the only layer |
| **5** | **Hybrid: search APIs + MTProto (opt-in) + own index** | All of the above combined, with graceful degradation when one layer is blocked | Still no private content, still no universal coverage | Bot token + provider keys + optional user session | Bounded per provider; cache + backoff | Low if MTProto is opt-in and rate-limited | Free → low monthly | **Recommended** |

### 2.2 Provider facts (checked 2026-11-21)

| Provider | Coverage [FACT] | Free tier [FACT] | Paid [FACT] | Notes |
|---|---|---|---|---|
| **Telegram Bot API** | No search method | — | — | `getChat @username` works for public chats |
| **`t.me/s/<channel>`** | Public channel preview as plain HTML, no login [FACT] | Unlimited | — | The foundation of every free method; dorkable with `site:t.me/s/` |
| **Telegram "Posts" search** | Cross-channel public-post search, launched **31 Jul 2025** | **Premium-only**, free daily quota, then **Stars per search** | Premium subscription + Stars | maxintel.org, re-checked 8 Oct 2026. **Logged-in user collection → research-persona risk.** |
| **tgAtlas** (tgatlas.org/api, RapidAPI `telegram155`) | MTProto REST: `/v1/usernames/<u>`, `/v1/contacts/search`, `/v1/channels/recommendations` | **2,500 calls/month, no card** | Paid tiers | Free directory search + recommendation graph. **[FACT]** per vendor page; free-tier quota needs live confirmation |
| **Telemetr.io** (api.tlmtr.io) | 2.5M+ channels, 70B+ posts, 27M new posts/day; `/v1/channels/search`, `/v1/catalog/search`, posts search, country/language/category filters | Trial **heavily limited**: search returns only a demo channel, `similar` ≤5, `mentions` ≤5, post search only demo channel | Credits or subscription | api.telemetr.me/doc + api.tlmtr.io (checked 2026-11-21) |
| **TGStat** (tgstat.com/api) | 3.14M+ channels, 64.2B+ posts, 8 languages, 37+ topics, human moderation; Search API = keyword → posts with RU/EN/AR morphology | None meaningful | Search **Start 2,100 ₽/mo** (420 ₽/word, 2.1 ₽/query, 5 keywords, 1,000 req/mo, 3-day results); S 4,200 ₽; M 12,600 ₽; L 47,250 ₽ | tgstat.com/api/search (checked 2026-11-21) |
| **Lyzem** | Search engine for public TG channels, groups, messages | Free | — | maxintel.org (8 Oct 2026); **[UNVERIFIED]** API surface |
| **RightDAO** | `site:t.me <q>` → handles | Free, no key | — | **Works** but rate-limits after bursts (observed); 11 handles / 0 active for "free api key" |
| **Apify actors** | `ryumoon-data/telegram-channel-finder` (snowball from seeds + username probing + in-channel search, **no login**); `themineworks/telegram-channel-finder` (Google `site:t.me/<handle>`, pay per channel) | — | Pay per run / per channel | Third-party uptime dependency |
| **Google / Bing / DDG / Mojeek / Startpage / Ecosia / Brave** | `site:t.me` dorks | Free | — | Google `gbv=1` = JS shell (0 results); Bing **ignores** `site:t.me`; DDG 202 anomaly; Mojeek captcha; Startpage Anubis; Ecosia 403; Brave 429 — all **observed** |

### 2.3 Cost estimate [ASSUMPTION]

| Tier | Monthly | What you get |
|---|---|---|
| **Free** | $0 | RightDAO + Lyzem + `t.me/s/` + own index + tgAtlas 2,500 calls |
| **Low** | ~$25–50 | + Telemetr paid entry or TGStat **Start** (2,100 ₽) |
| **Growth** | ~$140–260 | TGStat **M** (12,600 ₽) or Telemetr subscription |
| **Apify** | usage-based | pay per channel delivered; a no-result search is free |

---

## 3. Recommendation — hybrid, provider-agnostic, free-first

```
                    ┌─────────────────────────────┐
   user keyword ──▶ │  Query Variant Pipeline      │  Phase 2
   (any language)   │  detect → translate →         │
                    │  transliterate → synonyms     │
                    └──────────────┬──────────────┘
                                   │  variants[]
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
     ┌────────────────┐  ┌─────────────────┐  ┌──────────────────┐
     │ Discovery      │  │ Own index       │  │ Enrichment       │
     │ adapters       │  │ store.items +   │  │ Bot API getChat  │
     │ rightdao,      │  │ tg_channels +   │  │ + t.me/s/ probe  │
     │ telemetr,      │  │ tg_candidates   │  │ (title, subs,    │
     │ tgstat,        │  │ (Phase 3)       │  │  last post)      │
     │ tgatlas,       │  └────────┬────────┘  └────────┬─────────┘
     │ lyzem,         │           │                    │
     │ mtproto(opt-in)│           ▼                    ▼
     └───────┬────────┘      ┌──────────────────────────────┐
             │               │  Rank + Safety (Phase 4)     │
             └──────────────▶│  dedupe · recency · relevance│
                             │  spam/scam · unsafe · diversity
                             └──────────────┬───────────────┘
                                            ▼
                                  Telegram UX (Phase 5)
                                  cards + preview + buttons
```

**Why hybrid:** no single provider is complete; each fails differently. RightDAO gives handles
but rate-limits; `t.me/s/` gives ground truth on liveness; Telemetr/TGStat give catalogue depth
for a fee; the own index gives history and dedupe. The Bot API's only real job is **enrichment**
(title, member count, invite link) of handles the other layers found.

---

## 4. Gap analysis (current → target)

| # | Capability | Current state | Target | Gap | Phase |
|---|---|---|---|---|---|
| G1 | Accept keyword in any language | Partial — Latin/Arabic pass through | Full | No detection | P2 |
| G2 | Language detection | **Absent** | Script + stopword based, `lang` tag | New module | P2 |
| G3 | Translation of query | **Absent** | LLM-assisted when configured; builtin dictionary fallback | New | P2 |
| G4 | Transliteration (Urdu/Roman Urdu) | **Absent** | Arabic↔Latin table, bidirectional | New | P2 |
| G5 | Synonyms / related niche terms | **Absent** | Curated + LLM-assisted | New | P2 |
| G6 | Query-variant generation | **Absent** | Ordered, deduped variant list | New | P2 |
| G7 | Provider-agnostic discovery interface | Ad-hoc (`web_search_probe`) | `DiscoveryProvider` protocol + registry | New | P3 |
| G8 | RightDAO adapter w/ rate-limit + cache | Inline in `channels.py` | Adapter + cache + backoff | Refactor | P3 |
| G9 | ≥1 additional provider | None working | Telemetr or tgAtlas adapter | New | P3 |
| G10 | Optional MTProto adapter | None | Opt-in, rate-limited, clearly labelled | New (optional) | P3 |
| G11 | Local channel index / dedupe | `tg_channels` + `tg_candidates` | + `tg_posts` (post preview/date/lang) | Migration | P3 |
| G12 | Deduplication across providers | handle-level only | normalized handle + URL dedupe | New | P4 |
| G13 | Activity / recency scoring | 30-day liveness flag | Continuous recency score | New | P4 |
| G14 | Relevance scoring | `channel_signs` keyword set | variant-weighted relevance + reason text | New | P4 |
| G15 | Spam / scam filtering | none | signals: bot-only, no posts, giveaway keywords, verified flag | New | P4 |
| G16 | Unsafe / illegal content filter | policy `BLOCK_PATTERNS` for queries | extend to channel/post text | New | P4 |
| G17 | Source diversity | `max_items_per_source=6` | per-provider cap + MMR-style spread | Partially done | P4 |
| G18 | Result limits + pagination | cap 15 | page tokens + "More results" | Partial | P5 |
| G19 | Telegram card fields (title, link, preview, date, lang, reason, source) | title/handle/score/subs/status | + preview, date, lang, reason | Partial | P5 |
| G20 | Preview translation | none | LLM translate when configured | New | P5 |
| G21 | Loading / empty / error UX | partial | explicit 3 states | Partial | P5 |
| G22 | Inline buttons (More / Open / Translate / Refine) | scope + ✅/❌ + "Aur explore karo" | + More results, Open, Translate, Refine | Partial | P5 |
| G23 | Synthetic items never in `/explore`/digest/reports | **Done** (`items.synthetic`) | keep | ✅ done | P1 |
| G24 | Scheduler live by default | **Done** | keep | ✅ done | P1 |

---

## 5. Phased implementation plan

### Phase 1 — Verification ✅ DONE
- `6ac37ba` synthetic guard · `f93403c` docs.
- Evidence in §1.

### Phase 2 — Multilingual query pipeline ✅ DONE (this change)
**New file:** `jin_agent/query_variants.py`

| Function | Purpose |
|---|---|
| `detect_language(text)` | Script ranges (Arabic/Cyrillic/Devanagari/Latin) + stopword scoring → `{lang, confidence, script}` |
| `transliterate(text, direction)` | Arabic↔Latin Urdu table + Roman-Urdu→Arabic; idempotent |
| `translate_query(text, target_langs, cfg)` | LLM-assisted when `llm.resolve(cfg)["enabled"]`; else builtin EN↔UR dictionary |
| `synonyms(text, lang, cfg)` | Curated per-language synonym map + optional LLM expansion |
| `variants(query, cfg, max_variants=12)` | Ordered, deduped variant list with `{text, kind, lang}` |

**Wiring:** `channels.run_discovery(cfg, offline, max_add, query)` gains `variants=None`;
`telegram_bot._run_explore` passes `query_variants.variants(topic, cfg)`.
**Tests:** `jin_agent/tests/test_query_variants.py`.

### Phase 3 — Discovery layer (planned)
- New `jin_agent/discovery.py` with a provider protocol:
  `class Provider: name; healthy(); search_channels(variants, limit, cfg) -> list[dict]`.
- Adapters: `RightDAOProvider` (move logic out of `channels.py`, add cache + backoff),
  `TelemetrProvider` (key from `TELEMETRIO_API_KEY`), `TgAtlasProvider` (`TGATLAS_API_KEY`),
  `LyzemProvider` (no key), `MTProtoProvider` (**opt-in**, `JIN_AGENT_MTPROTO_ENABLED=1`).
- DB migration: `tg_posts(id, channel, post_id, text, posted_at, lang, url, synthetic)`
  for previews/dates; `tg_candidates` gains `lang`, `reason`, `discovered_at`.
- Env: `TELEMETRIO_API_KEY`, `TGATLAS_API_KEY`, `JIN_AGENT_MTPROTO_ENABLED`,
  `JIN_AGENT_DISCOVERY_PROVIDERS`, `JIN_AGENT_DISCOVERY_CACHE_TTL`.

### Phase 4 — Ranking & safety (planned)
- New `jin_agent/discovery_rank.py`: `dedupe()`, `recency_score()`, `relevance_score()`,
  `spam_score()`, `unsafe_check()`, `diversify()`.
- Reuse `policy.BLOCK_PATTERNS` for unsafe text.

### Phase 5 — Telegram UX (planned)
- Card format v3: title, @handle, t.me link, preview, date, language, reason, source.
- Buttons: `Open channel` (url), `More results` (page token), `Translate`, `Refine search`.
- Explicit loading / empty / error messages in Urdu + Roman Urdu + English.

---

## 6. Exact files, functions, migrations, env vars

### 6.1 Phase 2 (implemented)

| File | Change |
|---|---|
| `jin_agent/query_variants.py` | **NEW** — detection, transliteration, translation, synonyms, `variants()` |
| `jin_agent/tests/test_query_variants.py` | **NEW** — unit tests |
| `jin_agent/channels.py` | `run_discovery(..., variants=None)` — fan out over variants |
| `jin_agent/telegram_bot.py` | `_run_explore` builds variants once and passes them |
| `jin_agent/PHASES.md` | Phase 43 entry + `PHASE REVIEW — PHASE 43: READY` |
| `jin_agent/tests/test_governance.py` | review count / range bump |

### 6.2 Phase 3 (planned)

| File | Change |
|---|---|
| `jin_agent/discovery.py` | **NEW** — provider protocol + registry |
| `jin_agent/discovery_providers.py` | **NEW** — RightDAO/Telemetr/TgAtlas/Lyzem/MTProto adapters |
| `jin_agent/channels.py` | move RightDAO logic to provider; keep `probe`/`check_channel` |
| `jin_agent/store.py` | migration: `tg_posts`, `tg_candidates.lang/reason/discovered_at` |
| `jin_agent/config.py` | new keys (below) |
| `jin_agent/policy.py` | allowlist for new provider hosts |

### 6.3 Phase 4 (planned)
`jin_agent/discovery_rank.py` **NEW**.

### 6.4 Phase 5 (planned)
`jin_agent/telegram_bot.py` (`format_explore_cards_v3`, new callbacks),
`jin_agent/chat_context.py` (refine = new variant set).

### 6.5 Environment variables (all optional, default off)

| Var | Default | Meaning |
|---|---|---|
| `JIN_AGENT_DISCOVERY_PROVIDERS` | `rightdao,lyzem,tgatlas` | ordered provider list |
| `JIN_AGENT_DISCOVERY_CACHE_TTL` | `3600` | seconds |
| `TELEMETRIO_API_KEY` | — | paid tier unlocks depth |
| `TGATLAS_API_KEY` | — | free 2,500 calls/mo |
| `JIN_AGENT_MTPROTO_ENABLED` | `0` | **opt-in**, user account, ToS risk |
| `JIN_AGENT_QUERY_TRANSLATE` | `auto` | `auto`/`off`/`llm` |

---

## 7. Test cases per phase

**Phase 2** (`test_query_variants.py`)
1. `detect_language("موبائل سیکیورٹی")` → `ur` (Arabic script).
2. `detect_language("mobail security")` → `en`/roman, not `ur`.
3. `transliterate("موبائل")` → `mobail`; round-trip stable.
4. `transliterate("mobail security", to="arabic")` → `موبائل سیکیورٹی`.
5. `synonyms("firmware", "en")` includes `rom`, `flash`, `scatter`.
6. `synonyms("موبائل", "ur")` includes `موبائل فون`, `اسمارٹ فون`.
7. `variants()` dedupes and caps.
8. LLM off → deterministic output (no network).
9. Empty query → empty variants, no crash.

**Phase 3** — provider protocol contract tests, cache hit/miss, backoff on 429, migration on an old DB.
**Phase 4** — dedupe of the same handle from two providers, recency ordering, spam keyword filter, diversity cap.
**Phase 5** — loading/empty/error messages, button callback round-trip, Telegram HTML safety.

---

## 8. Rollout + rollback

| Step | Action | Gate |
|---|---|---|
| 1 | Phase 2 merge, suite green, probe 26/26 | ✅ before deploy |
| 2 | Deploy to FadeHost | user-initiated |
| 3 | Live `/explore` in EN / UR / Roman UR | no `example.org`, `synthetic=0` |
| 4 | Phase 3 free providers only | — |
| 5 | Paid provider (only if user buys a key) | user decision |
| 6 | MTProto adapter | **separate explicit opt-in** |

**Rollback:** every phase is behind a config/env flag and additive. Revert = set
`JIN_AGENT_DISCOVERY_PROVIDERS=rightdao` (or `off`) and redeploy; the pre-existing
`web_search_probe` path remains intact. No destructive DB change: Phase 3 migration only
**adds** tables/columns (`synthetic`-style), so a rollback keeps old data readable.

---

## 9. Explicit non-goals / honest limits

- No private channels, no `t.me/+…` invite content, no bypassing Telegram access controls.
- No claim of "all Telegram channels" — no provider has that; coverage is a slice.
- MTProto automation is **ToS-risky** and is opt-in only, clearly labelled.
- Telegram's own cross-channel "Posts" search is **Premium + Stars**, not free.
- Paid providers are stated as paid; nothing here silently introduces a bill.
- Synthetic/offline fixtures must never reach `/explore`, digest, or reports — enforced by
  `items.synthetic` and covered by `tests/test_synthetic_guard.py`.
