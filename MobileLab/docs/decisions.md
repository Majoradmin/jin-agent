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

### D29 — Blanket auto-continue approval for P3–P11 with subagent delegation (C23)
- **Date:** 2026-11-08 · **Context:** user ne kaha *"phase 3 kro or agy jtny phases hain unky leeay agent lga do taky km poora ho"*. `phases.md` §3 ka rule hai: `READY` par user ki manzoori maango **"jab tak 'automatically continue' na kaha ho"**.
- **Options:** har gate par ruk kar naya sawal poochna · sirf P3 kar ke rukna · P3–P11 ko aik hi approved run me subagents se poora karna.
- **Decision:** **teesra raasta**. P3–P11 sab pre-approved hain; per-phase rukne wali manzoori is run ke liye muattal hai. Har phase ka `TASK / IMPLEMENTATION / VERIFICATION / RESULT` aur `PHASE REVIEW` **phir bhi zaroori** hai. Kaam non-overlapping file ownership ke sath subagents ko delegate hoga; verification, doc sync, `PHASE REVIEW` aur commits centrally honge.
- **Reason:** user ne khud "agy jtny phases ... km poora ho" kaha; C15 (kuch incomplete na chhorhein) aur `phases.md` §3 ka documented exception dono isi taraf ishara karte hain. Agents se parallel kaam tez hota hai, par central verification se R4 doc drift aur R3 workflow-tootna control mein rehte hain.
- **Consequences:** `agent.md` addendum §N · `phases.md` §12–§20 reviews · koi phase skip nahi · P5/P10 N/A + wajah likhi jayegi · Sahulat & Safe Service Policy bilkul unchanged · subagents ko koi bypass / device-write / dependency-install ijazat nahi · aakhri `PHASE REVIEW` ke baad hi final `READY` darj hoga. Ye ijazat **is run tak seemit** hai; agle naye kaam par phir se poocha jayega.

### D30 — P5 Auth / Authorization = N/A (justified, not skipped)
- **Date:** 2026-11-09 · **Context:** P5 gate par multi-user auth, sessions, password / token aur tenant isolation ka faisla karna tha; P2 (D26 / R13 / O13) ne loopback boundary pakki ki thi.
- **Options:** (a) `http.server` par auth / session layer add karna · (b) `N/A + wajah` likh kar gate pass karna · (c) phase skip kar dena.
- **Decision:** **(b)** — `N/A + wajah`, **skip nahi**. App sirf `127.0.0.1` par, aik hi local user, koi remote access, koi doosra tenant, koi session model, koi account / password / token nahi. `ThreadingHTTPServer` + custom handler par auth lagana be-matlab attack surface aur naya dependency / framework laata.
- **Reason:** `http.server` official docs production / LAN ke liye recommended nahi (D26, R13); is liye P5 ka N/A **sirf loopback shart par** qabool hai. Single-user offline model me authenticate karne wala koi doosra principal hi nahi.
- **Consequences:** koi auth code, cookie, session store ya CSRF-token flow nahi. Agar **kabhi** app ko `127.0.0.1` se bahar LAN / Internet par expose karna ho to **naya ADR + auth + TLS + framework review lazmi** (O13, R13); tab P5 aur P10 dono N/A dobara khulenge. `llm_key` masking (`_mask_settings`) authentication nahi, P9 ka secret-handling fix hai. Sahulat & Safe Service Policy unchanged.

### D31 — P10 Deploy / CI-CD = N/A (justified, not skipped)
- **Date:** 2026-11-09 · **Context:** P10 gate par cloud deploy, hosted CI/CD, containers aur remote git ka faisla karna tha.
- **Options:** (a) hosted pipeline / container / remote add karna · (b) `N/A + wajah` likh kar gate pass karna · (c) phase skip kar dena.
- **Decision:** **(b)** — `N/A + wajah`, **skip nahi**. Distribution sirf `run.bat` + `python server.py` aik Windows PC par; zero installs, zero cloud, zero CI secrets, aur C7 ke mutabiq `git remote -v` empty hai.
- **Reason:** local-only target (C7 / C11); reproducibility stdlib-only stack + `run.bat` Python `>=3.10` guard + local git history se milti hai, koi build server ya registry zaroori nahi.
- **Consequences:** koi pipeline YAML, koi container image, koi deploy key, koi off-site artifact. `git diff --check` clean aur `core.autocrlf=false` local hygiene gate hain. Agar **kabhi** online distribution / hosted CI chahiye to **pehle naya ADR** (framework / TLS / auth / secret store / supply-chain), us ke baad hi code. Sahulat & Safe Service Policy unchanged.

### D32 — P9 security / perf / a11y baseline closure
- **Date:** 2026-11-09 · **Context:** P9 par `phases.md` §6 ke 13 QA findings band karne the; P2 ne unhe "P9 pending" likha tha (R15).
- **Options:** sirf doc claim · fixes + regression tests · fixes baghair tests.
- **Decision:** **fixes + passing regression tests**. Neeche har finding ka asli code symbol aur test naam darj hai; sirf verified symbols likhe gaye hain.
- **Reason:** R3 / R15 ka khatra tha ke hardening workflow tod de ya jhootha "sab fix" claim likha jaye; is liye har fix ka named test gate hai.
- **Consequences:** 13/13 closed; `python -W error::ResourceWarning -m unittest discover -s tests -p "test_*.py" -v` → `Ran 101 tests in 77.621s — OK`. **Koi bypass capability add nahi hui** — app sirf read / validate / plan / record karta hai; Sahulat & Safe Service Policy bilkul unchanged.

| QA # | Finding | Actual code fix | Regression test |
|---|---|---|---|
| 1 | `llm_key` plaintext leak | `server.py` `_mask_settings` | `test_settings_no_secret_leak` |
| 2 | invalid query params → `500` | `server.py` `_parse_num` | `test_invalid_query_params_return_400`, `test_no_stacktrace_on_bad_input` |
| 3 | `/api/reveal` prefix bypass + C6 | `server.py` `_authorize_path` (`realpath` / `commonpath`), `firmware.py` `MAX_FILES=4000` / `MAX_DEPTH=6` | `test_reveal_rejects_sibling_prefix`, `test_scan_outside_denied_by_default`, `test_scan_outside_allowed_with_flag`, `test_scan_rejects_symlink_escape`, `test_scan_rejects_unc_path` |
| 4 | unsafe feed URL | `web/app.js` `safe_url()` http/https allowlist + `research.py` `validate_url` | `test_javascript_url_rejected` |
| 5 | XML DTD / entity | `firmware.py` `_xml_precheck` | `test_dtd_entity_rejected` |
| 6 | `llm_endpoint` SSRF | `server.py` `validate_llm_endpoint` + `research.py` `validate_url` (feed host allowlist) | `test_llm_endpoint_rejects_internal` |
| 7 | headers / body cap / path leak | `server.py` four security headers (`Content-Security-Policy`, `X-Frame-Options`, `Referrer-Policy`, `X-Content-Type-Options`) + `MAX_BODY` 1 MiB + `_mask_settings` | `test_security_headers_present`, `test_body_size_cap_413`, `test_status_no_abs_db_path` |
| 8 | f-string SQL identifier | `server.py` article action allowlist | `test_article_action_allowlist` |
| 9 | a11y markup | static UI: 8 `role="tabpanel"`, `aria-live`, `:focus-visible`, `prefers-reduced-motion`, `lang="en"`, zero inline `<script>` | `test_a11y_markup` |
| 10 | perf | `db._session()` (har connection close), `server.py` pagination + `_prune_research_cache` | `test_save_package_single_txn`, `test_cache_bounded`, `test_packages_paginated` |
| 11 | minor bugs / version guard | `run.bat` Python `>=3.10` guard | characterization tests (suite ke andar) |
| 12 | swallowed LLM errors | `research.py` LLM error logging + `server.py` `_log` (rule-based fallback) | `test_llm_failure_logged_not_swallowed` |
| 13 | zero automated tests | `tests/` 8 files / 101 tests | poora suite (`Ran 101 tests … OK`) |

### D33 — P8 test strategy
- **Date:** 2026-11-09 · **Context:** P8 par poora project `unittest` suite chahiye tha; PHASE 1B me sirf 47 targeted tests the.
- **Options:** `pytest` / browser E2E runner · stdlib `unittest` + in-process harness · sirf manual smoke.
- **Decision:** **stdlib `unittest`** — `tests/` me **8 files** (`_harness.py`, `test_sahulat.py`, `test_security.py`, `test_firmware.py`, `test_db.py`, `test_research.py`, `test_server_api.py`, `test_static_governance.py`), **101 test methods**, aur `phases.md` §6 ke **32/32** named regression / characterization tests sab maujood.
- **Reason:** `pytest` PATH par nahi aur stdlib-only policy hai; `_harness.py` fixed throwaway `data/_p8_test.db` + in-process loopback server deta hai, reset sirf SQL `DELETE FROM` se (koi file delete / `shutil.rmtree` nahi). **Sab outbound network mocked**, production DB aur live internet kabhi touch nahi.
- **Consequences:** runner `python -W error::ResourceWarning -m unittest discover -s tests -p "test_*.py" -v` → `Ran 101 tests in 77.621s — OK`, **zero `ResourceWarning`** (`db._session()` leak fix). Verbatim-hash gate aur 9-doc count gate suite ke andar hain. `PY_COMPILE_OK` + `NODE_CHECK_OK` alag central checks hain.

### D34 — P11 monitoring / local logging / retention
- **Date:** 2026-11-09 · **Context:** P11 par monitoring, log retention aur O3 / O10 / O11 / O12 ka faisla karna tha.
- **Options:** cloud monitoring / metrics service · local-only logging + explicit deferrals · kuch na likhna.
- **Decision:** **local-only logging + honest deferrals**. `server.py` `_log` sirf local, loopback ke andar events likhta hai — koi telemetry, koi off-site export, koi cloud sink.
- **Reason:** C7 / C11 local-only; is liye monitoring bhi local rehti hai. Jo policy abhi configure nahi hui usay "ho gaya" kehna jhooth hota.
- **Consequences / open-question status:**
  - **~~O10~~ RESOLVED (D34 / D32):** common SSRF allowlist `research.validate_url` + `server.validate_llm_endpoint` + `app.js` `safe_url()` http/https allowlist se; QA #6 regression green.
  - **~~O12~~ RESOLVED (D34):** English UI chrome migration done (static UI `lang="en"`, 8 nav items, 8 `role="tabpanel"`, `aria-live`, `:focus-visible`, `prefers-reduced-motion`, 27 `sah*` IDs, zero inline `<script>`); **Roman Urdu content retained** (letters, refusal reasons, checklist hints, consent, research `khulasa`, help text) — C19 / D22 barqarar.
  - **O3 (log retention) — DEFERRED:** `_log` local likhta hai, lekin kitne din / kitna MB retain karna hai koi policy configure nahi; naye kaam par user ki manzoori chahiye (N7).
  - **O11 (case retention / export / deletion) — DEFERRED:** `cases` table additive aur local hai; export / deletion / retention policy abhi implement nahi, naye ADR + manzoori ke liye deferred.
  - **O2 (`llm_key` / bot token at-rest) — DEFERRED:** `_mask_settings` API response / log masking karta hai, lekin at-rest encryption (DPAPI / Credential Manager) ka faisla baqi hai.
  - **O4 (Telegram token storage / rotation / rate-limit) — DEFERRED:** Bot API adapter planned boundary hai; token lifecycle policy abhi code me nahi.
  - **O5 (legal deep/dark allowlist approval) — DEFERRED:** koi approved allowlist / approver record nahi; illegal sources reject policy barqarar.
  - **O6 (task plan rule-based vs LLM) — DEFERRED:** aaj rule-based planner hai; optional LLM model / endpoint / cost ka faisla baqi.
  - **O7 (public channel history) — DEFERRED:** Bot API se bahar ka legal/technical faisla baqi; koi history scrape claim nahi.
  - **O8 (firmware provenance hash policy) — DEFERRED:** kaunse files / kab / retention ka policy baqi.
  - **O1 (skills / MCP) — DEFERRED:** shortlist + cost / credentials + manzoori alag task (D7, C8).
  - **O13 (loopback se bahar exposure) — DEFERRED:** agar kabhi LAN / Internet par jana ho to naya ADR + auth + TLS + framework review lazmi (D30 / D31 / R13).
  - Sahulat & Safe Service Policy bilkul unchanged; **inmein se koi resolution invent nahi kiya gaya**.

---

### D35 — P12 single-run approval + Service Brief / official status surface
- **Date:** 2026-11-09 · **Context:** user ne PHASE 12 (Service Brief & Official Status Checks) ke liye "Aik hi run me poora karo (Recommended)" single-run ijazat di; N7 phase-by-phase pause sirf is feature ke liye muattal karna tha, boundary par koi asar nahi.
- **Options:** alag alag phases mein todna · aik hi approved run mein deliver karna · feature defer karna.
- **Decision:** **aik hi approved run** mein P12 deliver hua — `service_brief.py`, 5 `/api/service-brief/*` routes, Sahulat view card, 8 official sources, masked last-4 only, stateless. Approval **sirf is feature** ke liye thi; agle naye kaam par N7 wapas lagu.
- **Reason:** C15 (har phase mukammal) aur C23 / D29 ke consume hone ke baad bhi user ne is specific feature ke liye explicit single-run ijazat di; boundary (D19) ko chhedna nahi tha.
- **Consequences:** C26 register hua; P12 `phases.md` §21 mein `READY`; P5 / P10 N/A gates barqarar (D30 / D31); koi bypass capability add nahi hui.

### D36 — P13 Agent Memory design (SQLite source of truth + public Telegram only)
- **Date:** 2026-11-09 · **Context:** user ne memory feature maanga — har search, site, Telegram channel, problem, report aur feedback yaad rahe; memory kabhi delete na ho; user ko visible ho.
- **Options:** in-memory only (session mein kho jaye) · cloud vector DB (C7 / P3 ke khilaf) · **SQLite `memory_*` tables + human-readable `data/agent_memory.md` export**.
- **Decision:** **SQLite machine memory + Markdown export**. Source delete = `status='archived'`, priority 0 (hard delete nahi). Feedback useful/not-useful source usefulness/priority ±1 karta hai. Telegram sirf public `t.me/s/<channel>` preview — koi account, private group, userbot, MTProto ya login-based scraping nahi. Illegal onion / marketplace automation nahi (C13).
- **Reason:** local-only (C7 / P11), stdlib-only (C20), inspectable (user file khol kar parh sakta hai), history-preserving (archive not delete), aur privacy-safe (no secrets / private messages).
- **Consequences:** 7 additive `memory_*` tables (`db.py`), `agent_memory.py`, `telegram_public.py`, 13 memory API routes, 9th UI view `Agent Memory`, `VERSION 1.3.0`, `tests/test_memory.py` (17 tests). P12 ki tarah boundary unchanged; R18 / R19 register hue.

### D37 — LF-only docs + single atomic local commit for P12 / P13
- **Date:** 2026-11-12 · **Context:** P12 / P13 code + docs uncommitted the; `git diff --check` har doc line par "trailing whitespace" de raha tha.
- **Options:** `core.whitespace=cr-at-eol` set karna · `.gitattributes` add karna · **docs ko LF par wapas lana** · CRLF ko accept karna.
- **Decision:** 9 `MobileLab\docs\*.md` ko LF-only kiya (content same, sirf `\r\n` → `\n`), `agent.md` bilkul untouched, aur P12 / P13 ko aik atomic local commit mein dala (code + tests + docs + addendum ek saath taake beech ka commit doc-vs-code tests na toray).
- **Reason:** repo pehle se LF (`core.autocrlf=false`), aur config-level workaround asli drift chhupa deta. `agent.md` verbatim hash guard CRLF se break ho sakta tha, is liye usay chhua hi nahi gaya.
- **Consequences:** `git diff --check` clean; `agent.md` prefix SHA-256 `1de53535…0840` MATCH; koi remote, koi runtime / DB / dependency change nahi.

### D38 — Local LLM support without weakening the SSRF guard

- **Date:** 2026-11-12 · **Context:** user ne *"ye sbb ok krdo or app ki har category check kro work krti ha ya ni.?"* kaha. Category audit me mila ke local model na chalne ki asli wajah QA #6 `validate_llm_endpoint()` tha: user-supplied loopback endpoint `400` se reject hota tha aur `resolve` gate local providers par bhi `llm_key` mangta tha. Is liye Ollama / LM Studio kabhi enable hi na ho sakte the.
- **Options:** (1) SSRF guard mein loopback exception dena · (2) **app-owned local provider presets** + key-free local mode · (3) LLM feature hata dena · (4) user ko guard disable karne dena.
- **Decision:** option (2). `llm_provider` = `off` / `ollama` / `lmstudio` / `custom`; local URLs sirf `research.LOCAL_LLM_ENDPOINTS` code constant se; local par koi API key nahi; custom par purana guard + `_public_endpoint_ok()` barqarar. Diagnostics `/api/status.llm`, `/api/llm/status`, `/api/llm/test`.
- **Reason:** (1) aur (4) internal / metadata endpoints ka darwaza kholte — `D32` / QA #6 ki security regression toot jati; (3) user ki request ke khilaf tha. Presets se user ko kabhi URL type karne ki zarurat hi nahi, to guard ko chhoot dene ki zarurat hi nahi.
- **Consequences:** `VERSION 1.4.0`; additive `llm_provider` setting (koi naya table / migration nahi); 17+1 naye tests; `test_service_brief.py` ka hardcoded `1.3.0` assertion `server.VERSION` se compare karta hai; 9 docs + `agent.md` §Q sync; C28 register hua. Koi runtime / binary install nahi — model abhi `OFF` by design, rule-based Roman Urdu fallback chal raha hai.

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
| C23 | P3–P11 aik hi approved run me, subagent delegation ke sath; per-phase approval pause is run ke liye muattal, har `PHASE REVIEW` aur central verification barqarar (D29) |
| C24 | 13 QA findings `phases.md` §6 sab closed, har aik ka passing regression test (D32 / D33); koi bypass capability add nahi |
| C25 | P5 / P10 `N/A` justified, gates **passed not skipped** (D30 / D31); C23/D29 auto-continue is run me consume hua, N7 se naye kaam par phase-by-phase approval wapas |
| C26 | PHASE 12 ke liye user ne alag se single-run ijazat di — `Aik hi run me poora karo (Recommended)`; ye **sirf is feature** ke liye N7 ko muattal karti hai, Sahulat & Safe Service Policy par koi asar nahi, koi chhoot nahi |
| C27 | PHASE 13 (Agent Memory) ne SQLite `memory_*` source of truth + public `t.me/s/` preview + archive-not-delete + local-only design confirm ki (D36) |
| C28 | PHASE 14 confirm karta hai ke local LLM sirf **app-owned loopback presets** (Ollama / LM Studio) se, key-free aur diagnostics ke sath enable hoga; user-supplied SSRF guard bilkul unchanged rahega, koi runtime silently install nahi hoga (D38) |

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
- **~~O10~~** **RESOLVED (D34 / D32): common SSRF allowlist** — `research.validate_url` + `server.validate_llm_endpoint` + `app.js` `safe_url()` http/https allowlist; QA #6 `test_llm_endpoint_rejects_internal` green.
- **O11** case register retention / export / deletion policy (P11) — deferred (D34).
- **~~O12~~** **RESOLVED (D34): English UI chrome migration done, Roman Urdu content retained** — static UI `lang="en"`, 8 nav items, 8 `role="tabpanel"`, `aria-live` / `:focus-visible`; letters / reasons / hints / consent Roman Urdu rehte hain (C19 / D22).
- **O13** agar kabhi app ko `127.0.0.1` se bahar LAN / Internet par expose karna ho to kaunsa framework, auth, TLS aur deployment model chahiye; tab P5/P10 N/A dobara khulenge (P2 se naya, `R13`).

### Risks (R)
- **R1** verbatim drift → byte-compare + 22-section count (mitigated).
- **R2** banawati citations → P1 S1–S16 + P2 P2-01…P2-12 source registers se **mitigated**; `date checked = 2026-11-08`, koi generic `/3/` version claim local behavior ke tor par nahi.
- **R3** strict security fixes legitimate feeds / scan workflow tod dein → **mitigated with regression tests** (mocked offline suite, 101 tests) + `run.bat` smoke; koi workflow regression nahi.
- **R4** doc drift → P2 ne 7 tables / 4 indexes, `cases`, `/api/sahulat/*`, `tests\test_sahulat.py` sync kiya; **final doc-vs-code audit completed P11** (D32 / D33 / D34; `tests/` 8 files, 101 tests, 9 docs).
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
- **R15** outbound XML / SSRF / CSP / path-authz / secret handling P9 pending tha → **mitigated with regression tests** (P9 delivered: `_xml_precheck`, `validate_url` / `validate_llm_endpoint`, four security headers + CSP, `_authorize_path`, `_mask_settings`; QA #1–#13 closed, D32) · `P2-03`, `P2-05`, `P2-09`, `P2-12`, QA #1–#8 regression map ab green.
- **R16** Telegram P2 anchor re-check juzwi raha aur kuch fetches transient fail hue → P1 `S9` retained, P7 implementation se pehle dobara full re-check; koi naya unverified claim nahi.
