# Research Report — Telegram Research Bot UX, Message Splitting aur Loop Behaviour

**Date:** 18 Nov 2026
**Scope:** Sirf research + analysis. **Koi code change / implementation nahi kiya gaya.**
**Analyst:** JIN Agent (read-only inspection of `jin_agent` + public web sources)
**Question (user):** Bot ek jawab 3-4 messages mein kyun bhejta hai? Loop mein kyun chalta rehta hai aur rukta nahi? Information samajh kyun nahi aati? Google/Perplexity jaise systems aur Telegram search bots (Mother Search, Searchee, hidden indexes) report kaise karte hain?

---

## 1. Executive Summary

| # | Sawal | Jawab (short) |
|---|-------|----------------|
| 1 | 1 jawab 3-4 messages mein kyun? | Telegram ka hard limit **4,096 characters per message** hai. Aap ki last report **16,179 characters** thi → `ceil(16179/4096) = 4` chunks. Plus 1 progress message = **5 bubbles**. Ye bug nahi, platform limit + chunking design hai. |
| 2 | Loop mein kyun chalta hai, rukta nahi? | Teen alag "loops" hain: (a) long-polling loop by design (infinite), (b) **watchdog crash-restart loop** (SyntaxError ki wajah se — ab fix ho chuka), (c) 150s se lambi research ka orphan thread + global stop flag. Research algorithm khud loop nahi karta — `orchestrator.run()` single-pass hai. |
| 3 | Information samajh kyun nahi aati? | Report 16k chars lambi hai, TL;DR/3-key-findings nahi, Telegram tables render nahi karta, sources end mein lambi URLs ki list. Perplexity/ChatGPT DR "answer-first + inline citation + sources used + TOC" format use karte hain. |
| 4 | Telegram search bots kaise report karte hain? | Wo **research bots nahi, index bots** hain: keyword → short result list + pagination buttons + filters (`/export` CSV, `/top` trending). Report nahi likhte, is liye unka output chhota aur paginated hota hai. |

**Sab se bara actionable insight:** Ek hi research ke liye 5 messages bhejne ki zaroorat nahi. Industry pattern = **1 message jo edit hota rahe (progress) + 1 short summary + full report button/document**.

---

## 2. Masla #1 — Ek jawab 3-4 messages mein kyun?

### 2.1 Platform limit (verified facts)

| Cheez | Limit | Error |
|---|---|---|
| `sendMessage` text | **1–4,096 characters** (entities parse hone ke *baad*) | `400 Bad Request: message is too long` |
| Media caption | 0–1,024 characters | `message caption is too long` |
| Rich message (Bot API 10.1, 11 June 2026) | **32,768 characters** | n/a |

Telegram poora message reject karta hai — truncate nahi karta. Is liye chunking **client side** karni parti hai. ([dripl.ai](https://dripl.ai/blog/telegram-character-limit), [conferbot](https://www.conferbot.com/limits/telegram), [picklog](https://www.picklog.cc/blog/telegram-bot-message-limit))

**Unit ka nuance:** limit "characters" nahi, **Unicode code points after entity parsing** hain (2026 measurements). Emoji/combining marks par byte-count wale splitters galat jagah kaat dete hain; entity offsets UTF-16 mein hote hain. ([charliemorrison.dev](https://charliemorrison.dev/blog/telegram-4096-character-limit), [tgscope](https://dev.to/tgscope_629d565fb02dbb743/telegrams-1024-and-4096-limits-count-utf-16-code-units-not-characters-290i))

### 2.2 Hamare repo ka actual evidence

| Evidence | Value |
|---|---|
| `telegram_bot.py:32` | `SEND_CHUNK_LIMIT = 4096` |
| `telegram_bot.py:68–80` | `split_text()` — sirf `\n` par todta hai |
| `telegram_bot.py:208` | alag progress message: "🔍 Research chal rahi hai..." |
| `telegram_bot.py:225–230` | har chunk ke liye alag `sendMessage` |
| `data/reports/brief-20261118T065001.md` | **16,179 chars → 4 chunks** |

16,179 / 4,096 = 3.95 → **4 messages**, plus progress = **5 total**. Yehi aap ko "3-4 messages" dikhta hai.

**Side-effect (readability):** `split_text()` sirf newline par todta hai, blank-line/section boundary par nahi. Markdown table ya code block ke beech chunk cut ho sakta hai → adhoori table, toota hua formatting.

### 2.3 Industry isay kaise solve karta hai

| Pattern | Kya karta hai | Kahan use hota hai |
|---|---|---|
| **A. Numbered parts** | `1/4`, `2/4` labels + 1s gap (rate limit ~1 msg/sec/chat) | Common bot pattern ([dripl](https://dripl.ai/blog/telegram-character-limit), [kerit](https://kerit.cloud/blog/telegram-bot-api-limits-and-how-to-stay-under-them/)) |
| **B. Summary + link/document** | Chhota summary + poori report website/document par | (dripl) |
| **C. Edit-in-place progress** | Ek hi message ko `editMessageText` se update karna, naye message nahi | (kerit: "Edit instead of send… don't edit more than every 1–2 sec") |
| **D. Inline keyboard pagination** | Buttons se next page, ek message mein limited content | (conferbot) |
| **E. Document upload** | Long text `sendDocument` se .md/.pdf | (conferbot) |
| **F. Entity-preserving split** | Markdown bold/links ko chunk boundary par sahi todna | GramIO Split plugin ([gramio.dev](https://gramio.dev/plugins/official/split.html)) |
| **G. Rich messages (naya)** | 32,768 chars ek message mein — 16k report single bubble | Bot API 10.1, June 2026 ([dripl](https://dripl.ai/blog/telegram-character-limit)) |

### 2.4 Perplexity / ChatGPT / Gemini ka output shape

Ye teeno **ek hi "report view"** dete hain, message spam nahi:

- **ChatGPT Deep Research:** fullscreen report view + **table of contents** + **"sources used"** section + **activity history**; export Markdown/Word/PDF. ([OpenAI Help](https://help.openai.com/en/articles/10500283-deep-research-in-chatgpt), [OpenAI Dev Docs](https://developers.openai.com/api/docs/guides/deep-research))
- **Perplexity:** har claim par **inline numbered citations** — core identity. ([diflowrin](https://diflowrin.com/openai-vs-gemini-vs-perplexity-deep-research), [ynteractive](https://learn.ynteractive.com/content/compare/perplexity-vs-chatgpt-vs-gemini-for-research))
- **Gemini Deep Research:** pehle **editable research plan**, phir progress, phir cited report; Docs export. ([universaldigitalassistant](https://universaldigitalassistant.com/guides/deep-research-tools-compared))
- **Common denominator:** plan → progress → **ek structured report** (TOC + citations + limitations) → export.

---

## 3. Masla #2 — Loop mein chalna, rukta nahi

### 3.1 Theory: agent khud nahi rukta, loop ko rokna parta hai

- Model ke paas clock/meter nahi hota; "be thorough" likhna = "kabhi na ruk" instruction. Loop **code** enforce karta hai. ([learnaiengineering](https://learnaiengineering.dev/blog/ai-agent-loops-stopping-conditions-and-guardrails))
- Zaroori guards: **max iterations**, **wall-clock timeout**, **cost/token budget**, **tool-call dedup**, **progress check**. ([JetBrains](https://www.jetbrains.com/pages/ai-agents/architecture/ai-agent-loops))
- Academic survey: bounds = max turns, timeouts, retry limits, budgets, recursion limits; inke baghair same loop infinite agentic loop ban jata hai. ([arXiv 2607.01641](https://arxiv.org/html/2607.01641v1))
- Framework defaults: OpenAI Agents SDK `max_turns=10` (v0.24), CrewAI `max_iter=20`, LangGraph `recursion_limit` (docs 25 vs runtime 10007 — mismatch khud ek trap hai). ([agentnative](https://www.agentnative.dev/patterns/agent-loop-termination-pattern), [agentloopnotes](https://agentloopnotes.com/posts/agent-infinite-loop/))
- Doom-loop detection ladder: observe → steer → block → stop; exact-same-call 3rd repeat par stop. ([OpenRouter](https://openrouter.ai/blog/ai-agent-infinite-loop/))

### 3.2 Hamare code mein "loop" ke 4 mumkin asbaab (evidence-based)

| # | Loop | Evidence | Nature |
|---|---|---|---|
| 1 | **Long-polling loop** | `telegram_bot.py:247` → `while not stop.is_set():` | By design; ye "rukna" nahi chahiye — yehi bot ka dil hai. |
| 2 | **Watchdog crash-restart loop** | `watchdog.log`: `bot started pid=…` → `exited code=1` baar baar (11:41, 11:43, 11:45) | **Yehi asli "loop" tha.** `SyntaxError` (duplicate `global`) — ab fix ho chuka. |
| 3 | **Orphan research thread** | `telegram_bot.py:275` → `done.wait(timeout=150)`; thread `daemon=True`, timeout par kill nahi hota | 150s se lambi research background mein chalti rehti hai; naya command naya thread → **do research sath**, messages interleave. |
| 4 | **Global stop flag** | `telegram_bot.py:52,189,206,232` → `_stop_research` module-level global | Do concurrent threads ek hi flag share karte hain → ek ki `/stop` doosri ko bhi maar deta hai, ya flag reset se "auto-stop" behaviour ajeeb lagta hai. |

**Ahem:** `orchestrator.run()` **single-pass pipeline** hai (`orchestrator.py:24`) — koi `while` loop nahi. Matlab research algorithm khud infinite loop nahi karta; "loop" **transport layer** (polling / watchdog / threads) se aata hai.

### 3.3 "Rukta nahi" ka doosra pehlu — message flood

4 chunks back-to-back (~1 sec ke andar) aankh ko "loop of messages" lagta hai. Telegram ka safe rate **~1 message/sec per chat** hai; is se tez bhejna `429 Too Many Requests` bhi la sakta hai. ([kerit](https://kerit.cloud/blog/telegram-bot-api-limits-and-how-to-stay-under-them/))

---

## 4. Masla #3 — "Information ki samajh nahi aati"

### 4.1 Report anatomy ka masla

| Issue | Detail |
|---|---|
| Length | 16,179 chars = ~2,500 words ek chat bubble chain mein |
| No BLUF | Shuru mein "Bottom Line Up Front" / 3 key findings nahi |
| No TOC | Long report mein navigation nahi |
| Telegram tables | Telegram Markdown tables render **nahi** karta — alignment toot jata hai |
| Sources | End mein lambi URL list; claim-level linkage nahi |
| No confidence | Kya verified hai, kya nahi — clear nahi |

### 4.2 Top research systems ka format (industry consensus)

```
1. TL;DR (2-3 lines)
2. Key Findings (3-5 bullets, har bullet ke sath citation)
3. Details (sections, sub-headings)
4. Sources Used (numbered, clickable)
5. Limitations / Confidence (kya verify nahi ho saka)
```

- Perplexity: **har claim par numbered citation** (inline). ([ynteractive](https://learn.ynteractive.com/content/compare/perplexity-vs-chatgpt-vs-gemini-for-research))
- ChatGPT DR: TOC + sources used + activity history + export. ([OpenAI Help](https://help.openai.com/en/articles/10500283-deep-research-in-chatgpt))
- Public research warning: citation hona ≠ citation sahi hona — independent evaluation mein systems 11% se kam citation rubric items pura karte hain. Is liye "sources used" + "limitations" section zaroori. ([glasp](https://glasp.co/articles/deep-research-tools-compared))

---

## 5. Telegram search bots landscape (Searchee / Mother Search / "hidden" engines)

### 5.1 Ye bots kya hain

| Bot | Maqsad | Scale | Notes |
|---|---|---|---|
| **@SearcheeBot** | Channel directory, 40 categories, inline mode | ~292–322K MAU | TGStat se linked |
| **@MotherSearchBot** | "Google analogue in Telegram" — posts, channels, groups, chats | — | Content/post search (naam search nahi) |
| **@oSearchBot** | Channels + groups + content | ~163K MAU | General search |
| **Argo🔍Search** | Search + group directory + trending | — | 20 interface languages |
| **MySearch Bot** | Relevance+activity sorted, filters | ~1M MAU | 10 languages |
| **Kuaisou** | Channels/groups/videos/audio/messages/files | ~3M MAU | Chinese index |
| **JISOU** | Sab se bara Telegram search engine | ~5M MAU | Chinese-focused |

Sources: [GramBots](https://www.grambots.com/bots/searcheebot), [bitbrowser](https://www.bitbrowser.net/blog/top-telegram-search-bots), [traffnews](https://traffnews.com/telegram/boty-dlya-poiska-kanalov-v-telegram), [habr](https://habr.com/en/articles/990174), [grambots blog](https://www.grambots.com/blog/search-telegram-channels-groups)

### 5.2 Inka workflow (aur hamare se farq)

```
User: keyword (1-2 words best)
  ↓
Bot: short result list (10-20 items) + inline buttons
     [Channels] [Groups] [Bots] [Posts] [Next ▶]
  ↓
Filters: language (27 langs), category, trending (/top, /hot)
Export: /export → CSV
```

**Ye "research bots" nahi hain — ye "index/search bots" hain.**
- Report synthesize nahi karte → is liye unka output **chhota + paginated** hota hai, kabhi 4 messages nahi.
- Apna index maintain karte hain (public channels/posts crawl), is liye same keyword par Telegram native search se different results dete hain.
- "Hidden/special" engines (JISOU, Kuaisou) ka edge = **bara private index** + MTProto/userbot harvesting — ye legally/ToS ke لحاظ se risky zone hai, aur rate-limited hota hai.

### 5.3 Hamare bot ka position

Hamara bot = **research/synthesis bot** (Searchee/MotherSearch jaisa index bot nahi). Is liye comparison galat nahi, magar **output shape** un jaisa chhota nahi ho sakta — humein Perplexity/ChatGPT DR jaisa *structured single report* chahiye, 4 raw chunks nahi.

---

## 6. Comparison Table

| System | Output shape | Length handling | Citations | Loop control |
|---|---|---|---|---|
| **JIN Agent (current)** | 1 progress + 4 chunks (~16k chars) | 4096 hard split on `\n` | End-list | Long-poll infinite; watchdog restart; 150s thread timeout |
| **Perplexity** | Single answer, numbered inline cites | Server-side render | Inline per claim | Agent session + effort dial |
| **ChatGPT DR** | Report view: TOC + sources + activity | Fullscreen report + export | Source links + sources used | Plan → progress → report; interruptible |
| **Gemini DR** | Editable plan → cited report | Docs export | Citations | Plan approval first |
| **SearcheeBot** | Short channel list + pagination | Paginated buttons | Links | Stateless request/response |
| **MotherSearch** | Post/channel results | Paginated | Links | Stateless |

---

## 7. Recommendations (design-level — koi implementation nahi)

### 7.1 Output UX (4 messages ka hal)

1. **Ek hi progress message** banao aur `editMessageText` se update karo ("Searching… → Reading 12 sources… → Writing…"). 1 bubble.
2. **Final deliverable = 2 messages max:**
   - Msg 1: **TL;DR + 3–5 key findings** (≤1,000 chars)
   - Msg 2: full report **document** (.md/.pdf) ya inline button `[📄 Full report]`
3. Agar text hi bhejna hai: **`1/4` labels + 1s gap** (429 se bacho), aur **blank-line boundary** par split karo (table/code ke beech kabhi nahi).
4. Naya option: **Bot API 10.1 rich messages (32,768 chars)** — 16k report single bubble mein. Library support check karna hoga.

### 7.2 Loop control (rukne ka design)

1. **Ek chat = ek research** (mutex/queue). Doosra `/research` aaye to "pehli khatam hone dein" ya queue.
2. **Explicit stop conditions:** max iterations + wall-clock timeout + dedup (same tool call 3rd repeat) + progress check (naye sources nahi mil rahe → stop).
3. **Force-answer step**: limit hit hone par exception nahi, balke "jo mila us se answer + kya verify nahi hua" — partial answer behtar hai.
4. **Per-chat state**, global flag nahi (global flag concurrent threads mein cross-talk karta hai).
5. Watchdog logs ko monitor karo: `exited code=1` ka matlab crash loop (jaise aaj SyntaxError) — ye alag signal hai.

### 7.3 Readability (samajh aane ka design)

1. **BLUF template:** TL;DR → Key Findings (3–5) → Detail → Sources Used → Limitations/Confidence.
2. **Har finding ke sath source number** (`[1]`), end mein numbered clickable list.
3. Telegram par **tables avoid** karo — bullets use karo.
4. **Confidence line** hamesha: "X sources verified, Y unverified".
5. Log karo: `chars_per_report`, `chunks_sent`, `turns_used` — inhe eval metric banao.

---

## 8. Evidence Index (repo)

| File | Line | Kya dikhata hai |
|---|---|---|
| `jin_agent/telegram_bot.py` | 32 | `SEND_CHUNK_LIMIT = 4096` |
| `jin_agent/telegram_bot.py` | 68–80 | `split_text()` newline-only chunking |
| `jin_agent/telegram_bot.py` | 208 | progress message |
| `jin_agent/telegram_bot.py` | 225–233 | chunk send loop |
| `jin_agent/telegram_bot.py` | 247 | infinite long-poll `while` |
| `jin_agent/telegram_bot.py` | 275 | `done.wait(timeout=150)` |
| `jin_agent/telegram_bot.py` | 52 | global `_stop_research` |
| `jin_agent/orchestrator.py` | 24 | `run()` single-pass (no loop) |
| `jin_agent/data/logs/watchdog.log` | — | crash-restart loop evidence |
| `jin_agent/data/reports/brief-20261118T065001.md` | — | 16,179 chars → 4 chunks |

---

## 9. Sources (numbered)

1. Dripl — Telegram character limit (4096, rich messages 32,768, Bot API 10.1) — https://dripl.ai/blog/telegram-character-limit
2. Conferbot — Telegram Bot API limits 2026 — https://www.conferbot.com/limits/telegram
3. Picklog — Telegram bot message limit measured — https://www.picklog.cc/blog/telegram-bot-message-limit
4. Charlie Morrison — 4096 limit measured — https://charliemorrison.dev/blog/telegram-4096-character-limit
5. TGscope — UTF-16 code units study — https://dev.to/tgscope_629d565fb02dbb743/telegrams-1024-and-4096-limits-count-utf-16-code-units-not-characters-290i
6. Kerit Cloud — Bot API limits + edit-instead-of-send — https://kerit.cloud/blog/telegram-bot-api-limits-and-how-to-stay-under-them/
7. GramIO — Split plugin (entity-safe chunking) — https://gramio.dev/plugins/official/split.html
8. Telegram — Bot API reference — https://core.telegram.org/bots/api
9. Telegram — Bot features (inline keyboards, streaming replies) — https://core.telegram.org/bots/features
10. OpenAI Help — Deep research in ChatGPT (TOC, sources used, activity history) — https://help.openai.com/en/articles/10500283-deep-research-in-chatgpt
11. OpenAI Dev Docs — Deep research (citations, background mode) — https://developers.openai.com/api/docs/guides/deep-research
12. Diflowrin — OpenAI vs Gemini vs Perplexity Deep Research — https://diflowrin.com/openai-vs-gemini-vs-perplexity-deep-research
13. Universal Digital Assistant — Deep research tools compared — https://universaldigitalassistant.com/guides/deep-research-tools-compared
14. Ynteractive — Perplexity vs ChatGPT vs Gemini (citations) — https://learn.ynteractive.com/content/compare/perplexity-vs-chatgpt-vs-gemini-for-research
15. Glasp — Deep research tools compared (citation quality) — https://glasp.co/articles/deep-research-tools-compared
16. LearnAIEngineering — Agent loops: stopping conditions — https://learnaiengineering.dev/blog/ai-agent-loops-stopping-conditions-and-guardrails
17. JetBrains — AI agent loops (iteration limits) — https://www.jetbrains.com/pages/ai-agents/architecture/ai-agent-loops
18. arXiv 2607.01641 — Infinite agentic loops survey — https://arxiv.org/html/2607.01641v1
19. OpenRouter — Stopping AI agent infinite loops — https://openrouter.ai/blog/ai-agent-infinite-loop/
20. Agent Native — Loop termination pattern + framework defaults — https://www.agentnative.dev/patterns/agent-loop-termination-pattern
21. AgentLoopNotes — Debugging agents that never stop — https://agentloopnotes.com/posts/agent-infinite-loop/
22. Oracle Dev Blog — The agent loop decoded — https://blogs.oracle.com/developers/the-agent-loop-decoded-three-levels-every-agent-engineer-must-know
23. GramBots — Searchee Bot — https://www.grambots.com/bots/searcheebot
24. BitBrowser — Top 7 Telegram search bots tested 2026 — https://www.bitbrowser.net/blog/top-telegram-search-bots
25. Traffnews — Top Telegram channel search bots — https://traffnews.com/telegram/boty-dlya-poiska-kanalov-v-telegram
26. Habr — Top 25 useful Telegram bots (search engines) — https://habr.com/en/articles/990174
27. GramBots Blog — How to search Telegram — https://www.grambots.com/blog/search-telegram-channels-groups

---

**Disclaimer:** Ye report public sources + repo code ke read-only analysis par based hai. Live bot par experiments nahi kiye gaye (aap ki hidayat: no action). Koi file modify nahi ki gayi siwaye is report ke.
