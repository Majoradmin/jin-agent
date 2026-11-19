# JIN Agent — Replica Parity

**Matrix:** `replica/parity.csv` (76 features; 21 scored, 51 JIN extras, 1 skip)
**Competitors:** maddness/tg-deep-research, tsukeno/hermes-research, ashishki/telegram-research-agent
**Date:** 19 Nov 2026

## Summary

- **Overall parity score: 88.5 / 100** (features only; koi layout/visual diff nahi).
- **Must-haves: 11 of 11 done** — koi missing must-have nahi. Competitorverified must-haves ka poora hissa mojood hai.
- **Missing must-haves (build order):** **none** — sab 11 must-haves complete.
- **Missing should-haves (build order — agla kaam):**
  1. **PDF/HTML export** (reporting) — sirf `.md` file; ashishki HTML/PDF/MD + private reader deta hai. `[should]`
  2. **Multi-turn chat context** (memory) — sirf per-query `search_memory`; maddness (30-min session) aur ashishki (bounded turns) multi-turn dete hain. `[should]`
  3. **Confirmed external actions (Act)** (actions) — mail/calendar/write nahi; ashishki preview + one-use confirm + receipts karta hai. `[should]`
- **Sab se bada gap:** report **export format** (PDF/HTML) + **conversation memory** — dono user-facing parity gaps hain. Act tab tak JIN ka scope bahar hai.
- **Score ka matlab:** 88.5% iska matlab hai ke competitor-verified capabilities ka zyada tar hissa JIN me hai; 3 should-level gaps baqi. 51 features JIN ki apni additions hain (score se bahar, alag list me).

---

## Parity: 88.5 / 100

features 88.5  (21 counted, must-haves 11 of 11 done)

## By area, weakest first
- memory                         0.0  (1 features)
- actions                        0.0  (1 features)
- reporting                     60.0  (2 features)
- onboarding                   100.0  (1 features)
- research                     100.0  (5 features)
- search                       100.0  (2 features)
- channels                     100.0  (1 features)
- scheduler                    100.0  (2 features)
- ops                          100.0  (2 features)
- observability                100.0  (3 features)
- qa                           100.0  (1 features)

## Missing, in build order
- [should] actions: Confirmed external actions (Act), no  (mail/calendar/write nahi | src - | original: ashishki Act)
- [should] memory: Multi-turn chat context, no  (sirf per-query search_memory | src searchmemory.py | original: maddness session + ashishki turns)
- [should] reporting: PDF/HTML export, no  (sirf .md file; PDF/HTML nahi | src briefer.py:347 | original: ashishki HTML/PDF/MD export)

## Left out on purpose (not scored)
- Media/OCR inputs: koi upload/OCR adapter nahi | src - | original: ashishki media/OCR; JIN out-of-scope

## Yours, not in the original (not scored)
- Bot API "/" command menu
- /research --deep
- Progress 3s throttle
- BLUF message
- Query-term HTML highlight
- Report chunk fallback
- Confidence gate for file
- Honest absence states
- Mil gaya / Nahi mila gate
- Retry rounds with skip
- Round limit
- /stop
- /channels add confirm gate
- /channels rm (archive)
- /channels --all
- Channel health digest
- Channel auto-discovery
- Liveness probe + scoring
- Dead channel archive + TTL
- Stale channel marking
- /explore [topic]
- Explore cards + gate
- Site memory (tg_sites)
- /status agent+explore block
- Poll failure observability
- Firehose ingest
- Daily digest
- Per-query search memory
- Failed-channel negative memory
- Memory audit
- /memory
- Dark/deep web links-only
- Policy block gate
- SSRF allowlist
- Legal source register
- Adapters breadth
- Canonical dedup + near-dup
- Cross-verification
- Repeated-claim detection
- Confidence aggregate + caps
- Citation audit
- Redacted JSON logs
- Web console
- Hosted supervisor
- Watchdog
- CI gate
- Group rate limit
- SOCKS5 proxy
- Telegram chat allowlist
- Foreign-source translation
- Private channel scrape
- Dark-web fetch/crawl
- Multi-user auth
- Mobile app
