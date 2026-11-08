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

### D10 — HARD POLICY
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
- **Reason:** BSI: dark net browsing apne aap mein illegal nahi, lekin illegal content/download/goods/services illegal hain aur malware risk zyada hai; HARD POLICY bhi yahi maangta hai.
- **Consequences:** koi default Tor automation nahi; koi downloaded executable nahi; har approved source ka provenance; O5 allowlist approval pending.

### D16 — Any mobile task → safe plan/report (C14)
- **Date:** 2026-11-08 · **Context:** pehle user ne "koi bhi task" kaha, clarification me pehle `Sirf research` choose kiya, dobara poochhne par `Plan + report bhi` pakka kiya.
- **Options:** full automation / sirf research / safe plan + report with policy gate.
- **Decision:** agent koi bhi mobile-software task samjhe, research kare aur Roman Urdu mein **safe plan + report** de; device write/erase, flashing, bootloader/IMEI operations ya lock bypass steps kabhi na de.
- **Reason:** user ka aakhri confirmed jawab + HARD POLICY.
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
| C9 | Hamesha Roman Urdu |
| C10 | Sab project files / progress `J:\Ai Agent` mein |
| C11 | App local runtime; internet sirf agent / firmware / Telegram tak |
| C12 | Telegram Bot API: command + alert; purani public channel history ka dawa nahi |
| C13 | Deep/dark web sirf legal, public/authorized sources; illegal sources reject |
| C14 | Koi bhi mobile-software task → safe Roman Urdu plan + report under HARD POLICY |
| C15 | Step-by-step phases; har phase mukammal, kuch incomplete na chhorhein |
| C16 | Har research fact ka URL + `date checked`; facts aur recommendations alag |

### Assumptions (A — implementation se pehle / usi phase mein confirm)
- **A1** docs Roman Urdu prose + English headings/codes.
- **A2** verbatim block = `<long_text_quote>` ke andar ka poora text.
- **A3** tests production DB aur live internet kabhi touch na karein.
- **A4** `.gitignore` data/db/secrets/logs ignore karega.
- **A5** neutral repo-local git identity (D11).
- **A6** dedicated mobile nav nahi; responsive single-column fallback kaafi (P3 confirm).
- **A7** migration strategy ka faisla P6 ADR; aaj `CREATE TABLE IF NOT EXISTS` hai.
- **A8** Telegram pehle `getUpdates` long polling; webhook tab hi jab user maange (S9).
- **A9** research sources user-editable allowlist se; arbitrary URL default `OFF`.
- **A10** task plan pehle rule-based; optional LLM rewrite sirf configured endpoint par.

### Open questions (O — P1 ko nahi rokte; implementation se pehle band)
- **O1** skills / MCP shortlist + cost / credentials + manzoori.
- **O2** `llm_key` / Telegram token plaintext-at-rest vs Windows DPAPI / Credential Manager (P9 ADR).
- **O3** monitoring log retention (P11).
- **O4** Telegram token storage, rotation aur rate-limit/backoff policy (P7/P9).
- **O5** legal deep/dark web source allowlist kaun approve kare aur kis record ke sath (P7).
- **O6** task plan sirf rule-based ya optional LLM rewrite; model / endpoint / cost (P7).
- **O7** public channel history chahiye to Bot API se bahar ka legal/technical faisla (P7).
- **O8** firmware provenance hash policy: kaunse files, kab, aur retention (P7/P11).
- **O9** J8–J11 ke liye naya 8th view ya existing 7 views mein panels (P3).
- **O10** `llm_endpoint`, research sources aur Telegram endpoint ke liye common SSRF allowlist (P9).

### Risks (R)
- **R1** verbatim drift → byte-compare + 22-section count (mitigated).
- **R2** banawati citations → P1 S1–S16 source register se mitigated; P2 final technology citations due.
- **R3** strict security fixes legitimate feeds / scan workflow tod dein → mocked regression + `run.bat` smoke.
- **R4** doc drift → P11 doc-vs-code audit.
- **R5** default restriction rozana ke bahar wale scan ko roke → C6 opt-in.
- **R6** Telegram token leak / 24h update loss / webhook conflict → O2/O4 + AC-07 tests.
- **R7** illegal deep/dark source ya malware → C13 + AC-08 policy gate.
- **R8** task planner HARD POLICY se bahar step de de → C14 + AC-09 refusal tests.
- **R9** competitor claims ya pricing outdated ho jayein → `date checked` + P2/P11 re-check.
- **R10** AI hallucination ko fact mana jaye → C16 + `fact_or_recommendation` label + provenance.
