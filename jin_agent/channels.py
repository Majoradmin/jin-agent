"""P23: Telegram channel auto-discovery, liveness probe, informative scoring.

Aap ki request (2026-11-15): user channel ke naam nahi batayega - agent KHUD
research kare, informative channels dhondta rahe, khud add kare, aur check
kare ke channel dead hai ya working.

Legal boundary (Sahulat & Safe Service Policy / C13, unchanged):
- Sirf PUBLIC ``t.me/s/<channel>`` preview pages fetch hoti hain - wahi
  existing ``adapters.fetch`` contract (SSRF allowlist, timeout, size cap).
- Koi login, private group, userbot, MTProto ya historical scrape NAHI.
- Dead channel kabhi hard-delete nahi: ``status='dead'`` archive hota hai.

Discovery sources (sab public, language-agnostic):
1. WEB SEARCH: public search engine HTML par ``site:t.me/s <topic>`` - ye
   bootstrap hai (naye agent ke paas 0 channels hon to bhi dhoond lega).
2. PREVIEW HARVEST: fetched channel previews ke posts ke andar jo aur
   ``t.me/<handle>`` mentions milein (channels aapas me promote karte hain).
3. ARCHIVE HARVEST: firehose archive ke items ke text se t.me links.

Scoring (0-10, kisi bhi zaban ki channel par lagti hai): recency + post
volume + text richness + subscribers + topic keyword relevance.
"""

from __future__ import annotations

import base64
import concurrent.futures
import html as _html
import json
import math
import os
import re
import time
import urllib.parse

from . import adapters, config, store, util

VERSION = "1.0"

HANDLE_RE = re.compile(r"(?:t\.me|telegram\.me)/(?:s/)?@?([A-Za-z0-9_]{3,40})")
EXCLUDE_HANDLES = {"joinchat", "share", "proxy", "addstickers", "addlist",
                   "contact", "todo", "setlanguage", "premium", "telegram",
                   "telegramtips", "tdesktop", "android", "ios", "macos",
                   "login", "socks"}

# P39/P42: channel discovery ke liye keyless search engines (kram maloom).
# RightDAO pehle (Bing ``site:`` ignore karta hai, DDG anomaly deta hai),
# phir Bing, phir DDG html, phir DDG lite.
RIGHTDAO_SEARCH_URL = "https://rightdao.com/search?q="
# P43: Lyzem — Telegram-wide search engine (channel/group/bot/post/article),
# bina login, bina API key.
LYZEM_SEARCH_URL = "https://lyzem.com/search?q="
LYZEM_RESULT_RE = re.compile(r'<ul class="search-results">')
BING_SEARCH_URL = "https://www.bing.com/search?q="
DDG_HTML_URL = "https://html.duckduckgo.com/html/?q="
DDG_LITE_URL = "https://lite.duckduckgo.com/lite/?q="
RIGHTDAO_RESULT_RE = re.compile(r'class="item"')
BING_RESULT_RE = re.compile(r'<li class="b_algo"')
BING_TOKEN_RE = re.compile(r"u=a1([A-Za-z0-9_\-]+)")
DDG_UDDG_RE = re.compile(r"uddg=([^&\"']+)")

SCHEMA = """
CREATE TABLE IF NOT EXISTS tg_channels (
  channel TEXT PRIMARY KEY,
  status TEXT NOT NULL DEFAULT 'active',
  origin TEXT NOT NULL DEFAULT 'auto',
  added_at INTEGER NOT NULL DEFAULT 0,
  last_checked INTEGER NOT NULL DEFAULT 0,
  last_post_at TEXT NOT NULL DEFAULT '',
  post_count INTEGER NOT NULL DEFAULT 0,
  subscribers TEXT NOT NULL DEFAULT '',
  title TEXT NOT NULL DEFAULT '',
  score INTEGER NOT NULL DEFAULT 0,
  note TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS tg_candidates (
  handle TEXT PRIMARY KEY,
  found_at INTEGER NOT NULL DEFAULT 0,
  probed_at INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS tg_sites (
  url TEXT PRIMARY KEY,
  title TEXT NOT NULL DEFAULT '',
  source TEXT NOT NULL DEFAULT '',
  topic TEXT NOT NULL DEFAULT '',
  added_at INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS tg_discovery_state (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL DEFAULT '',
  updated_at INTEGER NOT NULL DEFAULT 0
);
"""

TOPIC_KEYWORDS = [
    "mobile firmware", "android security", "gsm repair", "mediatek qualcomm",
    "osint", "cyber security", "ai tools", "tech news",
]

RECHECK_AFTER_SECONDS = 3 * 24 * 3600  # liveness re-check har 3 din


# --------------------------------------------------------------------------
# Registry (tg_channels) - archive-not-delete
# --------------------------------------------------------------------------

def ensure_table() -> None:
    with store.session() as con:
        con.executescript(SCHEMA)


def list_channels(status: str | None = None) -> list[dict]:
    ensure_table()
    with store.session() as con:
        if status:
            rows = con.execute(
                "SELECT * FROM tg_channels WHERE status=? ORDER BY score DESC, channel",
                (status,)).fetchall()
        else:
            rows = con.execute(
                "SELECT * FROM tg_channels ORDER BY score DESC, channel").fetchall()
    return [dict(r) for r in rows]


def active_channels() -> list[str]:
    ensure_table()
    with store.session() as con:
        rows = con.execute(
            "SELECT channel FROM tg_channels WHERE status='active' "
            "ORDER BY score DESC").fetchall()
    return [r["channel"] for r in rows]


def counts() -> dict:
    ensure_table()
    with store.session() as con:
        rows = con.execute(
            "SELECT status, COUNT(*) AS n FROM tg_channels GROUP BY status"
        ).fetchall()
    out = {"active": 0, "dead": 0, "archived": 0}
    for r in rows:
        out[str(r["status"])] = int(r["n"])
    out["total"] = sum(out.values())
    return out


def dead_ttl_days() -> int:
    """Dead channel registry TTL (din). Default 30, env ``JIN_AGENT_CHANNEL_DEAD_TTL_DAYS``.

    Competitor pattern: silent/dead channels ka record time-to-live ke baad
    clean karo (14/30/90 din thresholds) taake registry unbounded na barhe.
    """
    try:
        return max(1, int(str(os.environ.get("JIN_AGENT_CHANNEL_DEAD_TTL_DAYS", "30")
                               or 30)))
    except (TypeError, ValueError):
        return 30


def cleanup_dead(threshold_days: int | None = None) -> int:
    """``status='dead'`` aur ``last_checked`` TTL purani rows delete karo.

    Archive-not-delete policy ka istisna sirf retention ke liye: dead registry
    rows jinki aakhri probe TTL (default 30 din) barhogar ho chuki ho unhe
    hatao taake table bounded rahe. Active/archived rows ko chhua nahi jata.
    """
    ensure_table()
    ttl = dead_ttl_days() if threshold_days is None else max(1, int(threshold_days))
    cutoff = util.epoch() - ttl * 86400
    with store.session() as con:
        cur = con.execute(
            "DELETE FROM tg_channels WHERE status='dead' AND last_checked<?",
            (cutoff,))
        return int(cur.rowcount)


def stale_ttl_days() -> int:
    """Active channel ke liye 'stale' (khamosh) window (din).

    Default 30, env ``JIN_AGENT_CHANNEL_STALE_DAYS``. Channel alive magar
    is dauran check nahi hua to ``status='stale'`` mark hota hai.
    """
    try:
        return max(1, int(str(os.environ.get("JIN_AGENT_CHANNEL_STALE_DAYS", "30")
                               or 30)))
    except (TypeError, ValueError):
        return 30


def mark_stale_channels(ttl_days: int | None = None) -> int:
    """Active channels jinki aakhri check ``ttl_days`` purani ho chuki ho.

    ``status='stale'`` mark karo (delete nahi — registry bounded rehta hai).
    """
    ensure_table()
    ttl = stale_ttl_days() if ttl_days is None else max(1, int(ttl_days))
    cutoff = util.epoch() - ttl * 86400
    with store.session() as con:
        cur = con.execute(
            "UPDATE tg_channels SET status='stale' "
            "WHERE status='active' AND last_checked<?", (cutoff,))
        return int(cur.rowcount)


def add_channel(channel: str, origin: str = "manual", note: str = "") -> dict:
    """Insert (ya existing row return) without probing - probe alag step hai."""
    channel = clean_handle(channel)
    if not channel:
        raise ValueError("Channel handle ghalat hai (sirf letters/numbers/_)")
    ensure_table()
    with store.session() as con:
        con.execute(
            "INSERT OR IGNORE INTO tg_channels(channel, status, origin, added_at, note) "
            "VALUES(?,?,?,?,?)",
            (channel, "active", "manual" if origin == "manual" else "auto",
             util.epoch(), note[:200]))
        row = con.execute("SELECT * FROM tg_channels WHERE channel=?",
                          (channel,)).fetchone()
    return dict(row)


def remove_channel(channel: str) -> dict:
    """Archive, never delete (D36 pattern)."""
    clean = clean_handle(channel)
    ensure_table()
    with store.session() as con:
        cur = con.execute(
            "UPDATE tg_channels SET status='archived', score=0, note='archived "
            "by user' WHERE channel=?", (clean,))
    if cur.rowcount == 0:
        raise ValueError("Channel registry me nahi mila")
    return {"channel": clean, "status": "archived"}


# --------------------------------------------------------------------------
# Sites memory (explore confirm gate) — archive-not-delete, local table
# --------------------------------------------------------------------------

def add_site(url: str, title: str = "", source: str = "",
             topic: str = "") -> dict:
    """Explore ke site/source ko memory me rakho (dobara rakhna = no-op)."""
    url = str(url or "").strip()
    if not url.startswith(("http://", "https://")):
        raise ValueError("Site URL ghalat hai")
    ensure_table()
    with store.session() as con:
        con.execute(
            "INSERT OR IGNORE INTO tg_sites(url, title, source, topic, added_at) "
            "VALUES(?,?,?,?,?)",
            (url, str(title or "")[:200], str(source or "")[:80],
             str(topic or "")[:120], util.epoch()))
        row = con.execute("SELECT * FROM tg_sites WHERE url=?", (url,)).fetchone()
    return dict(row)


def list_sites(limit: int = 50) -> list[dict]:
    ensure_table()
    with store.session() as con:
        rows = con.execute(
            "SELECT * FROM tg_sites ORDER BY added_at DESC LIMIT ?",
            (max(1, int(limit)),)).fetchall()
    return [dict(r) for r in rows]


def site_counts() -> dict:
    ensure_table()
    week_ago = util.epoch() - 7 * 86400
    with store.session() as con:
        row = con.execute("SELECT COUNT(*) FROM tg_sites").fetchone()
        wk = con.execute("SELECT COUNT(*) FROM tg_sites WHERE added_at>=?",
                         (week_ago,)).fetchone()
    return {"total": int(row[0]) if row else 0,
            "week": int(wk[0]) if wk else 0}


def save_discovery_state(state: dict) -> None:
    """Aakhri discovery ka hisaab (``/status`` ke liye) — additive, local."""
    ensure_table()
    with store.session() as con:
        con.execute(
            "INSERT OR REPLACE INTO tg_discovery_state(key, value, updated_at) "
            "VALUES('last', ?, ?)",
            (json.dumps(state, ensure_ascii=False)[:4000], util.epoch()))


def last_discovery_state() -> dict:
    """Aakhri discovery ka hisaab; na ho to {}."""
    ensure_table()
    with store.session() as con:
        row = con.execute(
            "SELECT value, updated_at FROM tg_discovery_state WHERE key='last'"
        ).fetchone()
    if not row:
        return {}
    try:
        return json.loads(row["value"] or "{}")
    except ValueError:
        return {}


def add_candidates(handles: list[str]) -> int:
    """Discovery pool me naye handles (existing/manual ko chhor kar)."""
    ensure_table()
    known = {r["channel"] for r in list_channels()}
    manual = {clean_handle(c) for c in (config.load().get("telegram_channels") or [])}
    n = 0
    with store.session() as con:
        for h in handles:
            clean = clean_handle(h)
            if not clean or clean in known or clean in manual:
                continue
            cur = con.execute(
                "INSERT OR IGNORE INTO tg_candidates(handle, found_at) VALUES(?,?)",
                (clean, util.epoch()))
            n += cur.rowcount
    return n


def pending_candidates() -> int:
    """Un-probed candidate handles ki tadad (``/status`` ka explore block)."""
    ensure_table()
    with store.session() as con:
        row = con.execute(
            "SELECT COUNT(*) FROM tg_candidates WHERE probed_at=0").fetchone()
    return int(row[0]) if row else 0


def take_candidates(limit: int) -> list[str]:
    """Pool se un-probed handles (consume nahi - probed_at mark hota hai)."""
    ensure_table()
    with store.session() as con:
        rows = con.execute(
            "SELECT handle FROM tg_candidates WHERE probed_at=0 ORDER BY found_at "
            "LIMIT ?", (max(1, int(limit)),)).fetchall()
        for r in rows:
            con.execute("UPDATE tg_candidates SET probed_at=? WHERE handle=?",
                        (util.epoch(), r["handle"]))
    return [r["handle"] for r in rows]


def clean_handle(raw: str) -> str:
    s = str(raw or "").strip()
    m = HANDLE_RE.search(s)
    if m:
        return m.group(1)
    bare = s.lstrip("@")
    if re.fullmatch(r"[A-Za-z0-9_]{3,40}", bare):
        return bare
    return ""


# --------------------------------------------------------------------------
# Candidate extraction (language agnostic)
# --------------------------------------------------------------------------

def extract_handles(text: str) -> list[str]:
    out, seen = [], set()
    for m in HANDLE_RE.finditer(str(text or "")):
        h = m.group(1)
        if h.lower() in EXCLUDE_HANDLES or h in seen:
            continue
        if re.fullmatch(r"[A-Za-z0-9_]{3,40}", h):
            seen.add(h)
            out.append(h)
    return out


def harvest_archive(cfg: dict | None = None, query: str = "") -> list[str]:
    """Firehose archive ke items ke text se t.me candidates.

    ``query`` diya ho to sirf woh items jinke text me query ke lafz hon —
    taake topic-driven explore usi topic par candidates de (neutral rotate
    ke baghair).
    """
    cfg = cfg or config.load()
    words = set(util.terms(query, 20)) if str(query or "").strip() else set()
    out, seen = [], set()
    try:
        with store.session() as con:
            rows = con.execute(
                "SELECT title, excerpt, body FROM items LIMIT 8000").fetchall()
    except Exception:
        return []
    for r in rows:
        text = " ".join([r["title"] or "", r["excerpt"] or "", r["body"] or ""])
        if words and not any(w in text.lower() for w in words):
            continue
        for h in extract_handles(text):
            if h not in seen:
                seen.add(h)
                out.append(h)
    return out[:400]


def decode_bing_url(token: str) -> str:
    """Bing ``ck/a`` token (urlsafe base64) ko asli URL me decode karo.

    Bing result links ``https://www.bing.com/ck/a?...&u=a1<token>`` me encoded
    hote hain. Token urlsafe base64 hai (padding kabhi-kabhi ghair-mukammal).
    """
    s = str(token or "").strip()
    if not s:
        return ""
    s += "=" * (-len(s) % 4)
    try:
        raw = base64.b64decode(s, altchars=b"-_", validate=True)
        return raw.decode("utf-8", "replace")
    except Exception:
        return ""


def parse_bing_html(html: str) -> list[str]:
    """Bing HTML se t.me handles — pehle ``ck/a`` decode, phir raw links."""
    out, seen = [], set()
    for m in BING_TOKEN_RE.finditer(str(html or "")):
        for h in extract_handles(decode_bing_url(m.group(1))):
            if h not in seen:
                seen.add(h)
                out.append(h)
    for h in extract_handles(html):
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out


def bing_has_results(html: str) -> bool:
    """Bing ne asli results diye? Anti-bot anomaly page par ``b_algo`` nahi hota."""
    return bool(BING_RESULT_RE.search(str(html or "")))


def parse_rightdao_html(html: str) -> list[str]:
    """RightDAO HTML se t.me handles — wahi ``extract_handles`` (noise filter)."""
    return extract_handles(html)


def rightdao_has_results(html: str) -> bool:
    """RightDAO ne asli results diye? Anti-bot/blocked page par ``class="item"``
    nahi hota. Marker na mile to ``bool(handles)`` fallback (b_algo jaisa)."""
    s = str(html or "")
    if RIGHTDAO_RESULT_RE.search(s):
        return True
    return bool(parse_rightdao_html(s))


def parse_ddg_html(html: str) -> list[str]:
    """DDG html results (``uddg=`` wrapping) se t.me handles."""
    out, seen = [], set()
    for m in DDG_UDDG_RE.finditer(str(html or "")):
        try:
            target = urllib.parse.unquote(m.group(1))
        except Exception:
            continue
        for h in extract_handles(target):
            if h not in seen:
                seen.add(h)
                out.append(h)
    for h in extract_handles(html):
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out


def lyzem_has_results(html: str) -> bool:
    """Lyzem ne asli results diye? Anti-bot/404 page par ``search-results`` nahi."""
    return bool(LYZEM_RESULT_RE.search(str(html or "")))


def parse_lyzem_html(html: str) -> list[dict]:
    """Lyzem search page se records: type/handle/title/descr/url/msg_id.

    Lyzem ek Telegram-wide search engine hai (lyzem.com) — bina login, bina key.
    Har result ke saath ``title="channel|group|bot|post|article|message"`` aur
    ``https://t.me/<handle>(/<msg_id>)`` link hota hai. Posts ke liye title
    aksar khaali hota hai, is liye descr se fallback.
    """
    s = str(html or "")
    block = re.search(r'<ul class="search-results">(.*?)</ul>', s, re.S)
    if not block:
        return []
    out: list[dict] = []
    seen: set[str] = set()
    for item in re.findall(r'<li class="search-result">(.*?)</li>',
                           block.group(1), re.S):
        t = re.search(r'search-result-type-wrapper\s*"\s+title="([^"]+)"', item)
        kind = (t.group(1) if t else "").strip().lower()
        a = re.search(
            r'search-result-title">\s*<a href="(https?://t\.me/[A-Za-z0-9_]+'
            r'(?:/\d+)?)"[^>]*>(.*?)</a>', item, re.S)
        url = _html.unescape(a.group(1)) if a else ""
        title = re.sub(r"\s+", " ", _html.unescape(
            re.sub(r"<[^>]+>", " ", a.group(2) or ""))).strip() if a else ""
        d = re.search(r'search-result-descr">\s*<a[^>]*>(.*?)</a>', item, re.S)
        descr = re.sub(r"\s+", " ", _html.unescape(
            re.sub(r"<[^>]+>", " ", d.group(1) or ""))).strip() if d else ""
        if not url:
            continue
        m = HANDLE_RE.search(url)
        handle = m.group(1) if m else ""
        if not handle or handle in seen:
            continue
        seen.add(handle)
        mid = re.search(r"/(\d+)$", url)
        out.append({"handle": handle, "url": url, "kind": kind,
                    "title": title or descr[:120], "descr": descr,
                    "msg_id": mid.group(1) if mid else ""})
    return out


def _engine_from_tried(tried: list[dict]) -> str:
    """``tried`` se sahi engine: pehla ``ok`` jis me anomaly nahi.

    Results mile magar t.me handle na mile, tab bhi ``/status`` ko kaunsa
    engine chal para hona chahiye — ``tried`` kram (Bing -> DDG) se pehla.
    """
    for t in tried or []:
        if isinstance(t, dict) and t.get("ok") and not t.get("anomaly"):
            name = str(t.get("engine") or "").strip()
            if name:
                return name
    return ""


def web_search_probe(query: str, cfg: dict | None = None,
                     providers=None, merge: bool = False) -> dict:
    """Provider-agnostic discovery probe — ``discovery.probe`` ka wrapper.

    Engine kram: RightDAO -> **Lyzem** -> Bing -> DDG html -> DDG lite (P43).
    Returns ``{"handles", "engine", "candidates", "anomaly", "error", "tried",
    "cached"}``. Cache ``discovery_cache_seconds`` (default 900s).
    """
    from . import discovery
    return discovery.probe(query, cfg, providers=providers, merge=merge)


def merge_web_probe(infos: list[dict]) -> dict:
    """Kai search probes (neutral rotation) ka ik hisaab."""
    infos = [i for i in (infos or []) if isinstance(i, dict)]
    if not infos:
        return {"engine": "", "candidates": 0, "anomaly": False,
                "error": "", "tried": []}
    engine = ""
    for i in infos:
        if i.get("engine"):
            engine = str(i["engine"])
            break
    if not engine:
        # Probe ne engine na bharna chhoda ho to tried se hi hisaab karo.
        engine = _engine_from_tried(
            [t for i in infos for t in (i.get("tried") or [])])
    error = ""
    for i in infos:
        if i.get("error"):
            error = str(i["error"])
    return {
        "engine": engine,
        "candidates": sum(int(i.get("candidates") or 0) for i in infos),
        "anomaly": all(bool(i.get("anomaly")) for i in infos),
        "error": error,
        "tried": [t for i in infos for t in (i.get("tried") or [])],
    }


def web_search_candidates(query: str, cfg: dict | None = None,
                          info: dict | None = None, merge: bool = False,
                          providers=None) -> list[str]:
    """Public search engine HTML par t.me/s search (RightDAO -> Lyzem -> Bing -> DDG).

    ``info`` dict diya ho to us me probe ka hisaab (engine/anomaly/error)
    bhar diya jata hai — ``run_discovery`` honest status ke liye istemal karta
    hai. Anti-bot anomaly par khali list, agla engine apne aap azmo.

    ``merge=True`` par saare providers se handles ikhatte hain (diversity).
    """
    probe = web_search_probe(query, cfg, merge=merge, providers=providers)
    if isinstance(info, dict):
        info.clear()
        info.update(probe)
    return probe["handles"]


# --------------------------------------------------------------------------
# Liveness probe + scoring
# --------------------------------------------------------------------------

def parse_preview(html: str, channel: str) -> dict:
    """Preview HTML ko parse karo (network-free) — selftest bhi isi se guzarta hai."""
    clean = clean_handle(channel)
    posts = re.findall(r'data-post="[^"]+"', html)
    title = ""
    m = re.search(r'og:title" content="([^"]{1,120})"', html)
    if m:
        title = m.group(1)
    last_post_at = ""
    t = re.search(r'<time datetime="([^"]{10,40})"', html)
    if t:
        last_post_at = t.group(1)[:19].replace("T", " ")
    subscribers = ""
    s = re.search(r'og:description" content="([\d.,KMB ]{1,20})\s*(?:subscribers|members)"',
                  html) or re.search(r'([\d.,]+\s*[KMB]?)\s*subscribers', html)
    if s:
        subscribers = s.group(1).strip()
    texts = re.findall(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>',
                       html, re.S)
    avg_len = (sum(len(x) for x in texts) // len(texts)) if texts else 0
    # Preview harvest: is channel ke posts me jo aur channels mention hon
    harvested = extract_handles(" ".join(texts)[:20000])
    return {
        "channel": clean,
        "alive": bool(posts),
        "post_count": len(posts),
        "title": title,
        "last_post_at": last_post_at,
        "subscribers": subscribers,
        "avg_text_len": avg_len,
        "harvested": harvested[:30],
        "checked_at": util.epoch(),
    }


def probe(channel: str, cfg: dict | None = None) -> dict:
    """PUBLIC t.me/s/<channel> preview fetch -> alive/dead + stats."""
    cfg = cfg or config.load()
    clean = clean_handle(channel)
    if not clean:
        raise ValueError("Channel handle ghalat hai")
    html = adapters.fetch(f"https://t.me/s/{clean}", cfg)
    return parse_preview(html, clean)


# Parser-drift selftest fixture (known markers) — HTML structure badalne par ye
# fail hota hai, taake parser drift deploy se pehle pakde jaye.
SELFTEST_HTML = (
    '<meta property="og:title" content="Selftest Channel">'
    '<meta property="og:description" content="1.2K subscribers">'
    '<div data-post="selftest/1"></div><div data-post="selftest/2"></div>'
    '<time datetime="2026-11-18T10:00:00+00:00"></time>'
    '<div class="tgme_widget_message_text">Firmware news</div>'
)


def parser_selftest() -> dict:
    """Parser invariants ki network-free selftest (drift gate)."""
    rec = parse_preview(SELFTEST_HTML, "selftest_ch")
    sc = score(rec, config.load())
    checks = [
        {"name": "title", "ok": rec["title"] == "Selftest Channel",
         "detail": rec["title"][:40]},
        {"name": "posts", "ok": rec["post_count"] >= 2,
         "detail": str(rec["post_count"])},
        {"name": "subscribers", "ok": "1.2" in rec["subscribers"],
         "detail": rec["subscribers"]},
        {"name": "last_post", "ok": bool(rec["last_post_at"]),
         "detail": rec["last_post_at"]},
        {"name": "score_range", "ok": 0 <= sc <= 10, "detail": str(sc)},
    ]
    return {"ok": all(c["ok"] for c in checks), "checks": checks}


def _age_days(last_post_at: str) -> int:
    """``last_post_at`` (ISO) se din; na ho to 9999."""
    import datetime
    if not last_post_at:
        return 9999
    try:
        dt = datetime.datetime.fromisoformat(str(last_post_at).strip().replace(" ", "T"))
        return max(0, int((datetime.datetime.now(datetime.UTC)
                           - dt.replace(tzinfo=datetime.UTC)).total_seconds() // 86400))
    except Exception:
        return 9999


def _subscribers_value(raw: str) -> float:
    subs = str(raw or "").lower()
    try:
        val = float(re.sub(r"[^\d.]", "", subs) or 0)
    except ValueError:
        return 0.0
    if "m" in subs:
        val *= 1_000_000
    elif "k" in subs:
        val *= 1_000
    return val


def score(rec: dict, cfg: dict | None = None) -> int:
    """Informative score 0-10 — LOG-SCALE (tgden/chatcrawler methodology).

    Linear thresholds (posts>=10 +2, subs>=10k +2) bade channels ko
    over-reward karte the. Ab activity aur subscribers ``lg(1+x)`` par
    scale hote hain, taake 1M-subs channel 10k-subs se sirf thoda behtar
    awe. Recency/topic/text signals wahi rehte hain.
    """
    cfg = cfg or config.load()
    s = 0.0
    age_days = _age_days(rec.get("last_post_at") or "")
    if age_days <= 2:
        s += 4
    elif age_days <= 7:
        s += 3
    elif age_days <= 14:
        s += 2
    elif age_days <= 30:
        s += 1
    # activity: log-scale (posts 30 din preview se), 0.6*lg(1+posts30d)
    posts = int(rec.get("post_count") or 0)
    s += min(3.0, 0.8 * math.log1p(max(0, posts)))
    # subscribers: log-scale thresholds
    val = _subscribers_value(rec.get("subscribers") or "")
    if val >= 1_000_000:
        s += 3.0
    elif val >= 100_000:
        s += 2.5
    elif val >= 10_000:
        s += 2.0
    elif val >= 1_000:
        s += 1.2
    elif val >= 100:
        s += 0.6
    elif val > 0:
        s += 0.3 * math.log1p(val) / math.log(101)
    if int(rec.get("avg_text_len") or 0) >= 80:
        s += 1
    # topic relevance: keywords title ya (offline me) channel name par
    title = (str(rec.get("title") or "") + " " + str(rec.get("channel") or "")).lower()
    topics = [str(t).lower() for t in (cfg.get("topics") or [])]
    kws = {"firmware", "android", "security", "gsm", "osint", "ai", "tech",
           "news", "mobile", "telecom", "hack", "cyber", "mod", "rom"}
    for kw in kws:
        if kw in title:
            s += 1
            break
    for t in topics:
        words = [w for w in re.findall(r"[a-z]{4,}", t)]
        if any(w in title for w in words):
            s += 1
            break
    return max(0, min(10, round(s)))


def channel_signs(rec: dict, cfg: dict | None = None) -> dict:
    """Positive signals ka hisaab (kam-az-kam-3-signs gate).

    Returns ``{"signs": int, "recent": bool, "topic_match": bool}``.
    """
    cfg = cfg or config.load()
    age_days = _age_days(rec.get("last_post_at") or "")
    recent = age_days <= 30
    title = (str(rec.get("title") or "") + " " + str(rec.get("channel") or "")).lower()
    kws = {"firmware", "android", "security", "gsm", "osint", "ai", "tech",
           "news", "mobile", "telecom", "hack", "cyber", "mod", "rom"}
    topic_match = any(kw in title for kw in kws)
    if not topic_match:
        for t in [str(x).lower() for x in (cfg.get("topics") or [])]:
            words = [w for w in re.findall(r"[a-z]{4,}", t)]
            if any(w in title for w in words):
                topic_match = True
                break
    signs = sum([
        bool(rec.get("alive")),
        int(rec.get("post_count") or 0) > 0,
        _subscribers_value(rec.get("subscribers") or "") > 0,
        bool(recent),
        int(rec.get("avg_text_len") or 0) >= 80,
        bool(topic_match),
    ])
    return {"signs": int(signs), "recent": bool(recent),
            "topic_match": bool(topic_match)}


def check_channel(channel: str, cfg: dict | None = None) -> dict:
    """Ek channel probe karo, row update karo (dead -> archive, delete nahi)."""
    cfg = cfg or config.load()
    ensure_table()
    clean = clean_handle(channel)
    try:
        rec = probe(channel, cfg)
    except Exception as exc:
        # Existing active row network-blip par dead na karo; sirf note likho.
        with store.session() as con:
            exists = con.execute("SELECT 1 FROM tg_channels WHERE channel=?",
                                 (clean,)).fetchone()
            if not exists:
                con.execute(
                    "INSERT INTO tg_channels(channel, status, origin, "
                    "added_at, note) VALUES(?,?,?,?,?)",
                    (clean, "dead", "auto", util.epoch(),
                     f"probe error: {type(exc).__name__}"))
            else:
                con.execute(
                    "UPDATE tg_channels SET last_checked=?, note=? WHERE channel=?",
                    (util.epoch(), f"probe error: {type(exc).__name__}", clean))
        return {"channel": clean, "alive": False, "status": "dead",
                "score": 0, "error": type(exc).__name__,
                "note": f"probe error: {type(exc).__name__}", "harvested": []}
    sc = score(rec, cfg)
    info = channel_signs(rec, cfg)
    if not rec["alive"]:
        status = "dead"
        note = f"dead: {rec['post_count']} posts on preview"
    elif not info["recent"]:
        # 30-din rule: preview zinda ho magar aakhri post 30 din se purani.
        age = _age_days(rec.get("last_post_at") or "")
        status = "dead"
        note = f"dead: aakhri post {age} din purani (30-din rule)"
    elif info["signs"] < 3:
        status = "insufficient_data"
        note = f"insufficient_data: sirf {info['signs']} positive signs"
    else:
        status = "active"
        note = "auto-discovered liveness check"
    with store.session() as con:
        con.execute(
            "INSERT OR IGNORE INTO tg_channels(channel, status, origin, added_at) "
            "VALUES(?,?,?,?)", (rec["channel"], status, "auto", util.epoch()))
        con.execute(
            "UPDATE tg_channels SET status=?, last_checked=?, last_post_at=?, "
            "post_count=?, subscribers=?, title=?, score=?, note=? WHERE channel=?",
            (status, rec["checked_at"], rec["last_post_at"], rec["post_count"],
             rec["subscribers"], rec["title"], sc, note, rec["channel"]))
    # Preview harvest: is channel ke posts me mile aur channels pool me dalo
    try:
        add_candidates(rec.get("harvested") or [])
    except Exception:
        pass
    out = dict(rec)
    out["status"] = status
    out["score"] = sc
    out["note"] = note
    return out


# --------------------------------------------------------------------------
# Discovery cycle (scheduler / CLI / API se chalta hai)
# --------------------------------------------------------------------------

def run_discovery(cfg: dict | None = None, offline: bool = False,
                  max_add: int | None = None, query: str = "",
                  variants: list | None = None) -> dict:
    """Poora cycle: candidates dhoondo -> probe -> good add, dead archive.

    ``query`` (topic) diya ho to web search, archive harvest aur pool isi
    query se filter hote hain — ``/explore <topic>`` us topic par hi explore
    kare (neutral rotation ke baghair). Query khaali = purana neutral rotate.

    ``variants`` (``query_variants.variants()`` ka natija) diya ho to web
    search un tamam variants par chalti hai (max 3) — yaani Urdu / Roman
    Urdu / English / tarjuma sab ek saath dhoondha jata hai.
    """
    cfg = cfg or config.load()
    ensure_table()
    max_add = int(max_add or util.clamp(
        cfg.get("channel_discovery_probe_per_run"), 1, 40, 8))
    min_score = int(util.clamp(cfg.get("channel_min_score"), 0, 10, 4))
    max_auto = int(util.clamp(cfg.get("channel_discovery_max_auto"), 1, 500, 60))
    q = str(query or "").strip()
    var_texts = []
    for v in (variants or [])[:3]:
        t = str(v.get("text") if isinstance(v, dict) else v or "").strip()
        if t:
            var_texts.append(t)
    search_terms = var_texts or ([q] if q else [])
    words = set()
    for t in ([q] + var_texts):
        words |= set(util.terms(t, 20))

    known = {r["channel"] for r in list_channels()}
    manual = {clean_handle(c) for c in (cfg.get("telegram_channels") or [])}
    candidates: list[str] = []
    web_infos: list[dict] = []

    # 1) web search (bootstrap) - offline me skip
    if not offline and bool(cfg.get("channel_discovery_web", True)):
        if search_terms:
            # topic-driven: query + us ke variants (Urdu/Roman/tarjuma)
            for term in search_terms[:3]:
                info: dict = {}
                candidates.extend(web_search_candidates(
                    term, cfg, info, merge=True,
                    providers=("rightdao", "lyzem")))
                web_infos.append(info)
        else:
            info: dict = {}
            topics = cfg.get("topics") or TOPIC_KEYWORDS
            kw = topics[int(time.time() // 3600) % len(topics)]
            candidates.extend(web_search_candidates(str(kw), cfg, info))
            web_infos.append(info)
            info = {}
            candidates.extend(web_search_candidates(
                TOPIC_KEYWORDS[int(time.time() // 3600) % len(TOPIC_KEYWORDS)],
                cfg, info))
            web_infos.append(info)
    web_info = merge_web_probe(web_infos)

    # 2) archive harvest (offline-safe) - query filter ke saath
    candidates.extend(harvest_archive(cfg, query=q))

    # 3) preview harvest pool: pichhle probes ke posts me mile channels
    with store.session() as con:
        pool = con.execute(
            "SELECT handle FROM tg_candidates WHERE probed_at=0 "
            "ORDER BY found_at LIMIT 200").fetchall()
    pool_handles = [r["handle"] for r in pool]
    if words:
        matched = [h for h in pool_handles
                   if any(w in h.lower() for w in words)]
        candidates.extend(matched or pool_handles)
    else:
        candidates.extend(pool_handles)

    candidates = [c for c in dict.fromkeys(candidates)
                  if c not in known and c not in manual]

    # Pool consume karo (probed_at mark) taake wahi dead candidate dobara na aaye
    take_candidates(min(len(candidates), max_add * 3))

    added, dead, summaries = [], [], []
    probe_rows: list[dict] = []
    auto_now = counts().get("active", 0)
    for cand in candidates[:max_add]:
        if auto_now >= max_auto:
            break
        res = check_channel(cand, cfg)
        summaries.append({"channel": res["channel"], "status": res["status"],
                          "score": res["score"]})
        probe_rows.append({
            "channel": res.get("channel"),
            "status": res.get("status"),
            "score": res.get("score"),
            "title": res.get("title") or "",
            "subscribers": res.get("subscribers") or "",
            "last_post_at": res.get("last_post_at") or "",
            "post_count": res.get("post_count") or 0,
            "note": res.get("note") or "",
        })
        if res["status"] == "active" and res["score"] >= min_score:
            added.append(res["channel"])
            auto_now += 1
        else:
            dead.append(res["channel"])

    # 4) liveness re-check: purane checked channels (dead/active dono).
    # Offline mode me koi network probe nahi hota (tests / no-internet rule).
    rechecked = 0
    now = util.epoch()
    if not offline:
        for row in list_channels():
            if rechecked >= max_add:
                break
            if row.get("status") == "archived":
                continue
            if now - int(row.get("last_checked") or 0) >= RECHECK_AFTER_SECONDS:
                check_channel(row["channel"], cfg)
                rechecked += 1

    out = {"query": q, "candidates": len(candidates), "probed": len(summaries),
           "added": added, "dead": dead, "rechecked": rechecked,
           "counts": counts(), "web_search": web_info,
           # Query variants jo is run me istemal hue (Urdu/Roman/tarjuma)
           "variants": list(search_terms),
           # Har probed candidate (active + dead/insufficient) — /explore card
           # ke liye. ``candidates`` count (int) barqarar hai (purane tests).
           "probe_rows": probe_rows}
    store.add_event("channel_discovery",
                    f"added={len(added)} dead={len(dead)} "
                    f"engine={web_info.get('engine') or 'n/a'} "
                    f"candidates={len(candidates)} "
                    f"active={out['counts']['active']}")
    try:
        save_discovery_state({
            "ts": util.epoch(), "query": q,
            "engine": web_info.get("engine") or "",
            "candidates": len(candidates), "probed": len(summaries),
            "added": len(added), "dead": len(dead),
            "anomaly": bool(web_info.get("anomaly")),
            "error": web_info.get("error") or "",
            "tried": web_info.get("tried") or [],
        })
    except Exception:
        pass
    return out


def adapter_channels(cfg: dict | None = None) -> list[str]:
    """TelegramAdapter ke liye: manual config list + discovered active."""
    cfg = cfg or config.load()
    manual = []
    for c in (cfg.get("telegram_channels") or []):
        clean = clean_handle(c)
        if clean:
            manual.append(clean)
    try:
        return list(dict.fromkeys(manual + active_channels()))
    except Exception:
        return manual


# --------------------------------------------------------------------------
# P28: Saved-channel post search (public ``t.me/s/<ch>?q=`` only)
# --------------------------------------------------------------------------

SEARCH_MAX_CHANNELS = 8
SEARCH_PER_CHANNEL = 6
SEARCH_WORKERS = 4


def search_url(channel: str, query: str) -> str:
    """Public preview ka server-side search URL.

    ``t.me/s/<channel>?q=<word>`` wohi search hai jo browser mein channel
    preview kholne par milti hai - koi login, userbot ya history scrape nahi.
    """
    clean = clean_handle(channel)
    if not clean:
        raise ValueError("Channel handle ghalat hai")
    return "https://t.me/s/" + clean + "?q=" + urllib.parse.quote(str(query or "")[:150])


def _search_one(clean: str, query: str, cfg: dict, per_channel: int, fetch) -> tuple:
    try:
        html = fetch(search_url(clean, query), cfg)
        return clean, adapters.parse_telegram(html, clean)[:per_channel], ""
    except Exception as exc:
        return clean, [], f"{type(exc).__name__}: {util.truncate(str(exc), 120)}"


def search_posts(query: str, channels_list: list[str] | None = None,
                 cfg: dict | None = None, limit: int = 10,
                 per_channel: int = SEARCH_PER_CHANNEL, fetch=None,
                 workers: int = SEARCH_WORKERS) -> dict:
    """Saved public channels ke andar keyword search (parallel, fail-safe).

    Returns ``{"query", "items", "channels", "ok", "failed"}``. Har item mein
    ``channel`` field hoti hai taake report mein "kaunsa channel" dikhe.
    """
    cfg = cfg or config.load()
    query = str(query or "").strip()
    if not query:
        return {"query": "", "items": [], "channels": [], "ok": 0, "failed": []}
    names = ([clean_handle(c) for c in adapter_channels(cfg)]
             if channels_list is None else
             [clean_handle(c) for c in channels_list])
    names = list(dict.fromkeys(n for n in names if n))[:SEARCH_MAX_CHANNELS]
    if not names:
        return {"query": query, "items": [], "channels": [], "ok": 0, "failed": []}

    fetch = fetch or adapters.fetch
    results = []
    with concurrent.futures.ThreadPoolExecutor(
            max_workers=max(1, min(int(workers or 1), len(names)))) as pool:
        futures = [pool.submit(_search_one, n, query, cfg, per_channel, fetch)
                   for n in names]
        for fut in futures:
            results.append(fut.result())

    items, failed, seen = [], [], set()
    for clean, found, err in results:
        if err:
            failed.append({"channel": clean, "error": err})
        for raw in found:
            url = str(raw.get("url") or "")
            if not url or url in seen:
                continue
            seen.add(url)
            item = dict(raw)
            item["channel"] = clean
            item["matched_in"] = "channel-search"
            items.append(item)
    return {"query": query, "items": items[:max(1, int(limit))],
            "channels": names, "ok": len(names) - len(failed), "failed": failed}

