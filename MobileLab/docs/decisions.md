# decisions.md — Architecture Decision Records + Classification Register

**Date:** 2026-11-08 · **Root:** `J:\Ai Agent`
Har ADR: date · context · options · final decision · reason · consequences.

---

## ADRs

### D1 — Existing MobileLab hi core app hai
- **Date:** 2026-11-08 · **Context:** user ne "hmari app" kaha; app pehle se ban chuka tha.
- **Options:** naya product banana / existing app par governance + QA lagana / dobara greenfield rebuild.
- **Decision:** existing `J:\Ai Agent\MobileLab` par **documentation + gap-closing**.
- **Reason:** code chal raha hai, verified hai, user ne isi ko "hmari app" kaha.
- **Consequences:** phases retroactive hain; P5/P10 N/A justify hone hain; koi rewrite nahi.

### D2 — Governance files ki jagah
- **Options:** root par sab / `MobileLab\docs\` mein sab / mix.
- **Decision:** `J:\Ai Agent\agent.md` (root) + 9 docs `J:\Ai Agent\MobileLab\docs\`.
- **Reason:** `agent.md` poore workspace ko govern karta hai; docs app ke andar.
- **Consequences:** do locations; `rules.md` mein dono ka zikr.

### D3 — Saare 12 gates, adapted
- **Options:** sirf zaroori phases / 12 phases lekin N/A likh kar / strict sab with fake auth.
- **Decision:** **12 gates barqarar**; jin ka matlab nahi unhein "N/A + wajah" se pass karna, **skip nahi**.
- **Reason:** user ke prompt ka explicit rule "Do not skip a phase unless I explicitly approve it".
- **Consequences:** P5 aur P10 chhote documentation gates hain, phir bhi `PHASE REVIEW` chahiye.

### D4 — Python standard library only
- **Options:** Flask + feedparser + requests / stdlib only / mix.
- **Decision:** **stdlib only**, koi `pip install` nahi.
- **Reason:** `ModuleNotFoundError: flask` / `feedparser` aaye; local offline zero-dependency target.
- **Consequences:** XML hardening, feed parsing, HTTP client sab khud likhna; tests bhi `unittest`; `pytest` nahi.

### D5 — Local-only git, koi remote nahi
- **Date:** 2026-11-08 · **Options:** GitHub remote / local only / koi git na ho.
- **Decision:** `J:\Ai Agent\.git` — **sirf local**, `chore:` initial commit, koi remote / cloud / credentials.
- **Reason:** user ne "Sirf local, koi remote nahi" choose kiya.
- **Consequences:** koi backup off-site nahi; `.gitignore` secrets/DB/logs ignore karega.

### D6 — Scan path: default restrict + explicit opt-in
- **Options:** hamesha khula / hamesha workspace tak band / default band + opt-in.
- **Decision:** **default workspace-restricted**, `allow_outside: true` par bahar ka folder, aur tab bhi realpath/isdir/symlink/UNC/max-limits checks.
- **Reason:** user ke lafz *"jab zarurat ho to kar lo, warna workspace tak restrict rakho"*. Draft plan mein "hamesha band" ghalat tha — ye technician ke `C:\Firmware\...` workflow ko todta.
- **Consequences:** UI mein explicit checkbox (P9), har opt-in `changelog.md` mein note.

### D7 — Skills / MCP installs defer
- **Options:** sab abhi install / shortlist + defer / kabhi na.
- **Decision:** **defer**, `Open question O1` ke taur par darj; alag task mein shortlist + justification + user ki manzoori.
- **Reason:** stdlib-only / local-only policy se takrao aur scope expansion.
- **Consequences:** koi naya connector / expert abhi enable nahi.

### D8 — Hamesha Roman Urdu (C9)
- **Date:** 2026-11-08 · **Context:** aik clarification batch Chinese/English mein tha; user ne kaha *"mery sth hmaesha roman urdu mein btt kea kro … mjhy ni smjh ai tum kia poch rahy ho"*.
- **Decision:** har reply / sawal / option / description / toast / doc prose **Roman Urdu**; sawal chhote, seedhe, aam lafzon mein. Technical terms / code / paths English.
- **Reason:** user ki explicit, dobara di gayi preference.
- **Consequences:** `rules.md`, `design.md`, `memory.md`, `agent.md` addendum sab is ke mutabiq; `lang="ur-PK-Latn"` rehta hai (Latin script).

### D9 — Sab project files `J:\Ai Agent` mein (C10)
- **Date:** 2026-11-08 · **Context:** user ne kaha *"har progress hr km hona chiye projects sbb yahein save kro bar bar c mein mt jao"*.
- **Options:** plan/progress C: par / J: par / dono jagah.
- **Decision:** har project file, doc, progress, test, log aur git repo **`J:\Ai Agent`** mein. `C:\Users\...\.workbuddy-ai\` sirf WorkBuddy ka app-managed internal session log / plan cache — usay project files ke liye istemal nahi.
- **Reason:** user ka explicit rule; aik hi jagah sab kuch milna chahiye.
- **Consequences:** `agent.md` hi source of truth; purana C: wala plan artifact historical hai; C: sirf aakhri dafa verbatim prompt nikalne ke liye parha gaya.

### D10 — Sahulat & Safe Service Policy
- **Decision:** Huawei ID / Google FRP / Samsung Account–Knox Guard / MDM / carrier / iCloud Activation Lock ka koi bypass automation ya steps nahi; sensitive partitions sirf flag.
- **Reason:** ye server-side ownership / anti-theft controls hain; paid tools bhi server record nahi badal sakte.
- **Consequences:** `PRD.md` out-of-scope + `rules.md` + `knowledge.py` + `agent.md` addendum; koi "research/test/hypothetical" exception nahi.

### D11 — Neutral local git identity (A5)
- **Context:** `git config --global user.name/email` empty.
- **Options:** global config set karna / repo-local neutral identity / commit na karna.
- **Decision:** repo-local `MobileLab Local <mobilelab@localhost.invalid>`; koi asli user data nahi gharha gaya.
- **Reason:** global config user ka personal data hai, usay chherna manzoor nahi; commit ke liye identity zaroori hai.
- **Consequences:** author obviously placeholder hai; agar user apna naam chahein to badal sakte hain (new commit, history rewrite nahi).

### D12 — Line endings / verbatim integrity
- **Date:** 2026-11-08 · **Context:** Windows Git ne `LF will be replaced by CRLF` warnings diye; `agent.md` ka verbatim prompt LF par hai.
- **Options:** kuch na karna / `.gitattributes` add karna / repo-local `core.autocrlf=false`.
- **Decision:** repo-local `core.autocrlf=false` + raw-byte verification.
- **Reason:** CRLF conversion checkout par prompt ke bytes badal deti → R1 (verbatim drift). Is se koi nayi file ya dependency nahi aati.
- **Consequences:** aane wale checkouts bhi LF rakhenge; agar kabhi repo doosre OS par jaye to `.gitattributes` ka faisla naya ADR hoga.

### D13 — Local runtime, scoped internet (C11)
- **Date:** 2026-11-08 · **Context:** user ne kaha *"abhi app sirf local chalani ha internet for agent and firmware ok"*.
- **Options:** bilkul offline / unrestricted outbound / scoped outbound.
- **Decision:** app `127.0.0.1` par local; internet sirf research agent, firmware/provenance maloomat aur Telegram Bot API tak; arbitrary URL default `OFF`.
- **Reason:** local-first requirement aur research/firmware ki zarurat dono barqarar.
- **Consequences:** `research.py` aur Telegram adapter ke liye common allowlist; offline core features graceful degrade; P9 SSRF gate.

### D14 — Telegram Bot API, command + alert (C12)
- **Date:** 2026-11-08 · **Context:** user ne `Bot: command + alert` choose kiya; Bot API official page verify kiya.
- **Options:** Bot API + `getUpdates` / MTProto-TDLib-Telethon / dono / webhook pehle.
- **Decision:** **stdlib `urllib.request` + official Bot API**; user-supplied token; `getUpdates` long polling; `sendMessage` result/alert; webhook baad mein agar user maange.
- **Reason:** zero-dependency policy; official HTTPS API; public-channel history Bot API excerpt mein documented nahi.
- **Consequences:** `limit` 1–100; updates max 24h; webhook aur `getUpdates` mutually exclusive; `message` vs `channel_post` alag; koi purani channel history ka dawa nahi; token storage O2/O4.

### D15 — Legal/authorized deep/dark web research only (C13)
- **Date:** 2026-11-08 · **Context:** user ne `Sirf legal, ijazat wala` choose kiya; BSI definitions verify kiye.
- **Options:** bilkul na jaye / unrestricted Tor crawl / legal public/authorized allowlist.
- **Decision:** sirf **legal, public ya authorized** sources; policy gate fetch se pehle; illegal marketplace, stolen credential, leaked firmware, bypass service, malware, private database reject.
- **Reason:** BSI: dark net browsing apne aap mein illegal nahi, lekin illegal content/download/goods/services illegal hain aur malware risk zyada hai; Sahulat & Safe Service Policy bhi yahi maangta hai.
- **Consequences:** koi default Tor automation nahi; koi downloaded executable nahi; har approved source ka provenance; O5 allowlist approval pending.

### D16 — Any mobile task → safe plan/report (C14)
- **Date:** 2026-11-08 · **Context:** pehle user ne "koi bhi task" kaha, clarification me pehle `Sirf research` choose kiya, dobara poochhne par `Plan + report bhi` pakka kiya.
- **Options:** full automation / sirf research / safe plan + report with policy gate.
- **Decision:** agent koi bhi mobile-software task samjhe, research kare aur Roman Urdu mein **safe plan + report** de; device write/erase, flashing, bootloader/IMEI operations ya lock bypass steps kabhi na de.
- **Reason:** user ka aakhri confirmed jawab + Sahulat & Safe Service Policy.
- **Consequences:** task classifier, fact/assumption/open/risk sections, source provenance, refusal path; P7/P9 regression tests.

### D17 — Competitive differentiation, bypass race nahi
- **Date:** 2026-11-08 · **Context:** P1 competitor research S1–S8; paid suites subscription/loader coverage par, open-source low-level read/write par, enterprise platforms SBOM/vulnerability par focus karte hain.
- **Options:** paid-suite clone / open-source low-level wrapper / validation + provenance + explainability + local records.
- **Decision:** teesra raasta: pre-flash package validation, explainable checks, Roman Urdu research, provenance, official-route job records, Telegram alerts aur safe task plan.
- **Reason:** yahi gap verified sources mein nazar aaya; bypass/device-write race legal aur platform risk ke khilaf hai.
- **Consequences:** koi device-operation feature nahi; marketing/PRD "advanced" ka matlab explainability aur QA, na ke lock removal.

### D18 — Research provenance / source register (C16)
- **Date:** 2026-11-08 · **Context:** R2 banawati citations; P0 ne koi citation nahi likha tha.
- **Options:** sirf summary / inline URLs / source register + local evidence records.
- **Decision:** `PRD.md` mein S1–S16 source register (`URL`, `date checked`); facts aur recommendations alag; P7 mein har research item ka local `sha256` evidence.
- **Reason:** user ne research maangi; governing prompt har result ke liye URL + date aur fact/recommendation separation maangta hai.
- **Consequences:** low-authority reseller/market-size claims exclude; speculation ko fact nahi likha; P2 technology table bhi inhi sources se jorega.

### D19 — Policy reframe: `HARD POLICY` → `Sahulat & Safe Service Policy` (C17)
- **Date:** 2026-11-08 · **Context:** user ne kaha `"ye jo hard policy ha esko remove krdo easy policy rakho mainy logo ki sahult k leay km krna ha na k koi galt km krna main gov of pakistan ka official employe hon"`.
- **Options:** (a) boundary hata dena / (b) sirf naam aur andaaz badalna + sahulat features add karna, boundary barqarar / (c) kuch na badalna. User ne (b) choose kiya — jis option me likha tha `bypass wali line waisi hi rehti hai`.
- **Decision:** docs + app + `knowledge.py` me policy ka naam `Sahulat & Safe Service Policy` aur pehli line **"hum kya madad karte hain"**. Har policy section me canonical note: purana naam `HARD POLICY`, **qaida bilkul waisa ka waisa**. Sath mein 6 sahulat features (FR-21…FR-26) add kiye.
- **Reason:** account / activation locks server-side ownership controls hain; local tool in server records ko badal nahi sakta, aur bypass automation chori-shuda devices ko dobara chalane ka sabse aam raasta hai. Sarkari mulazim hona is technical / legal haqeeqat ko nahi badalta — ulta documented, consent-based workflow un ke liye zyada mehfooz hai. User ki sahulat wali niyat poori karne ka raasta **official-route tooling** hai, na ke boundary hatana.
- **Consequences:** koi chhoot, role-based exception, "research/test/hypothetical" exception nahi. `PRD.md` out-of-scope list unchanged. R11 track; `test_policy_boundary_unchanged` regression. `agent.md` verbatim block untouched (SHA-256 re-checked).

### D20 — `cases` table additive, koi destructive migration nahi (C18)
- **Date:** 2026-11-08 · **Context:** case / asset register chahiye tha; user ki runtime DB `data/mobilelab.db` pehle se maujood hai.
- **Options:** naya DB file / ALTER migration script / `CREATE TABLE IF NOT EXISTS` in existing `SCHEMA`.
- **Decision:** teesra raasta. `db.init()` har run par `executescript(SCHEMA)` chalata hai, is liye purani DB par `cases` table + index khud ban jate hain — koi data loss, koi manual step.
- **Reason:** A7 (migration P6 ADR) aur C10 (sab local). Zero-dependency, offline, backward compatible.
- **Consequences:** `counts()` me `cases`; `/api/status` me naya count; dashboard stat 7th item. `data/` gitignored. Koi full IMEI / document upload nahi — `device_id` 40 char cap aur UI me "sirf aakhri 4 harkat" hint. O11 retention/export P11.

### D21 — 8th view `Sahulat / Official Route` — O9 resolved (C18)
- **Date:** 2026-11-08 · **Context:** P1 me O9 tha ke J8–J11 ke liye naya view ya existing panels.
- **Options:** existing panels me distribute / naya 8th view.
- **Decision:** naya 8th view, kyunke checklist + consent + letter + case register + request-check aik hi workflow hai aur alag jagah hone par technician ko 3–4 tabs ghoomne padte.
- **Reason:** user ne "sahulat" ko primary banaya; aik jagah sab kuch hona zyada aasan. `design.md` §4 ab 8 views.
- **Consequences:** `TITLES`, `nav()`, `#view-sahulat`, CSS `.sah-*` classes. J8–J11 ke **proposed integrations** abhi P7 par hain — PHASE 1B ne unhe implement nahi kiya (C15 ke mutabiq unhe P1B ka incomplete item nahi, balkay apne gate ka pending kaam mana gaya hai).

### D22 — Language split: content Roman Urdu, surface English (C19)
- **Date:** 2026-11-08 · **Context:** user ki nai hidayat: *"information report plan sbb mjhy roman urdu mein chiye werna baki sbb for professional looking eng use kro"*.
- **Decision:** C9 ko refine kiya (replace nahi):
  - **Roman Urdu:** tamam *information*, reports, plans, PRD / docs ki prose, PHASE REVIEW, status summaries, aur user se har baat (sawal + jawab).
  - **English (professional surface):** headings, section titles, table headers, code, identifiers, file paths, API routes, commit messages, technical terms, version strings, UI labels / navigation / button text.
- **Reason:** user ko apni zaban mein samajh chahiye, lekin deliverable ka structural / technical presentation professional aur industry-standard English rehna chahiye. Dono ka amal alag hai: *content* vs *surface*.
- **Consequences:** mojooda docs pehle se is pattern par hain (English headings + Roman Urdu prose) — koi bulk rewrite nahi. Naye docs / reports isi split par likhe jayenge. In-app Roman Urdu microcopy (toasts, hints, letter text) **content** hai, is liye Roman Urdu rehti hai; UI chrome / labels agle phases mein English surface ki taraf align honge (O12). Koi jhootha "poora app English ho gaya" claim nahi.
- **Risk:** is split ko "C9 khatam" samajhna — C9 zinda hai, sirf us ki domain ab clear hai.

### D23 — Retain Python stdlib stack after verified P2 selection (C20)
- **Date:** 2026-11-08 · **Context:** P2 ko 11 governing selection criteria aur official sources ke sath technology stack finalize karna tha; purana table unverified tha.
- **Options:** Flask / FastAPI / aiohttp par migrate · JS/Node runtime · existing Python stdlib stack barqarar.
- **Decision:** **existing Python 3.13 stdlib stack barqarar** — `ThreadingHTTPServer`, `sqlite3` + WAL, `urllib.request`, `xml.etree.ElementTree`, `ThreadPoolExecutor`, vanilla JS/CSS, `unittest`, `run.bat`. P2 me koi dependency, framework ya app code change nahi.
- **Reason:** local-only, zero-`pip`, offline, single-user requirement; existing app chal raha hai; Flask `3.1.x` mature alternative hai lekin Werkzeug / Jinja / Click dependencies aur production deployment model lata hai (`P2-11`). Official `http.server` warning is liye loopback boundary aur mazboot karta hai (`P2-01`).
- **Consequences:** `architecture.md` §2.1 / §2.2 final; app `VERSION` `1.1.0` barqarar; migration sirf naye ADR + user ijazat se. P5/P10 N/A justification zinda rehti hai.

### D24 — Adapter boundaries for modular replacement (C21)
- **Date:** 2026-11-08 · **Context:** governing prompt 2–5 saal ke upgrade / migration risks aur modular-replaceable architecture maangta hai.
- **Options:** direct calls chhorh dena · sab kuch aik framework me rewrite · explicit adapter contracts likhna.
- **Decision:** **teesra raasta**: `server.py` route registry, `db.py` repository, `research.fetch` outbound client, `parse_*` parsers, `sahulat.py` policy data, `app.js` UI modules, settings secrets, aur P7 `telegram.py` / `llm_client.py` adapters ke contracts `architecture.md` §21 me darj.
- **Reason:** har technology row ki replacement strategy ko code se jorna, bina P2 rewrite ke; feed / Bot API / LLM schema drift ka asar aik layer tak seemit.
- **Consequences:** P6/P7/P9 me code badalte waqt contracts pehle parhein; SQL ya framework migration me adaptern hi badalna padega. Koi jhootha "ab sab replaceable ho gaya" implementation claim nahi — contracts documented hain.

### D25 — SQLite WAL + 7-table schema + parameterized SQL
- **Date:** 2026-11-08 · **Context:** `architecture.md` §1 / §6 me purana `6 tables, 3 indexes` tha; PHASE 1B ne `cases` table aur `idx_cases_created` add kiye.
- **Options:** docs ko purana chhorhna · schema ko normalization kar ke rewrite · doc-vs-code sync + placeholder/security rules.
- **Decision:** **7 tables / 4 indexes** exact sync; `cases` ko main DB design me darj; WAL facts (`-wal` / `-shm`, network FS limit, auto-checkpoint, long-reader impact) aur `?` placeholder rule architecture me likhe.
- **Reason:** official `sqlite3` docs string-formatted SQL ko injection vulnerable kehti hain; SQLite WAL docs DB state aur copy behavior batate hain (`P2-02`, `P2-08`). Doc drift R4 ka seedha risk tha.
- **Consequences:** `/api/article` f-string SQL identifier QA #8 P9 me allowlist se fix hoga; WAL-aware backup policy P11; versioned migration P6 (`A7`).

### D26 — Loopback-only HTTP security baseline
- **Date:** 2026-11-08 · **Context:** `http.server` official docs production ke liye recommended nahi, CRLF header injection aur symlink warnings dete hain; MDN CSP aur OWASP SSRF bhi verify hue.
- **Options:** abhi WSGI framework + auth laga dena · loopback boundary likh kar P9 hardening schedule karna · kuch na likhna.
- **Decision:** **loopback-only boundary + P9 hardening schedule**: CSP, body cap, `realpath` / `commonpath`, XML pre-validation, SSRF allowlist with resolved-IP binding, redirects off, secret masking. P2 code nahi badalta.
- **Reason:** single-user local app; par official warning ko ignore karna bhi galat tha. P5 auth N/A sirf `127.0.0.1` par hi qabool hai.
- **Consequences:** LAN / Internet exposure ke liye naya framework + auth + TLS + deployment ADR aur user ijazat lazmi (`R13`). P9 regression tests `phases.md` §6 me maujood.

### D27 — External integrations via Bot API + stdlib HTTP (C11 / C12)
- **Date:** 2026-11-08 · **Context:** P1 `S9` aur P2 anchor re-check; user ne Telegram command + alert manzoor kiya tha.
- **Options:** MTProto / TDLib / Telethon · vendor SDK · official Bot API + `urllib.request` · arbitrary public-channel scraper.
- **Decision:** **official Bot API + stdlib `urllib.request`**, user-supplied token, P7 `telegram.py` adapter; optional OpenAI-compatible LLM bhi alag `llm_client.py` adapter se. Koi MTProto/TDLib/Telethon dependency, koi historical public-channel scrape claim nahi.
- **Reason:** zero-dependency policy; endpoint template `https://api.telegram.org/bot<token>/METHOD_NAME` P2 me directly verify hua; `getUpdates.limit` 1–100 aur 24h retention bhi P2 anchor se mile (`P2-10`). Webhook / `getUpdates` mutual-exclusivity aur `message` / `channel_post` P1 `S9` se retained.
- **Consequences:** token storage / rotation `O2/O4`, common SSRF allowlist `O10`, LLM rule-based fallback `O6`; core features offline rehte hain.

### D28 — P2 research provenance and version honesty (C22)
- **Date:** 2026-11-08 · **Context:** governing prompt har research result ke liye `source URL`, `date checked`, facts/recommendations separation aur speculation-not-fact maangta hai.
- **Options:** sirf summary · purane P1 sources par bharosa · P2 official re-check + explicit limitations.
- **Decision:** **12 P2 sources + 16 P1 sources** `architecture.md` §19 me full URL aur `date checked = 2026-11-08` ke sath; facts §20.1, assumptions §20.2, recommendations §20.3 alag. Python docs `3.13.18` vs local `3.13.14`, SQLite `3.53.1`, Expat `expat_2.8.1`; Telegram partial re-check aur transient fetch failures explicitly darj.
- **Reason:** `R2` banawati citations aur `R10` hallucination ko fact banana; purane generic `/3/` docs `3.15.2` dikhate the, unhe local runtime behavior ka saboot banana ghalat tha.
- **Consequences:** `architecture.md` §19.3 / §22, `rules.md` §17, `agent.md` addendum §M me yahi honesty rule; P7/P11 me sources dobara check honge. Koi low-authority price / market-size claim P2 facts me nahi.

---

## Classification Register

### Confirmed (C)
| # | Faisla |
|---|---|
| C1 | Core app = existing MobileLab |
| C2 | `agent.md` root, 9 docs `MobileLab\docs\` |
| C3 | Adapted, saare 12 gates; N/A + wajah |
| C4 | Static QA + stdlib `unittest` suite + regression tests |
| C5 | `agent.md` = verbatim + alag addendum |
| C6 | Scan default restrict + explicit opt-in |
| C7 | Sirf local git, koi remote/cloud/credentials |
| C8 | Skills/MCP defer = O1 |
| C9 | Hamesha Roman Urdu — ab D22/C19 se refined: content Roman Urdu, surface English |
| C10 | Sab project files / progress `J:\Ai Agent` mein |
| C11 | App local runtime; internet sirf agent / firmware / Telegram tak |
| C12 | Telegram Bot API: command + alert; purani public channel history ka dawa nahi |
| C13 | Deep/dark web sirf legal, public/authorized sources; illegal sources reject |
| C14 | Koi bhi mobile-software task → safe Roman Urdu plan + report under Sahulat & Safe Service Policy |
| C15 | Step-by-step phases; har phase mukammal, kuch incomplete na chhorhein |
| C16 | Har research fact ka URL + `date checked`; facts aur recommendations alag |
| C17 | Policy ka naam/andaaz `Sahulat & Safe Service Policy`; **boundary unchanged**, koi chhoot nahi (D19) |
| C18 | Sahulat toolkit (8th view, routes, checklist, consent, letters, case register, refusal-with-reason) scope mein (D20/D21) |
| C19 | Language split (D22): **information / report / plan / user communication = Roman Urdu**; **baqi sab = English** (headings, labels, code, identifiers, paths, API routes, commits, technical terms) — professional look ke liye |
| C20 | P2 verified stack: Python 3.13 stdlib, loopback `ThreadingHTTPServer`, SQLite WAL, vanilla JS/CSS, `unittest`, `run.bat`; koi dependency / framework / code migration nahi (D23) |
| C21 | Modular replacement via documented adapter contracts; P2 rewrite nahi karta (D24) |
| C22 | P2 research provenance: 12 P2 + 16 P1 sources, `URL + date checked`, facts/assumptions/recommendations alag, version nuance aur Telegram partial re-check explicitly darj (D28) |

### Assumptions (A — implementation se pehle / usi phase mein confirm)
- **A1** docs Roman Urdu prose + English headings/codes.
- **A2** verbatim block = `<long_text_quote>` ke andar ka poora text.
- **A3** tests production DB aur live internet kabhi touch na karein.
- **A4** `.gitignore` data/db/secrets/logs ignore karega.
- **A5** neutral repo-local git identity (D11).
- **A6** dedicated mobile nav nahi; responsive single-column fallback kaafi (P3 confirm).
- **A7** migration strategy ka faisla P6 ADR; aaj `CREATE TABLE IF NOT EXISTS` hai (D20 ne isi ko PHASE 1B me istemal kiya).
- **A11** user ka sarkari mulazim hona koi technical/legal exception paida nahi karta; sirf documentation tooling (D19).
- **A8** Telegram pehle `getUpdates` long polling; webhook tab hi jab user maange (S9).
- **A9** research sources user-editable allowlist se; arbitrary URL default `OFF`.
- **A10** task plan pehle rule-based; optional LLM rewrite sirf configured endpoint par.
- **A12** Python `3.13.18` docs local `3.13.14` ke liye relevant hain, lekin patch-level behavior barabar hone ka dawa nahi; runtime-specific checks local command / P8 tests se (D28).
- **A13** Telegram ke P1 `S9` facts abhi sahih hain; P2 ne endpoint / limit / 24h directly dobara dekhe, baqi facts ko "P1 verified, P2 re-check nahi" ke tor par rakha gaya hai.
- **A14** agle 2–5 saal me hardware-backed integrity, anti-rollback, provenance aur official-route record keeping ki ahmiyat barhegi; ye trend assumption hai, revenue ya market-share fact nahi.
- **A15** feed schemas, Bot API aur optional LLM endpoints badal sakte hain; adapter layer aur offline degradation is liye zaruri hai.

### Open questions (O — P1 ko nahi rokte; implementation se pehle band)
- **O1** skills / MCP shortlist + cost / credentials + manzoori.
- **O2** `llm_key` / Telegram token plaintext-at-rest vs Windows DPAPI / Credential Manager (P9 ADR).
- **O3** monitoring log retention (P11).
- **O4** Telegram token storage, rotation aur rate-limit/backoff policy (P7/P9).
- **O5** legal deep/dark web source allowlist kaun approve kare aur kis record ke sath (P7).
- **O6** task plan sirf rule-based ya optional LLM rewrite; model / endpoint / cost (P7).
- **O7** public channel history chahiye to Bot API se bahar ka legal/technical faisla (P7).
- **O8** firmware provenance hash policy: kaunse files, kab, aur retention (P7/P11).
- **O9** ~~naya 8th view ya existing panels (P3)~~ **RESOLVED (D21): 8th view `Sahulat / Official Route`**.
- **O10** `llm_endpoint`, research sources aur Telegram endpoint ke liye common SSRF allowlist (P9).
- **O11** case register retention / export / deletion policy (P11).
- **O12** C19/D22 ke mutabiq existing in-app Roman Urdu *chrome* (nav labels, buttons, toasts) ko English surface par kab / kis phase mein migrate karna hai; content strings (letters, reasons, hints) Roman Urdu rehte hain (P3/P11).
- **O13** agar kabhi app ko `127.0.0.1` se bahar LAN / Internet par expose karna ho to kaunsa framework, auth, TLS aur deployment model chahiye; tab P5/P10 N/A dobara khulenge (P2 se naya, `R13`).

### Risks (R)
- **R1** verbatim drift → byte-compare + 22-section count (mitigated).
- **R2** banawati citations → P1 S1–S16 + P2 P2-01…P2-12 source registers se **mitigated**; `date checked = 2026-11-08`, koi generic `/3/` version claim local behavior ke tor par nahi.
- **R3** strict security fixes legitimate feeds / scan workflow tod dein → mocked regression + `run.bat` smoke.
- **R4** doc drift → P2 ne 7 tables / 4 indexes, `cases`, `/api/sahulat/*`, `tests\test_sahulat.py` sync kiya; final audit P11.
- **R5** default restriction rozana ke bahar wale scan ko roke → C6 opt-in.
- **R6** Telegram token leak / 24h update loss / webhook conflict → O2/O4 + AC-07 tests.
- **R7** illegal deep/dark source ya malware → C13 + AC-08 policy gate.
- **R8** task planner Sahulat & Safe Service Policy se bahar step de de → C14 + AC-09 refusal tests.
- **R9** competitor claims ya pricing outdated ho jayein → `date checked` + P2/P11 re-check.
- **R10** AI hallucination ko fact mana jaye → C16 / C22 + `fact_or_recommendation` label + provenance.
- **R11** policy ke naam badalne ko "boundary hata di" samajh liya jaye → D19 canonical note har section + `test_policy_boundary_unchanged` + `PRD.md` out-of-scope list unchanged (mitigated).
- **R12** C19/D22 language split ko C9 ki mansookhi samajhna → D22 + `rules.md` §16 + `agent.md` §L; C9 zinda hai (clarified).
- **R13** `http.server` ko production / LAN par expose karna → P2 loopback boundary + P5/P10 N/A sirf isi shart par; exposure ke liye naya ADR / auth / TLS / framework (D26).
- **R14** official docs `3.13.18` vs local runtime `3.13.14` patch drift → `A12` / `D28`; runtime-specific behavior local verify, docs se patch equality ka dawa nahi.
- **R15** outbound XML / SSRF / CSP / path-authz / secret handling abhi P9 pending → `P2-03`, `P2-05`, `P2-09`, `P2-12`, QA #1–#8 regression map.
- **R16** Telegram P2 anchor re-check juzwi raha aur kuch fetches transient fail hue → P1 `S9` retained, P7 implementation se pehle dobara full re-check; koi naya unverified claim nahi.
