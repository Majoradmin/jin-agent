"""End-to-end pipeline: gate -> plan -> tools -> normalize -> verify -> rank -> brief.

One query in, one professional Roman Urdu brief out. A network failure never
crashes a run and never produces a fabricated news item.
"""

from __future__ import annotations

import time

from . import (VERSION, adapters, briefer, config, llm, normalizer, planner,
               policy, ranker, store, util, verifier)


def run(query: str, live: bool = False, days: int = 7, limit: int = 25,
        keys: list[str] | None = None, cfg: dict | None = None,
        save: bool = True) -> dict:
    """Execute one research run. Default is OFFLINE (deterministic, no network)."""
    cfg = cfg or config.load()
    query = str(query or "").strip()[: util.clamp(cfg.get("max_query_chars"), 100, 8000, 4000)]
    started = time.monotonic()
    store.init_db()
    run_id = store.record_run(query, "live" if live else "offline")
    gate = policy.classify(query)

    if gate["verdict"] == "blocked":
        audit = verifier.citation_audit([])
        metrics = {"blocked": True, "sources_ok": 0, "sources_failed": 0,
                   "items": 0, "duration_ms": round((time.monotonic() - started) * 1000)}
        built = briefer.build(query, [], [], cfg, None, audit, metrics,
                              metrics["duration_ms"], "offline", blocked=gate)
        saved = briefer.save(built, query, metrics) if save else {}
        store.finish_run(run_id, metrics, 0, 0, 0)
        store.add_event("blocked", "Request blocked by " + policy.POLICY_ID)
        return {"ok": True, "blocked": True, "gate": gate, "items": [],
                "diagnostics": [], "plan": {"calls": [], "source": "none"},
                "audit": audit, "metrics": metrics, "report": built,
                "saved": saved, "run_id": run_id}

    plan_result = planner.plan(query, cfg)
    ctx = {"cfg": cfg, "offline": not live, "query": query}
    executed = planner.execute(plan_result, ctx)

    normalized: list[dict] = []
    for raw in executed["items"]:
        rec = normalizer.normalize(raw, cfg=cfg)
        if rec:
            normalized.append(rec)
    unique: dict[str, dict] = {}
    for rec in normalized:
        unique.setdefault(rec["guid"], rec)
    normalized = list(unique.values())
    ingest = store.upsert_items(normalized)             # firehose: store everything

    items = verifier.cross_check([verifier.verify(rec) for rec in normalized])
    # "sab kuch store, best kuch report": archive keeps every source record,
    # but the brief prints one row per story instead of the same headline N times.
    pool = ranker.rank(items, query, max(limit * 3, limit))
    collapsed = verifier.collapse(pool)
    merged_away = len(pool) - len(collapsed)
    words = util.terms(query, 20)
    on_topic = [r for r in collapsed if ranker.matched_terms(r, words)] if words else collapsed
    off_topic_dropped = len(collapsed) - len(on_topic)
    ranked = on_topic[:limit]
    if ranked:
        store.upsert_items(ranked)                       # persist scores / confidence

    diagnostics = executed["diagnostics"]
    for diag in diagnostics:
        store.touch_source(diag.get("key", ""),
                           bool(diag.get("ok") and diag.get("count", 0)),
                           diag.get("error", ""))

    audit = verifier.citation_audit(ranked)
    ages = [a for a in (util.days_since(i.get("published", "")) for i in ranked) if a is not None]
    freshness = round(sorted(ages)[len(ages) // 2], 2) if ages else None
    sources_ok = sum(1 for d in diagnostics if d.get("ok") and d.get("count", 0))
    sources_failed = sum(1 for d in diagnostics if not d.get("ok"))
    duration_ms = round((time.monotonic() - started) * 1000)
    metrics = {
        "items": len(ranked), "raw_items": len(executed["items"]),
        "unique_stories": len(ranked), "duplicate_rows_merged": merged_away,
        "off_topic_dropped": off_topic_dropped,
        "dedupe_rate_pct": round(100.0 * (1 - len(normalized) / len(executed["items"])), 1)
        if executed["items"] else 0.0,
        "sources_ok": sources_ok, "sources_failed": sources_failed,
        "sources_total": len(diagnostics), "freshness_median_days": freshness,
        "provenance_pct": audit["provenance_pct"], "fabricated_citations": audit["fabricated"],
        "verified": sum(1 for i in ranked if i.get("verified")),
        "not_verified": sum(1 for i in ranked if not i.get("verified")),
        "cross_verified": sum(1 for i in ranked if i.get("cross_verified")),
        "tools_used": len(plan_result["calls"]), "tools_rejected": len(plan_result["rejected"]),
        "planner": plan_result["source"], "llm_mode": llm.resolve(cfg)["mode"],
        "duration_ms": duration_ms, "live": bool(live), "ingest": ingest,
    }
    built = briefer.build(query, ranked, diagnostics, cfg, plan_result, audit,
                          metrics, duration_ms, "live" if live else "offline")
    saved = briefer.save(built, query, metrics) if save else {}
    store.finish_run(run_id, metrics, len(ranked), sources_ok, sources_failed)
    store.add_event("research", f"query={util.truncate(query, 80)} items={len(ranked)} "
                                f"sources_ok={sources_ok}")
    return {
        "ok": True, "blocked": False, "gate": gate, "query": query,
        "items": ranked, "diagnostics": diagnostics, "plan": plan_result,
        "tool_text": executed["tool_text"], "audit": audit, "metrics": metrics,
        "report": built, "saved": saved, "run_id": run_id,
    }


def digest(cfg: dict | None = None, limit_per_category: int = 3) -> dict:
    """Daily brief built from the local archive (no network required)."""
    cfg = cfg or config.load()
    store.init_db()
    buckets: dict[str, list[dict]] = {}
    for item in store.search_archive("", 300):
        buckets.setdefault(item.get("category", "Custom Watchlist"), []).append(item)
    picked = []
    for category in sorted(buckets):
        rows = sorted(buckets[category], key=lambda r: r.get("score", 0), reverse=True)
        picked.extend(rows[:limit_per_category])
    # Archive rows do not store the derived provenance dict; rebuild it so the
    # citation audit measures real fields instead of an empty dict.
    checked = verifier.cross_check([verifier.verify(r) for r in picked])
    merged_away = len(checked)
    picked = verifier.collapse(checked)
    merged_away -= len(picked)
    audit = verifier.citation_audit(picked)
    metrics = {"items": len(picked), "categories": len(buckets), "source": "archive",
               "unique_stories": len(picked), "duplicate_rows_merged": merged_away}
    built = briefer.build("Daily digest (local archive)", picked, [], cfg, None,
                          audit, metrics, 0, "archive")
    return {"ok": True, "report": built,
            "saved": briefer.save(built, "Daily digest", metrics)}


def status(cfg: dict | None = None) -> dict:
    cfg = cfg or config.load()
    ov = store.overview()
    return {
        "version": VERSION, "policy_id": policy.POLICY_ID,
        "date_checked": policy.DATE_CHECKED,
        "llm": llm.status(cfg), "tor_mode": cfg.get("tor_mode"),
        "fts5": ov.get("fts5"), "fts_error": ov.get("fts_error"),
        "counts": {k: ov.get(k) for k in ("items", "runs", "sources", "watchlist",
                                          "jobs", "reports", "feedback", "events")},
        "cross_verified": ov.get("cross_verified"),
        "source_register": len(policy.register()),
        "adapters": len(adapters.ADAPTERS),
        "assumptions": cfg.get("assumptions", {}),
    }
