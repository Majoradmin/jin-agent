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

### Assumptions (A — implementation se pehle / usi phase mein confirm)
- **A1** docs Roman Urdu prose + English headings/codes.
- **A2** verbatim block = `<long_text_quote>` ke andar ka poora text.
- **A3** tests production DB aur live internet kabhi touch na karein.
- **A4** `.gitignore` data/db/secrets/logs ignore karega.
- **A5** neutral repo-local git identity (D11).
- **A6** dedicated mobile nav nahi; responsive single-column fallback kaafi (P3 confirm).
- **A7** migration strategy ka faisla P6 ADR; aaj `CREATE TABLE IF NOT EXISTS` hai.

### Open questions (O — critical nahi)
- **O1** skills / MCP shortlist + cost / credentials + manzoori.
- **O2** `llm_key` plaintext-at-rest vs Windows DPAPI (P9 ADR).
- **O3** monitoring log retention (P11).

### Risks (R)
- **R1** verbatim drift → byte-compare + 22-section count (mitigated).
- **R2** banawati citations → P2 mein asli browsing + URL + `date checked`; P0 mein koi citation nahi.
- **R3** strict security fixes legitimate feeds / scan workflow tod dein → mocked regression + `run.bat` smoke.
- **R4** doc drift → P11 doc-vs-code audit.
- **R5** default restriction rozana ke bahar wale scan ko roke → C6 opt-in.
