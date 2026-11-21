"""SQLite WAL + FTS5 archive for JIN Agent.

Everything is local, additive and auto-migrating. Sources are archived, never
deleted; only old *articles* are removed by the retention job.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import stat
from contextlib import contextmanager
from datetime import datetime, timezone

from . import canonical, config, policy, util

FTS_ENABLED = True
FTS_ERROR = ""

SCHEMA_MAIN = """
CREATE TABLE IF NOT EXISTS items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  guid TEXT NOT NULL UNIQUE,
  url TEXT NOT NULL DEFAULT '',
  canonical TEXT NOT NULL DEFAULT '',
  title TEXT NOT NULL DEFAULT '',
  source TEXT NOT NULL DEFAULT '',
  source_key TEXT NOT NULL DEFAULT '',
  tier TEXT NOT NULL DEFAULT 'T0',
  trust REAL NOT NULL DEFAULT 0.5,
  trust_label TEXT NOT NULL DEFAULT 'Unverified',
  category TEXT NOT NULL DEFAULT 'Custom Watchlist',
  published TEXT NOT NULL DEFAULT '',
  date_checked TEXT NOT NULL DEFAULT '',
  fetched_at TEXT NOT NULL DEFAULT '',
  excerpt TEXT NOT NULL DEFAULT '',
  body TEXT NOT NULL DEFAULT '',
  fingerprint TEXT NOT NULL DEFAULT '',
  content_hash TEXT NOT NULL DEFAULT '',
  entities TEXT NOT NULL DEFAULT '[]',
  score REAL NOT NULL DEFAULT 0,
  reasons TEXT NOT NULL DEFAULT '[]',
  confidence REAL NOT NULL DEFAULT 0,
  verified INTEGER NOT NULL DEFAULT 0,
  cross_verified INTEGER NOT NULL DEFAULT 0,
  link_only INTEGER NOT NULL DEFAULT 0,
  useful INTEGER NOT NULL DEFAULT 0,
  synthetic INTEGER NOT NULL DEFAULT 0,
  meta TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_items_fingerprint ON items(fingerprint);
CREATE INDEX IF NOT EXISTS idx_items_fetched ON items(fetched_at);
CREATE INDEX IF NOT EXISTS idx_items_category ON items(category);
CREATE INDEX IF NOT EXISTS idx_items_source ON items(source_key);

CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  query TEXT NOT NULL DEFAULT '',
  mode TEXT NOT NULL DEFAULT 'offline',
  started_at TEXT NOT NULL DEFAULT '',
  finished_at TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'running',
  items_count INTEGER NOT NULL DEFAULT 0,
  sources_ok INTEGER NOT NULL DEFAULT 0,
  sources_failed INTEGER NOT NULL DEFAULT 0,
  metrics TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS sources (
  key TEXT PRIMARY KEY,
  name TEXT NOT NULL DEFAULT '',
  tier TEXT NOT NULL DEFAULT 'T0',
  trust REAL NOT NULL DEFAULT 0.5,
  enabled INTEGER NOT NULL DEFAULT 1,
  ok_count INTEGER NOT NULL DEFAULT 0,
  fail_count INTEGER NOT NULL DEFAULT 0,
  last_ok TEXT NOT NULL DEFAULT '',
  last_error TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'ok',
  last_verified_at TEXT NOT NULL DEFAULT '',
  stale_days INTEGER NOT NULL DEFAULT 30
);
CREATE TABLE IF NOT EXISTS watchlist (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  term TEXT NOT NULL UNIQUE,
  category TEXT NOT NULL DEFAULT 'Custom Watchlist',
  active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT '',
  last_hit TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS entities (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  item_id INTEGER NOT NULL,
  kind TEXT NOT NULL DEFAULT '',
  value TEXT NOT NULL DEFAULT '',
  UNIQUE(item_id, kind, value)
);
CREATE TABLE IF NOT EXISTS jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT NOT NULL,
  payload TEXT NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'pending',
  run_at REAL NOT NULL DEFAULT 0,
  attempts INTEGER NOT NULL DEFAULT 0,
  last_error TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT '',
  finished_at TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status, run_at);
CREATE TABLE IF NOT EXISTS schedule_state (
  key TEXT PRIMARY KEY,
  last_ts REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS reports (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL DEFAULT '',
  query TEXT NOT NULL DEFAULT '',
  fmt TEXT NOT NULL DEFAULT 'md',
  path TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT '',
  metrics TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS feedback (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  guid TEXT NOT NULL,
  useful INTEGER NOT NULL DEFAULT 0,
  note TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL DEFAULT '',
  kind TEXT NOT NULL DEFAULT '',
  detail TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS page_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_key TEXT NOT NULL DEFAULT '',
  url TEXT NOT NULL DEFAULT '',
  canonical TEXT NOT NULL DEFAULT '',
  ts TEXT NOT NULL DEFAULT '',
  first_seen TEXT NOT NULL DEFAULT '',
  content_hash TEXT NOT NULL DEFAULT '',
  size INTEGER NOT NULL DEFAULT 0,
  text TEXT NOT NULL DEFAULT '',
  changed INTEGER NOT NULL DEFAULT 0,
  added_lines INTEGER NOT NULL DEFAULT 0,
  removed_lines INTEGER NOT NULL DEFAULT 0,
  diff TEXT NOT NULL DEFAULT '[]',
  UNIQUE(source_key, canonical)
);
CREATE INDEX IF NOT EXISTS idx_page_snapshots_ts ON page_snapshots(ts);
CREATE INDEX IF NOT EXISTS idx_page_snapshots_source ON page_snapshots(source_key);
CREATE TABLE IF NOT EXISTS chat_context (
  chat_id TEXT PRIMARY KEY,
  last_queries TEXT NOT NULL DEFAULT '[]',
  updated_at REAL NOT NULL DEFAULT 0
);
"""

SCHEMA_FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS items_fts
  USING fts5(title, excerpt, body, source, content='items', content_rowid='id');
CREATE TRIGGER IF NOT EXISTS items_ai AFTER INSERT ON items BEGIN
  INSERT INTO items_fts(rowid, title, excerpt, body, source)
  VALUES (new.id, new.title, new.excerpt, new.body, new.source);
END;
CREATE TRIGGER IF NOT EXISTS items_ad AFTER DELETE ON items BEGIN
  INSERT INTO items_fts(items_fts, rowid, title, excerpt, body, source)
  VALUES ('delete', old.id, old.title, old.excerpt, old.body, old.source);
END;
CREATE TRIGGER IF NOT EXISTS items_au AFTER UPDATE ON items BEGIN
  INSERT INTO items_fts(items_fts, rowid, title, excerpt, body, source)
  VALUES ('delete', old.id, old.title, old.excerpt, old.body, old.source);
  INSERT INTO items_fts(rowid, title, excerpt, body, source)
  VALUES (new.id, new.title, new.excerpt, new.body, new.source);
END;
"""

ITEM_FIELDS = (
    "guid", "url", "canonical", "title", "source", "source_key", "tier", "trust",
    "trust_label", "category", "published", "date_checked", "fetched_at", "excerpt",
    "body", "fingerprint", "content_hash", "entities", "score", "reasons",
    "confidence", "verified", "cross_verified", "link_only", "useful",
    "synthetic", "meta",
)


def _set_owner_only(path: Path, mode: int) -> str:
    """Path ka mode tab badlo jab wo current process ke ho. Warna warning.

    Symlink par nahi (lstat) — nahi to kisi aur file ka mode badal jata.
    """
    try:
        st = os.lstat(path)
    except OSError as exc:
        return f"{path}: stat fail ({exc})"
    if not (stat.S_ISREG(st.st_mode) or stat.S_ISDIR(st.st_mode)):
        return f"{path}: regular file/dir nahi — chmod skip"
    if st.st_uid != os.getuid():
        return f"{path}: is process ke malik nahi (uid {st.st_uid}) — chmod skip"
    try:
        os.chmod(path, mode)
    except OSError as exc:
        return f"{path}: chmod fail ({exc})"
    return ""


def secure_permissions() -> dict:
    """Data dir (0700) aur DB (0600) restrictive karo — sirf apne files par.

    Multi-user host par DB me poora archive hota hai; dusre users ko parhna
    na chahiye. Windows par skip (POSIX permission model nahi). Result me
    dir/db modes aur warnings (naam nahi, sirf mode/uid) darj hain.
    """
    result = {"dir": None, "db": None, "skipped": "", "warnings": []}
    if os.name == "nt":
        result["skipped"] = "windows"
        return result
    d = config.data_dir()
    if d.is_dir():
        warn = _set_owner_only(d, 0o700)
        if warn:
            result["warnings"].append(warn)
        else:
            result["dir"] = 0o700
        # Sensitive subdirs bhi owner-only (reports/backups/runs).
        for sub in ("reports", "backups", "runs"):
            p = d / sub
            if p.is_dir():
                warn = _set_owner_only(p, 0o700)
                if warn:
                    result["warnings"].append(warn)
    else:
        result["warnings"].append(f"{d}: mojood nahi")
    db = config.db_path()
    if db.is_file():
        warn = _set_owner_only(db, 0o600)
        if warn:
            result["warnings"].append(warn)
        else:
            result["db"] = 0o600
    return result


def connect() -> sqlite3.Connection:
    config.ensure_dirs()
    secure_permissions()
    con = sqlite3.connect(str(config.db_path()), timeout=15)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA busy_timeout=15000")
    return con


@contextmanager
def session():
    """Commit/rollback AND close - avoids ResourceWarning under -W error."""
    con = connect()
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init_db() -> dict:
    global FTS_ENABLED, FTS_ERROR
    with session() as con:
        con.executescript(SCHEMA_MAIN)
        # Purani DB migration: synthetic (offline fixture) items ka flag.
        # FTS triggers se PEHLE — external-content FTS5 par trigger wala
        # UPDATE "database disk image is malformed" deta hai.
        icols = {r[1] for r in con.execute("PRAGMA table_info(items)")}
        if "synthetic" not in icols:
            con.execute("ALTER TABLE items ADD COLUMN synthetic INTEGER NOT NULL DEFAULT 0")
            # Purani offline fixture items (example.org) ko synthetic mark karo.
            con.execute("UPDATE items SET synthetic=1 WHERE url LIKE '%example.org%' "
                        "OR url LIKE '%example%.onion%'")
        try:
            con.executescript(SCHEMA_FTS)
            FTS_ENABLED = True
            FTS_ERROR = ""
        except sqlite3.OperationalError as exc:
            FTS_ENABLED = False
            FTS_ERROR = str(exc)
        # Purani DB migration: source lifecycle columns.
        cols = {r[1] for r in con.execute("PRAGMA table_info(sources)")}
        for name, ddl in (("status", "TEXT NOT NULL DEFAULT 'ok'"),
                          ("last_verified_at", "TEXT NOT NULL DEFAULT ''"),
                          ("stale_days", "INTEGER NOT NULL DEFAULT 30")):
            if name not in cols:
                con.execute(f"ALTER TABLE sources ADD COLUMN {name} {ddl}")
        for row in policy.SOURCE_REGISTER:
            con.execute(
                "INSERT OR IGNORE INTO sources(key,name,tier,trust,enabled) VALUES(?,?,?,?,?)",
                (row["key"], row["name"], row["tier"], row["trust"], int(row["auto"])))
    return {"fts5": FTS_ENABLED, "fts_error": FTS_ERROR, "db": str(config.db_path())}


def _json(value) -> str:
    try:
        return json.dumps(value, ensure_ascii=False)[:8000]
    except (TypeError, ValueError):
        return "{}"


def _row_to_dict(row) -> dict:
    d = dict(row)
    for key in ("entities", "reasons", "meta"):
        if key in d:
            try:
                d[key] = json.loads(d[key] or "[]")
            except ValueError:
                d[key] = [] if key != "meta" else {}
    return d


def upsert_items(items: list[dict]) -> dict:
    """Insert or refresh items. Dedupe is by guid (canonical URL + fingerprint)."""
    stats = {"seen": 0, "inserted": 0, "updated": 0, "skipped": 0}
    placeholders = ",".join("?" for _ in ITEM_FIELDS)
    updates = ",".join(f"{f}=excluded.{f}" for f in ITEM_FIELDS if f != "guid")
    sql = (f"INSERT INTO items({','.join(ITEM_FIELDS)}) VALUES({placeholders}) "
           f"ON CONFLICT(guid) DO UPDATE SET {updates}")
    with session() as con:
        for raw in items or []:
            stats["seen"] += 1
            item = dict(raw)
            canonical_url = (item.get("canonical")
                             or canonical.canonicalize(item.get("url", "")))
            item["canonical"] = canonical_url
            item["guid"] = item.get("guid") or (
                item.get("source_key", "src") + ":" +
                util.fingerprint(item.get("title", ""), canonical_url))
            item["date_checked"] = item.get("date_checked") or util.now_iso()
            item["fetched_at"] = item.get("fetched_at") or util.now_iso()
            item["fingerprint"] = item.get("fingerprint") or util.fingerprint(
                item.get("title", ""), canonical_url)
            item["content_hash"] = item.get("content_hash") or canonical.content_hash(
                item.get("title", ""), item.get("excerpt", ""), item.get("body", ""))
            for key in ("entities", "reasons", "meta"):
                if not isinstance(item.get(key), str):
                    item[key] = _json(item.get(key, [] if key != "meta" else {}))
            for key in ("verified", "cross_verified", "link_only", "useful"):
                item[key] = int(bool(item.get(key)))
            # Offline fixture / synthetic items user-facing archive se bahar.
            # Wajah: hosted scheduler offline chalne par ``example.org`` jaisi
            # banawati links explore/digest me asli khabar lagti thin.
            _meta = item.get("meta")
            if isinstance(_meta, str):
                try:
                    _meta = json.loads(_meta or "{}")
                except ValueError:
                    _meta = {}
            _meta = dict(_meta or {})
            item["synthetic"] = int(bool(item.get("synthetic")
                                         or item.get("kind") == "fixture"
                                         or item.get("offline") is True
                                         or _meta.get("offline") is True
                                         or _meta.get("kind") == "fixture"))
            values = []
            for field in ITEM_FIELDS:
                value = item.get(field, "" if field not in ("trust", "score", "confidence") else 0)
                values.append(value if value is not None else ("" if isinstance(value, str) else 0))
            exists = con.execute("SELECT 1 FROM items WHERE guid=?", (item["guid"],)).fetchone()
            try:
                con.execute(sql, values)
            except sqlite3.Error:
                stats["skipped"] += 1
                continue
            stats["updated" if exists else "inserted"] += 1
            row = con.execute("SELECT id FROM items WHERE guid=?", (item["guid"],)).fetchone()
            if row:
                _sync_entities(con, row["id"], item.get("entities", "[]"))
    return stats


def _sync_entities(con, item_id: int, raw):
    try:
        entities = json.loads(raw) if isinstance(raw, str) else (raw or [])
    except ValueError:
        return
    for ent in entities or []:
        if isinstance(ent, dict):
            kind, value = ent.get("kind", ""), ent.get("value", "")
        elif isinstance(ent, (tuple, list)) and len(ent) >= 2:
            kind, value = ent[0], ent[1]
        else:
            continue
        if kind and value:
            con.execute("INSERT OR IGNORE INTO entities(item_id,kind,value) VALUES(?,?,?)",
                        (item_id, str(kind)[:40], str(value)[:120]))


def _fts_expression(query: str) -> str:
    words = [w for w in re.findall(r"[A-Za-z0-9][A-Za-z0-9._-]{1,}", str(query or ""))][:8]
    parts = ['"' + w.replace('"', '""') + '"' for w in words]
    return " OR ".join(parts) if parts else '""'


def search_archive(query: str = "", limit: int = 30, category: str = "") -> list[dict]:
    limit = util.clamp(limit, 1, 200, 30)
    cat_where, cat_param = "", []
    if category and category != "all":
        cat_where = " AND category=?"
        cat_param = [category]
    if FTS_ENABLED and str(query or "").strip():
        try:
            sql = ("SELECT i.* FROM items_fts f JOIN items i ON i.id=f.rowid "
                   "WHERE items_fts MATCH ? AND i.synthetic=0")
            args = [_fts_expression(query)]
            if cat_where:
                sql += " AND i.category=?"
                args += cat_param
            sql += " ORDER BY i.score DESC, i.fetched_at DESC LIMIT ?"
            args.append(limit)
            with session() as con:
                return [_row_to_dict(r) for r in con.execute(sql, args)]
        except sqlite3.Error:
            pass  # graceful fallback below
    sql = "SELECT * FROM items WHERE synthetic=0"
    params: list = []
    if str(query or "").strip():
        sql += " AND (title LIKE ? OR excerpt LIKE ? OR source LIKE ?)"
        like = "%" + str(query).strip()[:120] + "%"
        params = [like, like, like]
    if cat_where:
        sql += cat_where
        params += cat_param
    sql += " ORDER BY score DESC, fetched_at DESC LIMIT ?"
    params.append(limit)
    with session() as con:
        return [_row_to_dict(r) for r in con.execute(sql, params)]


def get_item(guid: str):
    with session() as con:
        row = con.execute("SELECT * FROM items WHERE guid=?", (guid,)).fetchone()
        return _row_to_dict(row) if row else None


def counts() -> dict:
    tables = ("items", "runs", "sources", "watchlist", "jobs", "reports", "feedback", "events", "entities",
              "page_snapshots")
    out = {}
    with session() as con:
        for table in tables:
            out[table] = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    return out


def overview() -> dict:
    out = counts()
    out["fts5"] = FTS_ENABLED
    out["fts_error"] = FTS_ERROR
    out["db"] = str(config.db_path())
    with session() as con:
        row = con.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 1").fetchone()
        out["last_run"] = dict(row) if row else None
        out["cross_verified"] = con.execute(
            "SELECT COUNT(*) FROM items WHERE cross_verified=1").fetchone()[0]
        out["link_only"] = con.execute(
            "SELECT COUNT(*) FROM items WHERE link_only=1").fetchone()[0]
    return out


def list_sources() -> list[dict]:
    with session() as con:
        health = {r["key"]: dict(r) for r in con.execute("SELECT * FROM sources")}
    out = []
    for row in policy.register():
        h = health.get(row["key"], {})
        out.append({**row, "enabled": bool(h.get("enabled", row["auto"])),
                    "ok_count": h.get("ok_count", 0), "fail_count": h.get("fail_count", 0),
                    "last_ok": h.get("last_ok", ""), "last_error": h.get("last_error", ""),
                    "status": h.get("status", "ok"),
                    "last_verified_at": h.get("last_verified_at", "")})
    return out


def source_stale_days() -> int:
    """Source lifecycle stale window (din). Default 30, env ``JIN_AGENT_SOURCE_STALE_DAYS``."""
    try:
        return max(1, int(str(os.environ.get("JIN_AGENT_SOURCE_STALE_DAYS", "30") or 30)))
    except (TypeError, ValueError):
        return 30


def touch_source(key: str, ok: bool, error: str = "") -> None:
    """Source health update — lifecycle status ke saath (ok/verification_failed)."""
    with session() as con:
        if ok:
            con.execute("UPDATE sources SET ok_count=ok_count+1,last_ok=?,last_error='',"
                        "status='ok',last_verified_at=? WHERE key=?",
                        (util.now_iso(), util.now_iso(), key))
        else:
            con.execute("UPDATE sources SET fail_count=fail_count+1,last_error=?,"
                        "status='verification_failed' WHERE key=?",
                        (util.truncate(error, 200), key))


def mark_stale_sources(stale_days: int | None = None) -> int:
    """``ok`` sources jinki aakhri kamyabi verification ``stale_days`` purani ho
    chuki ho unhe ``stale`` mark karo (ipiton STEWARDSHIP pattern)."""
    days = source_stale_days() if stale_days is None else max(1, int(stale_days))
    cutoff = datetime.fromtimestamp(util.epoch() - days * 86400, timezone.utc)
    cutoff_iso = cutoff.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    with session() as con:
        cur = con.execute(
            "UPDATE sources SET status='stale' WHERE status='ok' "
            "AND last_verified_at<>'' AND last_verified_at<?", (cutoff_iso,))
        return int(cur.rowcount)


def set_source_enabled(key: str, enabled: bool) -> None:
    with session() as con:
        con.execute("UPDATE sources SET enabled=? WHERE key=?", (int(bool(enabled)), key))


CHAT_CONTEXT_MAX = 5


def save_chat_query(chat_id, query: str) -> None:
    """Chat ka aakhri sawal JSON list me jamu karo (max ``CHAT_CONTEXT_MAX``).

    Multi-turn follow-up ke liye: ``chat_context.attach`` pichhla sawal
    prompt me jodta hai. Key Telegram chat id hai (``run`` id nahi).
    """
    q = util.truncate(str(query or "").strip(), 400)
    if not q:
        return
    with session() as con:
        row = con.execute("SELECT last_queries FROM chat_context WHERE chat_id=?",
                          (str(chat_id),)).fetchone()
        queries: list[str] = []
        if row and row["last_queries"]:
            try:
                parsed = json.loads(row["last_queries"])
                if isinstance(parsed, list):
                    queries = [str(x).strip() for x in parsed if str(x).strip()]
            except (TypeError, ValueError):
                queries = []
        if not queries or queries[-1] != q:
            queries.append(q)
        queries = queries[-CHAT_CONTEXT_MAX:]
        con.execute(
            "INSERT INTO chat_context(chat_id,last_queries,updated_at) "
            "VALUES(?,?,?) ON CONFLICT(chat_id) DO UPDATE SET "
            "last_queries=excluded.last_queries,updated_at=excluded.updated_at",
            (str(chat_id), _json(queries), util.epoch()))


def last_chat_query(chat_id) -> str:
    """Chat ka aakhri sawal; na ho to ``""``."""
    with session() as con:
        row = con.execute("SELECT last_queries FROM chat_context WHERE chat_id=?",
                          (str(chat_id),)).fetchone()
    if not row or not row["last_queries"]:
        return ""
    try:
        queries = json.loads(row["last_queries"])
    except (TypeError, ValueError):
        return ""
    if isinstance(queries, list) and queries:
        return str(queries[-1] or "")
    return ""


def clear_chat_context(chat_id) -> int:
    """``/new`` par chat context saaf — rowcount (0 ya 1)."""
    with session() as con:
        cur = con.execute("DELETE FROM chat_context WHERE chat_id=?", (str(chat_id),))
        return int(cur.rowcount)


def record_run(query: str, mode: str = "offline") -> int:
    with session() as con:
        cur = con.execute("INSERT INTO runs(query,mode,started_at,status) VALUES(?,?,?,'running')",
                          (util.truncate(query, 400), mode, util.now_iso()))
        return int(cur.lastrowid)


def finish_run(run_id: int, metrics: dict, items_count: int, sources_ok: int,
               sources_failed: int) -> None:
    with session() as con:
        con.execute("UPDATE runs SET finished_at=?,status='done',metrics=?,items_count=?,"
                    "sources_ok=?,sources_failed=? WHERE id=?",
                    (util.now_iso(), _json(metrics), items_count, sources_ok,
                     sources_failed, run_id))


def list_runs(limit: int = 20) -> list[dict]:
    with session() as con:
        return [dict(r) for r in con.execute("SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,))]


def add_watchlist(term: str, category: str = "Custom Watchlist") -> dict:
    term = str(term or "").strip()[:120]
    if not term:
        raise ValueError("Watchlist term khali hai")
    with session() as con:
        con.execute("INSERT OR IGNORE INTO watchlist(term,category,created_at) VALUES(?,?,?)",
                    (term, category, util.now_iso()))
        row = con.execute("SELECT * FROM watchlist WHERE term=?", (term,)).fetchone()
        return dict(row)


def list_watchlist(active_only: bool = False) -> list[dict]:
    sql = "SELECT * FROM watchlist" + (" WHERE active=1" if active_only else "") + " ORDER BY id DESC"
    with session() as con:
        return [dict(r) for r in con.execute(sql)]


def set_watchlist_hit(term: str) -> None:
    with session() as con:
        con.execute("UPDATE watchlist SET last_hit=? WHERE term=?", (util.now_iso(), term))


def remove_watchlist(term: str) -> None:
    """Archive, never delete (policy: sources/records are archived)."""
    with session() as con:
        con.execute("UPDATE watchlist SET active=0 WHERE term=?", (term,))


def feedback_score(guid: str) -> int:
    with session() as con:
        row = con.execute("SELECT COALESCE(SUM(useful),0) FROM feedback WHERE guid=?", (guid,)).fetchone()
        return int(row[0] or 0)


def feedback_scores() -> dict:
    """One connection for the whole ranking pass instead of one per item."""
    with session() as con:
        return {r[0]: int(r[1] or 0) for r in con.execute(
            "SELECT guid, COALESCE(SUM(useful),0) FROM feedback GROUP BY guid")}


def add_feedback(guid: str, useful: bool, note: str = "") -> dict:
    with session() as con:
        con.execute("INSERT INTO feedback(guid,useful,note,created_at) VALUES(?,?,?,?)",
                    (guid, int(bool(useful)), util.truncate(note, 300), util.now_iso()))
        score = feedback_score(guid)
        con.execute("UPDATE items SET useful=? WHERE guid=?", (score, guid))
        return {"guid": guid, "useful": score}


def save_report(title: str, query: str, path: str, fmt: str = "md",
                metrics: dict | None = None) -> dict:
    with session() as con:
        cur = con.execute(
            "INSERT INTO reports(title,query,fmt,path,created_at,metrics) VALUES(?,?,?,?,?,?)",
            (util.truncate(title, 200), util.truncate(query, 400), fmt, path,
             util.now_iso(), _json(metrics or {})))
        return {"id": int(cur.lastrowid), "title": title, "path": path}


def list_reports(limit: int = 30) -> list[dict]:
    with session() as con:
        return [dict(r) for r in con.execute("SELECT * FROM reports ORDER BY id DESC LIMIT ?", (limit,))]


def get_report(report_id: int):
    with session() as con:
        row = con.execute("SELECT * FROM reports WHERE id=?", (report_id,)).fetchone()
        return dict(row) if row else None


def add_event(kind: str, detail: str = "") -> None:
    clean = re.sub(r"(bot\d+:[A-Za-z0-9_-]{10,}|sk-[A-Za-z0-9_-]{10,})", "***", str(detail))
    with session() as con:
        con.execute("INSERT INTO events(ts,kind,detail) VALUES(?,?,?)",
                    (util.now_iso(), kind, util.truncate(clean, 500)))


def list_events(limit: int = 50) -> list[dict]:
    with session() as con:
        return [dict(r) for r in con.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,))]


def enqueue_job(kind: str, payload: dict | None = None, run_at: float | None = None) -> int:
    with session() as con:
        cur = con.execute(
            "INSERT INTO jobs(kind,payload,run_at,created_at) VALUES(?,?,?,?)",
            (kind, _json(payload or {}), float(run_at if run_at is not None else util.epoch()),
             util.now_iso()))
        return int(cur.lastrowid)


def claim_job():
    with session() as con:
        row = con.execute("SELECT * FROM jobs WHERE status='pending' AND run_at<=? "
                          "ORDER BY run_at,id LIMIT 1", (util.epoch(),)).fetchone()
        if not row:
            return None
        con.execute("UPDATE jobs SET status='running',attempts=attempts+1 WHERE id=?", (row["id"],))
        return dict(row)


def finish_job(job_id: int, ok: bool, error: str = "") -> None:
    with session() as con:
        con.execute("UPDATE jobs SET status=?,last_error=?,finished_at=? WHERE id=?",
                    ("done" if ok else "failed", util.truncate(error, 300), util.now_iso(), job_id))


def list_jobs(limit: int = 30) -> list[dict]:
    with session() as con:
        return [dict(r) for r in con.execute("SELECT * FROM jobs ORDER BY id DESC LIMIT ?", (limit,))]


def get_schedule_state(key: str) -> float:
    with session() as con:
        row = con.execute("SELECT last_ts FROM schedule_state WHERE key=?", (key,)).fetchone()
        return float(row[0]) if row else 0.0


def set_schedule_state(key: str, ts: float | None = None) -> None:
    with session() as con:
        con.execute("INSERT INTO schedule_state(key,last_ts) VALUES(?,?) "
                    "ON CONFLICT(key) DO UPDATE SET last_ts=excluded.last_ts",
                    (key, float(ts if ts is not None else util.epoch())))


def _table_exists(con, name: str) -> bool:
    row = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                      (name,)).fetchone()
    return row is not None


def _retention_days(days: int | None = None) -> int:
    """Retention window (din). Default 180, env ``JIN_AGENT_RETENTION_DAYS``."""
    if days is None:
        try:
            days = int(str(os.environ.get("JIN_AGENT_RETENTION_DAYS", "180") or 180))
        except (TypeError, ValueError):
            days = 180
    return util.clamp(days, 1, 3650, 180)


def retention(days: int | None = None) -> dict:
    """Purani records ka sweep — items ke ilawa operational tables bhi bounded.

    Articles (items) ke saath ye tables bhi prune hote hain: ``events``,
    ``runs``, ``reports``, ``jobs``, ``search_memory``, ``tg_candidates``.
    Dead ``tg_channels`` (30 din purane) delete hote hain taake registry
    unbounded na barhe. Sources / watchlist archive-not-delete rehte hain.
    """
    days = _retention_days(days)
    cutoff = datetime.fromtimestamp(util.epoch() - days * 86400, timezone.utc)
    cutoff_iso = cutoff.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    cutoff_epoch = util.epoch() - days * 86400
    pruned: dict[str, int] = {}
    with session() as con:
        removed = con.execute("DELETE FROM items WHERE fetched_at<>'' AND fetched_at<?",
                              (cutoff_iso,)).rowcount
        con.execute("DELETE FROM entities WHERE item_id NOT IN (SELECT id FROM items)")
        for table, column in (("events", "ts"), ("runs", "started_at"),
                              ("reports", "created_at"), ("jobs", "created_at")):
            if _table_exists(con, table):
                pruned[table] = con.execute(
                    f"DELETE FROM {table} WHERE {column}<>'' AND {column}<?",
                    (cutoff_iso,)).rowcount
        if _table_exists(con, "search_memory"):
            pruned["search_memory"] = con.execute(
                "DELETE FROM search_memory WHERE updated_at<?", (cutoff_epoch,)).rowcount
        if _table_exists(con, "tg_candidates"):
            pruned["tg_candidates"] = con.execute(
                "DELETE FROM tg_candidates WHERE found_at<?", (cutoff_epoch,)).rowcount
        # Freelist pages wapas le lo (auto_vacuum off ho to no-op bhi safe).
        try:
            con.execute("PRAGMA incremental_vacuum")
        except sqlite3.Error:
            pass
    # Dead channel registry TTL (channels module apni table ensure karta hai).
    # Alag connection — upar wala write transaction commit ho chuka hai.
    try:
        from . import channels as channels_mod
        pruned["tg_channels_dead"] = channels_mod.cleanup_dead()
        pruned["tg_channels_stale"] = channels_mod.mark_stale_channels()
    except Exception:
        pruned["tg_channels_dead"] = 0
        pruned["tg_channels_stale"] = 0
    try:
        pruned["sources_stale"] = mark_stale_sources()
    except Exception:
        pruned["sources_stale"] = 0
    try:
        pruned["traces"] = _prune_traces()
    except Exception:
        pruned["traces"] = 0
    vacuum = vacuum_db()
    add_event("retention", f"Removed {removed} articles older than {days} days; "
                           f"pruned={pruned}")
    return {"removed": int(removed), "pruned": pruned, "vacuum": vacuum,
            "cutoff": cutoff_iso, "days": days}


def vacuum_db(threshold_pages: int = 1000) -> dict:
    """DB file chhota rakho: ``VACUUM`` agar freelist bara ho.

    ``incremental_vacuum`` retention ke andar chalta hai; agar us se bhi
    freelist zyada bana (bade delete) to yahan poora ``VACUUM`` DB rebuild
    karke file size wapas le leta hai. Best-effort — fail par bhi run
    crash nahi hota.
    """
    before = after = 0
    done = False
    try:
        con = sqlite3.connect(str(config.db_path()), timeout=15)
        try:
            con.execute("PRAGMA busy_timeout=15000")
            before = int(con.execute("PRAGMA freelist_count").fetchone()[0])
            if before >= max(0, int(threshold_pages)):
                con.execute("VACUUM")
                done = True
            after = int(con.execute("PRAGMA freelist_count").fetchone()[0])
        finally:
            con.close()
    except sqlite3.Error:
        return {"freelist_before": before, "freelist_after": after, "vacuumed": False}
    return {"freelist_before": before, "freelist_after": after, "vacuumed": done}


def _prune_backups(keep: int | None = None) -> int:
    """``data/backups/`` me aakhri N backup rakho, purane delete karo."""
    if keep is None:
        try:
            keep = int(str(os.environ.get("JIN_AGENT_BACKUP_KEEP", "7") or 7))
        except (TypeError, ValueError):
            keep = 7
    keep = max(1, int(keep))
    folder = config.backups_dir()
    try:
        files = sorted(
            (p for p in folder.iterdir()
             if p.is_file() and p.name.startswith("jin_agent-") and p.suffix == ".db"),
            key=lambda p: p.name, reverse=True)
    except OSError:
        return 0
    pruned = 0
    for old in files[keep:]:
        try:
            old.unlink()
            pruned += 1
        except OSError:
            continue
    return pruned


def _prune_traces(days: int | None = None) -> int:
    """``data/runs/`` ke purane per-run trace JSON hatao (default 30 din)."""
    if days is None:
        try:
            days = int(str(os.environ.get("JIN_AGENT_TRACE_DAYS", "30") or 30))
        except (TypeError, ValueError):
            days = 30
    days = max(1, int(days))
    folder = config.runs_dir()
    cutoff = util.epoch() - days * 86400
    try:
        entries = list(folder.iterdir())
    except OSError:
        return 0
    pruned = 0
    for path in entries:
        if path.suffix != ".json":
            continue
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
                pruned += 1
        except OSError:
            continue
    return pruned


def backup() -> dict:
    """SQLite online backup - stdlib, no external process. Rolling retention."""
    from pathlib import Path
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    dest = config.backups_dir() / f"jin_agent-{stamp}.db"
    source = connect()
    target = sqlite3.connect(str(dest))
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    pruned = _prune_backups()
    add_event("backup", f"Backup written: {Path(dest).name} (pruned {pruned} old)")
    return {"path": str(dest), "bytes": dest.stat().st_size,
            "pruned": int(pruned), "keep": _backup_keep()}


def _backup_keep() -> int:
    try:
        return max(1, int(str(os.environ.get("JIN_AGENT_BACKUP_KEEP", "7") or 7)))
    except (TypeError, ValueError):
        return 7
