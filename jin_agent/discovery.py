"""P43 - Provider-agnostic Telegram discovery layer.

`channels.py` ke HTML parsers (``parse_rightdao_html`` / ``parse_lyzem_html`` /
``parse_bing_html`` / ``parse_ddg_html``) istemal karte hue yahan **engine kram,
per-provider cache aur fan-out** mojood hai. Net result ``channels.web_search_probe``
ke liye hi hai — ye module discovery provider ko alag interface deta hai taake
naye provider (Telemetr / tgAtlas / MTProto) bina ``channels`` badle jude jaa saken.

Koi nayi third-party dependency NAHI. Rate limit ``adapters.fetch`` ke andar
(``ratelimit``) hi lagi hai; yahan sirf chhota TTL cache hai taake ek hi query
ka dobara probe na ho.
"""

from __future__ import annotations

import html as _html
import re
import time
import urllib.parse

from . import adapters, channels, config

#: Discovery engine ka kram — pehle jo results de, usi se handles milte hain.
PROVIDERS = ("rightdao", "lyzem", "bing", "ddg-html", "ddg-lite")

DEFAULT_CACHE_TTL = 900.0

_CACHE: dict[str, tuple[float, dict]] = {}

_URL_RE = re.compile(r"https?://t\.me/(?:s/)?([A-Za-z0-9_]{3,40})(?:/(\d+))?")


def cache_ttl(cfg: dict | None = None) -> float:
    """Discovery cache TTL (``discovery_cache_seconds``, default 900s).

    ``0`` ya manfi = cache band. Turant purana cache bhi saaf ho jata hai.
    """
    try:
        raw = (cfg or config.load()).get("discovery_cache_seconds")
        return max(0.0, float(DEFAULT_CACHE_TTL if raw in (None, "") else raw))
    except (TypeError, ValueError):
        return DEFAULT_CACHE_TTL


def _key(providers, query: str) -> str:
    return "|".join(list(providers) + [str(query or "").strip().lower()])


def cache_get(key: str, cfg: dict | None = None) -> dict | None:
    ttl = cache_ttl(cfg)
    hit = _CACHE.get(key)
    if not hit:
        return None
    ts, val = hit
    if ttl <= 0 or time.monotonic() - ts > ttl:
        _CACHE.pop(key, None)
        return None
    return val


def cache_put(key: str, value: dict, cfg: dict | None = None) -> None:
    if cache_ttl(cfg) <= 0:
        return
    if len(_CACHE) > 512:
        _CACHE.clear()
    _CACHE[key] = (time.monotonic(), value)


def clear_cache() -> None:
    """Cache khali karo (tests + ``/selftest`` ke liye)."""
    _CACHE.clear()


def _engines(query: str, providers) -> list[tuple[str, str, str]]:
    """Provider naam -> (name, url, kind)."""
    q = urllib.parse.quote("site:t.me " + str(query)[:120])
    ddg_q = urllib.parse.quote("site:t.me/s " + str(query)[:120])
    raw_q = urllib.parse.quote(str(query)[:120])
    table = {
        "rightdao": ("rightdao", channels.RIGHTDAO_SEARCH_URL + q, "rightdao"),
        "lyzem": ("lyzem", channels.LYZEM_SEARCH_URL + raw_q, "lyzem"),
        "bing": ("bing", channels.BING_SEARCH_URL + q, "bing"),
        "ddg-html": ("ddg-html", channels.DDG_HTML_URL + ddg_q, "ddg-html"),
        "ddg-lite": ("ddg-lite", channels.DDG_LITE_URL + ddg_q, "ddg-lite"),
    }
    return [table[p] for p in providers if p in table]


def _parse(kind: str, html: str) -> tuple[list[str], bool]:
    """(handles, anomaly) — anomaly matlab engine ne asli results hi nahi diye."""
    if kind == "rightdao":
        return channels.parse_rightdao_html(html), not channels.rightdao_has_results(html)
    if kind == "lyzem":
        recs = channels.parse_lyzem_html(html)
        return [r["handle"] for r in recs], not channels.lyzem_has_results(html)
    if kind == "bing":
        hs = channels.parse_bing_html(html)
        return hs, not channels.bing_has_results(html)
    if kind == "ddg-html":
        hs = channels.parse_ddg_html(html)
        return hs, not hs
    hs = channels.extract_handles(html)
    return hs, not hs


def _probe_merge(query: str, cfg: dict, provs: tuple,
                 tried: list[dict]) -> dict:
    """Saare providers chalao aur handles ikhatte karo (source diversity).

    Koi provider block/anomaly ho to usay chhor do — baqi se handles lo.
    """
    handles: list[str] = []
    seen: set[str] = set()
    engines: list[str] = []
    sources: dict[str, str] = {}
    records: list[dict] = []
    saw_results = False
    for name, url, kind in _engines(query, provs):
        try:
            html = adapters.fetch(url, cfg)
        except Exception as exc:
            tried.append({"engine": name, "ok": False,
                          "error": type(exc).__name__})
            continue
        hs, anomaly = _parse(kind, html)
        tried.append({"engine": name, "ok": True, "handles": len(hs),
                      "anomaly": bool(anomaly)})
        if anomaly or not hs:
            continue
        saw_results = True
        engines.append(name)
        if kind == "lyzem":
            try:
                records = channels.parse_lyzem_html(html)
            except Exception:
                records = []
        for h in hs:
            if h not in seen:
                seen.add(h)
                handles.append(h)
            sources.setdefault(h.lower(), name)
    if not handles:
        error = ("results me t.me channel nahi mila" if saw_results
                 else "kisi engine ne results nahi diye")
        return {"handles": [], "engine": "", "engines": [], "sources": {},
                "records": records,
                "candidates": 0, "anomaly": False, "error": error,
                "tried": tried, "cached": False}
    return {"handles": handles[:60], "engine": ", ".join(engines),
            "engines": engines, "sources": sources, "records": records,
            "candidates": len(handles),
            "anomaly": False, "error": "", "tried": tried, "cached": False}


def probe(query: str, cfg: dict | None = None,
          providers=None, merge: bool = False) -> dict:
    """Search engines ko kram se azmo; pehla asli results wala jeette hai.

    ``merge=True`` par saare providers chalte hain aur handles ikhatte hote
    hain (source diversity) — ``engine`` us waqt ``, `` se jura hota hai.
    Cache ``discovery_cache_seconds`` (default 900s) par band hai.
    """
    cfg = cfg or config.load()
    provs = tuple(providers or PROVIDERS)
    key = _key(provs, query) + ("|merge" if merge else "")
    hit = cache_get(key, cfg)
    if hit is not None:
        return dict(hit, cached=True)
    if merge:
        out = _probe_merge(query, cfg, provs, tried=[])
        cache_put(key, out, cfg)
        return out

    tried: list[dict] = []
    saw_anomaly = False
    saw_results = False
    for name, url, kind in _engines(query, provs):
        try:
            html = adapters.fetch(url, cfg)
        except Exception as exc:
            tried.append({"engine": name, "ok": False,
                          "error": type(exc).__name__})
            continue
        handles, anomaly = _parse(kind, html)
        tried.append({"engine": name, "ok": True, "handles": len(handles),
                      "anomaly": bool(anomaly)})
        if anomaly:
            saw_anomaly = True
            continue
        saw_results = True
        if handles:
            out = {"handles": handles[:60], "engine": name,
                   "sources": {h.lower(): name for h in handles[:60]},
                   "records": [],
                   "candidates": len(handles), "anomaly": False,
                   "error": "", "tried": tried, "cached": False}
            cache_put(key, out, cfg)
            return out
        # results mila magar t.me handle nahi — agla engine azmo

    if saw_results:
        error = "results me t.me channel nahi mila"
        engine = channels._engine_from_tried(tried)
    elif saw_anomaly:
        error = "search engine ne results nahi diye (anti-bot)"
        engine = ""
    else:
        error = "kisi engine ne results nahi diye"
        engine = ""
    out = {"handles": [], "engine": engine, "engines": [], "sources": {},
           "records": [], "candidates": 0,
           "anomaly": saw_anomaly and not saw_results,
           "error": error, "tried": tried, "cached": False}
    cache_put(key, out, cfg)
    return out


def lyzem_records(query: str, cfg: dict | None = None) -> list[dict]:
    """Lyzem se **poori records** (type/handle/title/descr/url) — kache me.

    ``/explore`` ke cards me post preview + source link dikhane ke liye.
    Fail par ``[]`` (jhoot nahi).
    """
    cfg = cfg or config.load()
    key = "lyzem|" + str(query or "").strip().lower()
    hit = cache_get(key, cfg)
    if hit is not None:
        return hit["records"]
    url = channels.LYZEM_SEARCH_URL + urllib.parse.quote(str(query)[:120])
    try:
        html = adapters.fetch(url, cfg)
    except Exception:
        cache_put(key, {"records": []}, cfg)
        return []
    recs = channels.parse_lyzem_html(html)
    cache_put(key, {"records": recs}, cfg)
    return recs


def handle_from_url(url: str) -> str:
    """``https://t.me/<handle>(/<msg_id>)`` -> handle."""
    m = _URL_RE.search(str(url or ""))
    return m.group(1) if m else ""


def clean_text(text: str) -> str:
    """HTML tags hatao, entities theek karo, whitespace collapse karo."""
    s = re.sub(r"<[^>]+>", " ", str(text or ""))
    s = _html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()
