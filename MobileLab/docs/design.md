# design.md — MobileLab UI/UX

**Date:** 2026-11-08 · **Status:** PHASE 0 baseline; PHASE 3 finalize karega.
**Source:** har value `J:\Ai Agent\MobileLab\web\style.css` aur `web\index.html` se parh kar likhi gayi hai — koi value andaz se nahi.

---

## 1. UI/UX principles

- **Light theme**, saaf contrast, technician ke liye compact density.
- **Roman Urdu** copy; technical terms English (C9).
- Har important screen par **loading / empty / error / success** state.
- Keyboard accessibility aur WCAG intent.
- Koi placeholder UI ko final implementation na mana jaye.
- Local-first: koi external font / CDN / analytics nahi.

## 2. Design system (verified tokens)

| Token | Value | Istemal |
|---|---|---|
| `--bg` | `#f4f6fb` | page background |
| `--surface` | `#ffffff` | cards, sidebar |
| `--surface2` | `#fafbfe` | hover / soft rows |
| `--border` | `#e3e8f0` | borders |
| `--text` | `#1c2536` | primary text |
| `--muted` | `#6b7690` | secondary text |
| `--faint` | `#98a2b8` | hints / small print |
| `--primary` | `#3b5bdb` | actions, brand mark |
| `--primary-dark` | `#2f4bc0` | active nav |
| `--primary-soft` | `#eef2ff` | active background |
| `--green` / `--green-soft` | `#0f9d6e` / `#e8f8f1` | OK / healthy |
| `--amber` / `--amber-soft` | `#d9860b` / `#fff5e3` | warn |
| `--red` / `--red-soft` | `#d64545` / `#fdeceb` | error |
| `--blue` / `--blue-soft` | `#2f80c4` / `#e9f3fc` | info |
| `--shadow` | `0 1px 2px rgba(20,32,64,.05),0 6px 20px rgba(20,32,64,.05)` | cards |
| `--radius` | `12px` | corners |

**Typography:** `font-family:"Segoe UI",Tahoma,system-ui,-apple-system,sans-serif` · body `14px` / `line-height:1.55` · `h1` 20px (`font-weight:650`, `letter-spacing:-.2px`) · `h2` 15px · `h3` 14px · `button,input,select,textarea` inherit karte hain.

**Layout / spacing:** `.app{display:flex;min-height:100vh}` · sidebar `width:238px;flex:0 0 238px`, `position:sticky;top:0;height:100vh` · `.nav-item` `padding:10px 12px`, `border-radius:9px` · `.two-col` `grid-template-columns:1fr 1fr;gap:18px;align-items:start` · `.two-col > .card{margin-bottom:0}`.

## 3. Responsive behavior (verified media queries)

| Breakpoint | Rule |
|---|---|
| `max-width:1050px` | `.two-col` → `1fr` |
| `max-width:1100px` | `.stat-grid` → `repeat(3,1fr)` |
| `max-width:900px` | `.focus-grid` → `1fr 1fr` |
| `max-width:900px` | `.check-grid` → `1fr 1fr` |
| `max-width:1000px` | `.report-grid` → `1fr` |
| `max-width:1000px` | `.pkg-layout` → `1fr` |
| `max-width:1100px` | `.res-results` → `1fr` |

Mobile-friendly single-column fallback inhi breakpoints se aati hai. Koi dedicated mobile nav nahi — **Assumed (A6)**, P3 mein confirm.

## 4. Views (7)

`Dashboard` · `Firmware Packages` · `Research Agent` · `Model Brief` · `Job Register` · `Knowledge / Help` · `Settings`.
Navigation: hash routing (`location.hash` + `hashchange`), `.nav-item[data-view]`, `.view.active`. `nav()` active class aur title update karta hai.

## 5. Component patterns

- **Card** — har panel `.card`, header + body.
- **Nav** — sidebar buttons with icon span (`.ni`), active dot (`.nav-dot`).
- **Tables / grids** — `.pkg-layout`, `.report-grid`, `.check-grid`, `.focus-grid`, `.stat-grid`, `.res-results`.
- **Forms** — labeled inputs, `spellcheck="false"` on path fields, submit buttons with `busy()` state.
- **Toast** — success/error feedback.
- **Skeleton / spinner** — loading state.
- **Escaping** — har dynamic string `esc()` se guzarta hai (`app.js`).

## 6. States

| State | Implementation |
|---|---|
| Loading | `busy()` + skeleton; dashboard news async fetch |
| Empty | e.g. *"Koi package select karain ya upar naya scan chalayein."* |
| Error | `toast()` + API `_err()` JSON; research source diagnostics |
| Success | toast + list refresh + auto-select first package |
| Destructive | package delete par confirmation (P6/P9 mein audit) |

## 7. Accessibility — aaj ki halat (verified gaps, QA #9)

**Maujood:** `<html lang="ur-PK-Latn">`, `<meta name="viewport">`, brand SVG par `aria-hidden="true"`, semantic `<button>` nav items.

**Kami (P9 mein fix + `test_a11y_markup`):**
- `lang="ur-PK-Latn"` aur mostly-English UI ka mismatch → ADR mein faisla (P9).
- Tab / tabpanel roles aur `aria-current` nahi.
- Toast par `aria-live="polite"` nahi.
- `<a href="#" data-goto>` ko `<button>` banana hai.
- Decorative icon spans par `aria-hidden` nahi.
- `prefers-reduced-motion` ka koi rule nahi (verify: `style.css` mein zero matches).
- Focus-visible aur keyboard trap audit.

## 8. Form behavior / validation

- Path field empty → client + server `400`.
- Ghalat numeric query params → `400` JSON (P6).
- `llm_key` masked `***` round-trip; kabhi plaintext return na ho (P9).
- Explicit opt-in checkbox "Workspace se bahar ka folder (explicit)" P9 mein add hoga (C6).
- Destructive actions par confirmation.

## 9. Language / localization

Roman Urdu prose (`ur-PK-Latn` Latin script), **RTL nahi**. Technical terms (`preloader`, `scatter`, `Firehose`, `EDL`, `rawprogram`, API paths) English. Koi translation layer nahi — single locale by design.

## 10. Dark / light mode

**Sirf light.** Dark mode N/A: single-user local tool, user ne light theme confirm kiya; koi theme toggle nahi. P3 gate par ye N/A justification darj hogi.

## 11. Pending (P3 finalize, P9 implement)

Design tokens ka doc-vs-CSS audit · a11y markup fixes · `prefers-reduced-motion` · focus styles · reduced-motion gate · har view ke liye illustrated empty/error/success states audit.
