"""End-to-end pipeline: gate -> plan -> tools -> normalize -> verify -> rank -> brief.

One query in, one professional Roman Urdu brief out. A network failure never
crashes a run and never produces a fabricated news item.
"""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import (VERSION, adapters, briefer, config, llm, logging_setup,
               normalizer, planner, policy, ranker, snapshots, store, util,
               verifier)
# Local ``metrics`` dict (run naap) module ko shadow karta hai - is liye alias.
from . import metrics as metrics_lib


def _log():
    """Logger current data dir par bind karo (tests data dir badalte hain)."""
    return logging_setup.get_logger("orchestrator")


# Ek hi source ki aik hi qisam ki items poori report par kabza na karey.
# Misal: "free api key" par 14 Stack Exchange sawaal — score to barabar thi,
# magar report "repeated" lagti thi. Har source se zyada se zyada ye items.
DEFAULT_MAX_PER_SOURCE = 6


def _diversify(ranked: list[dict], cap: int) -> list[dict]:
    """Ranked list me se har source ki items ``cap`` par rok do.

    Source ka matlab ``source_key`` (``source`` display naam nahi) — taake
    "Google News RSS" aur "Google News RSS (topic)" alag na ginne jayen.
    """
    counts: dict[str, int] = {}
    out: list[dict] = []
    for item in ranked:
        key = str(item.get("source_key") or item.get("source") or "")
        if counts.get(key, 0) >= cap:
            continue
        counts[key] = counts.get(key, 0) + 1
        out.append(item)
    return out


def _write_trace(payload: dict) -> str:
    """Per-run trace JSON (``data/runs/<id>.json``) — Hermes trace.py pattern.

    Query, plan, tool calls, sources, tokens, duration, confidence. Best-effort:
    disk fail hone par run crash nahi hota.
    """
    try:
        path = config.runs_dir() / f"{int(payload.get('run_id') or 0)}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2,
                                   default=str), encoding="utf-8")
        return str(path)
    except (OSError, TypeError, ValueError):
        return ""


def run(query: str, live: bool = False, days: int = 7, limit: int = 25,
        keys: list[str] | None = None, cfg: dict | None = None,
        save: bool = True, skip_sources: list[str] | None = None,
        on_stage=None) -> dict:
    """Execute one research run. Default is OFFLINE (deterministic, no network).

    ``on_stage(name, detail)`` optional progress callback — Telegram bot is
    har stage par wahi status message edit karta hai (Plan → Sources → Fetch →
    Verify → Brief). Callback kabhi run ko crash nahi karta.
    """
    log = _log()

    def _stage(name: str, detail: str = "") -> None:
        if on_stage is None:
            return
        try:
            on_stage(name, detail)
        except Exception:
            pass

    cfg = dict(cfg or config.load())
    if skip_sources:
        cfg["skip_sources"] = [str(s) for s in skip_sources]
    query = str(query or "").strip()[: util.clamp(cfg.get("max_query_chars"), 100, 8000, 4000)]
    started = time.monotonic()
    started_iso = util.now_iso()
    store.init_db()
    run_id = store.record_run(query, "live" if live else "offline")
    try:
        llm.reset_tokens()
    except Exception:
        pass
    gate = policy.classify(query)

    if gate["verdict"] == "blocked":
        _stage("Plan", "blocked")
        audit = verifier.citation_audit([])
        metrics = {"blocked": True, "sources_ok": 0, "sources_failed": 0,
                   "items": 0, "changes_sources": 0,
                   "confidence": 0.0, "confidence_label": "n/a",
                   "tokens": llm.token_usage(), "token_budget": llm.token_budget(),
                   "token_cost_usd": 0.0, "budget_exceeded": False,
                   "duration_ms": round((time.monotonic() - started) * 1000)}
        empty_changes = {"since": None, "generated_at": util.now_iso(),
                         "sources": [], "total": 0,
                         "added_lines": 0, "removed_lines": 0}
        built = briefer.build(query, [], [], cfg, None, audit, metrics,
                              metrics["duration_ms"], "offline", blocked=gate)
        saved = briefer.save(built, query, metrics) if save else {}
        store.finish_run(run_id, metrics, 0, 0, 0)
        store.add_event("blocked", "Request blocked by " + policy.POLICY_ID)
        metrics_lib.inc("queries_total")
        metrics_lib.inc("runs_blocked")
        metrics_lib.observe("run", metrics["duration_ms"])
        if saved:
            metrics_lib.inc("reports_total")
        log.info("run blocked", extra={"fields": {"query": util.truncate(query, 80),
                                                 "policy": policy.POLICY_ID}})
        trace_path = _write_trace({"run_id": run_id, "query": query, "mode": "offline",
                      "blocked": True, "started_at": started_iso,
                      "finished_at": util.now_iso(),
                      "duration_ms": metrics["duration_ms"],
                      "plan": {"calls": [], "source": "none"}, "tools": [],
                      "diagnostics": [], "metrics": metrics,
                      "confidence": 0.0, "confidence_label": "n/a",
                      "tokens": llm.token_usage(),
                      "saved": (saved or {}).get("md", "")})
        metrics_lib.persist()      # summary ko final state par likho
        return {"ok": True, "blocked": True, "gate": gate, "items": [],
                "diagnostics": [], "plan": {"calls": [], "source": "none"},
                "audit": audit, "metrics": metrics, "report": built,
                "saved": saved, "run_id": run_id, "changes": empty_changes,
                "trace_path": trace_path}

    plan_result = planner.plan(query, cfg)
    _stage("Plan", f"{len(plan_result.get('calls') or [])} tools")
    ctx = {"cfg": cfg, "offline": not live, "query": query}
    _stage("Sources", " ".join(str(c.get('tool')) for c in (plan_result.get('calls') or []))[:80])
    executed = planner.execute(plan_result, ctx)
    _stage("Fetch", f"{len(executed.get('items') or [])} raw items")

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
    _stage("Verify", f"{len(normalized)} normalized · {len(items)} verified")
    # "sab kuch store, best kuch report": archive keeps every source record,
    # but the brief prints one row per story instead of the same headline N times.
    pool = ranker.rank(items, query, max(limit * 3, limit))
    collapsed = verifier.collapse(pool)
    merged_away = len(pool) - len(collapsed)
    words = util.terms(query, 20)
    on_topic = [r for r in collapsed if ranker.matched_terms(r, words)] if words else collapsed
    off_topic_dropped = len(collapsed) - len(on_topic)
    max_per_source = util.clamp(cfg.get("max_items_per_source"), 1, 25,
                                DEFAULT_MAX_PER_SOURCE)
    diverse = _diversify(on_topic, max_per_source)
    diversity_dropped = len(on_topic) - len(diverse)
    ranked = diverse[:limit]
    if ranked:
        store.upsert_items(ranked)                       # persist scores / confidence

    diagnostics = executed["diagnostics"]
    for diag in diagnostics:
        store.touch_source(diag.get("key", ""),
                           bool(diag.get("ok") and diag.get("count", 0)),
                           diag.get("error", ""))
    changes = snapshots.changes_since_last_run(limit=20)
    try:
        snapshots.mark_seen()
    except Exception:
        pass

    audit = verifier.citation_audit(ranked)
    ages = [a for a in (util.days_since(i.get("published", "")) for i in ranked) if a is not None]
    freshness = round(sorted(ages)[len(ages) // 2], 2) if ages else None
    sources_ok = sum(1 for d in diagnostics if d.get("ok") and d.get("count", 0))
    sources_failed = sum(1 for d in diagnostics if not d.get("ok"))
    duration_ms = round((time.monotonic() - started) * 1000)
    confidence = verifier.aggregate_confidence(ranked)
    tokens = llm.token_usage()
    metrics = {
        "items": len(ranked), "raw_items": len(executed["items"]),
        "confidence": confidence["value"],
        "confidence_label": confidence["label"],
        "tokens": tokens,
        "token_cost_usd": round(tokens["total_tokens"] / 1_000_000
                                * llm.cost_per_1m(), 4),
        "token_budget": llm.token_budget(),
        "budget_exceeded": tokens["total_tokens"] > llm.token_budget(),
        "unique_stories": len(ranked), "duplicate_rows_merged": merged_away,
        "off_topic_dropped": off_topic_dropped,
        "diversity_dropped": diversity_dropped,
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
        "changes_sources": changes["total"],
        "change_lines_added": changes["added_lines"],
        "change_lines_removed": changes["removed_lines"],
        "duration_ms": duration_ms, "live": bool(live), "ingest": ingest,
    }
    built = briefer.build(query, ranked, diagnostics, cfg, plan_result, audit,
                          metrics, duration_ms, "live" if live else "offline")
    _stage("Brief", f"{len(ranked)} findings")
    saved = briefer.save(built, query, metrics) if save else {}
    store.finish_run(run_id, metrics, len(ranked), sources_ok, sources_failed)
    store.add_event("research", f"query={util.truncate(query, 80)} items={len(ranked)} "
                                f"sources_ok={sources_ok}")
    metrics_lib.inc("queries_total")
    metrics_lib.inc("runs_ok")
    metrics_lib.inc("fetch_errors", sources_failed)
    metrics_lib.observe("run", duration_ms)
    metrics_lib.set_gauge("items_last_run", len(ranked))
    if saved:
        metrics_lib.inc("reports_total")
    log.info("run done", extra={"fields": {
        "mode": "live" if live else "offline", "items": len(ranked),
        "sources_ok": sources_ok, "sources_failed": sources_failed,
        "duration_ms": duration_ms, "query": util.truncate(query, 80)}})
    trace_path = _write_trace({"run_id": run_id, "query": query,
                  "mode": "live" if live else "offline",
                  "blocked": False, "started_at": started_iso,
                  "finished_at": util.now_iso(), "duration_ms": duration_ms,
                  "plan": plan_result,
                  "tools": [c["tool"] for c in plan_result["calls"]],
                  "diagnostics": diagnostics, "metrics": metrics,
                  "confidence": confidence["value"],
                  "confidence_label": confidence["label"],
                  "tokens": llm.token_usage(),
                  "saved": (saved or {}).get("md", ""), "changes": changes})
    metrics_lib.persist()          # throttled auto-persist ke baad final summary
    return {
        "ok": True, "blocked": False, "gate": gate, "query": query,
        "items": ranked, "diagnostics": diagnostics, "plan": plan_result,
        "tool_text": executed["tool_text"], "audit": audit, "metrics": metrics,
        "report": built, "saved": saved, "run_id": run_id, "changes": changes,
        "trace_path": trace_path,
    }


def run_many(queries: list[str], live: bool = False, days: int = 7, limit: int = 25,
             keys: list[str] | None = None, cfg: dict | None = None,
             save: bool = True, max_concurrent: int = 3) -> dict:
    """Parallel "agents": same pipeline per query, bounded concurrency.

    User-facing "many agents" entry: N independent research runs chaltay hain
    ek saath (ThreadPoolExecutor), har ek apni brief generate karta hai.
    """
    clean = [str(q).strip() for q in (queries or []) if str(q).strip()]
    if not clean:
        return {"ok": False, "error": "Koi query nahi hai", "runs": []}
    if len(clean) > 20:
        return {"ok": False, "error": "Zid 20 query tak allow", "runs": []}
    runs: list[dict] = []
    with ThreadPoolExecutor(max_workers=max(1, int(max_concurrent))) as ex:
        futures = {ex.submit(run, q, live=live, days=days, limit=limit, keys=keys,
                              cfg=cfg, save=save): q for q in clean}
        for fut in as_completed(futures):
            q = futures[fut]
            try:
                r = fut.result()
                runs.append({"query": q, **r})
            except Exception as exc:  # ek bad agent doosre ko rok na de
                runs.append({"query": q, "ok": False, "error": type(exc).__name__,
                             "items": [], "metrics": {}})
    return {"ok": True, "runs": runs, "count": len(runs)}


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
    changes = snapshots.recent_changes(limit=12)
    conf = verifier.aggregate_confidence(picked)
    metrics = {"items": len(picked), "categories": len(buckets), "source": "archive",
               "unique_stories": len(picked), "duplicate_rows_merged": merged_away,
               "changes_sources": changes["total"],
               "confidence": conf["value"], "confidence_label": conf["label"]}
    built = briefer.build("Daily digest (local archive)", picked, [], cfg, None,
                          audit, metrics, 0, "archive")
    saved = briefer.save(built, "Daily digest", metrics)
    if saved:
        metrics_lib.inc("reports_total")
    metrics_lib.persist()
    return {"ok": True, "report": built, "saved": saved, "changes": changes}


def status(cfg: dict | None = None) -> dict:
    cfg = cfg or config.load()
    ov = store.overview()
    return {
        "version": VERSION, "policy_id": policy.POLICY_ID,
        "date_checked": policy.DATE_CHECKED,
        "llm": llm.status(cfg), "tor_mode": cfg.get("tor_mode"),
        "fts5": ov.get("fts5"), "fts_error": ov.get("fts_error"),
        "counts": {k: ov.get(k) for k in ("items", "runs", "sources", "watchlist",
                                          "jobs", "reports", "feedback", "events",
                                          "page_snapshots")},
        "cross_verified": ov.get("cross_verified"),
        "source_register": len(policy.register()),
        "adapters": len(adapters.ADAPTERS),
        "assumptions": cfg.get("assumptions", {}),
        "changes": snapshots.recent_changes(limit=5),
        "metrics": metrics_lib.compact(),
    }
