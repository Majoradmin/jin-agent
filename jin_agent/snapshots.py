"""P27 - page snapshots and change detection ("naya kya aaya").

Every live adapter payload (and every planner ``fetch_url`` page) can be
snapshotted. A snapshot stores a content hash, the size, a timestamp and a
bounded copy of the visible text. Comparing the new text with the previous
snapshot gives a small, honest diff summary:

  * how many lines were added / removed,
  * the first N changed lines (``+ new`` / ``- old``),
  * per-source "changes since last run" for the orchestrator / digest payload.

The table is local SQLite (``page_snapshots``) and upserts one row per
``(source_key, canonical_url)`` - no unbounded history, no network.
"""

from __future__ import annotations

import difflib
import json
from datetime import datetime, timezone

from . import canonical, config, store, util

STATE_KEY = "snapshots:last_run"
MAX_SNAPSHOT_CHARS = 8000
MAX_DIFF_LINES = 5
MAX_STORED_ROWS = 2000

SCHEMA = """
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
"""

_READY_PATH = ""


def ensure_table() -> None:
    """Create the table once per data directory (tests switch data dirs)."""
    global _READY_PATH
    target = str(config.db_path())
    if _READY_PATH == target:
        return
    with store.session() as con:
        con.executescript(SCHEMA)
    _READY_PATH = target


def _clean_lines(text: str) -> list[str]:
    return [line.strip() for line in str(text or "").splitlines()
            if line.strip()][:2000]


def diff_text(old: str, new: str, max_lines: int = MAX_DIFF_LINES) -> dict:
    """Line-level diff summary. Pure, deterministic and bounded."""
    old_lines, new_lines = _clean_lines(old), _clean_lines(new)
    added = removed = 0
    changed: list[str] = []
    matcher = difflib.SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if tag in ("replace", "delete"):
            removed += max(0, i2 - i1)
            for line in old_lines[i1:i2]:
                if len(changed) < max_lines:
                    changed.append("- " + line)
        if tag in ("replace", "insert"):
            added += max(0, j2 - j1)
            for line in new_lines[j1:j2]:
                if len(changed) < max_lines:
                    changed.append("+ " + line)
    return {"added_lines": added, "removed_lines": removed,
            "changed_lines": changed[:max(max_lines, 1)],
            "changed": bool(added or removed)}


def record(source_key: str, url: str, text: str, cfg: dict | None = None) -> dict:
    """Store one snapshot and return its change summary.

    ``new=True`` means this source/URL had no prior snapshot; ``changed`` is
    False when the content hash is identical to the previous snapshot.
    """
    cfg = cfg or config.load()
    ensure_table()
    limit = util.clamp(cfg.get("snapshot_max_chars"), 500, 50000, MAX_SNAPSHOT_CHARS)
    body = str(text or "")[:limit]
    canon = canonical.canonicalize(url)
    if not canon:
        return {"source_key": source_key, "url": "", "changed": False, "new": False,
                "added_lines": 0, "removed_lines": 0, "changed_lines": [],
                "size": 0, "content_hash": "", "ts": util.now_iso()}
    digest = canonical.content_hash("", "", body)
    size = len(body.encode("utf-8", "replace"))
    ts = util.now_iso()
    with store.session() as con:
        row = con.execute(
            "SELECT text, content_hash, size FROM page_snapshots "
            "WHERE source_key=? AND canonical=?", (str(source_key)[:60], canon)
        ).fetchone()
        previous = dict(row) if row else None
        if previous is None:
            new = True
            diff = diff_text("", body, util.clamp(cfg.get("change_max_lines"), 1, 20,
                                                  MAX_DIFF_LINES))
        else:
            new = False
            if previous.get("content_hash") == digest:
                diff = {"added_lines": 0, "removed_lines": 0,
                        "changed_lines": [], "changed": False}
            else:
                diff = diff_text(previous.get("text", ""), body,
                                 util.clamp(cfg.get("change_max_lines"), 1, 20,
                                            MAX_DIFF_LINES))
        con.execute(
            "INSERT INTO page_snapshots(source_key,url,canonical,ts,first_seen,"
            "content_hash,size,text,changed,added_lines,removed_lines,diff) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(source_key,canonical) DO UPDATE SET "
            "url=excluded.url,ts=excluded.ts,content_hash=excluded.content_hash,"
            "size=excluded.size,text=excluded.text,changed=excluded.changed,"
            "added_lines=excluded.added_lines,removed_lines=excluded.removed_lines,"
            "diff=excluded.diff",
            (str(source_key)[:60], str(url or "")[:1000], canon, ts, ts, digest,
             size, body, int(diff["changed"]), int(diff["added_lines"]),
             int(diff["removed_lines"]), json.dumps(diff["changed_lines"],
                                                    ensure_ascii=False)))
        con.execute(
            "DELETE FROM page_snapshots WHERE id NOT IN "
            "(SELECT id FROM page_snapshots ORDER BY ts DESC, id DESC LIMIT ?)",
            (MAX_STORED_ROWS,))
    return {"source_key": str(source_key)[:60], "url": str(url or "")[:1000],
            "canonical": canon, "changed": bool(diff["changed"]), "new": new,
            "added_lines": int(diff["added_lines"]),
            "removed_lines": int(diff["removed_lines"]),
            "changed_lines": list(diff["changed_lines"]), "size": size,
            "content_hash": digest, "ts": ts}


def _decode(row: dict) -> dict:
    out = dict(row)
    try:
        out["changed_lines"] = json.loads(out.pop("diff", "[]") or "[]")
    except ValueError:
        out["changed_lines"] = []
    out["changed"] = bool(out.get("changed"))
    return out


def list_snapshots(limit: int = 50) -> list[dict]:
    ensure_table()
    with store.session() as con:
        rows = [dict(r) for r in con.execute(
            "SELECT * FROM page_snapshots ORDER BY ts DESC, id DESC LIMIT ?",
            (util.clamp(limit, 1, MAX_STORED_ROWS, 50),))]
    return [_decode(r) for r in rows]


def _since_iso(since) -> str:
    if since in (None, "", 0, 0.0):
        return ""
    if isinstance(since, (int, float)):
        return datetime.fromtimestamp(float(since), timezone.utc).replace(
            microsecond=0).isoformat().replace("+00:00", "Z")
    return str(since)


def changes_since(since=None, limit: int = 20) -> dict:
    """Per-source change summary for snapshots newer than ``since``."""
    ensure_table()
    since_iso = _since_iso(since)
    sql = ("SELECT * FROM page_snapshots WHERE changed=1 AND ts>? "
           "ORDER BY ts DESC, id DESC LIMIT ?")
    with store.session() as con:
        rows = [dict(r) for r in con.execute(sql, (since_iso, MAX_STORED_ROWS))]
    grouped: dict[str, dict] = {}
    for row in rows:
        key = str(row.get("source_key") or "")
        if key not in grouped:
            grouped[key] = _decode(row)
    sources = sorted(grouped.values(), key=lambda r: r.get("ts", ""), reverse=True)
    sources = sources[: util.clamp(limit, 1, 200, 20)]
    total_added = sum(int(r.get("added_lines") or 0) for r in sources)
    total_removed = sum(int(r.get("removed_lines") or 0) for r in sources)
    return {"since": since_iso or None, "generated_at": util.now_iso(),
            "sources": sources, "total": len(sources),
            "added_lines": total_added, "removed_lines": total_removed}


def recent_changes(limit: int = 20) -> dict:
    """Latest changed snapshot per source, no time filter."""
    return changes_since(None, limit)


def changes_since_last_run(limit: int = 20) -> dict:
    """Changes recorded since :func:`mark_seen` was last called."""
    result = changes_since(store.get_schedule_state(STATE_KEY), limit)
    return result


def mark_seen(ts: float | None = None) -> None:
    """Advance the "last run" marker (called once at the end of a pipeline run)."""
    store.set_schedule_state(STATE_KEY, ts)


def counts() -> dict:
    ensure_table()
    with store.session() as con:
        rows = con.execute(
            "SELECT source_key, COUNT(*) AS n, SUM(changed) AS changed "
            "FROM page_snapshots GROUP BY source_key").fetchall()
    out = {"sources": len(rows), "snapshots": 0, "changed": 0, "by_source": {}}
    for row in rows:
        out["snapshots"] += int(row["n"] or 0)
        out["changed"] += int(row["changed"] or 0)
        out["by_source"][row["source_key"]] = int(row["n"] or 0)
    return out


def prune(keep_days: int = 90) -> int:
    """Retention for snapshots only (items are handled by store.retention)."""
    ensure_table()
    days = util.clamp(keep_days, 1, 3650, 90)
    cutoff = datetime.fromtimestamp(util.epoch() - days * 86400, timezone.utc).replace(
        microsecond=0).isoformat().replace("+00:00", "Z")
    with store.session() as con:
        removed = con.execute("DELETE FROM page_snapshots WHERE ts<?",
                              (cutoff,)).rowcount
    return int(removed or 0)
