# design.md — MobileLab UI/UX

**Date:** 2026-11-08 · **Updated:** 2026-11-12 · **Status:** PHASE 3 final — **READY** (gate review `phases.md` §12); P12 / P13 / P14 final sync · **Document version:** 2.3.0
**Root:** `J:\Ai Agent` · **App:** `J:\Ai Agent\MobileLab` · **App `VERSION`:** `1.4.0` (P14 ne code badla)
**Sources read (2026-11-08):** `web/style.css`, `web/index.html`, `web/app.js` · `docs/phases.md` (P3 row, §2 N/A table, §6 QA map) · `docs/architecture.md` 2.0.0 · `docs/rules.md` §12 / §16 · `docs/PRD.md` §12 · `agent.md` addendum §N.
**Language (C19 / D22):** information / report / plan / prose = **Roman Urdu**; headings, section titles, table headers, labels, code, CSS tokens, identifiers, paths, IDs aur technical terms = **English** (professional surface). Koi purani content ko English mein bulk rewrite nahi kiya gaya.


## 1. UI/UX principles

- **Light theme**, saaf contrast, technician ke liye compact density. `:root` mein aik hi light palette hai (`§3`); koi dark branch nahi (`§9` N/A).
- **C19 / D22 split:** user-facing *content* Roman Urdu, *surface* (nav, buttons, labels, headings, table headers) English. Tafseel `§10`.
- Har important screen par **loading / empty / error / success** state (`§7`), keyboard accessibility aur WCAG intent (`§8`).
- **Local-first:** koi external font / CDN / analytics / bundler nahi; `font-family` local system stack hai (`§4`).
- Koi placeholder UI ko final implementation na mana jaye; har dynamic string `esc()` se guzare, har rendered link `safe_url()` (`http`/`https` only) se (`web\app.js:6–20`).
- Status kabhi sirf rang se na bataya jaye — har badge / issue ka text label ho (`.tag`, `.issue`, `.score`, `.do-list`, `.diag`).

## 2. Views (9) — exact nav labels

**[VERIFIED NOW]** `index.html` ke `<button class="nav-item" data-view="…">` elements, sidebar order mein:

| # | Nav label (exact) | `data-view` | Section id |
|---|---|---|---|
| 1 | `Dashboard` | `dashboard` | `view-dashboard` |
| 2 | `Firmware Packages` | `packages` | `view-packages` |
| 3 | `Research Agent` | `research` | `view-research` |
| 4 | `Model Brief` | `models` | `view-models` |
| 5 | `Job Register` | `jobs` | `view-jobs` |
| 6 | `Sahulat / Official Route` | `sahulat` | `view-sahulat` |
| 7 | `Agent Memory` | `memory` | `view-memory` |
| 8 | `Knowledge / Help` | `knowledge` | `view-knowledge` |
| 9 | `Settings` | `settings` | `view-settings` |

8th view `Sahulat / Official Route` PHASE 1B mein add hua (`D21`, `O9` resolved) aur `Job Register` ke baad; 9th view `Agent Memory` PHASE 13 mein add hua (`D36`). Markup counts: `class="view"` × 9, `id="view-"` × 9, `data-view="` × 9; `tests/test_static_governance.py` aur `tests/test_sahulat.py` me 9-view assertion green. Navigation hash routing (`location.hash` + `hashchange`) aur `nav(view)` se chalti hai (`web/app.js:61-74`): `.nav-item.active` toggle, `.view.active` toggle, `TITLES` map se `#viewTitle` / `#viewSub` update. `TITLES` (`app.js:22-31`) bhi inhi 9 keys par hai.

## 3. Design token audit — light theme (VERIFIED NOW)

`web\style.css:1–11` mein **aik hi `:root` block** hai, **20 custom properties**. Neeche har variable → asli value → asli istemal (selector / property) darj hai; koi hex value invent nahi ki gayi. Ye read-back purane `design.md` §2 ki values se bhi match karti hai.

| Variable | Value (as in `style.css`) | Where used (selectors / properties) |
|---|---|---|
| `--bg` | `#f4f6fb` | `body` `background` (`:14`) |
| `--surface` | `#ffffff` | `background` of `.sidebar`, `.topbar`, `.card`, `.stat`, `input,select,textarea`, `.btn`, `.check-grid label`, `.res-card`, `.route .rl a`, `.acc`, `.sr-body .rl a` |
| `--surface2` | `#fafbfe` | `background` of `.nav-item:hover`, `.focus-item`, `.btn.ghost`, `.chip`, `.sources-box`, `.issue`, `.pkg-item`, `.file-table tr:hover td`, `.diag span`, `.route`, `.sah-route`, `.sah-check`, `.sah-consent` / `.sah-letter` |
| `--border` | `#e3e8f0` | default `1px solid` hairline across ~30 selectors: `.sidebar`, `.brand`, `.side-foot`, `.side-note`, `.topbar`, `.card`, `.stat`, `input,select,textarea`, `.btn`, `.chip`, `.sources-box`, `.check-grid label`, `.issue`, `.check-table`, `.file-table`, `.pkg-item`, `.diag span`, `.res-card`, `.rc-foot`, `.mini-news .mn`, `.route`, `.job-table`, `.acc`, `.gloss`, `.sah-route`, `.sah-check`, `.sah-consent` / `.sah-letter` |
| `--text` | `#1c2536` | `body` `color`; `.nav-item:hover`, `.checkline`, `.sr-docs b`, `.sah-h3`, `.sah-consent` / `.sah-letter` `color` |
| `--muted` | `#6b7690` | secondary text: `.brand-sub`, `.nav-item`, `.side-foot`, `.topbar p`, `.clock`, `.muted`, `.stat .l`, `.focus-item .fd`, `label`, `.chip`, `.sources-box summary`, `.issue .id`, `.pkg-item .pm`, `.empty-state`, `.file-table th`, `.diag span`, `.rc-excerpt`, `.rc-foot .src`, `.mini-news .mk`, `.kv .k`, `.route ol`, `.job-table th`, `.sah-out .sr-steps`, `.sr-docs`, `.sr-steps`, `.sah-check em` |
| `--faint` | `#98a2b8` | `.side-small` `color` **only** (`:45`) — single-use, sab se kam istemal hone wala token |
| `--primary` | `#3b5bdb` | `a` `color`; `.notice-icon` bg; `.checkline input` / `.sah-check input` `accent-color`; `.btn.primary` bg + border; `.link-btn` `color`; `.chip:hover` / `.chip.active`; `input:focus` `border-color`; `.pkg-item:hover` / `.pkg-item.active` `border-color` |
| `--primary-dark` | `#2f4bc0` | `.nav-item.active` `color`; `.tag` `color`; `.stat .n`; `.btn.primary:hover` bg; `.kind` `color`; `.gloss td:first-child`; `.sah-route summary strong` |
| `--primary-soft` | `#eef2ff` | `background` of `.brand-mark`, `.nav-item.active`, `.tag`, `.notice`, `.pkg-item.active`, `.kind`, `.rc-khulasa`; `input:focus` `box-shadow` ring (`0 0 0 3px var(--primary-soft)`) |
| `--green` | `#0f9d6e` | `.nav-dot`, `.dot-live`, `.notice.soft .notice-icon`, `.health-bar span` bg; `.side-status`, `.pill`, `.tag.green`, `.check-table .good`, `.score`, `.do-list li:before` (✓) `color` |
| `--green-soft` | `#e8f8f1` | `.dot-live` ring `box-shadow`; `background` of `.pill`, `.tag.green`, `.notice.soft`, `.score` |
| `--amber` | `#d9860b` | `.tag.amber` `color`; `.issue.warn` `border-color`; `.kind.warn` `color` |
| `--amber-soft` | `#fff5e3` | `background` of `.tag.amber`, `.issue.warn`, `.kind.warn` |
| `--red` | `#d64545` | `.tag.red` `color`; `.issue.error` `border-color`; `.check-table .bad`, `.diag span.bad`, `.do-list.no li:before` (✕) `color`; `.toast.bad` bg |
| `--red-soft` | `#fdeceb` | `background` of `.tag.red`, `.issue.error`, `.diag span.bad` |
| `--blue` | `#2f80c4` | `.issue.info` `border-color`; `.kind.qcom` `color`; `.route .rn` / `.sr-body .rn` `color` |
| `--blue-soft` | `#e9f3fc` | `background` of `.issue.info`, `.kind.qcom` |
| `--shadow` | `0 1px 2px rgba(20,32,64,.05),0 6px 20px rgba(20,32,64,.05)` | `box-shadow` of `.card`, `.stat`, `.res-card` |
| `--radius` | `12px` | `border-radius` of `.card`, `.notice`, `.stat`, `.res-card` |

### 3.1 Mismatch / unused token notes (honest audit)

- **Koi token unused nahi:** 20/20 `:root` properties `style.css` mein kam-az-kam aik dafa `var(…)` se reference hoti hain (read-back + targeted grep se verify). `--faint` sirf aik jagah (`.side-small`) istemal hota hai — "near-unused", lekin strictly unused nahi. Is liye koi token delete karne ki recommendation nahi.
- **Hardcoded-color drift (asli mismatch):** token system ke bawajood ~16 literal hex values aur aik `rgba()` seedha CSS mein likhe gaye hain, jin ka koi `--*` token nahi: `#d9e2ff` (`.notice` border), `#cdeada` (`.notice.soft` border), `#fff` (`.notice-icon`, `.btn.primary`, `.chip.active` text), `#42507a` / `#3c5a4c` (`.notice p` / `.notice.soft p`), `#c7d0e4` (`.btn:hover` border), `#edf0f7` (`.health-bar` bg), `#f0f2f8` (`.file-table td` / `.job-table td` borders), `#eef1f7` / `#f8f9fc` (`.skeleton` gradient), `#f6d5d2` (`.diag span.bad` border), `#b9c6f7` (`.res-card.saved` border), `#33406b` (`.rc-khulasa` text), `#414c66` (`.acc .ab` / `.do-list li`), `#fbfcff` (`.sah-letter` bg), `#1c2536` (`.toast` bg), `rgba(0,0,0,.2)` (`.toast` shadow). Khaas mismatch: `.toast` ka `#1c2536` bilkul `--text` ki value hai lekin literal likha gaya hai, aur `#fff` `--surface` ki jagah. Table borders `#f0f2f8` na `--border` (`#e3e8f0`) se milte hain na `--surface2` (`#fafbfe`) se. Ye tokenization ka pending cleanup candidate hai (**P9/P11, abhi fix ka dawa nahi**); P3 sirf drift darj karta hai.
- **JS-side consumption:** kuch tokens sirf CSS mein nahi, `app.js` ke inline style strings mein bhi aate hain — `loadPackages()` `var(--green-soft)` / `var(--amber-soft)` / `var(--red-soft)` / `var(--green)` / `var(--amber)` / `var(--red)` (`app.js:131–132`), `renderReport()` health-bar `background:${color}` (`app.js:146,160`), `sahMsg()` `var(--red)` / `var(--muted)` (`app.js:477`). Is liye "token sirf CSS mein" wala farz galat hai — audit ko dono files par chalana zaruri hai.
- **Koi dark token set / `prefers-color-scheme` branch nahi** — `§9` ke N/A se mutabiq. Koi `--font-*` ya `--space-*` token bhi nahi; sirf `--radius` sizing token hai (`§4`).

## 4. Typography & spacing scale (VERIFIED NOW)

**Typography.** Koi font/size token nahi; sab literal values hain.

| Level | Rule (as in `style.css`) |
|---|---|
| Font stack | `"Segoe UI",Tahoma,system-ui,-apple-system,sans-serif` (`:15`) — local system fonts, koi external font nahi |
| Base | `body{font-size:14px;line-height:1.55}`; `h1,h2,h3,h4{font-weight:650;margin:0}`; `p{margin:0 0 8px}` |
| `h1` | `font-size:20px;letter-spacing:-.2px` |
| `h2` | `font-size:15px` |
| `h3` | `font-size:14px` (`.sah-h3` override `12.8px`) |
| `h4` | koi explicit size nahi → base `14px` inherit |
| Controls | `button,input,select,textarea{font-family:inherit;font-size:inherit;color:inherit}` |
| Monospace | `.sah-consent,.sah-letter{font-family:ui-monospace,Consolas,monospace;font-size:11.5px;line-height:1.6}` |
| Weights | `550`, `600`, `650`, `700` (`.stat .n{font-size:24px;font-weight:700;letter-spacing:-.5px}`) |
| De-facto size ladder | literal px, koi scale token nahi: `10.5, 11, 11.3, 11.5, 11.6, 11.8, 12, 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7, 12.8, 13, 13.5, 13.6, 14, 15, 16, 20, 24` px |

**Spacing.** Koi `--space-*` token nahi; sirf `--radius:12px` sizing token hai. Sab gaps / paddings literal px hain.

| Level | Rule |
|---|---|
| De-facto ladder | `3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 20, 22, 26, 50, 60` px |
| Shell | `.app{min-height:100vh}` · `.sidebar{width:238px;flex:0 0 238px;position:sticky;top:0;height:100vh}` · `.topbar{padding:16px 26px;position:sticky;top:0;z-index:5}` · `.content{padding:22px 26px 60px;max-width:1500px}` |
| Card / nav | `.card{padding:18px 20px;margin-bottom:18px}` · `.nav{gap:3px;padding:14px 10px}` · `.nav-item{padding:10px 12px;border-radius:9px}` |
| Grid gaps | `.two-col{gap:18px}` · `.stat-grid{gap:12px}` · `.focus-grid{gap:12px}` · `.form-grid{gap:12px}` · `.form-row{gap:12px}` · `.res-results{gap:14px}` · `.sah-grid{gap:20px}` |
| Min-widths | `.stat-grid{minmax(150px,1fr)}` · `.form-row label{min-width:150px}` · `.form-row .grow{min-width:260px}` · `.form-row.filters label{min-width:135px}` · `.inline-form input{min-width:220px}` · `.clock{min-width:120px}` |
| Radii | `5px` (`.kind`) · `7px` (`.check-grid label`) · `8px` (inputs, `.btn`, `.rc-khulasa`, `.sah-check`) · `9px` (`.nav-item`, `.pkg-item`, `.route`, `.acc`, `.skeleton`, `.sah-route`, `.toast`) · `10px` (`.focus-item`) · `11px` (`.brand-mark`) · `12px` = `--radius` (`.card`, `.notice`, `.stat`, `.res-card`) · `99px` (pills / tags / chips / `.health-bar`) |

**Design-system gap (honest):** type aur spacing dono ad-hoc literal px par hain, koi scale tokens nahi. P3 ye de-facto scale document karta hai; tokenize karna P9/P11 ka cleanup candidate hai, abhi "ho gaya" ka dawa nahi.

## 5. Responsive breakpoints — actually in CSS (VERIFIED NOW)

> **P11 correction (2026-11-09):** neeche wala P3-snapshot `8 @media blocks` tha. Final code mein **9 `@media` blocks** hain — 8 desktop-first `max-width` blocks (4 distinct values) + aik `@media (prefers-reduced-motion: reduce)` (`style.css:272`, P9 / QA #9). Baqi snapshot table waisa hi rehta hai; final state §12 mein hai.

`style.css` mein **9 `@media` blocks** hain, **4 distinct `max-width` values** + aik `prefers-reduced-motion` gate par. Koi `min-width`, `print`, `orientation` ya container query nahi.

| Breakpoint | Blocks | Rule + line |
|---|---|---|
| `max-width:1100px` | 2 | `.stat-grid{grid-template-columns:repeat(3,1fr)}` (`:88`) · `.res-results{grid-template-columns:1fr}` (`:182`) |
| `max-width:1050px` | 2 | `.two-col{grid-template-columns:1fr}` (`:75`) · `.sah-grid{grid-template-columns:1fr}` (`:252`) |
| `max-width:1000px` | 2 | `.report-grid{grid-template-columns:1fr}` (`:141`) · `.pkg-layout{grid-template-columns:1fr}` (`:156`) |
| `max-width:900px` | 2 | `.focus-grid{grid-template-columns:1fr 1fr}` (`:94`) · `.check-grid{grid-template-columns:1fr 1fr}` (`:132`) |

Natija: `≤1100px` par stats 3-col aur research 1-col; `≤1050px` par `.two-col` / `.sah-grid` single-column; `≤1000px` par report / package layout single-column; `≤900px` par focus / check grids 2-col. **Responsive risk (P3 note, P9/P11 candidate):** `900px` se neeche koi breakpoint nahi, sidebar har width par `238px` sticky rehta hai (koi hamburger / collapse nahi), is liye bahut tang viewports explicitly handle nahi hote — `A6` ka "single-column fallback" sirf grids tak seemit hai. **P9 update:** motion ka gate ab deliver ho chuka hai — `@media (prefers-reduced-motion: reduce)` (`style.css:272`) tamam `animation` / `transition` ko `.01ms` kar deta hai (`rules.md §11`, QA #9). Sirf `900px` se neeche ka tang-viewport risk `A6` ke mutabiq documented aur deferred rehta hai.

## 6. Component patterns (VERIFIED NOW against `style.css` / `index.html` / `app.js`)

- **Cards** — `.card` (`--surface` bg, `--border`, `--radius`, `--shadow`, `padding:18px 20px`, `margin-bottom:18px`); `.card-head{display:flex;justify-content:space-between}` with `h2`; `.two-col > .card{margin-bottom:0}`. Har view ka primary container.
- **Tables / grids** — `.stat-grid` (`repeat(auto-fit,minmax(150px,1fr))`), `.two-col`, `.report-grid`, `.pkg-layout` (`310px 1fr`), `.check-grid` (4 cols), `.focus-grid` (4 cols), `.form-grid` (2 cols + `.wide{grid-column:1/-1}`), `.sah-grid` (`1fr 1.25fr`), `.res-results` (2 cols). Tables `.file-table`, `.job-table`, `.check-table`, `.gloss`: `border-collapse:collapse`, uppercase `th` (`text-transform:uppercase;letter-spacing:.4px`), `.file-table tr:hover td` `--surface2` highlight.
- **Forms** — `label{display:flex;flex-direction:column;gap:5px;font-size:11.8px;font-weight:600;color:var(--muted)}` (implicit association); `input,select,textarea{padding:9px 11px;border:1px solid var(--border);border-radius:8px;outline:none;transition}`; `input:focus{border-color:var(--primary);box-shadow:0 0 0 3px var(--primary-soft)}` (**P9 update:** `:focus-visible` ab `style.css:19–25` par `a` / `button` / `input` / `select` / `textarea` / `summary` / `[tabindex]` ke liye maujood hai — `§8` ka gap band); `.checkline` row-label + `accent-color:var(--primary)`; `.btn` (`.primary`, `.ghost`, `.sm`, `:disabled{opacity:.55;cursor:wait}`), `.link-btn`, `.chip` / `.chip.active`, `<details class="sources-box"><summary>`. `spellcheck="false"` path fields par.
- **Stat grid** — `.stat` (`.n` 24px/700 `--primary-dark`, `.l` 11.5px `--muted`). `renderStats()` (`app.js:77–87`) 7 cards inject karta hai: `Packages`, `Scanned files`, `Research items`, `Saved`, `Model cards`, `Jobs`, `Sahulat cases`.
- **Toast** — `.toast` fixed `right:22px;bottom:22px`, bg `#1c2536`, white, `opacity:0;transform:translateY(12px);pointer-events:none;transition:all .22s;z-index:50;max-width:390px`; `.show{opacity:1;transform:none}`; `.bad{background:var(--red)}`. `toast()` (`app.js:49–53`) `textContent` set karta hai, class toggle, `3600ms` timeout. **P9 update:** `#toast` ab `role="status" aria-live="polite" aria-atomic="true"` (`index.html:321`); `#sideMeta` / `#sahFormMsg` / `#setMsg` par bhi `aria-live="polite"` — `§8` ka gap band.
- **Skeleton loaders** — `.skeleton{height:70px;border-radius:9px;background:linear-gradient(90deg,#eef1f7,#f8f9fc,#eef1f7);background-size:200% 100%;animation:sh 1.3s infinite}` + `@keyframes sh`; `.view.active{animation:fade .22s ease}` + `@keyframes fade`. Initial placeholders: `#dashNews`, `#pkgList`, `#pkgDetail`, `#sahRoutes`, `#modelOut`, `#sahCheckOut`, `runScan()` output. **P9 update:** `@media (prefers-reduced-motion: reduce)` (`style.css:272`) `fade` / `sh` animations ko neutralize karta hai — `§8` ka gap band.
- **Research cards** — `.res-card` with `.rc-top` (`.tag`, `.score`, date), `.rc-title` (`linkHtml()` → validated `<a>` ya `<span>`), `.rc-khulasa` (Roman Urdu khulasa, `--primary-soft` bg), `.rc-excerpt`, `.rc-foot` (source, `Save` / `Mark read` `<button>`, `Open ↗` `<a rel="noopener noreferrer">`); `.res-card.saved{border-color:#b9c6f7}`. `.mini-news .mn/.mt/.mk` dashboard news, `.diag` per-source status pills (`.bad`), `.res-toolbar` result count.
- **Sahulat letter `<pre>`** — `.sah-consent` / `.sah-letter`: `white-space:pre-wrap;word-break:break-word;font-family:ui-monospace,Consolas,monospace;font-size:11.5px;line-height:1.6;--surface2 bg;--border;--radius 9px;padding:12px 14px;max-height:330px;overflow:auto`. `textContent` se render (`app.js:424,520,530`) — **kabhi `innerHTML` nahi**, HTML-injection ka raasta band (`rules.md §15`). `#sahFormMsg` inline Roman Urdu status; `copyText()` (`app.js:479–492`) copy buttons.
- **Routes / checklist** — `.route` / `.sah-route` `<details>` with keyboard-operable `<summary>`, `.sr-docs` `<ul>`, `.sr-steps` `<ol>`, `.rl` link pills, `.rn` note, `[data-pick]` "Is route ko form mein chunein" button. `.sah-checklist` → 8 `.sah-check` wrapped `<label>` + checkbox, required items par `zaroori` `.tag.amber`, hint `<em>`. Service boundary `.do-list` / `.do-list.no` ✓ / ✕ **text** ke sath (sirf rang par depend nahi).

## 7. Loading / empty / error / success states — per view (VERIFIED NOW)

Quoted strings seedha `index.html` / `app.js` se hain. Har view ke liye char states:

| View | Loading | Empty | Error | Success |
|---|---|---|---|---|
| `Dashboard` | `#dashNews` mein 2 `.skeleton`; `#sideMeta` `loading…`; `#statGrid` `/api/status` tak khaali | `Abhi koi matching khabar nahi mili. Research Agent mein filters khol kar dobara try karain.` | `Fetch nahi hua: {message}` (`#dashNews`); `toast('Init fail: …', true)` | 7 stat cards, `.mini-news .mn` items, scan `.notice.soft` `Scan mukammal — N files, health X%` |
| `Firmware Packages` | `#pkgList` / `#pkgDetail` / `#pkgScanOut` skeleton; `busy()` → `Chal raha hai…` | `Abhi koi package nahi. Upar folder scan karain.` · `Koi package select karain ya upar naya scan chalayein.` · `Koi file nahi` · `Koi issue nahi mila — package saaf lag raha hai.` | `#pkgScanOut` `.issue.error` `Scan fail` + `toast(e.message,true)`; `Pehle folder path likhein` | `toast('Scan ho gaya — package #N save ho gaya')`, auto `nav('packages')` + auto-select, health report, `refreshCounts()` |
| `Research Agent` | `busy($('#resFetch'),true,'Fetch ho raha hai…')`; `#fetchStamp` `abhi tak fetch nahi` | `Is filter par koi result nahi. Min score kam karain, days barhayein ya query badlein.` · saved: `Abhi kuch save nahi kiya. Research cards par "Save" dabayein.` | `#resResults` card `.issue.error` `Fetch fail` + `toast`; `#resDiag` per-source `.bad` pills | `#fetchStamp` `live · {fetched_at}` / `cache se · …`, `N results` toolbar, `.res-card` grid, diagnostics |
| `Model Brief` | `#modelOut` skeleton card | `Is model ka koi scanned package nahi.` · `Koi live khabar nahi mili.` · `Model number likhein` toast | `#modelOut` `.issue.error`; `toast(e.message,true)` on save | model card form + live info + official routes; `toast('Model card save ho gaya')` |
| `Job Register` | **koi inline skeleton nahi** — `loadJobs()` view open / `Reload` par `#jobList` swap karta hai (honest gap) | `Register khaali hai. Upar pehla job add karain.` | `#jobList` `.issue.error` + `toast(e.message,true)` | `.job-table` rows; `toast('Job register ho gaya')`; form fields clear |
| `Sahulat / Official Route` | `#sahRoutes` / `#sahCheckOut` skeleton; `#sahPolicyLead` `loading…`; `busy()` on letter/case buttons; `#sahLetter` hint | `Pehle customer ki request likhein.` · `Case register khaali hai. Upar form bhar kar pehla case save karain.` · `Letter yahan aayega…` | `Sahulat data load nahi hua` issue card; `#sahFormMsg` red Roman Urdu reason; `letter_error` on `draft` case; `toast(e.message,true)` | 6 `<details>` routes; `✓ Case {case_no} save ho gaya aur letter tayyar hai.`; toast; `Sahulat cases` stat refresh; `<pre>` letter `textContent` se |
| `Knowledge / Help` | **koi skeleton nahi** — `#knowledgeOut` `init()` → `renderKnowledge()` tak khaali | static KB; agar `/api/knowledge` fail ho to panel khaali rehta hai (**koi error card nahi** — honest gap) | sirf global `toast('Init fail: …', true)` | boundary card, `.acc` details, `.gloss` table, `.do-list`, official routes |
| `Settings` | **koi skeleton nahi** — `loadSettings()` boot par fields / `#statusOut` `.kv` bhar deta hai | `#setKey` jaan-bujh kar khaali (`khali chhor dein = offline mode`); endpoint / model placeholders | `toast(e.message,true)` on load / save | `#setMsg` `✓ Save ho gaya` (3s), `toast('Settings save ho gaye')`, `#setKey` clear, `System status` `.kv` |

**Honest state gaps (P3 note, P9/P11 candidates, abhi fix nahi):** `#jobList`, `#knowledgeOut` aur `#statusOut` par koi initial skeleton nahi; `Knowledge / Help` aur `Settings` par API-failure ke liye koi dedicated error card nahi (sirf global toast). `toast()` par abhi `aria-live` nahi (`§8`). Inhe P3 document karta hai, "sab states mukammal" ka jhootha dawa nahi karta.

## 8. Accessibility plan

### 8.1 WCAG intent
Design intent **WCAG 2.1 AA** ke char principles (perceivable, operable, understandable, robust) ke mutabiq hai — ye **intent** hai, koi certified conformance claim nahi (`rules.md §12`, `PRD.md §12 AC-05`). Maqsad: har control keyboard se chalay, har state announce ho, koi information sirf rang par depend na karay, zoom / narrow viewport par content na tootay.

### 8.2 [VERIFIED NOW — PHASE 3 SNAPSHOT] aaj CSS / HTML mein kya hai

> **P11 correction (2026-11-09):** ye 8.2 ki list **PHASE 3 ke waqt** ka snapshot hai, aaj ka final state nahi. Neeche "maujood nahi / zero matches / abhi `aria-live` nahi" wale sab statements P9 me **delivered** ho chuke hain: `<html lang="en">`, 8 `role="tabpanel"`, `aria-current` / `aria-selected` / `aria-controls`, `aria-live` (`#toast`, `#sideMeta`, `#sahFormMsg`, `#setMsg`), `:focus-visible` (`style.css:19–25`), `@media (prefers-reduced-motion: reduce)` (`style.css:272`), aur `href="#"` ki jagah `<button>`. Regression gate `test_a11y_markup` green; final state §12 aur `decisions.md` D32 mein. Historical snapshot is liye rakha gaya hai taake P3 design intent ka record na mitay.
- `<html lang="ur-PK-Latn">` (`index.html:2`) — P3 snapshot; P9 mein `<html lang="en">` ho gaya (`§8.4` ADR amal).
- `<meta name="viewport" content="width=device-width,initial-scale=1">` (`index.html:5`).
- Brand SVG `aria-hidden="true"` (`index.html:16`) — **poore `web\` tree mein aik hi `aria-*` / `role` match hai** (grep se verify).
- Nav controls semantic `<button class="nav-item" data-view>` (`index.html:31–38`) — default keyboard-focusable; active state sirf `.active` class se, koi `aria-current` nahi.
- Forms implicit `<label>` association, `<summary>` keyboard-operable, `input:focus` ring (`style.css:102`).
- **Maujood nahi (verify kiya):** `role="tablist"/"tab"/"tabpanel"`, `aria-selected`, `aria-controls`, `aria-current`, `aria-live`, `:focus-visible`, `@media (prefers-reduced-motion)` — `style.css` / `index.html` / `app.js` mein zero matches.
- `<a href="#" data-goto="sahulat">` aur `<a href="#" data-goto="knowledge">` abhi `index.html:68` par maujood hain (`rules.md §12` inhe `<button>` banana kehta hai).
- Toast `<div id="toast" class="toast">` (`index.html:321`) par koi `aria-live` nahi.

### 8.3 [P9 PLAN — P11 note: IMPLEMENTED] — separate subagent ka target tha
> **Ye sab P9 ke targets hain, P3 ka implemented dawa nahi.** Regression test: **`test_a11y_markup`** (`phases.md §6`, QA #9). CSP / `safe_url()` / security headers bhi usi P9 subagent ke scope hain; P3 unhe design target ke tor par likhta hai.

- **Tab semantics:** `.nav` par `role="tablist"`; har `.nav-item` par `role="tab"` + `aria-controls="view-<name>"` + `aria-selected="true|false"`; har `.view` par `role="tabpanel"` + `aria-labelledby` (associated tab id).
- **Current state:** active `.nav-item` par `aria-current="page"` (ya tab pattern ke mutabiq `aria-selected="true"`); `.active` class sirf visual ke liye rehne dein.
- **Live regions:** `#toast` par `role="status"` + `aria-live="polite"`; inline status (`#sahFormMsg`, `#setMsg`, result count, `#fetchStamp`, `#srcCount`) par bhi `aria-live="polite"` taake success / error focus chhine baghair announce ho. `aria-live="assertive"` sirf zaroori errors par, default polite.
- **Decorative `aria-hidden`:** `.ni` icon spans, `.notice-icon` (`i`), `.dot-live`, `.nav-dot`, `.brand-mark` SVG, ✓ / ✕ glyphs, decorative `<em>` separators — taake screen reader "◈ i ✓" na parhay. Sirf decorative; koi labeled control `aria-hidden` na ho.
- **`:focus-visible`:** `.nav-item`, `.btn`, `.link-btn`, `.chip`, `a`, `input,select,textarea`, `summary`, `.pkg-item`, `.sah-check`, `.res-card a` par visible focus outline; maujooda `:focus` ring fallback ke tor par rehay; mouse par focus indicator hataya na jaye.
- **Keyboard navigation:** tabs par Arrow Left/Right + Home/End (roving `tabindex`), Enter/Space activate; `hashchange` already wired (`app.js:616–619`); skip-to-content link; `<details>` focus management; destructive delete `confirm()` dialog already keyboard-reachable (`app.js:205`); koi keyboard trap na ho.
- **`<button>` instead of `<a href="#">`:** dono `data-goto` links ko `<button type="button" data-goto>` banaya jaye, `e.preventDefault()` handler (`app.js:620–623`) barqarar; koi `href="#"` navigation link na reh ay.
- **`prefers-reduced-motion`:** naya `@media (prefers-reduced-motion:reduce)` `fade` / `sh` animations aur `transition`s ko disable karay (`rules.md §11`); `§5` mein confirm kiya gaya ke abhi aisa koi rule nahi.
- **Honesty note:** `test_a11y_markup` ka green hona P9 gate par verify hoga; P3 usay "pass" nahi likhta. URL / CSP fixes ka apna P9 evidence (`test_javascript_url_rejected`, `test_security_headers_present`, …) alag hai.

### 8.4 `lang` ADR (decision P3, implementation P9)
- **Faisla (P3 final):** `<html lang="en">` — kyunke professional surface (nav, buttons, labels, headings, table headers, code, identifiers) English hai (`C19 / D22`, `agent.md §L`). Har Roman Urdu **content** block ko apna `lang="ur-PK-Latn"` milega: service letters (`#sahLetter`), consent (`#sahConsent`), refusal reasons / official-route text (`#sahCheckOut`), checklist hints (`.sah-check em`), research `khulasa` (`.rc-khulasa`, `.mini-news .mk`), help / KB text (`.acc .ab`, `.notice p`, `.do-list li`), empty / error / success explanations aur toasts.
- **Wajah:** aaj ka `<html lang="ur-PK-Latn">` (`index.html:2`) mostly-English chrome ko screen readers / translation tools ke liye ghalat label karta hai (`rules.md §12` ne ye faisla P9 ADR par chhora tha; P3 design decision pakka karta hai). `dir` implicit `ltr` rehta hai — RTL `§9` mein N/A hai.
- **Hadd:** ye **sirf attribute / markup** ka faisla hai, content ka bulk rewrite nahi (`D22`: "C9 khatam nahi, sirf refined"). Koi Roman Urdu string English nahi hogi is ADR se. **[P9 PLAN]** code mein change aayega.

## 9. N/A items — justification (gate pass, skip nahi)

`phases.md §2` ki P3 row ke mutabiq do items is app par be-matlab hain; "N/A + wajah" ke sath gate pass, koi skip nahi. P5 / P10 ke N/A apne apne gates par likhe jayenge, yahan dohraya nahi gaya.

| N/A item | Justification (VERIFIED NOW) |
|---|---|
| **Dark mode toggle** | User ne light theme confirm kiya (`phases.md §2`: "user ne light theme confirm kiya"). `style.css:1–11` mein aik hi light `:root` palette hai; koi `[data-theme]`, koi `@media (prefers-color-scheme)`, koi dark token set aur `index.html` mein koi theme-toggle control nahi. Single-user local tool; dark theme ka koi product matlab nahi. Is liye toggle **N/A + wajah**. (Ye `prefers-reduced-motion` ke P9 plan se alag hai — woh accessibility hai, theme nahi.) |
| **RTL layout** | Roman Urdu **Latin script** (`ur-PK-Latn`) hai, left-to-right (`phases.md §2`: "Roman Urdu Latin script (`ur-PK-Latn`) hai"). `<html>` par koi `dir="rtl"` nahi, `style.css` mein koi `direction:rtl`, logical-property mirroring ya `[dir]` selector nahi. RTL support ka koi matlab nahi; **N/A + wajah**. `lang` ADR (`§8.4`) bhi `ltr` hi rakhta hai. |

## 10. Localization / O12 resolution

**O12** (`PRD.md §7`, `agent.md §N/L`: "in-app Roman Urdu chrome → English surface migration phase (P3/P11)") **P3 mein resolve hota hai** — faisla pakka, code P9.

| Layer | Language | Examples (VERIFIED NOW) |
|---|---|---|
| English UI chrome (surface) | **English** | 8 nav labels, `Dashboard`, `Model Brief`, `Job Register`, `Settings`, `System status`, `Official routes`, `Live information`, `Register`, table headers (`Date`, `IMEI`, `Model`, …), `Save`, `Refresh`, `Reload`, `Delete`, tags / badges, CSS / JS identifiers |
| Roman Urdu content | **Roman Urdu (rehta hai)** | service-request letters, refusal reasons + official-route guidance, checklist hints, consent text, research `khulasa`, help / KB text, notices, empty / error / success explanations, toasts |

- **Decision:** UI chrome (nav, buttons, labels, headings, table headers, status pills) English professional surface hai; **content strings Roman Urdu rehte hain** — letters, refusal reasons, checklist hints, consent, research `khulasa`, help text. Koi translation layer, koi doosra locale, koi `i18n` framework nahi — single locale by design. Koi purani prose ko "ab English karo" ke naam par bulk rewrite nahi (`D22`: C9 refined, khatam nahi).
- **[VERIFIED NOW] aaj ki halat:** 8 nav labels pehle se English hain aur kai headings English hain; lekin button / label / heading microcopy abhi bhi largely Roman Urdu hai — maslan `Jaldi scan`, `Taaza mobile-software khabarein`, `App ka focus`, `Naya package scan karein`, `Brief banayein`, `Register save karein`, `Check karein`, `Sirf letter preview`, `Case save + letter`, `zaroori`, `Koi package select karain…`. Is liye chrome migration **code mein mukammal nahi**.
- **[P9 PLAN] O12 code implementation:** aik alag subagent `index.html` / `app.js` ki chrome strings ko English par migrate karega aur **har Roman Urdu content string ko waisa ka waisa** rakhega. P3 sirf ye decision + classification table finalize karta hai; `web/*` ko chhedta nahi aur "migration ho gayi" ka dawa nahi karta. `PRD.md §15` / `agent.md §L` ke "O12 (P3/P11)" references isi P3 decision + P9 code split se mutabiq hain.

## 11. PHASE 3 acceptance criteria

| ID | Criterion | Expected evidence |
|---|---|---|
| **AC-P3-01** | `design.md` version `2.0.0`, status `PHASE 3 final — gate review phases.md §12`, documentation-only. | Header read-back; coordinator ka `git diff --name-only` sirf `docs/design.md` dikhaye (koi `web/*` / `.py` / `.js` / DB / `agent.md` edit nahi); `agent.md` verbatim prefix SHA-256 `1de53535942d8e7f1b31b3d9b55c9ae4854e85fd667e14e02f314a62010fd840` MATCH; koi local commit / `git` command / `unittest` run is agent ne nahi kiya. |
| **AC-P3-02** | 8 views exact nav labels ke sath, sidebar order mein. | `§2` table `index.html:31–38` se byte-for-byte match: `Dashboard`, `Firmware Packages`, `Research Agent`, `Model Brief`, `Job Register`, `Sahulat / Official Route`, `Knowledge / Help`, `Settings`; `class="view"` × 8 / `id="view-"` × 8 / `data-view="` × 8; `TITLES` (`app.js:22–31`) 8 keys. |
| **AC-P3-03** | Light-theme token audit asli CSS par, variable → value → where used, koi invented hex nahi. | `§3` ki 20/20 values `style.css:1–11` ke literals se match (`--bg:#f4f6fb`, `--primary:#3b5bdb`, `--shadow:0 1px 2px rgba(20,32,64,.05),0 6px 20px rgba(20,32,64,.05)`, `--radius:12px`, …); mismatch section `§3.1` wohi hardcoded literals darj karay jo grep se mile (`#1c2536 == --text`, `#fff`, `#f0f2f8`, `#eef1f7`, `#414c66`, `rgba(0,0,0,.2)`, …); 20/20 tokens used, `--faint` single-use, aur JS-side `var(--…)` consumption (`app.js:131–132,146,477`) darj. Doc-vs-CSS read-back green. |
| **AC-P3-04** | Typography / spacing / breakpoints actual CSS se. | `§4` base `14px / 1.55`, `"Segoe UI"` stack, `h1 20px / h2 15px / h3 14px`, weight `650`, `--radius:12px`, monospace letter stack — sab `style.css` se; `§5` bilkul 8 `@media` blocks / 4 widths (`1100, 1050, 1000, 900`) line numbers ke sath, koi guessed breakpoint nahi, `prefers-reduced-motion` ki gair-mojoodgi darj. |
| **AC-P3-05** | Component patterns + har view ke loading / empty / error / success states real selectors / copy se. | `§6` selectors (`.card`, `.stat-grid`, `.skeleton`, `.res-card`, `.sah-letter` `<pre>`, `.sah-route`, `.sah-check`, `.toast`) `style.css` mein maujood; `§7` quoted strings `index.html` / `app.js` se (`Abhi koi package nahi…`, `Case register khaali hai…`, `Fetch nahi hua: …`); honest gaps (koi skeleton `#jobList` / `#knowledgeOut` / `#statusOut` par, Knowledge / Settings par koi dedicated error card) darj. |
| **AC-P3-06** | Accessibility plan: WCAG intent, tablist / tab / tabpanel, `aria-selected` / `aria-controls` / `aria-current`, `aria-live="polite"`, decorative `aria-hidden`, `:focus-visible`, keyboard nav, `<button>` over `<a href="#">`, `lang` ADR. | `§8` mein har item maujood; `[VERIFIED NOW]` aur `[P9 PLAN]` alag; sirf aik `aria-*` (`aria-hidden`, `index.html:16`) aur `<a href="#">` × 2 (`index.html:68`) aaj ke gaps darj; `lang="en"` on `<html>` + `lang="ur-PK-Latn"` on Roman Urdu content blocks ADR `§8.4`; **`test_a11y_markup`** QA #9 (`phases.md §6`) referenced aur fixes ko "abhi implemented" NAHI likha gaya. |
| **AC-P3-07** | N/A items justified; O12 resolved (English chrome / Roman Urdu content), P9 code implementation noted. | `§9` `phases.md §2` P3 row se match (dark mode toggle, RTL); `§10` nav already English / chrome microcopy abhi Roman Urdu, P9 migrate, koi bulk rewrite nahi (D22), single locale, `index.html` / `style.css` mein koi `dir="rtl"` nahi; P5 / P10 N/A yahan dohraya nahi gaya. |
| **AC-P3-08** | P3 gate hygiene, 9-doc consistency, koi scope creep, P9 fixes explicitly deferred. | 9/9 docs maujood; `design.md` cross-references `PRD.md §12 (AC-05)`, `rules.md §12 / §16`, `phases.md §2 / §6`, `architecture.md 2.0.0`, `agent.md §N`; Sahulat & Safe Service Policy unchanged — koi bypass / device write / erase / flash / bootloader / IMEI content nahi (`D19` canonical note `preamble` mein); `test_a11y_markup` + CSP / URL / header fixes `[P9 PLAN]` labelled; P9 subagent ka code is doc ka dawa nahi. |

**P3 result:** upar wale criteria `phases.md §12` ke `PHASE REVIEW — PHASE 3` me verify ho kar **`READY`** darj hue. P3 documentation-only tha; a11y / URL / CSP code fixes, `test_a11y_markup` aur central verification **P9** par scheduled the — P3 ne unhe fix hone ka koi jhootha dawa nahi kiya tha. P11 final state neeche §12 mein.

---

## 12. P11 final note — P3 `READY` / O12 resolved (2026-11-09)

> Ye P3 ke `[VERIFIED NOW]` / `[P9 PLAN]` snapshot ke baad ka **final state** hai. Token audit (§3), responsive breakpoints (§5), states (§7), a11y plan (§8) aur `AC-P3-01…AC-P3-08` (§11) **waisa ka waisa barqarar** hain — inhe dobara nahi likha gaya. Koi naya citation / URL add nahi kiya gaya.

- **Status:** PHASE 3 `READY` — `phases.md` §12 `PHASE REVIEW — PHASE 3` final review. C23 / D29 auto-continue run me P3–P11 sab gates pass hue; project complete (N7: naye kaam par phase-by-phase approval wapas).
- **O12 RESOLVED (`D34`):** English UI chrome migration **done**, Roman Urdu content **retained**. Verified static UI: `lang="en"`, 8 views / 8 nav items / 8 `role="tabpanel"`, 27 `sah*` IDs, zero inline `<script>`, `aria-live`, `:focus-visible`, `prefers-reduced-motion`. Letters, refusal reasons, checklist hints, consent, research `khulasa` aur help text Roman Urdu rehte hain (C19 / D22). Is liye §10 ka "[P9 PLAN] chrome migration code mein mukammal nahi" wala P3-snapshot ab superseded hai — code deliver ho chuka.
- **P9 a11y / URL / CSP fixes delivered (`D32`):** `test_a11y_markup` green; `web/app.js` `safe_url()` http/https allowlist (`test_javascript_url_rejected`); four security headers + CSP (`test_security_headers_present`); `<html lang="en">` ADR (§8.4) amal me aaya. §8.3 ke `[P9 PLAN]` targets ab implemented hain.
- **Central verification:** `python -W error::ResourceWarning -m unittest discover -s tests -p "test_*.py" -v` → `Ran 101 tests in 77.621s — OK`, zero `ResourceWarning`; `node --check web/app.js` → `NODE_CHECK_OK`; `agent.md` verbatim prefix SHA-256 `1de53535942d8e7f1b31b3d9b55c9ae4854e85fd667e14e02f314a62010fd840` MATCH; docs `9/9`.
- **Security review:** Sahulat & Safe Service Policy bilkul unchanged — koi bypass automation, device write / erase / flash / IMEI operation ya lock-removal step kahin nahi (D19 canonical note barqarar).

---

## 13. P12 / P13 design sync (2026-11-09)

- **P12 Service Brief design:** Sahulat view card with `svc*` IDs (`svcCard`, `svcAsk`, `svcAskBtn`, `svcAskOut`, `svcMode`, `svcBrand`, `svcCustomer`, `svcModel`, `svcId`, `svcChecks`, `svcProof`, `svcConsentChk`, `svcLive`, `svcRunBtn`, `svcCopyBtn`, `svcOutput`, `svcFacts`, `svcSources`, `svcDisclaimer`, `svcMsg`); styling via `.svc-cols`, `.svc-src`, `#svcOutput`; reuse of existing tokens (`--surface`, `--border`, `--primary`, `--muted`). Card is stateless.
- **P13 Agent Memory design:** 9th view `memory` with `memStats` (stat grid), source card (`memSourceList`), Telegram card (`memTgList`, `memTgSearch*`, `memTgResults`), recall (`memRecallOut`), problem memory (`memProbList`), query history (`memQueries`), feedback (`memFeedback`), `memExportBtn` / `memReloadBtn` / `memExportMsg`; CSS block `/* P13 - Agent Memory view. */` with `.mem-list`, `.mem-item`, `.mem-top`, `.mem-text`, `.mem-results`; one new responsive rule `@media(max-width:900px){.mem-list,.mem-results{max-height:none}}`.
- **Design truth:** design.md keeps its P3 snapshot + P11/P12/P13 sync notes; tokens / breakpoints / states / a11y unchanged by P13 except the new responsive rule (explicitly registered as an added media query).

---

## 14. P13 final design note - PHASE 13 `READY` (2026-11-09)

- **Status:** PHASE 13 `READY` (`phases.md` section 22).
- **Design delta:** +1 view (`memory`), +1 `@media` block (max-width 900), reuse of existing tokens only (no new colour tokens, no new font). a11y attributes retained (`aria-live`, `lang`, `aria-labelledby`).
- **O12 / D34 English-chrome note remains valid:** nav labels / headings / buttons English; Roman Urdu content retained (`C19` / `D22`).
- **Verification:** `web/index.html` 9 views / 9 nav / 9 `tabpanel`; `web/style.css` 10 `@media`; `web/app.js` 9-view `TITLES` key.

---

## 15. P14 Settings — Model source (2026-11-12)

- **Control:** `Model source` `<select id="setProvider">` — `Off` (default), `Ollama`, `LM Studio`, `Custom OpenAI-compatible endpoint`. Labels English, wazahat Roman Urdu (C19 / D22).
- **Conditional fields:** `syncLlmProvider()` non-custom provider par `setEndpoint` / `setKey` ko `disabled` + explanatory `title` deta hai; Save payload unhein sirf `custom` par bhejta hai. Is se stale loopback endpoint wala `400` SSRF error khatam hua.
- **Diagnostics:** `#llmState` `aria-live` status line (`Model ON …` / `Model OFF …` with reason), `#llmTest` button aur `#llmTestMsg` `aria-live` result. Koi secret UI par nahi.
- **Invariants unchanged:** 9 views / 9 nav / 9 `role="tabpanel"` / 27 `sah*` IDs / zero inline `<script>` / `lang="en"` / `aria-live` / `:focus-visible` / `prefers-reduced-motion`; `web/style.css` 10 `@media` blocks — koi naya color token ya font nahi.
- **Light theme:** existing tokens reuse; disabled inputs native browser styling, koi dark surface nahi.
