"""MobileLab - local SQLite store. Zero third-party dependencies."""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, "data")
DB_PATH = os.path.join(DATA_DIR, "mobilelab.db")

_LOCK = threading.RLock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS packages (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    path         TEXT NOT NULL,
    oem          TEXT,
    model        TEXT,
    platform     TEXT,
    chipset      TEXT,
    storage      TEXT,
    file_count   INTEGER DEFAULT 0,
    total_size   INTEGER DEFAULT 0,
    health       INTEGER DEFAULT 0,
    tags         TEXT DEFAULT '',
    notes        TEXT DEFAULT '',
    report_json  TEXT DEFAULT '{}',
    created_at   REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS package_files (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    package_id  INTEGER NOT NULL REFERENCES packages(id) ON DELETE CASCADE,
    relpath     TEXT NOT NULL,
    size        INTEGER DEFAULT 0,
    fingerprint TEXT,
    kind        TEXT,
    meta_json   TEXT DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_pf_package ON package_files(package_id);
CREATE INDEX IF NOT EXISTS idx_pf_hash ON package_files(fingerprint);

CREATE TABLE IF NOT EXISTS articles (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    guid        TEXT UNIQUE,
    title       TEXT,
    url         TEXT,
    source      TEXT,
    published   TEXT,
    category    TEXT,
    score       REAL DEFAULT 0,
    matched     TEXT DEFAULT '',
    excerpt     TEXT DEFAULT '',
    khulasa     TEXT DEFAULT '',
    saved       INTEGER DEFAULT 0,
    is_read     INTEGER DEFAULT 0,
    fetched_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_articles_fetched ON articles(fetched_at);

CREATE TABLE IF NOT EXISTS models (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    model        TEXT UNIQUE NOT NULL,
    oem          TEXT DEFAULT '',
    chipset      TEXT DEFAULT '',
    platform     TEXT DEFAULT '',
    storage      TEXT DEFAULT '',
    official_url TEXT DEFAULT '',
    notes        TEXT DEFAULT '',
    updated_at   REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    imei        TEXT DEFAULT '',
    model       TEXT DEFAULT '',
    customer    TEXT DEFAULT '',
    proof_ok    INTEGER DEFAULT 0,
    route       TEXT DEFAULT '',
    notes       TEXT DEFAULT '',
    created_at  REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS cases (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    case_no      TEXT UNIQUE NOT NULL,
    technician   TEXT DEFAULT '',
    shop         TEXT DEFAULT '',
    customer     TEXT NOT NULL,
    contact      TEXT DEFAULT '',
    brand        TEXT DEFAULT '',
    model        TEXT DEFAULT '',
    device_id    TEXT DEFAULT '',
    issue_type   TEXT DEFAULT '',
    route_id     TEXT DEFAULT '',
    proof_json   TEXT DEFAULT '[]',
    proof_ok     INTEGER DEFAULT 0,
    consent      INTEGER DEFAULT 0,
    status       TEXT DEFAULT 'draft',
    notes        TEXT DEFAULT '',
    created_at   REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cases_created ON cases(created_at);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""

DEFAULT_SETTINGS = {
    "llm_endpoint": "",
    "llm_key": "",
    "llm_model": "",
    "auto_min_score": "2",
    "cache_minutes": "15",
    "technician": "",
    "shop": "",
}


def connect() -> sqlite3.Connection:
    os.makedirs(DATA_DIR, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=15, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con


@contextmanager
def _session():
    """Yield a connection, commit/rollback on exit, then ALWAYS close it.

    ``with sqlite3.connect(...)`` only manages the transaction -- it does not
    close the handle. Explicit closing removes ResourceWarning leaks under the
    full P8 regression suite.
    """
    with _LOCK:
        con = connect()
        try:
            with con:
                yield con
        finally:
            con.close()


def init() -> None:
    with _session() as con:
        con.executescript(SCHEMA)
        for k, v in DEFAULT_SETTINGS.items():
            con.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (k, v))
        con.commit()


def rows(sql: str, args=()) -> list[dict]:
    with _session() as con:
        return [dict(r) for r in con.execute(sql, args).fetchall()]


def one(sql: str, args=()):
    with _session() as con:
        r = con.execute(sql, args).fetchone()
        return dict(r) if r else None


def execute(sql: str, args=()) -> int:
    with _session() as con:
        cur = con.execute(sql, args)
        con.commit()
        return cur.lastrowid or 0


def get_settings() -> dict:
    return {r["key"]: r["value"] for r in rows("SELECT key,value FROM settings")}


def set_settings(data: dict) -> dict:
    for k, v in data.items():
        if k in DEFAULT_SETTINGS:
            execute("INSERT INTO settings(key,value) VALUES(?,?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (k, str(v or "")))
    return get_settings()


def save_package(scan: dict, report: dict, name: str = "", tags: str = "", notes: str = "") -> int:
    """Insert the package and all its files in ONE connection / transaction (QA #10)."""
    meta = scan.get("meta", {})
    with _LOCK:
        con = connect()
        try:
            cur = con.execute(
                """INSERT INTO packages
                   (name,path,oem,model,platform,chipset,storage,file_count,total_size,health,tags,notes,report_json,created_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    name or os.path.basename(scan["root"]),
                    scan["root"],
                    meta.get("oem", ""),
                    meta.get("model", ""),
                    meta.get("platform", ""),
                    meta.get("chipset", ""),
                    meta.get("storage", ""),
                    len(scan.get("files", [])),
                    scan.get("total_size", 0),
                    report.get("health", 0),
                    tags,
                    notes,
                    json.dumps(report, ensure_ascii=False),
                    time.time(),
                ),
            )
            pid = cur.lastrowid or 0
            file_rows = [
                (pid, f["relpath"], f["size"], f.get("fingerprint", ""),
                 f.get("kind", ""), json.dumps(f.get("meta", {}), ensure_ascii=False))
                for f in scan.get("files", [])
            ]
            if file_rows:
                con.executemany(
                    "INSERT INTO package_files(package_id,relpath,size,fingerprint,kind,meta_json) "
                    "VALUES(?,?,?,?,?,?)", file_rows)
            con.commit()
            return pid
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()


def package_detail(pid: int) -> dict | None:
    p = one("SELECT * FROM packages WHERE id=?", (pid,))
    if not p:
        return None
    p["files"] = rows("SELECT * FROM package_files WHERE package_id=? ORDER BY relpath", (pid,))
    for f in p["files"]:
        try:
            f["meta"] = json.loads(f.get("meta_json") or "{}")
        except Exception:
            f["meta"] = {}
    try:
        p["report"] = json.loads(p.get("report_json") or "{}")
    except Exception:
        p["report"] = {}
    return p


def duplicate_files(fingerprint: str, exclude_pid: int | None = None) -> list[dict]:
    if not fingerprint:
        return []
    sql = """SELECT pf.relpath, p.id AS package_id, p.name AS package_name, p.path AS package_path
             FROM package_files pf JOIN packages p ON p.id=pf.package_id
             WHERE pf.fingerprint=?"""
    args: list = [fingerprint]
    if exclude_pid:
        sql += " AND p.id<>?"
        args.append(exclude_pid)
    return rows(sql + " LIMIT 20", tuple(args))


def upsert_articles(items: list[dict]) -> None:
    with _session() as con:
        for a in items:
            con.execute(
                """INSERT INTO articles
                   (guid,title,url,source,published,category,score,matched,excerpt,khulasa,fetched_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(guid) DO UPDATE SET
                     score=excluded.score, matched=excluded.matched,
                     excerpt=excluded.excerpt, khulasa=excluded.khulasa,
                     fetched_at=excluded.fetched_at, category=excluded.category""",
                (a["guid"], a["title"], a["url"], a["source"], a.get("published", ""),
                 a.get("category", "general"), a.get("score", 0), a.get("matched", ""),
                 a.get("excerpt", ""), a.get("khulasa", ""), time.time()),
            )
        con.commit()


def cached_articles(max_age_minutes: int) -> list[dict]:
    cutoff = time.time() - max_age_minutes * 60
    return rows("SELECT * FROM articles WHERE fetched_at>=? ORDER BY score DESC, fetched_at DESC", (cutoff,))


def add_case(d: dict) -> dict:
    """Sahulat case / asset register. Additive schema — existing DB auto-migrates via init()."""
    case_no = d.get("case_no") or ("ML-" + time.strftime("%Y%m%d") + "-" + os.urandom(3).hex().upper())
    cid = execute(
        """INSERT INTO cases
           (case_no,technician,shop,customer,contact,brand,model,device_id,issue_type,
            route_id,proof_json,proof_ok,consent,status,notes,created_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (case_no, d.get("technician", ""), d.get("shop", ""), d["customer"],
         d.get("contact", ""), d.get("brand", ""), d.get("model", ""),
         d.get("device_id", ""), d.get("issue_type", ""), d.get("route_id", ""),
         json.dumps(d.get("proof", []), ensure_ascii=False),
         1 if d.get("proof_ok") else 0, 1 if d.get("consent") else 0,
         d.get("status", "draft"), d.get("notes", ""), time.time()),
    )
    row = one("SELECT * FROM cases WHERE id=?", (cid,)) or {}
    try:
        row["proof"] = json.loads(row.get("proof_json") or "[]")
    except Exception:
        row["proof"] = []
    return row


def list_cases(limit: int = 200) -> list[dict]:
    try:
        limit = max(1, min(500, int(limit)))
    except (TypeError, ValueError):
        limit = 200
    items = rows("SELECT * FROM cases ORDER BY created_at DESC LIMIT ?", (limit,))
    for r in items:
        try:
            r["proof"] = json.loads(r.get("proof_json") or "[]")
        except Exception:
            r["proof"] = []
    return items


def counts() -> dict:
    return {
        "packages": one("SELECT COUNT(*) n FROM packages")["n"],
        "files": one("SELECT COUNT(*) n FROM package_files")["n"],
        "articles": one("SELECT COUNT(*) n FROM articles")["n"],
        "saved": one("SELECT COUNT(*) n FROM articles WHERE saved=1")["n"],
        "models": one("SELECT COUNT(*) n FROM models")["n"],
        "jobs": one("SELECT COUNT(*) n FROM jobs")["n"],
        "cases": one("SELECT COUNT(*) n FROM cases")["n"],
    }
