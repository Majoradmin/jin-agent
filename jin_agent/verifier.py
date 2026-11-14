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

from . import policy, util


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


def cross_check(items: list[dict]) -> list[dict]:
    """Same event from >=2 independent sources -> cross-verified boost."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        groups[item.get("fingerprint", "")].append(item)
    out = []
    for group in groups.values():
        sources = {i.get("source_key", "") for i in group}
        multi = len(sources) >= 2
        for item in group:
            rec = dict(item)
            if multi:
                rec["cross_verified"] = True
                rec["confidence"] = round(min(0.98, float(rec.get("confidence", 0)) + 0.15), 2)
                rec["reasons"] = list(rec.get("reasons") or []) + ["cross-verified"]
                prov = dict(rec.get("provenance") or {})
                prov["cross_verified_with"] = sorted(sources)
                rec["provenance"] = prov
            out.append(rec)
    return out


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
