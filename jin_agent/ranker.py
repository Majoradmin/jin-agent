"""Smart ranking: relevance + trust + freshness + cross-verification + feedback."""

from __future__ import annotations

from . import store, util

WEIGHTS = {"relevance": 1.0, "trust": 3.0, "freshness": 2.0,
           "cross": 2.5, "feedback": 1.5}


def matched_terms(item: dict, query_terms: list[str]) -> list[str]:
    """Query terms actually present in the item. Used as a relevance floor."""
    blob = (str(item.get("title") or "") + " " +
            str(item.get("excerpt") or "")).lower()
    return [t for t in query_terms if t in blob]


def score(item: dict, query_terms: list[str], weights: dict | None = None,
          feedback=None) -> tuple[float, list[str]]:
    w = {**WEIGHTS, **(weights or {})}
    title = str(item.get("title") or "").lower()
    reasons: list[str] = []
    matched = matched_terms(item, query_terms)
    relevance = len(matched) * (2.0 if any(t in title for t in matched) else 1.0)
    if matched:
        reasons.append("keywords: " + ", ".join(matched[:6]))
    trust = util.clamp(item.get("trust"), 0.0, 1.0, 0.5)
    reasons.append("trust " + str(round(trust, 2)))
    age = util.days_since(item.get("published", ""))
    if age is None:
        freshness = 0.2
        reasons.append("date unknown")
    else:
        freshness = max(0.0, 1.0 - min(age, 30.0) / 30.0)
        reasons.append(f"{age:.1f}d old")
    cross = 1.0 if item.get("cross_verified") else 0.0
    if cross:
        reasons.append("cross-verified")
    if feedback is None:
        try:
            feedback = store.feedback_score(item.get("guid", ""))
        except Exception:
            feedback = 0
    feedback = max(-1.0, min(1.0, float(feedback or 0)))
    if feedback:
        reasons.append("feedback " + str(int(feedback)))
    link_penalty = -2.0 if item.get("link_only") else 0.0
    offline_penalty = -1.0 if (item.get("meta") or {}).get("offline") else 0.0
    total = (w["relevance"] * relevance + w["trust"] * trust +
             w["freshness"] * freshness + w["cross"] * cross +
             w["feedback"] * feedback + link_penalty + offline_penalty)
    return round(max(0.0, total), 2), reasons[:8]


def rank(items: list[dict], query: str, limit: int = 25) -> list[dict]:
    words = util.terms(query, 20)
    try:
        feedback_map = store.feedback_scores()
    except Exception:
        feedback_map = {}
    scored = []
    for item in items or []:
        rec = dict(item)
        sc, reasons = score(rec, words, feedback=feedback_map.get(rec.get("guid", ""), 0))
        rec["score"] = sc
        rec["reasons"] = reasons
        scored.append(rec)
    scored.sort(key=lambda r: (r["score"], r.get("confidence", 0), r.get("title", "")),
                reverse=True)
    return scored[: util.clamp(limit, 1, 200, 25)]
