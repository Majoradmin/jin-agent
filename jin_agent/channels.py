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

import json
import re
import time
import urllib.parse

from . import adapters, config, store, util

VERSION = "1.0"

HANDLE_RE = re.compile(r"(?:t\.me|telegram\.me)/(?:s/)?@?([A-Za-z0-9_]{3,40})")
EXCLUDE_HANDLES = {"joinchat", "share", "proxy", "addstickers", "addlist",
                   "contact", "todo", "setlanguage", "premium", "telegram",
                   "telegramtips", "tdesktop", "android", "ios", "macos"}

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


def harvest_archive(cfg: dict | None = None) -> list[str]:
    """Firehose archive ke items ke text se t.me candidates."""
    cfg = cfg or config.load()
    out, seen = [], set()
    try:
        with store.session() as con:
            rows = con.execute(
                "SELECT title, excerpt, body FROM items LIMIT 8000").fetchall()
    except Exception:
        return []
    for r in rows:
        text = " ".join([r["title"] or "", r["excerpt"] or "", r["body"] or ""])
        for h in extract_handles(text):
            if h not in seen:
                seen.add(h)
                out.append(h)
    return out[:400]


def web_search_candidates(query: str, cfg: dict | None = None) -> list[str]:
    """Public search engine HTML par site:t.me/s search. Sirf public GET."""
    cfg = cfg or config.load()
    q = urllib.parse.quote("site:t.me/s " + str(query)[:120])
    try:
        html = adapters.fetch("https://html.duckduckgo.com/html/?q=" + q, cfg)
    except Exception:
        return []
    out, seen = [], set()
    # DDG result links uddg=<urlencoded> wrapping par hote hain
    for m in re.finditer(r"uddg=([^&\"']+)", html):
        try:
            target = urllib.parse.unquote(m.group(1))
        except Exception:
            continue
        for h in extract_handles(target):
            if h not in seen:
                seen.add(h)
                out.append(h)
    # kabhi kabhi raw t.me/s/ handle page text me bhi hota hai
    for h in extract_handles(html):
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out[:60]


# --------------------------------------------------------------------------
# Liveness probe + scoring
# --------------------------------------------------------------------------

def probe(channel: str, cfg: dict | None = None) -> dict:
    """PUBLIC t.me/s/<channel> preview fetch -> alive/dead + stats."""
    cfg = cfg or config.load()
    clean = clean_handle(channel)
    if not clean:
        raise ValueError("Channel handle ghalat hai")
    html = adapters.fetch(f"https://t.me/s/{clean}", cfg)
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


def score(rec: dict, cfg: dict | None = None) -> int:
    """Informative score 0-10 (koi language filter NAHI - aap ki request)."""
    cfg = cfg or config.load()
    s = 0
    last = rec.get("last_post_at") or ""
    # recency: ISO "YYYY-MM-DD HH:MM" string-compare kaam karta hai
    try:
        import datetime
        age_days = 9999
        if last:
            dt = datetime.datetime.fromisoformat(last.strip().replace(" ", "T"))
            age_days = max(0, int((datetime.datetime.now(datetime.UTC)
                                   - dt.replace(tzinfo=datetime.UTC)).total_seconds() // 86400))
        if age_days <= 2:
            s += 4
        elif age_days <= 7:
            s += 3
        elif age_days <= 14:
            s += 2
        elif age_days <= 30:
            s += 1
    except Exception:
        pass
    posts = int(rec.get("post_count") or 0)
    if posts >= 10:
        s += 2
    elif posts >= 5:
        s += 1
    if int(rec.get("avg_text_len") or 0) >= 80:
        s += 1
    subs = str(rec.get("subscribers") or "").lower()
    try:
        val = float(re.sub(r"[^\d.]", "", subs) or 0)
        if "m" in subs:
            val *= 1_000_000
        elif "k" in subs:
            val *= 1_000
        if val >= 10_000:
            s += 2
        elif val >= 1_000:
            s += 1
    except Exception:
        pass
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
    return max(0, min(10, s))


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
                "score": 0, "error": type(exc).__name__, "harvested": []}
    sc = score(rec, cfg)
    status = "active" if rec["alive"] else "dead"
    note = ("auto-discovered liveness check" if rec["alive"]
            else f"dead: {rec['post_count']} posts on preview")
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
    return out


# --------------------------------------------------------------------------
# Discovery cycle (scheduler / CLI / API se chalta hai)
# --------------------------------------------------------------------------

def run_discovery(cfg: dict | None = None, offline: bool = False,
                  max_add: int | None = None) -> dict:
    """Poora cycle: candidates dhoondo -> probe -> good add, dead archive."""
    cfg = cfg or config.load()
    ensure_table()
    max_add = int(max_add or util.clamp(
        cfg.get("channel_discovery_probe_per_run"), 1, 40, 8))
    min_score = int(util.clamp(cfg.get("channel_min_score"), 0, 10, 4))
    max_auto = int(util.clamp(cfg.get("channel_discovery_max_auto"), 1, 500, 60))

    known = {r["channel"] for r in list_channels()}
    manual = {clean_handle(c) for c in (cfg.get("telegram_channels") or [])}
    candidates: list[str] = []

    # 1) web search (bootstrap) - offline me skip
    if not offline and bool(cfg.get("channel_discovery_web", True)):
        topics = cfg.get("topics") or TOPIC_KEYWORDS
        kw = topics[int(time.time() // 3600) % len(topics)]
        candidates.extend(web_search_candidates(str(kw), cfg))
        candidates.extend(web_search_candidates(
            TOPIC_KEYWORDS[int(time.time() // 3600) % len(TOPIC_KEYWORDS)], cfg))

    # 2) archive harvest (offline-safe)
    candidates.extend(harvest_archive(cfg))

    # 3) preview harvest pool: pichhle probes ke posts me mile channels
    with store.session() as con:
        pool = con.execute(
            "SELECT handle FROM tg_candidates WHERE probed_at=0 "
            "ORDER BY found_at LIMIT 200").fetchall()
    candidates.extend(r["handle"] for r in pool)

    candidates = [c for c in dict.fromkeys(candidates)
                  if c not in known and c not in manual]

    # Pool consume karo (probed_at mark) taake wahi dead candidate dobara na aaye
    take_candidates(min(len(candidates), max_add * 3))

    added, dead, summaries = [], [], []
    auto_now = counts().get("active", 0)
    for cand in candidates[:max_add]:
        if auto_now >= max_auto:
            break
        res = check_channel(cand, cfg)
        summaries.append({"channel": res["channel"], "status": res["status"],
                          "score": res["score"]})
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

    out = {"candidates": len(candidates), "probed": len(summaries),
           "added": added, "dead": dead, "rechecked": rechecked,
           "counts": counts()}
    store.add_event("channel_discovery",
                    f"added={len(added)} dead={len(dead)} "
                    f"active={out['counts']['active']}")
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
