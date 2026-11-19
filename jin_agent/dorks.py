"""P41: Google-dork helper — query + operators se dork banao.

Legal boundary (Sahulat & Safe Service Policy, barqarar):
- Dork sirf public web search ke liye banta hai.
- Onion dork fetch NAHI hota — sirf prefilled link display hota hai.
- Koi private/illegal source, bypass ya credential dump nahi.
"""

from __future__ import annotations

import base64
import re
import urllib.parse

from . import policy, util

# --------------------------------------------------------------------------
# Operators
# --------------------------------------------------------------------------

def site(query, domain: str) -> str:
    return f'site:{domain} "{query}"'


def intitle(query: str) -> str:
    return f'intitle:"{query}"'


def inurl(query: str) -> str:
    return f'inurl:"{query}"'


def filetype(query: str, ext: str) -> str:
    return f'filetype:{ext} "{query}"'


def exact(query: str) -> str:
    return f'"{query}"'


def exclude(query: str, terms) -> str:
    """`site:t.me/s <q> -twitter -instagram` — negative operators."""
    blocked = " ".join("-" + str(t).lstrip("-") for t in (terms or ()))
    return f"{query} {blocked}".strip()


def build(query: str, ops=()) -> str:
    """Query + operator list ko ik dork me jodo."""
    parts = [str(query or "").strip()]
    parts += [str(o).strip() for o in (ops or ()) if str(o).strip()]
    return " ".join(p for p in parts if p)


# --------------------------------------------------------------------------
# Presets
# --------------------------------------------------------------------------

def tg(query: str) -> str:
    """Telegram public channel dork."""
    return f'site:t.me/s {query} -twitter -instagram'


def pdf(query: str) -> str:
    return filetype(query, "pdf")


def gov(query: str) -> str:
    return site(query, "gov")


def edu(query: str) -> str:
    return site(query, "edu")


def pastebin(query: str) -> str:
    return site(query, "pastebin.com")


DORK_PRESETS = [
    ("tg", "📡 Telegram", tg),
    ("intitle", "🔎 intitle", intitle),
    ("inurl", "🔗 inurl", inurl),
    ("pdf", "📄 PDF", pdf),
    ("gov", "🏛️ .gov", gov),
    ("edu", "🎓 .edu", edu),
    ("pastebin", "📋 Pastebin", pastebin),
]


# --------------------------------------------------------------------------
# Backends (live test 2026-11-19, JIN-Agent UA) — jo na chale auto=False
# --------------------------------------------------------------------------

DORK_BACKENDS = [
    {"key": "dork-bing", "name": "Bing", "auto": True,
     "url": "https://www.bing.com/search?q={q}",
     "note": "Live: dork qabool, asli results."},
    {"key": "dork-mojeek", "name": "Mojeek", "auto": False,
     "url": "https://www.mojeek.com/search?q={q}",
     "note": "Live: anti-bot captcha — auto=False."},
    {"key": "dork-ddg-lite", "name": "DuckDuckGo Lite", "auto": False,
     "url": "https://lite.duckduckgo.com/lite/?q={q}",
     "note": "Live: HTTP 202 anomaly — auto=False."},
    {"key": "dork-startpage", "name": "Startpage", "auto": False,
     "url": "https://www.startpage.com/sp/search?query={q}",
     "note": "Live: Anubis anti-bot challenge — auto=False."},
    {"key": "dork-ecosia", "name": "Ecosia", "auto": False,
     "url": "https://www.ecosia.org/search?q={q}",
     "note": "Live: HTTP 403 unusual traffic — auto=False."},
    {"key": "dork-google", "name": "Google (gbv=1)", "auto": False,
     "url": "https://www.google.com/search?q={q}&gbv=1&hl=en",
     "note": "Live: JS shell, 0 result — auto=False."},
]


def working_backends() -> list[dict]:
    return [b for b in DORK_BACKENDS if b.get("auto")]


def backend_status() -> list[dict]:
    return [{"key": b["key"], "name": b["name"], "ok": bool(b.get("auto")),
             "note": b.get("note", "")} for b in DORK_BACKENDS]


def backend_url(backend: dict, dork: str) -> str:
    return str(backend.get("url") or "").replace(
        "{q}", urllib.parse.quote(str(dork or "")[:300]))


# --------------------------------------------------------------------------
# Bing result parser (ck/a base64) — dork results ke liye
# --------------------------------------------------------------------------

_BING_TOKEN_RE = re.compile(r"u=a1([A-Za-z0-9_\-]+)")
_BING_BLOCK_RE = re.compile(r'<li class="b_algo".*?</li>', re.S)
_TAG_RE = re.compile(r"<[^>]+>")


def _decode_bing(token: str) -> str:
    s = str(token or "").strip()
    if not s:
        return ""
    s += "=" * (-len(s) % 4)
    try:
        raw = base64.b64decode(s, altchars=b"-_", validate=True)
        return raw.decode("utf-8", "replace")
    except Exception:
        return ""


def parse_bing_results(html: str, limit: int = 10) -> list[dict]:
    """Bing HTML se dork results (title + asli URL)."""
    out = []
    for block in _BING_BLOCK_RE.findall(str(html or "")):
        m = re.search(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', block, re.S)
        if not m:
            continue
        href = m.group(1)
        if "bing.com/ck/a" in href:
            tok = _BING_TOKEN_RE.search(href)
            href = _decode_bing(tok.group(1)) if tok else ""
        title = util.clean_text(_TAG_RE.sub(" ", m.group(2)), 240)
        if href.startswith(("http://", "https://")) and title:
            out.append({"title": title, "url": href})
        if len(out) >= int(limit):
            break
    return out


# --------------------------------------------------------------------------
# Render + optional live search
# --------------------------------------------------------------------------

def onion_link(query: str) -> dict:
    """Onion dork — sirf link, fetch NAHI (policy.DARK_WEB_RULE)."""
    q = urllib.parse.quote(str(query or "")[:150])
    return {"title": "Ahmia — onion search (Tor browser me kholein)",
            "url": "https://ahmia.fi/search/?q=" + q,
            "note": policy.DARK_WEB_RULE}


def render(query: str, results: list[dict] | None = None) -> str:
    """`/dork` ka message — presets + backend links + status."""
    q = str(query or "").strip()
    lines = [f"🔍 Dork: {util.truncate(q, 120)}", ""]
    engines = working_backends()
    for key, label, fn in DORK_PRESETS:
        dork = fn(q)
        lines.append(f"• {label}: {dork}")
        for b in engines[:1]:
            lines.append(f"  {backend_url(b, dork)}")
    onion = onion_link(q)
    lines += ["", f"🕶️ Onion (sirf link, fetch nahi): {onion['url']}"]
    if results:
        lines += ["", "🌐 Live results:"]
        for i, r in enumerate(results[:5], 1):
            lines.append(f"{i}. {util.truncate(str(r.get('title') or ''), 80)}")
            lines.append(f"   {r.get('url')}")
    elif engines:
        lines += ["", "🌐 Live results: is dafa nahi mile (backend block/anti-bot)."]
    lines += ["", "📋 Dork backend:"] + [
        f"  {'✓' if s['ok'] else '✗'} {s['name']}: {s['note']}"
        for s in backend_status()]
    return "\n".join(lines)


def search(dork: str, cfg: dict | None = None, limit: int = 8) -> list[dict]:
    """Pehle kaam karne wale backend (Bing) se dork results. Fail par []."""
    engines = working_backends()
    if not engines:
        return []
    from . import adapters
    try:
        html = adapters.fetch(backend_url(engines[0], dork), cfg or {})
    except Exception:
        return []
    return parse_bing_results(html, limit)


def selftest() -> dict:
    """Network-free invariants (drift gate)."""
    checks = [
        {"name": "tg", "ok": tg("android") ==
         'site:t.me/s android -twitter -instagram', "detail": tg("android")},
        {"name": "pdf", "ok": pdf("android") == 'filetype:pdf "android"',
         "detail": pdf("android")},
        {"name": "exclude", "ok": exclude("q", ("twitter", "-instagram")) ==
         "q -twitter -instagram", "detail": exclude("q", ("twitter", "-instagram"))},
        {"name": "parse", "ok": bool(parse_bing_results(
            '<li class="b_algo"><a href="https://www.bing.com/ck/a?u=a1'
            'aHR0cHM6Ly9leGFtcGxlLmNvbS94">Example</a></li>')),
         "detail": "bing ck/a decode"},
        {"name": "backends", "ok": len(working_backends()) >= 1,
         "detail": str(len(working_backends()))},
        {"name": "onion_link_only", "ok": "onion" not in onion_link("x")["url"],
         "detail": onion_link("x")["url"][:40]},
    ]
    return {"ok": all(c["ok"] for c in checks), "checks": checks}
