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
import os

from . import store, util

VERSION = "1.0"
DEFAULT_MAX_ROUNDS = 5


def max_rounds() -> int:
    """Rounds cap (env ``JIN_AGENT_MAX_ROUNDS``, default 5) — unbounded growth rok."""
    try:
        return max(1, int(str(os.environ.get("JIN_AGENT_MAX_ROUNDS",
                                             str(DEFAULT_MAX_ROUNDS))
                          or DEFAULT_MAX_ROUNDS)))
    except (TypeError, ValueError):
        return DEFAULT_MAX_ROUNDS


SCHEMA = """
CREATE TABLE IF NOT EXISTS search_memory (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  chat_id INTEGER NOT NULL,
  query_key TEXT NOT NULL,
  query TEXT NOT NULL,
  round_no INTEGER NOT NULL DEFAULT 1,
  used_sources TEXT NOT NULL DEFAULT '[]',
  used_channels TEXT NOT NULL DEFAULT '[]',
  failed_channels TEXT NOT NULL DEFAULT '[]',
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
        # Purani DB migration: failed_channels column add karo.
        cols = {r[1] for r in con.execute("PRAGMA table_info(search_memory)")}
        if "failed_channels" not in cols:
            con.execute("ALTER TABLE search_memory "
                        "ADD COLUMN failed_channels TEXT NOT NULL DEFAULT '[]'")


def channel_negative_ttl_days() -> int:
    """Failed-channel negative memory TTL (din).

    Default 7, env ``JIN_AGENT_CHANNEL_NEGATIVE_TTL_DAYS``. 0 = hamesha yaad.
    """
    try:
        return max(0, int(str(os.environ.get("JIN_AGENT_CHANNEL_NEGATIVE_TTL_DAYS", "7")
                               or 7)))
    except (TypeError, ValueError):
        return 7


def _failed_entries(row) -> list[dict]:
    return _parse_failed((row or {}).get("failed_channels") or "[]")


def failed_channels(row_id: int) -> list[str]:
    """TTL ke andar waale failed channel handles (purane nahi)."""
    row = get(row_id)
    if not row:
        return []
    now = util.epoch()
    ttl = channel_negative_ttl_days() * 86400
    out: list[str] = []
    for entry in _failed_entries(row):
        handle = str(entry.get("channel") or "").strip()
        at = float(entry.get("at") or 0)
        if not handle:
            continue
        if ttl and now - at > ttl:
            continue
        if handle not in out:
            out.append(handle)
    return out


def remember_failed(row_id: int, channels=None) -> dict | None:
    """Channel ko negative memory me TTL ke saath yaad rakho (dobara try na ho)."""
    row = get(row_id)
    if not row:
        return None
    now = util.epoch()
    ttl = channel_negative_ttl_days() * 86400
    merged: dict[str, float] = {}
    for entry in _failed_entries(row):
        handle = str(entry.get("channel") or "").strip()
        if handle:
            merged[handle] = float(entry.get("at") or 0)
    for raw in channels or []:
        handle = str(raw or "").strip()
        if handle:
            merged[handle] = now
    kept = [{"channel": h, "at": at} for h, at in merged.items()
            if not ttl or now - at <= ttl]
    with store.session() as con:
        con.execute("UPDATE search_memory SET failed_channels=?, updated_at=? "
                    "WHERE id=?", (json.dumps(kept), now, int(row_id)))
    return get(row_id)


def query_key(query: str) -> str:
    """Normalised key: lowercase, spaces collapsed, 120 chars."""
    return " ".join(str(query or "").lower().split())[:120]


def _loads(raw: str) -> list[str]:
    try:
        data = json.loads(raw or "[]")
    except Exception:
        return []
    return [str(x) for x in data] if isinstance(data, list) else []


def _parse_failed(raw) -> list[dict]:
    if isinstance(raw, list):
        return [e for e in raw if isinstance(e, dict)]
    try:
        data = json.loads(raw or "[]")
    except (TypeError, ValueError):
        return []
    return [e for e in data if isinstance(e, dict)] if isinstance(data, list) else []


def _row_to_dict(row) -> dict:
    return {
        "id": int(row["id"]),
        "chat_id": int(row["chat_id"]),
        "query": str(row["query"]),
        "query_key": str(row["query_key"]),
        "round_no": int(row["round_no"] or 1),
        "used_sources": _loads(row["used_sources"]),
        "used_channels": _loads(row["used_channels"]),
        "failed_channels": _parse_failed(row["failed_channels"] or "[]"),
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
    if advance:
        round_no = min(round_no, max_rounds())
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
