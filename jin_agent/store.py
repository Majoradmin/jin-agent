"""SQLite WAL + FTS5 archive for JIN Agent.

Everything is local, additive and auto-migrating. Sources are archived, never
deleted; only old *articles* are removed by the retention job.
"""

from __future__ import annotations

import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from . import config, policy, util

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
  last_error TEXT NOT NULL DEFAULT ''
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
    "confidence", "verified", "cross_verified", "link_only", "useful", "meta",
)


def connect() -> sqlite3.Connection:
    config.ensure_dirs()
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
        try:
            con.executescript(SCHEMA_FTS)
            FTS_ENABLED = True
            FTS_ERROR = ""
        except sqlite3.OperationalError as exc:
            FTS_ENABLED = False
            FTS_ERROR = str(exc)
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
            canonical = item.get("canonical") or util.canonical_url(item.get("url", ""))
            item["canonical"] = canonical
            item["guid"] = item.get("guid") or (
                item.get("source_key", "src") + ":" +
                util.fingerprint(item.get("title", ""), canonical))
            item["date_checked"] = item.get("date_checked") or util.now_iso()
            item["fetched_at"] = item.get("fetched_at") or util.now_iso()
            item["fingerprint"] = item.get("fingerprint") or util.fingerprint(
                item.get("title", ""), canonical)
            item["content_hash"] = item.get("content_hash") or util.sha256(
                (item.get("title", "") + item.get("excerpt", "") + item.get("body", ""))[:4000])
            for key in ("entities", "reasons", "meta"):
                if not isinstance(item.get(key), str):
                    item[key] = _json(item.get(key, [] if key != "meta" else {}))
            for key in ("verified", "cross_verified", "link_only", "useful"):
                item[key] = int(bool(item.get(key)))
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
                   "WHERE items_fts MATCH ?")
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
    sql = "SELECT * FROM items WHERE 1=1"
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
    tables = ("items", "runs", "sources", "watchlist", "jobs", "reports", "feedback", "events", "entities")
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
                    "last_ok": h.get("last_ok", ""), "last_error": h.get("last_error", "")})
    return out


def touch_source(key: str, ok: bool, error: str = "") -> None:
    with session() as con:
        if ok:
            con.execute("UPDATE sources SET ok_count=ok_count+1,last_ok=?,last_error='' WHERE key=?",
                        (util.now_iso(), key))
        else:
            con.execute("UPDATE sources SET fail_count=fail_count+1,last_error=? WHERE key=?",
                        (util.truncate(error, 200), key))


def set_source_enabled(key: str, enabled: bool) -> None:
    with session() as con:
        con.execute("UPDATE sources SET enabled=? WHERE key=?", (int(bool(enabled)), key))


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


def retention(days: int = 90) -> dict:
    """Delete old ARTICLES only. Sources / watchlist are archived, never deleted."""
    days = util.clamp(days, 1, 3650, 90)
    cutoff = datetime.fromtimestamp(util.epoch() - days * 86400, timezone.utc)
    cutoff_iso = cutoff.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    with session() as con:
        removed = con.execute("DELETE FROM items WHERE fetched_at<>'' AND fetched_at<?",
                              (cutoff_iso,)).rowcount
        con.execute("DELETE FROM entities WHERE item_id NOT IN (SELECT id FROM items)")
    add_event("retention", f"Removed {removed} articles older than {days} days")
    return {"removed": int(removed), "cutoff": cutoff_iso, "days": days}


def backup() -> dict:
    """SQLite online backup - stdlib, no external process."""
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
    add_event("backup", f"Backup written: {Path(dest).name}")
    return {"path": str(dest), "bytes": dest.stat().st_size}
