"""SQLite job queue scheduler, firehose mode, watchlist alerts, retention, backup.

Uses a plain background thread (no Windows Task Scheduler install, no cloud).
The loop is stoppable and never raises out of a job - one bad adapter cannot
take down the 24/7 ingest.
"""

from __future__ import annotations

import threading
import time

from . import adapters, alerts, channels, config, normalizer, orchestrator, store, util

JOB_MINUTES = {
    "feeds": "feeds_minutes",
    "telegram": "telegram_minutes",
    "papers": "papers_minutes",
    "digest": "digest_minutes",
    "watchlist": "watchlist_minutes",
    "retention": "retention_minutes",
    "discovery": "discovery_minutes",
}


def firehose(query: str = "mobile firmware security tools", cfg: dict | None = None,
             offline: bool = True, keys: list[str] | None = None) -> dict:
    """Store EVERYTHING the adapters return (dedupe, no ranking, no filtering)."""
    cfg = cfg or config.load()
    store.init_db()
    raw, diagnostics = adapters.run(query, keys=keys, days=7, limit=50,
                                    cfg=cfg, offline=offline)
    records = [r for r in (normalizer.normalize(x, cfg=cfg) for x in raw) if r]
    ingest = store.upsert_items(records)
    for diag in diagnostics:
        store.touch_source(diag.get("key", ""), bool(diag.get("ok")),
                           diag.get("error", ""))
    store.add_event("firehose", f"raw={len(raw)} records={len(records)} "
                                f"inserted={ingest['inserted']} updated={ingest['updated']}")
    return {"raw": len(raw), "records": len(records), "ingest": ingest,
            "diagnostics": diagnostics}


def run_job(kind: str, payload: dict | None = None, cfg: dict | None = None,
            offline: bool = True) -> dict:
    payload = payload or {}
    cfg = cfg or config.load()
    if kind == "feeds":
        return firehose(str(payload.get("query") or "mobile firmware security tools"),
                        cfg, offline)
    if kind == "telegram":
        return firehose(str(payload.get("query") or "firmware"),
                        cfg, offline, keys=["telegram-public"])
    if kind == "papers":
        return firehose(str(payload.get("query") or "firmware security"),
                        cfg, offline, keys=["openalex", "crossref", "arxiv"])
    if kind == "digest":
        out = orchestrator.digest(cfg)
        head = "\n".join(out["report"]["markdown"].splitlines()[:12])
        alerts.notify(head, cfg)
        return {"report": (out.get("saved") or {}).get("md", ""),
                "items": out["report"]["facts_count"]}
    if kind == "watchlist":
        hits = []
        for row in store.list_watchlist(active_only=True):
            found = store.search_archive(row["term"], 10)
            if found:
                hits.append({"term": row["term"], "count": len(found),
                             "title": found[0].get("title", "")})
                store.set_watchlist_hit(row["term"])
        if hits:
            alerts.notify("Watchlist alert:\n" + "\n".join(
                f"- {h['term']}: {h['count']} hits | {h['title'][:100]}" for h in hits), cfg)
        return {"hits": hits}
    if kind == "discovery":
        return channels.run_discovery(cfg, offline)
    if kind == "retention":
        kept = store.retention(int(cfg.get("retention_days") or 90))
        try:
            kept["backup"] = store.backup()
        except Exception as exc:
            kept["backup_error"] = type(exc).__name__
        return kept
    return {"error": "Unknown job kind: " + str(kind)[:60]}


def tick(cfg: dict | None = None, offline: bool = True, max_jobs: int = 8) -> dict:
    """Enqueue due jobs, then claim and execute pending jobs."""
    cfg = cfg or config.load()
    store.init_db()
    now = util.epoch()
    enqueued, processed, errors = [], [], []
    schedule = cfg.get("schedule") or {}
    for kind, setting in JOB_MINUTES.items():
        minutes = util.clamp(schedule.get(setting), 1, 10080, 60)
        last = store.get_schedule_state(kind)
        if now - last >= minutes * 60:
            store.enqueue_job(kind, {"trigger": "scheduler", "offline": offline})
            store.set_schedule_state(kind, now)
            enqueued.append(kind)
    for _ in range(max_jobs):
        job = store.claim_job()
        if not job:
            break
        try:
            import json
            payload = json.loads(job.get("payload") or "{}")
            result = run_job(job["kind"], payload, cfg,
                             bool(payload.get("offline", offline)))
            store.finish_job(job["id"], True)
            processed.append({"id": job["id"], "kind": job["kind"], "result": result})
        except Exception as exc:
            msg = f"{type(exc).__name__}: {util.truncate(str(exc), 160)}"
            store.finish_job(job["id"], False, msg)
            errors.append({"id": job["id"], "kind": job["kind"], "error": msg})
            store.add_event("job_error", msg)
    return {"enqueued": enqueued, "processed": processed, "errors": errors}


class Scheduler(threading.Thread):
    """Stoppable background scheduler. ``start()`` is non-blocking."""

    def __init__(self, cfg: dict | None = None, offline: bool = True,
                 poll_seconds: int = 20):
        super().__init__(daemon=True, name="jin-agent-scheduler")
        self.cfg = cfg or config.load()
        self.offline = offline
        self.poll = max(5, int(poll_seconds))
        self._stop = threading.Event()
        self.last_tick: dict = {}
        self.ticks = 0

    def run(self):
        while not self._stop.is_set():
            try:
                self.last_tick = tick(self.cfg, self.offline)
                self.ticks += 1
            except Exception as exc:
                store.add_event("scheduler", f"tick error {type(exc).__name__}")
            self._stop.wait(self.poll)

    def stop(self, timeout: float = 3.0):
        self._stop.set()
        if self.is_alive():
            self.join(timeout)

    def state(self) -> dict:
        return {"running": self.is_alive(), "ticks": self.ticks,
                "poll_seconds": self.poll, "offline": self.offline,
                "last_tick": self.last_tick}
