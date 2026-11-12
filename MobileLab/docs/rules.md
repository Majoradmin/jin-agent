# rules.md — MobileLab Coding & Operating Rules

**Date:** 2026-11-08 · **Status:** PHASE 0 baseline + PHASE 1 rules. Ye file `agent.md` ke verbatim prompt ka project-level amal hai; us prompt ki koi shaq is file se kam nahi hoti.
**Root:** sab kaam `J:\Ai Agent` mein (C10).

---

## 1. Zaban aur jagah (C9 / C10)

- Har reply, har sawal, har option, har toast, har doc prose **Roman Urdu**. Sirf code, paths, API routes, technical terms English.
- Sawal chhote, seedhe, aam lafzon mein.
- **Har** project file, doc, progress, test, log, git repo `J:\Ai Agent` ke andar. `C:\Users\...\.workbuddy-ai\` sirf WorkBuddy ka internal data hai — us par project files nahi.

## 2. Coding conventions

- Python: PEP-8-ish, `snake_case` functions/variables, type hints jahan maujood (`dict | None`), chhote modular functions.
- JavaScript: `camelCase`, `const`/`let`, `$$`/`$` helpers, `esc()` har dynamic value par.
- CSS: existing `kebab-case` class names; naye tokens `--` variables se.
- Meaningful names; comments sirf **kyun** samjhane ke liye.
- Koi giant function / giant component / hidden global state / duplicate logic nahi.
- Koi hardcoded secret, hardcoded user data, ya hardcoded absolute user path nahi.

## 3. Required / prohibited libraries

**Required:** sirf **Python standard library** — `http.server`, `sqlite3`, `urllib.request`, `xml.etree.ElementTree`, `hashlib`, `json`, `re`, `threading`, `concurrent.futures`, `os`, `time`, `unittest`, `unittest.mock`, `tempfile`.
**Prohibited:** koi bhi `pip install`; `flask`, `feedparser`, `requests`, `defusedxml`, `pytest`, koi JS framework / CDN / external font / analytics / telemetry.
**Wajah:** local, offline, zero-dependency Windows PC; pichhle turn mein `flask` aur `feedparser` ke `ModuleNotFoundError` aaye the, is liye stdlib-only faisla pakka hua.
**Naya dependency:** sirf tab jab user ko wajah batayi jaye aur explicit manzoori mile — is project mein abhi koi nahi.

## 4. Sahulat & Safe Service Policy (sab se upar)

> **Pehle madad, phir hadd.** MobileLab law ful owner / technician ki sahulat ke liye hai: firmware validation, documentation, official-route guidance, consent aur local case register.
>
> **Canonical note (D19 / C17):** purana internal naam `HARD POLICY` tha. PHASE 1B mein **sirf naam aur andaaz** badla — neeche wali **har qaida bilkul barqarar** hai. Koi role-based, "research", "test" ya "hypothetical" exception nahi. User ne khud `bypass wali line waisi hi rehti hai` wala option manzoor kiya.

- Huawei ID, Google FRP, Samsung Account / Knox Guard, MDM, carrier lock, iCloud Activation Lock ka **koi bypass automation ya step-by-step tareeqa nahi**.
- Sirf official routes + proof-of-ownership (`knowledge.py`, `PRD.md` out-of-scope).
- `frp`, `persistent`, `config`, `devinfo`, `modemst1`, `modemst2`, `nvram`, `nvdata`, `nvcfg`, `seccfg`, `proinfo`, `metadata` jaise partitions **sirf FLAG** — kabhi write / erase / flash command nahi.
- Koi aisa command nahi jo ownership / anti-theft state badle.
- Is rule se koi "research", "test" ya "hypothetical" exception nahi.

## 5. Security rules

- Loopback-only (`127.0.0.1`), single-user; auth N/A (P5 justification).
- **Input validation** API boundary par: ghalat `int`/`float` → `400` JSON, kabhi `500`/stack trace nahi (QA #2).
- **Output encoding:** `esc()` + `safe_url()` (`http`/`https` only) — `javascript:` / `data:` reject (QA #4).
- **SQL:** parameterized queries; SQL identifier explicit allowlist (`{saved,is_read}`), f-string SQL nahi (QA #8).
- **XSS / CSRF:** `nosniff`, `no-store`, CSP, `X-Frame-Options: DENY`, `Referrer-Policy`, state-changing POST par Origin check (P9).
- **SSRF:** `llm_endpoint` scheme + host validation; private / loopback / link-local / metadata ranges block (QA #6).
- **Path:** `os.path.realpath` + `os.path.commonpath` (prefix nahi), authorization `exists()` se pehle; symlink / junction / UNC / remote reject; Windows guard for `os.startfile` (QA #3).
- **Secrets:** `POST /api/settings` kabhi plaintext `llm_key` na return kare (QA #1); `.env` / keys / tokens git mein nahi; at-rest faisla O2 / P9 ADR.
- **XML:** parse se pehle `<!DOCTYPE` / `<!ENTITY` reject (QA #5).
- **Body:** 1 MiB cap → `413`.
- **Headers / info leak:** `/api/status` se absolute DB path hatao (QA #7).
- **Error handling:** koi `except Exception: return None` chup karne wala nahi; failure log karo aur rule-based fallback do (QA #12).
- Har security fix ka threat + mitigation + regression test + baqi risk darj karo.

## 6. Database rules

- SQLite WAL + `foreign_keys=ON`, `row_factory=sqlite3.Row`.
- Schema changes **migrations** se; `db.init()` aaj `CREATE TABLE IF NOT EXISTS` karta hai — migration strategy ka faisla P6 mein ADR ke taur par darj hoga (**Assumed A7**, abhi claim nahi).
- Indexes intentionally; multi-step writes aik transaction mein (QA #10: `save_package` aik connection/txn).
- FK + data-integrity constraints; `ON DELETE` behavior documented.
- Koi N+1 query nahi; `/api/packages` par `limit`/`offset` + cap (P9).
- Soft-delete sirf jab zarurat ho — abhi hard delete with confirmation.
- Internal DB structure `/api/status` jaise endpoints par expose na ho.

## 7. API rules

- Consistent JSON: `{"ok":true,...}` ya `{"error":"..."}`; appropriate HTTP codes.
- Body / query / path params sab validate; safe aur kaam ki error messages, koi stack trace nahi.
- Har endpoint documented (`architecture.md`), har protected endpoint ka authz model (yahan loopback + path allowlist).
- Idempotency (duplicate article GUID), rate-limiting ka faisla P9 ADR.
- `MAX_FILES=4000`, `MAX_DEPTH=6`; scan default workspace-restricted + explicit `allow_outside` opt-in (C6).

## 8. Testing rules

- **Sirf stdlib `unittest`** (`pytest` maujood nahi aur install nahi karna).
- `MobileLab\tests\` mein: `test_db`, `test_firmware`, `test_research`, `test_server`, `test_security`, `test_a11y`.
- `helpers.py`: `tempfile.TemporaryDirectory()`, patched `db.DB_PATH`, `unittest.mock.patch` for `urllib.request.urlopen`; **kabhi production DB ya live internet touch na kare** (A3).
- Har test: happy path · validation failure · unauthorized/not-found · empty data · loading/API failure · duplicate · boundary values · responsive smoke.
- Koi task sirf "compile ho gaya" par complete nahi.
- **Command:** `cd J:\Ai Agent\MobileLab && python -m unittest discover -s tests -v`
- Extra checks: `python -m py_compile *.py`, `node --check web/app.js`, manual `run.bat` smoke.

## 9. Error-handling / AI behavior rules

- Koi error chup kar ke na chhorho; root cause dhundho aur theek karo.
- Koi kaam "ho gaya" ka dawa baghair verification ke na karo.
- Research mein **banawati citation nahi**; har fact ke saath source URL + `date checked`, facts aur recommendations alag.
- Roman Urdu; koi missing requirement / credential / API / user data na gharho.
- Critical requirement clear hone tak implementation na karo.
- Confirmed / Assumed / Open question / Risk hamesha alag likho.

## 10. Git / change management

- **Sirf local** repo `J:\Ai Agent\.git`; koi remote / cloud / credentials nahi (C7).
- Conventional commits: `feat: / fix: / refactor: / test: / docs: / chore: / security:`.
- Commit se pehle: type + message + files + tests + risk level batao.
- Chhote logical units; history rewrite ya user work delete nahi baghair explicit ijazat.
- Destructive command (delete / reset / overwrite) kabhi bina manzoori nahi.

## 11. Performance rules

- Connection reuse / context manager; `save_package` aik transaction (QA #10).
- `_CACHE` bounded LRU + TTL; unbounded cache nahi.
- Feed `TIMEOUT=10`, pool 8–16 workers, `limit` 5–200.
- Pagination bade collections par.
- `prefers-reduced-motion` gate; premature optimization nahi.

## 12. Accessibility rules

- Har screen: loading / empty / error / success + keyboard + clear validation + responsive.
- WCAG intent: tab/tabpanel roles, `aria-current`, `aria-live="polite"`, decorative `aria-hidden`, focus-visible.
- `<a href="#">` navigation links ki jagah `<button>`.
- `lang` attribute ka faisla P9 ADR (`ur-PK-Latn` vs English-heavy UI).
- Mobile/responsive behavior important screens par test karo.

## 13. Phase / memory rules

- 12 gates; koi skip nahi; N/A items "N/A + wajah" ke saath gate pass.
- Har task: `TASK / IMPLEMENTATION / VERIFICATION / RESULT`.
- Har meaningful decision ke baad `memory.md`, `progress.md`, `decisions.md` (ADR), `changelog.md` (user-visible badlao) update.
- Naye task se pehle relevant docs parho.
- Special commands: `next / continue / status / review / research / explain / fix / stop`.

## 14. PHASE 1 research / integration rules (C11–C16)

- **Internet boundary:** app local; outbound sirf research agent, firmware/provenance aur Telegram Bot API. Arbitrary URL default `OFF`; har outbound host allowlist se guzare.
- **Provenance:** har fact ka `source_url` + `date checked`; `fact` aur `recommendation` alag labels; koi speculation ko fact na likho; low-authority price/market claims exclude karo. Source register `PRD.md` §5.3 S1–S16.
- **Telegram:** sirf official HTTPS `https://api.telegram.org/bot<token>/METHOD_NAME`; stdlib `urllib.request`; koi MTProto/TDLib/Telethon nahi. Token kabhi API response, log, toast ya doc mein plaintext na ho. `getUpdates` aur webhook dono ek sath nahi; `limit` 1–100; `offset` har response ke baad recalculate; 24h retention ka dawa na karo; `channel_post` ko historical public-channel history na samjho.
- **Deep/dark web:** sirf legal, public ya authorized sources. Policy check **fetch se pehle**. Illegal marketplace, stolen credential, leaked/proprietary firmware, bypass service, malware, private database, unauthorized access sab reject. Koi downloaded executable execute na ho. BSI definition aur warning docs/UI mein rehni chahiye.
- **Task plan/report:** koi bhi mobile-software task ka Roman Urdu safe plan/report; facts, assumptions, open questions, risks aur safe steps alag. Sahulat & Safe Service Policy classifier har output par lage; koi device write/erase, flash, bootloader/IMEI operation ya lock bypass step generate na ho. Prohibited request par refusal + official route.
- **Security:** OWASP SSRF allowlist, scheme/host validation, private/loopback/link-local/metadata block, redirects off, connection-time IP validation. Ye `llm_endpoint`, research sources aur Telegram endpoint sab par lage.
- **Competitor boundary:** paid suites ya open-source low-level tools ki device-operation capabilities copy nahi karni; MobileLab read/validate/provenance/plan par rehta hai.
- **Phase completeness:** har phase ka `PHASE REVIEW` aur `READY` gate; koi incomplete item agle phase par na chhorhein (C15).

## 15. PHASE 1B — Sahulat toolkit rules (C17 / C18)

- **Boundary immutable:** `Sahulat & Safe Service Policy` sirf presentation reframe hai. Koi bhi doc, API, test ya UI string boundary ko kamzor na kare (R11). Canonical note har policy section mein zaroori hai.
- **No bypass in generated content:** `sahulat.py` ke routes / steps / letters / `check_request()` output mein koi bypass tareeqa, exploit, loader trick, partition write/erase command ya account-removal step na ho. Regression test is par gate hai.
- **Consent gate:** letter aur case save ke liye `consent=true` + tamam required proof items zaroori. Missing par `400` JSON with specific Roman Urdu reason — kabhi `500` ya stack trace nahi.
- **Input caps:** `validate_case()` har field ko cap kare (`notes` 1000, `device_id` 40, baqi 200); unknown `proof` / `route_id` drop ya empty; `lang` allowlist `{roman, english}`; `limit` 1–500 clamp + invalid par `200`.
- **URL safety:** koi bhi rendered link `safe_url()` se guzare — `http`/`https` only; `javascript:` / `data:` reject; sab `<a>` par `rel="noopener noreferrer"`.
- **Plain-text output:** letter `<pre>` mein `textContent` se render ho, `innerHTML` se nahi — HTML injection ka raasta band.
- **DB additive only:** `cases` table `CREATE TABLE IF NOT EXISTS` se bane; purani DB ko destructive migration na chhoo; `data/` gitignored; koi full IMEI / credential / customer document upload nahi.
- **Privacy / official role:** user ka sarkari mulazim hona koi technical exception paida nahi karta. Department devices ke liye sirf documentation / authorization / asset-register tooling — koi device access automation nahi.
- **Honesty:** PHASE 1B mein koi naya web browse nahi; links pehle se verified S1–S16 / `knowledge.py` sources hain. Koi naya citation, market claim ya "policy hata di" dawa nahi.
- **Letter gate (QA fix):** `make_letter()` **sirf** `validate_letter()` use kare, `validate_case()` nahi — warna required proof items enforce na hon aur AC-15 / AC-16 tootein. Case `draft` save ho sakta hai, par us ke sath letter generate na ho (`letter_error` wapas jaye).
- **Classification window (QA fix):** `check_request()` banned patterns ko `MAX_QUERY_CHARS = 4000` ke hard-bounded window par chalaye. 500-char UI cap par truncate karne se lambi request ke aakhir mein likha banned phrase cut off ho kar classification se bach jata hai. Window bounded rehni chahiye (regex DoS na ho).
- **Har refusal ka link:** blocked response mein kam-az-kam aik `https://` official link ho. Jis route ke links khaali hon wahan `GENERIC_LINKS` fallback (sirf `ROUTES` ke andar se, koi naya URL nahi). Generic "bypass" wording par brand ka andaza na lagayein — `route_id = ""` aur brand-neutral `official_route`.
- **Targeted tests:** `tests/test_sahulat.py` stdlib `unittest`, production DB / live internet touch na kare; throwaway DB `MobileLab/data/_p1b_test.db` (gitignored) aur SQL `DELETE FROM cases` se deterministic. Full project suite **P8** ka deliverable hai — targeted suite ko poora suite keh kar jhootha green claim na banayein.

## 16. Language split (C19 / D22)

- **Roman Urdu (content):** har information, report, plan, PRD / docs prose, PHASE REVIEW, status summary, aur user se har sawal + jawab. Ye C9 ka asli maqsad hai.
- **English (professional surface):** headings, section titles, table headers, code, identifiers, file paths, API routes, commit messages, version strings, technical terms, UI labels / navigation / button text.
- **Faisla ka amal:** *content* aur *surface* alag hain. Ek hi file mein English heading + Roman Urdu prose bilkul theek hai (mojooda 9 docs isi pattern par hain).
- **Reframe nahi:** C9 khatam nahi hua, sirf refined hua. Koi bhi purani doc ko "ab English karo" ke naam par bulk rewrite na karein.
- **In-app text:** letters, refusal reasons, checklist hints, consent = **content** (Roman Urdu rehta). Nav / button / chrome labels = **surface** (English ki taraf O12 / P3/P11). Har naye string ko is table par classify kar ke likhein.
- **Tests:** language rules ka koi automated gate nahi; `PHASE REVIEW` me documentation status par read-back verify karein.

## 17. PHASE 2 — Research honesty / technology-selection rules (C20–C22)

- **Verified stack (P2):** Python 3.13 stdlib, loopback `ThreadingHTTPServer`, `sqlite3` + WAL, `urllib.request`, `xml.etree.ElementTree`, explicit `ThreadPoolExecutor`, vanilla JS/CSS, `unittest`, `run.bat`. Koi dependency, framework ya code migration P2 mein nahi (D23).
- **Provenance:** har technology fact ka `source URL` + `date checked`; `P2-01…P2-12` aur P1 `S1–S16` `architecture.md` §19 mein. Har item ko `fact` / `assumption` / `recommendation` ke label se likhein; speculation ko fact na banayein (C16 / C22 / D28).
- **Version honesty:** official docs `Python 3.13.18 documentation` hain, local runtime `Python 3.13.14`. Docs patch-level behavior ka saboot nahi; runtime-specific dawa local command ya P8 test se verify karein. Generic `/3/` pages `3.15.2` dikhate the — unhein local runtime ka hawala na banayein (A12 / R14).
- **Partial verification:** jo source fetch fail ya juzwi re-check hua (Telegram anchors), usay explicitly darj karein aur purane verified source ko "P1 verified, P2 re-check nahi" ka label dein. Koi naya unverified claim na likhein (R16).
- **Architecture truth:** `architecture.md` ko `db.py` / `server.py` / `web\*` se match rakhein — 7 tables / 4 indexes, `cases`, 6 `/api/sahulat/*` routes, 8 views, `tests\test_sahulat.py`, `VERSION 1.1.0`. Doc drift R4 hai.
- **Technology fields:** har major technology ke 5 fields (selected option, alternatives, why selected, trade-offs, replacement strategy) aur 11 governing selection criteria `architecture.md` §2.1 / §2.2 se kam na hon.
- **No scope creep:** P2 documentation-only. Security fixes P9, integrations P7, full suite P8, `run.bat` guard P4 — P2 unhe fix hone ka jhootha dawa na kare.
- **Loopback boundary:** `http.server` production ke liye recommended nahi; app sirf `127.0.0.1` par. LAN / Internet exposure ke liye naya ADR + auth + TLS + framework + user ijazat lazmi (D26 / R13).
- **Adapter contracts:** replacement `architecture.md` §21 ke documented contracts se; P2 khud rewrite nahi karta (D24).

## 18. Security regression rules (P9 / D32)

- **Boundary immutable:** code aur tests dono mein koi bypass capability nahi — na Huawei ID / Google FRP / Samsung Account / Knox Guard / MDM / carrier / iCloud Activation Lock bypass automation ya step-by-step tareeqa, na device write / erase / flash / IMEI operation. App sirf read / validate / plan / record karta hai (Sahulat & Safe Service Policy, D10 / D19 / C17).
- **Har security fix ka named regression test lazmi:** 13/13 QA findings `phases.md` §6 me closed, har aik ka passing test (`decisions.md` D32). Bina test ke koi "fix ho gaya" claim nahi.
- **Verified baseline:** four security headers (`Content-Security-Policy`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `X-Content-Type-Options: nosniff`) + `Cache-Control: no-store` · `MAX_BODY` 1 MiB → `413` · `_authorize_path` (`realpath` / `commonpath`) · `validate_llm_endpoint` + `research.validate_url` (feed host allowlist) · `firmware._xml_precheck` · `_mask_settings` (`llm_key` `***`) · `app.js` `safe_url()` http/https allowlist · article action allowlist · `server._log` local-only.
- **Threat + mitigation + regression test + baqi risk:** har naye security change par ye char likhein. At-rest encryption (O2), log retention (O3) aur case retention / export / deletion (O11) abhi **deferred** hain — inhe "resolved" likhna mana hai (D34).
- Koi stack trace / internal error client ko na jaye; secret kabhi API response, log, toast ya doc mein plaintext na ho. Koi role-based / "research" / "test" / "hypothetical" exception nahi.

## 19. Testing rules (P8 / D33)

- **Sirf stdlib `unittest`**; `pytest` ya browser E2E runner nahi. `tests/` = **8 files / 101 tests** (`_harness.py` + 7 `test_*.py`); `phases.md` §6 ke **32/32** named regression / characterization tests maujood.
- **Kabhi live internet na touch karein:** har outbound request `unittest.mock` se mocked; network down par offline graceful degradation ka test ho.
- **Kabhi production DB na touch karein:** fixed throwaway `data/_p8_test.db` (gitignored) istemal; reset **sirf SQL `DELETE FROM`** se — koi file delete / `shutil.rmtree` / `os.remove` nahi (sandbox `SAFE_DELETE_FAIL_CLOSED`). In-process loopback server `_harness.py` se.
- **Runner:** `python -W error::ResourceWarning -m unittest discover -s tests -p "test_*.py" -v` → `Ran 101 tests in 77.621s — OK`, **zero `ResourceWarning`** (`db._session()` har connection close karta hai). Koi task sirf "compile ho gaya" par complete nahi.
- **Suite ke andar gates:** `agent.md` verbatim prefix SHA-256 `1de53535942d8e7f1b31b3d9b55c9ae4854e85fd667e14e02f314a62010fd840` MATCH aur **exactly 9 docs** ka count gate (`test_docs_count_exactly_9`).
- **Central extras:** `python -m py_compile db.py server.py firmware.py research.py sahulat.py knowledge.py tests/*.py` → `PY_COMPILE_OK`; `node --check web/app.js` → `NODE_CHECK_OK`.
- **Tests aur code dono mein koi bypass capability nahi** — Sahulat & Safe Service Policy kabhi na todein, chahe "test", "research" ya "hypothetical" label ho.
---

## 20. PHASE 12 / 13 memory + service-brief rules (D35 / D36 / C26 / C27)

- **Memory boundary:** memory = `agent_memory.py` + SQLite `memory_*` tables + `data/agent_memory.md` export; koi cloud / vector DB / paid dependency (C20 / C7).
- **Source lifecycle:** user-added source delete par hard delete nahi — `status='archived'` + `priority=0` (D36); useful feedback = +1 usefulness / +1 priority (max 5 / 10), not-useful = -1 (D36).
- **Telegram boundary:** public `t.me/s/<channel>` preview (`telegram_public.py`) — host allowlist (`t.me`, `telegram.me`), 10s timeout, 2 MB cap, SSRF-guarded via `research.validate_url`; koi account / private group / userbot / MTProto / login-based scraping (C12 / C27 / D36); illegal onion / marketplace automation reject (C13).
- **Service brief boundary:** `service_brief.py` stateless; masked last-4 only; khali official worksheets; no fabricated status finding; koi IMEI / credential / GSX / carrier-login store (D35 / D19).
- **Memory safety:** memory poisoning se bachao — har fact / query / source ke saath source + timestamp; facts vs claims alag; unverified leads 14 din baad re-check; low-value sources archive, delete na.
- **Privacy:** memory me full IMEI, passwords, tokens, private messages, payment data store nahi (C9 / D22); `/api/memory/*` koi secret na return karta.

## 21. PHASE 14 — Local LLM rules (D38 / C28)

- **App-owned URLs only:** `LOCAL_LLM_ENDPOINTS` code mein fixed hain; user se kabhi loopback URL na lein. `ollama` / `lmstudio` par `llm_endpoint` setting ignore hoti hai.
- **SSRF guard immutable:** `server._check_endpoint()` aur `validate_llm_endpoint()` mein koi chhoot na dein — `127.0.0.1`, `localhost`, `::1`, `10.*`, `169.254.169.254`, `metadata.google.internal` user-supplied endpoint ke tor par hamesha `400` / `False` (`D32` regression test barqarar).
- **Keys:** local providers ko key nahi chahiye; `custom` ko public `http/https` endpoint + key + model chahiye. `llm_status()` / `llm_probe()` / `/api/llm/test` kabhi key, token ya `Authorization` header return na karein; `GET /api/settings` `***` mask kare.
- **No silent install:** app koi model runtime / binary download ya install na kare; model `OFF` hone par rule-based Roman Urdu fallback hi sahih behavior hai, koi error na dikhein.
- **Probe bounds:** `llm_probe()` aik chhota request, `timeout=8` default, reply 80 chars tak, exception type se zyada detail client ko na jaye; failure graceful `{"ok": false, "error": ...}`.
- **Policy:** Sahulat & Safe Service Policy bilkul unchanged — model sirf research khulasa rewrite karta hai, koi device / account / lock operation nahi.
