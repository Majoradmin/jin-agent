"""Provenance, trust labels and cross-verification.

Honest definitions:
  citation_ok  = the item carries a real-looking http(s) URL + source + date checked
  verified     = citation_ok AND it came from a validated adapter AND it is not
                 a links-only / offline-fixture record
  url_fetched  = FALSE for third-party article links. The agent fetched the
                 adapter endpoint, NOT the article URL. This is stated openly
                 in every report's "Not Verified" section.
No citation is ever invented by this module.
"""

from __future__ import annotations

from collections import defaultdict

from . import canonical, policy, util


def verify(item: dict) -> dict:
    out = dict(item)
    meta = dict(out.get("meta") or {})
    offline = bool(meta.get("offline"))
    link_only = bool(out.get("link_only"))
    url = str(out.get("url") or "").strip()
    source = str(out.get("source") or "").strip()
    date_checked = str(out.get("date_checked") or util.now_iso())
    citation_ok = bool(url.lower().startswith(("http://", "https://")) and source and date_checked)
    if offline:
        trust_label = "Fixture (offline)"
        confidence = 0.20
        verified = False
        note = "Offline evaluation fixture - NOT a real citation."
    elif link_only:
        trust_label = "Unverified (link only)"
        confidence = 0.35
        verified = False
        note = policy.DARK_WEB_RULE
    else:
        trust_label = policy.trust_label(util.clamp(out.get("trust"), 0.0, 1.0, 0.5))
        verified = citation_ok
        confidence = round(min(0.95, 0.35 + 0.45 * util.clamp(out.get("trust"), 0, 1, 0.5)
                               + (0.10 if out.get("published") else 0.0)
                               + (0.05 if citation_ok else 0.0)), 2)
        note = ("Article URL was NOT fetched independently; it is a citation "
                "returned by a validated public adapter." if citation_ok
                else "Missing URL / source / date checked.")
    out["trust_label"] = trust_label
    out["verified"] = bool(verified)
    out["confidence"] = round(confidence, 2)
    out["date_checked"] = date_checked
    out["provenance"] = {
        "url": url, "canonical": out.get("canonical", ""), "source": source,
        "source_key": out.get("source_key", ""), "tier": out.get("tier", ""),
        "published": out.get("published", ""), "date_checked": date_checked,
        "content_hash": out.get("content_hash", ""), "trust_label": trust_label,
        "citation_ok": bool(citation_ok), "url_fetched": False,
        "kind": "offline-fixture" if offline else ("onion-link" if link_only else "adapter-result"),
        "note": note,
    }
    meta["verified"] = bool(verified)
    meta["note"] = note
    out["meta"] = meta
    return out


def _independent(item: dict) -> bool:
    """Only a real, citation-bearing adapter result can corroborate an event.

    Offline fixtures are ONE synthetic story replayed by every adapter, and
    links-only onion records were never fetched. Counting either of those as
    independent corroboration would manufacture trust out of duplicated text.
    """
    meta = item.get("meta") or {}
    if not isinstance(meta, dict):
        return False
    if meta.get("offline") or item.get("link_only"):
        return False
    prov = item.get("provenance") or {}
    return bool(prov.get("citation_ok", item.get("verified", False)))


def cross_check(items: list[dict]) -> list[dict]:
    """Same event from >=2 independent ADAPTER sources -> cross-verified boost."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        groups[item.get("fingerprint", "")].append(item)
    out = []
    for group in groups.values():
        sources = {i.get("source_key", "") for i in group if _independent(i)}
        multi = len(sources) >= 2
        for item in group:
            rec = dict(item)
            if multi and _independent(rec):
                rec["cross_verified"] = True
                rec["confidence"] = round(min(0.98, float(rec.get("confidence", 0)) + 0.15), 2)
                rec["reasons"] = list(rec.get("reasons") or []) + ["cross-verified"]
                prov = dict(rec.get("provenance") or {})
                prov["cross_verified_with"] = sorted(sources)
                rec["provenance"] = prov
            else:
                rec["cross_verified"] = False
                if len(group) > 1:
                    prov = dict(rec.get("provenance") or {})
                    prov["cross_check_note"] = (
                        "Repeated record is not independent corroboration "
                        "(offline fixture, link-only, or missing citation)."
                    )
                    rec["provenance"] = prov
            out.append(rec)
    return out


def collapse(items: list[dict]) -> list[dict]:
    """One row per story for reporting. The archive keeps every source record.

    ``items`` must already be ranked: the highest-scored record survives and
    the others are listed as ``also_sources`` instead of being printed again.
    P27 adds canonical-URL and near-duplicate-title clustering on top of the
    exact fingerprint match (same story, slightly different headline).
    """
    best: dict[str, dict] = {}
    for item in items:
        key = (item.get("fingerprint") or item.get("guid") or
               canonical.dedupe_key(item) or item.get("title", ""))
        target = key if key in best else _cluster_match(item, best)
        current = best.get(target) if target else None
        if current is None:
            rec = dict(item)
            rec["also_sources"] = []
            rec["duplicate_count"] = 1
            best[key] = rec
            continue
        name = str(item.get("source") or "")
        if name and name != current.get("source") and name not in current["also_sources"]:
            current["also_sources"].append(name)
        current["duplicate_count"] += 1
        if item.get("cross_verified"):
            current["cross_verified"] = True
    return list(best.values())


def _cluster_match(item: dict, best: dict[str, dict]):
    """Find an existing cluster with the same canonical URL or a near-dup title."""
    item_url = canonical.canonicalize(item.get("canonical") or item.get("url") or "")
    item_title = str(item.get("title") or "")
    for key, rec in best.items():
        if item_url:
            rec_url = canonical.canonicalize(rec.get("canonical") or rec.get("url") or "")
            if rec_url and rec_url == item_url:
                return key
        if canonical.near_duplicate_titles(item_title, str(rec.get("title") or "")):
            return key
    return None


def citation_audit(items: list[dict]) -> dict:
    total = len(items or [])
    with_url = with_date = with_source = fabricated = link_only = offline = 0
    for item in items or []:
        prov = item.get("provenance") or {}
        url = str(item.get("url") or "")
        if url.lower().startswith(("http://", "https://")):
            with_url += 1
        if item.get("date_checked"):
            with_date += 1
        if item.get("source"):
            with_source += 1
        if item.get("link_only"):
            link_only += 1
        if (item.get("meta") or {}).get("offline"):
            offline += 1
        # Fabricated = a real-looking record with no citation, or an offline
        # fixture that is NOT honestly labelled as a fixture.
        if not prov.get("citation_ok"):
            fabricated += 1
        elif (item.get("meta") or {}).get("offline") and prov.get("kind") != "offline-fixture":
            fabricated += 1
    return {
        "total": total, "with_url": with_url, "with_date": with_date,
        "with_source": with_source, "fabricated": fabricated,
        "provenance_pct": round(100.0 * (total - fabricated) / total, 1) if total else 100.0,
        "link_only": link_only, "offline_fixtures": offline,
    }
