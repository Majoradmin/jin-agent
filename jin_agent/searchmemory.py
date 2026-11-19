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
  rejected_ideas TEXT NOT NULL DEFAULT '[]',
  source_stats TEXT NOT NULL DEFAULT '{}',
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
        for name, ddl in (("failed_channels", "TEXT NOT NULL DEFAULT '[]'"),
                          ("rejected_ideas", "TEXT NOT NULL DEFAULT '[]'"),
                          ("source_stats", "TEXT NOT NULL DEFAULT '{}'")):
            if name not in cols:
                con.execute(f"ALTER TABLE search_memory ADD COLUMN {name} {ddl}")


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


def rejected_ideas(row_id: int) -> list[str]:
    row = get(row_id)
    return list(row.get("rejected_ideas") or []) if row else []


def remember_rejected(row_id: int, ideas=None) -> dict | None:
    """Jo ideas user ne 'nai mila' par reject kiye — unhe yaad rakho (dobara na doonde)."""
    row = get(row_id)
    if not row:
        return None
    cur = [str(x) for x in (row.get("rejected_ideas") or [])]
    for raw in ideas or []:
        text = str(raw or "").strip()[:200]
        if text and text not in cur:
            cur.append(text)
    with store.session() as con:
        con.execute("UPDATE search_memory SET rejected_ideas=?, updated_at=? "
                    "WHERE id=?", (json.dumps(cur), util.epoch(), int(row_id)))
    return get(row_id)


def source_stats(row_id: int) -> dict:
    row = get(row_id)
    return dict(row.get("source_stats") or {}) if row else {}


def note_source_stat(row_id: int, source: str, kind: str = "cited") -> dict | None:
    """Per-source counter (acted/cited/skipped/rejected) — suppression memory."""
    row = get(row_id)
    if not row:
        return None
    key = str(source or "").strip()
    if not key:
        return row
    stats = dict(row.get("source_stats") or {})
    bucket = stats.setdefault(key, {"acted": 0, "cited": 0,
                                    "skipped": 0, "rejected": 0})
    if kind in bucket:
        bucket[kind] = int(bucket[kind]) + 1
    with store.session() as con:
        con.execute("UPDATE search_memory SET source_stats=?, updated_at=? "
                    "WHERE id=?", (json.dumps(stats), util.epoch(), int(row_id)))
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


def _loads_dict(raw) -> dict:
    try:
        data = json.loads(raw or "{}")
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


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
        "rejected_ideas": _loads(row["rejected_ideas"]),
        "source_stats": _loads_dict(row["source_stats"]),
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


def reset_chat(chat_id: int) -> int:
    """``/new`` — chat ka active context band karo (naya research fresh shuru)."""
    ensure_table()
    with store.session() as con:
        cur = con.execute(
            "UPDATE search_memory SET status='done', updated_at=? "
            "WHERE chat_id=? AND status='active'", (util.epoch(), int(chat_id)))
        return int(cur.rowcount)


def audit(stale_days: int | None = None) -> dict:
    """Memory ka duplicate/conflict/stale scan + audit trail (ashishki pattern)."""
    ensure_table()
    if stale_days is None:
        try:
            stale_days = int(str(os.environ.get("JIN_AGENT_MEMORY_STALE_DAYS", "30") or 30))
        except (TypeError, ValueError):
            stale_days = 30
    with store.session() as con:
        rows = con.execute("SELECT * FROM search_memory ORDER BY id DESC").fetchall()
    now = util.epoch()
    active: dict[tuple, list[dict]] = {}
    stale: list[dict] = []
    for row in rows:
        d = _row_to_dict(row)
        if d["status"] != "active":
            continue
        active.setdefault((d["chat_id"], d["query_key"]), []).append(d)
        age = now - int(d.get("updated_at") or 0)
        if age > stale_days * 86400:
            stale.append({"id": d["id"], "query": d["query"],
                          "age_days": int(age // 86400)})
    duplicates: list[dict] = []
    conflicts: list[dict] = []
    for (chat_id, qkey), items in active.items():
        if len(items) > 1:
            duplicates.append({"chat_id": chat_id, "query": items[0]["query"],
                               "count": len(items), "ids": [i["id"] for i in items]})
            used = {tuple(sorted(i.get("used_sources") or [])) for i in items}
            if len(used) > 1:
                conflicts.append({"chat_id": chat_id, "query": items[0]["query"],
                                  "count": len(items)})
    try:
        store.add_event("memory_audit", f"duplicates={len(duplicates)} "
                                        f"conflicts={len(conflicts)} stale={len(stale)}")
    except Exception:
        pass
    return {"duplicates": duplicates, "conflicts": conflicts, "stale": stale}


def recent(chat_id: int, limit: int = 5) -> list[dict]:
    ensure_table()
    with store.session() as con:
        rows = con.execute(
            "SELECT * FROM search_memory WHERE chat_id=? ORDER BY id DESC LIMIT ?",
            (int(chat_id), max(1, int(limit)))).fetchall()
    return [_row_to_dict(r) for r in rows]
