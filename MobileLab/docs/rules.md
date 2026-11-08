# rules.md — MobileLab Coding & Operating Rules

**Date:** 2026-11-08 · **Status:** PHASE 0 baseline. Ye file `agent.md` ke verbatim prompt ka project-level amal hai; us prompt ki koi shaq is file se kam nahi hoti.
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

## 4. HARD POLICY (sab se upar)

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
