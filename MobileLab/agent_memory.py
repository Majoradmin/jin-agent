"""Agent memory (P13) - persistent, local-only research memory.

Two layers, one source of truth:

* SQLite tables (``memory_*``) are the machine memory used for recall, ranking
  and learning. They live in the same DB as the rest of MobileLab so tests and
  the production app share one connection policy and one backup.
* ``data/agent_memory.md`` is a human-readable export the user can open at any
  time (``write_markdown``). It is generated from SQLite, never the reverse.

Design rules
------------
* Never lose history: low-value sources are **archived** (status), not deleted.
* Every learned fact keeps a target + timestamp; feedback only adjusts scores.
* No cloud, no secrets, no private messages. Telegram support is limited to the
  public ``t.me/s/<channel>`` preview handled by :mod:`telegram_public`.
* Standard library only.
"""
from __future__ import annotations

import hashlib
import os
import re
import time
import urllib.parse
from datetime import datetime, timezone

import db
import research

VERSION = "1.0"

SEED_SOURCES = [
    # Official / primary (highest priority)
    {"key": "android-bulletin", "name": "Android Security Bulletin", "url": "https://source.android.com/docs/security/bulletin", "type": "official", "category": "security", "trust": 1.0, "usefulness": 5, "priority": 10, "notes": "Monthly Android platform + vendor patches"},
    {"key": "samsung-smr", "name": "Samsung Security (SMR)", "url": "https://security.samsungmobile.com/securityUpdate.smsb", "type": "official", "category": "security", "trust": 1.0, "usefulness": 5, "priority": 10, "notes": "Samsung monthly security maintenance release"},
    {"key": "apple-security", "name": "Apple Security Releases", "url": "https://support.apple.com/100100", "type": "official", "category": "apple", "trust": 1.0, "usefulness": 5, "priority": 10, "notes": "iOS / iPadOS security releases"},
    {"key": "gsmarena", "name": "GSMArena", "url": "https://www.gsmarena.com/", "type": "media", "category": "firmware", "trust": 0.7, "usefulness": 3, "priority": 4},
    {"key": "xda", "name": "XDA Developers", "url": "https://xdaforums.com/", "type": "community", "category": "tools", "trust": 0.6, "usefulness": 3, "priority": 4},
    {"key": "github-mtkclient", "name": "mtkclient", "url": "https://github.com/bkerler/mtkclient", "type": "community", "category": "mtk", "trust": 0.8, "usefulness": 4, "priority": 6, "notes": "MediaTek tooling releases"},
    {"key": "github-edl", "name": "Qualcomm EDL client", "url": "https://github.com/bkerler/edl", "type": "community", "category": "qcom", "trust": 0.8, "usefulness": 4, "priority": 6, "notes": "Qualcomm EDL tooling"},
    {"key": "ahmia", "name": "Ahmia onion index", "url": "https://ahmia.fi/", "type": "onion-index", "category": "deep-web", "trust": 0.5, "usefulness": 2, "priority": 2, "notes": "Legal onion discovery only; links, no crawling"},
]

# Feed / query source names exactly as research.py reports them in diagnostics.
_SEED_FEEDS = [
    ("Google News (live)", "search", "general", 0.8, 4, 7),
    ("Hacker News (live)", "community", "tools", 0.7, 3, 5),
    ("Open-source tool releases", "code", "tools", 0.9, 4, 6),
    ("GitHub Releases", "code", "tools", 0.9, 4, 6),
    ("GSMArena", "media", "firmware", 0.7, 3, 4),
    ("XDA Developers", "community", "tools", 0.6, 3, 4),
    ("Android Authority", "media", "firmware", 0.7, 3, 4),
    ("Android Police", "media", "firmware", 0.7, 3, 4),
    ("9to5Google", "media", "firmware", 0.7, 3, 4),
    ("SamMobile", "media", "firmware", 0.7, 3, 4),
    ("Apple Newsroom", "official", "apple", 0.9, 4, 6),
    ("Telegram Public Preview", "telegram", "social", 0.4, 2, 2),
    ("YouTube (official RSS/API)", "video", "social", 0.5, 3, 3),
    ("Facebook (link only)", "social", "social", 0.3, 1, 1),
    ("Instagram (link only)", "social", "social", 0.3, 1, 1),
]

ENTITY_CVE = re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.I)
ENTITY_MODEL = re.compile(r"\b(?:SM-[A-Z0-9]{4,10}|CPH\d{4}|ELE-[A-Z0-9]+|MT\d{4,5}|SDM?\d{3,4})\b", re.I)


def _now() -> float:
    return time.time()


def _ts(value) -> str:
    try:
        return datetime.fromtimestamp(float(value), timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except (TypeError, ValueError, OSError, OverflowError):
        return ""


def _date(value) -> str:
    try:
        return datetime.fromtimestamp(float(value), timezone.utc).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OSError, OverflowError):
        return ""


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-")
    return s[:80] or "source"


def _source_key(name: str, url: str) -> str:
    host = ""
    if url:
        try:
            host = (urllib.parse.urlsplit(url).hostname or "").lower().replace(".", "-")
        except Exception:
            host = ""
    return _slug(host or name)


def _cell(value, limit: int = 90) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).replace("|", "/").strip()
    return text[:limit]


def ensure_seeded() -> None:
    """Insert the default source registry once (idempotent, one transaction)."""
    with db._session() as con:
        if con.execute("SELECT COUNT(*) n FROM memory_sources").fetchone()["n"]:
            return
        now = _now()
        rows = []
        for s in SEED_SOURCES + [
            {"key": _slug(n), "name": n, "url": "", "type": t, "category": c,
             "trust": tr, "usefulness": u, "priority": p, "notes": ""}
            for (n, t, c, tr, u, p) in _SEED_FEEDS
        ]:
            rows.append((s["key"], s["name"], s.get("url", ""), s.get("type", "web"),
                         s.get("category", "general"), float(s.get("trust", 0.5)),
                         int(s.get("usefulness", 3)), int(s.get("priority", 0)),
                         s.get("notes", ""), now, now))
        con.executemany(
            """INSERT OR IGNORE INTO memory_sources
               (key,name,url,type,category,trust,usefulness,priority,status,notes,
                added_by,ok_count,fail_count,last_ok,last_error,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,'active',?,'system',0,0,0,'',?,?)""",
            rows)
        con.commit()


# ---------------------------------------------------------------------------
# Source registry
# ---------------------------------------------------------------------------

def list_sources(include_archived: bool = False, limit: int = 200) -> list[dict]:
    ensure_seeded()
    limit = max(1, min(500, int(limit or 200)))
    where = "" if include_archived else "WHERE status='active'"
    return db.rows(
        f"SELECT * FROM memory_sources {where} "
        f"ORDER BY priority DESC, usefulness DESC, name ASC LIMIT ?", (limit,))


def get_source(sid: int):
    return db.one("SELECT * FROM memory_sources WHERE id=?", (int(sid),))


def add_source(data: dict) -> dict:
    """Add or update a user-supplied site. Invalid / unsafe URLs are rejected."""
    ensure_seeded()
    name = str(data.get("name") or "").strip()
    url = str(data.get("url") or "").strip()
    if not name:
        raise ValueError("Source ka naam likhein")
    if url:
        if not re.match(r"^https?://", url, re.I):
            raise ValueError("URL sirf http:// ya https:// se shuru ho sakta hai")
        try:
            research.validate_url(url)          # SSRF / private-host guard
        except ValueError as e:
            raise ValueError(str(e))
    key = _slug(data.get("key") or _source_key(name, url))
    try:
        usefulness = max(1, min(5, int(data.get("usefulness") or 3)))
    except (TypeError, ValueError):
        usefulness = 3
    try:
        priority = max(0, min(10, int(data.get("priority") or max(0, usefulness - 1))))
    except (TypeError, ValueError):
        priority = max(0, usefulness - 1)
    try:
        trust = max(0.0, min(1.0, float(data.get("trust", 0.5))))
    except (TypeError, ValueError):
        trust = 0.5
    now = _now()
    existing = db.one("SELECT id FROM memory_sources WHERE key=?", (key,))
    if existing:
        db.execute(
            """UPDATE memory_sources SET name=?,url=?,type=?,category=?,trust=?,
               usefulness=?,priority=?,status='active',notes=?,updated_at=? WHERE key=?""",
            (name, url, str(data.get("type") or "web"),
             str(data.get("category") or "general"), trust, usefulness, priority,
             str(data.get("notes") or ""), now, key),
        )
    else:
        db.execute(
            """INSERT INTO memory_sources
               (key,name,url,type,category,trust,usefulness,priority,status,notes,
                added_by,ok_count,fail_count,last_ok,last_error,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,'active',?,'user',0,0,0,'',?,?)""",
            (key, name, url, str(data.get("type") or "web"),
             str(data.get("category") or "general"), trust, usefulness, priority,
             str(data.get("notes") or ""), now, now),
        )
    return db.one("SELECT * FROM memory_sources WHERE key=?", (key,)) or {}


def promote_source(sid: int, useful: bool = True) -> dict:
    row = get_source(sid)
    if not row:
        raise ValueError("Source nahi mila")
    delta = 1 if useful else -1
    usefulness = max(1, min(5, int(row.get("usefulness") or 3) + delta))
    priority = max(0, min(10, int(row.get("priority") or 0) + delta))
    db.execute(
        "UPDATE memory_sources SET usefulness=?,priority=?,updated_at=? WHERE id=?",
        (usefulness, priority, _now(), int(sid)))
    return get_source(sid) or {}


def archive_source(sid: int) -> dict:
    row = get_source(sid)
    if not row:
        raise ValueError("Source nahi mila")
    db.execute(
        "UPDATE memory_sources SET status='archived',priority=0,updated_at=? WHERE id=?",
        (_now(), int(sid)))
    return get_source(sid) or {}


def touch_source(name: str, ok: bool, error: str = "") -> None:
    """Record a fetch success/failure for the matching registry source."""
    if not name:
        return
    row = db.one("SELECT id FROM memory_sources WHERE name=? COLLATE NOCASE", (name,))
    if not row:
        return
    if ok:
        db.execute(
            "UPDATE memory_sources SET ok_count=ok_count+1,last_ok=?,last_error='',updated_at=? WHERE id=?",
            (_now(), _now(), row["id"]))
    else:
        db.execute(
            "UPDATE memory_sources SET fail_count=fail_count+1,last_error=?,updated_at=? WHERE id=?",
            (str(error or "")[:300], _now(), row["id"]))


# ---------------------------------------------------------------------------
# Telegram public channel registry
# ---------------------------------------------------------------------------

def normalize_channel(raw: str) -> str:
    """Accept @name, name, t.me/name, t.me/s/name -> bare channel username."""
    text = str(raw or "").strip()
    text = re.sub(r"^https?://", "", text, flags=re.I)
    text = re.sub(r"^(?:www\.)?(?:t|telegram)\.me/", "", text, flags=re.I)
    text = text.split("?", 1)[0].split("#", 1)[0]
    text = text.strip().strip("/").lstrip("@")
    if text.lower().startswith("s/"):
        text = text[2:]
    text = text.strip().strip("/").lstrip("@")
    if not re.fullmatch(r"[A-Za-z0-9_]{3,64}", text):
        raise ValueError("Telegram channel username ghalat hai (sirf letters, numbers, _; 3-64)")
    return text


def list_telegram(include_disabled: bool = False, limit: int = 200) -> list[dict]:
    limit = max(1, min(500, int(limit or 200)))
    where = "" if include_disabled else "WHERE enabled=1"
    return db.rows(
        f"SELECT * FROM memory_telegram {where} ORDER BY category, channel LIMIT ?", (limit,))


def add_telegram(data: dict) -> dict:
    ensure_seeded()
    channel = normalize_channel(data.get("channel") or data.get("handle") or data.get("name") or "")
    title = str(data.get("title") or "").strip() or channel
    category = str(data.get("category") or "gsm").strip() or "gsm"
    notes = str(data.get("notes") or "").strip()
    now = _now()
    db.execute(
        """INSERT INTO memory_telegram
           (channel,title,category,notes,enabled,ok_count,fail_count,last_ok,last_error,created_at,updated_at)
           VALUES(?,?,?,?,1,0,0,0,'',?,?)
           ON CONFLICT(channel) DO UPDATE SET
             title=excluded.title,category=excluded.category,notes=excluded.notes,
             enabled=1,updated_at=excluded.updated_at""",
        (channel, title, category, notes, now, now))
    return db.one("SELECT * FROM memory_telegram WHERE channel=?", (channel,)) or {}


def archive_telegram(tid: int) -> dict:
    row = db.one("SELECT * FROM memory_telegram WHERE id=?", (int(tid),))
    if not row:
        raise ValueError("Telegram channel nahi mila")
    db.execute("UPDATE memory_telegram SET enabled=0,updated_at=? WHERE id=?", (_now(), int(tid)))
    return db.one("SELECT * FROM memory_telegram WHERE id=?", (int(tid),)) or {}


def touch_telegram(channel: str, ok: bool, error: str = "") -> None:
    try:
        ch = normalize_channel(channel)
    except ValueError:
        return
    if ok:
        db.execute(
            "UPDATE memory_telegram SET ok_count=ok_count+1,last_ok=?,last_error='',updated_at=? WHERE channel=?",
            (_now(), _now(), ch))
    else:
        db.execute(
            "UPDATE memory_telegram SET fail_count=fail_count+1,last_error=?,updated_at=? WHERE channel=?",
            (str(error or "")[:300], _now(), ch))


def remember_telegram_if_new(channel: str, title: str = "", category: str = "gsm") -> dict | None:
    """Auto-remember a channel the user searched (explicit groups stay editable)."""
    try:
        ch = normalize_channel(channel)
    except ValueError:
        return None
    if db.one("SELECT id FROM memory_telegram WHERE channel=?", (ch,)):
        return None
    return add_telegram({"channel": ch, "title": title or ch, "category": category,
                         "notes": "auto-remembered from search"})


# ---------------------------------------------------------------------------
# Query / problem / report memory
# ---------------------------------------------------------------------------

def _qkey(query: str, category: str = "all") -> str:
    raw = f"{str(query or '').strip().lower()}|{str(category or 'all').lower()}"
    return hashlib.sha1(raw.encode("utf-8", "replace")).hexdigest()[:24]


def _remember_entity(name: str, kind: str = "term", notes: str = "") -> None:
    text = str(name or "").strip()
    if len(text) < 3:
        return
    now = _now()
    db.execute(
        """INSERT INTO memory_entities(name,type,aliases,last_seen,notes)
           VALUES(?,?,'',?,?)
           ON CONFLICT(name) DO UPDATE SET last_seen=excluded.last_seen""",
        (text[:120], kind, now, str(notes or "")[:300]))


def record_research(params: dict, result: dict) -> dict | None:
    """Save one research run: query, terms, source health and entities."""
    ensure_seeded()
    query = str((result or {}).get("query") or (params or {}).get("q") or "").strip()
    if not query:
        return None
    category = str((result or {}).get("category") or (params or {}).get("category") or "all")
    terms = [str(t) for t in ((result or {}).get("terms") or [])][:20]
    qkey = _qkey(query, category)
    now = _now()
    old = db.one("SELECT * FROM memory_queries WHERE qkey=?", (qkey,))
    if old:
        db.execute(
            """UPDATE memory_queries SET hits=hits+1,result_count=?,returned=?,
               sources_ok=?,sources_failed=?,terms=?,updated_at=? WHERE qkey=?""",
            (int(result.get("total") or 0), int(result.get("returned") or 0),
             int(result.get("sources_ok") or 0), int(result.get("sources_failed") or 0),
             ", ".join(terms), now, qkey))
        hits = int(old.get("hits") or 1) + 1
    else:
        db.execute(
            """INSERT INTO memory_queries
               (qkey,query,category,terms,result_count,returned,sources_ok,sources_failed,
                hits,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,1,?,?)""",
            (qkey, query[:300], category, ", ".join(terms),
             int(result.get("total") or 0), int(result.get("returned") or 0),
             int(result.get("sources_ok") or 0), int(result.get("sources_failed") or 0),
             now, now))
        hits = 1
    for d in (result.get("diagnostics") or []):
        touch_source(d.get("source", ""), bool(d.get("ok")), d.get("error", ""))
    for term in terms:
        _remember_entity(term, "term")
    for item in (result.get("items") or [])[:30]:
        blob = f"{item.get('title', '')} {item.get('excerpt', '')}"
        for cve in ENTITY_CVE.findall(blob):
            _remember_entity(cve.upper(), "cve")
        for model in ENTITY_MODEL.findall(blob):
            _remember_entity(model.upper(), "model")
    return {"qkey": qkey, "query": query, "category": category,
            "hits": hits, "terms": terms}


def recall(query: str = "", category: str = "all", limit: int = 6) -> dict:
    """Look up similar past queries, known problems and priority sources."""
    ensure_seeded()
    limit = max(1, min(30, int(limit or 6)))
    q = str(query or "").strip()
    if q:
        like = "%" + q + "%"
        queries = db.rows(
            "SELECT * FROM memory_queries WHERE query LIKE ? OR terms LIKE ? "
            "ORDER BY updated_at DESC LIMIT ?", (like, like, limit))
        problems = db.rows(
            "SELECT * FROM memory_problems WHERE title LIKE ? OR model LIKE ? OR symptoms LIKE ? "
            "ORDER BY updated_at DESC LIMIT ?", (like, like, like, limit))
    else:
        queries = db.rows("SELECT * FROM memory_queries ORDER BY updated_at DESC LIMIT ?", (limit,))
        problems = db.rows("SELECT * FROM memory_problems ORDER BY updated_at DESC LIMIT ?", (limit,))
    if category and category != "all":
        sources = db.rows(
            "SELECT * FROM memory_sources WHERE status='active' AND category=? "
            "ORDER BY priority DESC, usefulness DESC LIMIT ?", (category, 8))
    else:
        sources = list_sources(limit=8)
    last = queries[0] if queries else None
    known = bool(queries or problems)
    msg = ""
    if known:
        msg = ("Pehle bhi is topic par research hui hai — "
               f"{len(queries)} query record, {len(problems)} problem record mile.")
    return {
        "known": known, "query": q, "message": msg,
        "queries": queries, "problems": problems, "sources": sources,
        "last_seen": _ts(last.get("updated_at")) if last else "",
    }


def add_problem(data: dict) -> dict:
    ensure_seeded()
    title = str(data.get("title") or data.get("q") or "").strip()
    if not title:
        raise ValueError("Masla / problem ka title likhein")
    now = _now()
    pid = db.execute(
        """INSERT INTO memory_problems
           (title,model,symptoms,findings,status,notes,created_at,updated_at)
           VALUES(?,?,?,?,?,?,?,?)""",
        (title[:300], str(data.get("model") or "")[:120],
         str(data.get("symptoms") or "")[:2000], str(data.get("findings") or "")[:4000],
         str(data.get("status") or "open")[:40], str(data.get("notes") or "")[:2000],
         now, now))
    _remember_entity(title, "problem")
    if data.get("model"):
        _remember_entity(str(data.get("model")), "model")
    return db.one("SELECT * FROM memory_problems WHERE id=?", (pid,)) or {}


def add_feedback(data: dict) -> dict:
    ensure_seeded()
    rating = str(data.get("rating") or "useful").strip().lower()
    if rating not in ("useful", "not_useful"):
        raise ValueError("Rating 'useful' ya 'not_useful' honi chahiye")
    target_type = str(data.get("target_type") or "item")[:40]
    target_key = str(data.get("target_key") or "")[:300]
    source = str(data.get("source") or "")[:200]
    note = str(data.get("note") or "")[:1000]
    now = _now()
    fid = db.execute(
        """INSERT INTO memory_feedback(target_type,target_key,source,rating,note,created_at)
           VALUES(?,?,?,?,?,?)""",
        (target_type, target_key, source, rating, note, now))
    if source:
        useful = rating == "useful"
        row = db.one("SELECT id FROM memory_sources WHERE name=? COLLATE NOCASE", (source,))
        if row:
            promote_source(int(row["id"]), useful)
    return db.one("SELECT * FROM memory_feedback WHERE id=?", (fid,)) or {}


def list_feedback(limit: int = 50) -> list[dict]:
    limit = max(1, min(500, int(limit or 50)))
    return db.rows("SELECT * FROM memory_feedback ORDER BY created_at DESC LIMIT ?", (limit,))


def save_report(data: dict) -> dict:
    markdown = str(data.get("markdown") or "")
    query = str(data.get("query") or "")[:300]
    title = str(data.get("title") or query or "Research report")[:300]
    report_no = str(data.get("report_no") or "").strip()
    if not report_no:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        report_no = f"REP-{stamp}-{os.urandom(2).hex().upper()}"
    now = _now()
    db.execute(
        """INSERT INTO memory_reports
           (report_no,query,title,category,item_count,confidence,markdown,created_at)
           VALUES(?,?,?,?,?,?,?,?)""",
        (report_no, query, title, str(data.get("category") or "all"),
         int(data.get("item_count") or 0), str(data.get("confidence") or "mixed"),
         markdown[:200_000], now))
    return db.one("SELECT id,report_no,query,title,category,item_count,confidence,created_at "
                  "FROM memory_reports WHERE report_no=?", (report_no,)) or {}


def list_reports(limit: int = 30) -> list[dict]:
    limit = max(1, min(200, int(limit or 30)))
    return db.rows(
        "SELECT id,report_no,query,title,category,item_count,confidence,created_at "
        "FROM memory_reports ORDER BY created_at DESC LIMIT ?", (limit,))


# ---------------------------------------------------------------------------
# Overview + human-readable Markdown export
# ---------------------------------------------------------------------------

def overview() -> dict:
    ensure_seeded()
    return {
        "version": VERSION,
        "counts": {
            "sources": db.one("SELECT COUNT(*) n FROM memory_sources WHERE status='active'")["n"],
            "archived_sources": db.one("SELECT COUNT(*) n FROM memory_sources WHERE status='archived'")["n"],
            "telegram": db.one("SELECT COUNT(*) n FROM memory_telegram WHERE enabled=1")["n"],
            "queries": db.one("SELECT COUNT(*) n FROM memory_queries")["n"],
            "problems": db.one("SELECT COUNT(*) n FROM memory_problems")["n"],
            "reports": db.one("SELECT COUNT(*) n FROM memory_reports")["n"],
            "feedback": db.one("SELECT COUNT(*) n FROM memory_feedback")["n"],
            "entities": db.one("SELECT COUNT(*) n FROM memory_entities")["n"],
        },
        "sources": list_sources(limit=60),
        "telegram": list_telegram(limit=60),
        "queries": db.rows("SELECT * FROM memory_queries ORDER BY updated_at DESC LIMIT 25"),
        "problems": db.rows("SELECT * FROM memory_problems ORDER BY updated_at DESC LIMIT 25"),
        "reports": list_reports(20),
        "feedback": list_feedback(25),
        "entities": db.rows("SELECT * FROM memory_entities ORDER BY last_seen DESC LIMIT 40"),
        "generated_at": _ts(_now()),
        "markdown_file": "data/agent_memory.md",
    }


def export_markdown() -> str:
    """Render the whole memory as one human-readable Markdown document."""
    ensure_seeded()
    now = _ts(_now())
    sources = list_sources(include_archived=True, limit=200)
    telegram = list_telegram(include_disabled=True, limit=200)
    queries = db.rows("SELECT * FROM memory_queries ORDER BY updated_at DESC LIMIT 80")
    problems = db.rows("SELECT * FROM memory_problems ORDER BY updated_at DESC LIMIT 50")
    reports = list_reports(40)
    feedback = list_feedback(80)
    entities = db.rows("SELECT * FROM memory_entities ORDER BY last_seen DESC LIMIT 120")

    out = [
        "# agent_memory.md — Agent Runtime Memory",
        "",
        f"**Version:** {VERSION} · **Generated:** {now} · **Owner:** local user  ",
        "**Status:** LIVE — SQLite se auto-generated. Edit files ke bajaye UI se changes karein.",
        "**Scope:** local only · no cloud · no secrets · no private messages.",
        "",
        "> Ye file agent ki **runtime memory** hai. Project context `docs/memory.md` mein rehta hai.",
        "> Rule: **append-only** history + weekly compaction. Sources archive hoti hain, delete nahi.",
        "",
        "---",
        "",
        "## 1. User Profile",
        "",
        "- **Language:** Roman Urdu content, English headings/labels/technical terms.",
        "- **Style:** professional, concise, source-first, no hype.",
        "- **Priority topics:** mobile software, firmware, Android/iOS, security, tools.",
        "- **Other topics:** all public topics allowed.",
        "- **Do not store:** full IMEI, passwords, tokens, private messages, payment data.",
        "",
        "## 2. Preferences",
        "",
        "| # | Preference | Value |",
        "|---|---|---|",
        "| 1 | Report language | Roman Urdu + English technical terms |",
        "| 2 | Report style | Khulasa → Kya hua → Matlab → Kya karein → Source |",
        "| 3 | Confidence labels | Official / Verified / Reported / Unverified / Rumor |",
        "| 4 | Auto-fetch | Public feeds + Telegram public + legal deep web |",
        "| 5 | Social media | Official APIs where available; otherwise link-only |",
        "| 6 | Tor/onion | Links only (auto-fetch later, legal review ke baad) |",
        "| 7 | Retention | 90 days default; archive older |",
        "",
        "## 3. Source Registry",
        "",
        "| id | source | type | trust | usefulness | priority | status | ok | fail | last_ok | notes |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for s in sources:
        out.append(
            f"| {s['id']} | {_cell(s['name'], 60)} | {_cell(s['type'], 20)} | "
            f"{s['trust']} | {s['usefulness']} | {s['priority']} | {s['status']} | "
            f"{s['ok_count']} | {s['fail_count']} | {_date(s['last_ok']) or '—'} | "
            f"{_cell(s.get('notes'), 60)} |")
    out += [
        "",
        "**Promotion rule:** useful feedback = +1 usefulness / +1 priority (max 5 / 10).",
        "**Demotion rule:** not-useful feedback = −1; archived sources priority 0 (delete nahi).",
        "",
        "## 4. Telegram Public Channels",
        "",
        "| id | channel | title | category | status | ok | fail | last_ok | notes |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for t in telegram:
        out.append(
            f"| {t['id']} | @{_cell(t['channel'], 40)} | {_cell(t['title'], 50)} | "
            f"{_cell(t['category'], 20)} | {'active' if t['enabled'] else 'archived'} | "
            f"{t['ok_count']} | {t['fail_count']} | {_date(t['last_ok']) or '—'} | "
            f"{_cell(t.get('notes'), 60)} |")
    out += [
        "",
        "> Sirf public `t.me/s/<channel>` preview. Private groups, userbot/MTProto aur",
        "> login-based scraping is app mein nahi hai.",
        "",
        "## 5. Query History",
        "",
        "| qkey | query | category | results | returned | sources ok/fail | hits | last run |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for q in queries:
        out.append(
            f"| {_cell(q['qkey'], 12)} | {_cell(q['query'], 70)} | {_cell(q['category'], 15)} | "
            f"{q['result_count']} | {q['returned']} | {q['sources_ok']}/{q['sources_failed']} | "
            f"{q['hits']} | {_date(q['updated_at'])} |")
    out += [
        "",
        "## 6. Problem Memory",
        "",
    ]
    if not problems:
        out.append("_Abhi koi problem save nahi hui._")
    for p in problems:
        out += [
            f"### P-{p['id']:03d} — {_cell(p['title'], 100)}",
            "",
            f"- **Model:** {_cell(p.get('model'), 60) or '—'}",
            f"- **Status:** {_cell(p.get('status'), 20)}",
            f"- **Symptoms:** {_cell(p.get('symptoms'), 300) or '—'}",
            f"- **Findings:** {_cell(p.get('findings'), 500) or '—'}",
            f"- **Notes:** {_cell(p.get('notes'), 300) or '—'}",
            f"- **Last checked:** {_date(p.get('updated_at'))}",
            "",
        ]
    out += [
        "## 7. Report Index",
        "",
        "| report | date | topic | items | confidence |",
        "|---|---|---|---|---|",
    ]
    for r in reports:
        out.append(
            f"| {_cell(r['report_no'], 40)} | {_date(r['created_at'])} | "
            f"{_cell(r['title'], 60)} | {r['item_count']} | {_cell(r['confidence'], 15)} |")
    out += [
        "",
        "## 8. Feedback",
        "",
        "| date | target | source | rating | note |",
        "|---|---|---|---|---|",
    ]
    for f in feedback:
        out.append(
            f"| {_date(f['created_at'])} | {_cell(f['target_type'], 15)}: "
            f"{_cell(f['target_key'], 40)} | {_cell(f['source'], 40)} | "
            f"{_cell(f['rating'], 15)} | {_cell(f['note'], 80)} |")
    out += [
        "",
        "## 9. Entity Memory",
        "",
        "| entity | type | notes | last seen |",
        "|---|---|---|---|",
    ]
    for e in entities:
        out.append(
            f"| {_cell(e['name'], 60)} | {_cell(e['type'], 20)} | "
            f"{_cell(e.get('notes'), 60)} | {_date(e['last_seen'])} |")
    out += [
        "",
        "## 10. Learning Rules",
        "",
        "1. **User feedback:** useful = +1 usefulness / priority; not useful = −1.",
        "2. **Citation:** source ka data report mein use hua = +1 (manual promote).",
        "3. **Cross-verification:** 2+ independent sources = higher confidence label.",
        "4. **Failure:** fetch fail = fail_count +1; 3 consecutive fails = review/demote.",
        "5. **Decay:** 5% per 30 days (future scheduler job).",
        "6. **Promotion:** usefulness ≥ 4 = priority fetch.",
        "7. **Never delete:** low-value sources archive hoti hain, delete nahi.",
        "8. **Fact vs claim:** LLM ka guess fact ke tor par store nahi hoga.",
        "9. **Expiry:** unverified leads 14 din baad re-check.",
        "10. **Memory poisoning se bachao:** har fact ke sath source + date.",
        "",
        "## 11. Lifecycle",
        "",
        "1. **Before search:** `recall(query, entities)` → similar queries, known sources.",
        "2. **During search:** priority sources pehle (priority DESC, usefulness DESC).",
        "3. **After search:** `record_research(...)` → query, source health, entities.",
        "4. **After feedback:** `add_feedback(...)` → source score update.",
        "5. **Export:** UI se `data/agent_memory.md` regenerate.",
        "",
        "> **No cloud. No secrets. No private data.**",
        "",
    ]
    return "\n".join(out)


def write_markdown() -> dict:
    """Regenerate ``data/agent_memory.md`` from SQLite (the live export)."""
    text = export_markdown()
    os.makedirs(db.DATA_DIR, exist_ok=True)
    path = os.path.join(db.DATA_DIR, "agent_memory.md")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return {"ok": True, "file": "data/agent_memory.md", "bytes": len(text.encode("utf-8")),
            "generated_at": _ts(_now())}
