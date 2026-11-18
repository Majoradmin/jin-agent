"""P29: per-query search memory — kaunse sources/channels use ho chuke.

User ki hidayat: "agar main 'no' kahoon to jo ab tak search engine / channel /
zaraaye use kiye hain memory me rakho." Har round ke used adapter keys aur
used channels SQLite mein save hote hain; agla round unhe skip karta hai taake
wahi cheez dobara na dhoondhi jaye.

Sirf metadata save hota hai (key names + channel handles). Koi query text
sirf local DB mein rehta hai; koi network call nahi.
"""

from __future__ import annotations

import json

from . import store, util

VERSION = "1.0"

SCHEMA = """
CREATE TABLE IF NOT EXISTS search_memory (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  chat_id INTEGER NOT NULL,
  query_key TEXT NOT NULL,
  query TEXT NOT NULL,
  round_no INTEGER NOT NULL DEFAULT 1,
  used_sources TEXT NOT NULL DEFAULT '[]',
  used_channels TEXT NOT NULL DEFAULT '[]',
  status TEXT NOT NULL DEFAULT 'active',
  created_at INTEGER NOT NULL DEFAULT 0,
  updated_at INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_search_memory_chat
  ON search_memory(chat_id, query_key);
"""


def ensure_table() -> None:
    with store.session() as con:
        con.executescript(SCHEMA)


def query_key(query: str) -> str:
    """Normalised key: lowercase, spaces collapsed, 120 chars."""
    return " ".join(str(query or "").lower().split())[:120]


def _loads(raw: str) -> list[str]:
    try:
        data = json.loads(raw or "[]")
    except Exception:
        return []
    return [str(x) for x in data] if isinstance(data, list) else []


def _row_to_dict(row) -> dict:
    return {
        "id": int(row["id"]),
        "chat_id": int(row["chat_id"]),
        "query": str(row["query"]),
        "query_key": str(row["query_key"]),
        "round_no": int(row["round_no"] or 1),
        "used_sources": _loads(row["used_sources"]),
        "used_channels": _loads(row["used_channels"]),
        "status": str(row["status"]),
        "created_at": int(row["created_at"] or 0),
        "updated_at": int(row["updated_at"] or 0),
    }


def begin(chat_id: int, query: str) -> dict:
    """Active run return karo, warna naya round-1 row banao."""
    ensure_table()
    key = query_key(query)
    with store.session() as con:
        row = con.execute(
            "SELECT * FROM search_memory WHERE chat_id=? AND query_key=? "
            "AND status='active' ORDER BY id DESC LIMIT 1",
            (int(chat_id), key)).fetchone()
        if row:
            return _row_to_dict(row)
        now = util.epoch()
        cur = con.execute(
            "INSERT INTO search_memory(chat_id, query_key, query, round_no, "
            "created_at, updated_at) VALUES(?,?,?,?,?,?)",
            (int(chat_id), key, str(query)[:1000], 1, now, now))
        row = con.execute("SELECT * FROM search_memory WHERE id=?",
                          (cur.lastrowid,)).fetchone()
    return _row_to_dict(row)


def get(row_id: int) -> dict | None:
    ensure_table()
    with store.session() as con:
        row = con.execute("SELECT * FROM search_memory WHERE id=?",
                          (int(row_id),)).fetchone()
    return _row_to_dict(row) if row else None


def remember(row_id: int, sources=None, channels=None,
             advance: bool = False) -> dict | None:
    """Is round ke used sources/channels merge karo (optionally next round)."""
    row = get(row_id)
    if not row:
        return None
    used_s = list(dict.fromkeys(row["used_sources"] + [str(s) for s in (sources or [])]))
    used_c = list(dict.fromkeys(row["used_channels"] + [str(c) for c in (channels or [])]))
    round_no = row["round_no"] + (1 if advance else 0)
    with store.session() as con:
        con.execute(
            "UPDATE search_memory SET used_sources=?, used_channels=?, "
            "round_no=?, updated_at=? WHERE id=?",
            (json.dumps(used_s), json.dumps(used_c), round_no,
             util.epoch(), int(row_id)))
    return get(row_id)


def mark_done(row_id: int) -> dict | None:
    ensure_table()
    with store.session() as con:
        con.execute("UPDATE search_memory SET status='done', updated_at=? WHERE id=?",
                    (util.epoch(), int(row_id)))
    return get(row_id)


def reset(row_id: int) -> dict | None:
    """Sab sources dobara try karne ke liye used lists clear karo."""
    ensure_table()
    with store.session() as con:
        con.execute(
            "UPDATE search_memory SET used_sources='[]', used_channels='[]', "
            "round_no=1, status='active', updated_at=? WHERE id=?",
            (util.epoch(), int(row_id)))
    return get(row_id)


def recent(chat_id: int, limit: int = 5) -> list[dict]:
    ensure_table()
    with store.session() as con:
        rows = con.execute(
            "SELECT * FROM search_memory WHERE chat_id=? ORDER BY id DESC LIMIT ?",
            (int(chat_id), max(1, int(limit)))).fetchall()
    return [_row_to_dict(r) for r in rows]
