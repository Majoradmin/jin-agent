"""Professional Roman Urdu report builder.

Style guide (opencode plan section 7):
  - Headings / labels / technical terms = English
  - Explanation / summary / analysis = Roman Urdu
  - Formal tone; no slang, no emojis, no hype
  - Every item carries source + date checked + confidence
  - FACTS and RECOMMENDATIONS are separate sections
  - "Kya verify nahi hua" is its own section
"""

from __future__ import annotations

import csv
import io
import json

from . import config, policy, store, util

HINTS = {
    "Mobile & Firmware": "Flash karne se pehle exact model, region / CSC aur binary revision match karain; galat package bootloop ya blocked binary deta hai.",
    "Android": "Build number, security patch level aur vendor variant note karain; purane loader naye patch par kaam nahi karte.",
    "iOS": "Activation aur carrier policy Apple ke server par rehti hai, device mein nahi; sirf official support aur purchase proof mustanad hain.",
    "Security": "Naya patch purane loader, DA aur test-point flows ko na-qabil bana sakta hai; apne packages aur tool versions update karain.",
    "AI & Local LLM": "Model ka size apne RAM / VRAM ke hisaab se chunain; tool access aur source-only summarization se hallucination ghatti hai.",
    "Hardware & Chipsets": "Chipset, storage type (eMMC / UFS) aur loader version aik doosre se match honay chahiye.",
    "Tools & Reverse Engineering": "Tool ka version, supported-model list aur changelog dekhain; cracked builds se parhez karain.",
    "Telecom": "Carrier policy aur regulatory status server-side hoti hai; sirf official carrier / regulator record par bharosa karain.",
    "Business & Policy": "Qanooni aur compliance maloomat ke liye official gazette / regulator page ka URL aur date checked zaroor darj karain.",
    "Science": "Preprint ko final peer-reviewed natija na samjhein; DOI aur publication date check karain.",
    "World": "Global khabaron ko kam-az-kam do azad sources se cross-check karain pehle ke inhen faislay ki bunyaad banayein.",
    "Custom Watchlist": "Watchlist keyword par aane wali naye items ko archive mein search kar ke purane record se milayein.",
}

RECOMMENDATIONS = {
    "Mobile & Firmware": "Apne local package catalog mein usi model ka record update karain.",
    "Security": "Mutaliqa security bulletin ka official page bookmark karain aur patch level note karain.",
    "Tools & Reverse Engineering": "Release notes par version aur supported-model list verify karain.",
    "iOS": "Apple Support ya authorized service route par case open karain.",
    "AI & Local LLM": "Tool layer ke baahar kisi bhi raw browsing ki ijazat na dein.",
    "Hardware & Chipsets": "Loader aur firmware ka chipset / storage match pehle check karain.",
    "Science": "DOI ya arXiv ID ke sath apni local references list update karain.",
    "World": "Aik se zyada sources se tasdeeq ke baghair customer ko natija na dein.",
}


def display_source(item: dict) -> str:
    """A synthetic fixture is never presented as a real publisher attribution."""
    meta = item.get("meta") or {}
    if isinstance(meta, dict) and meta.get("offline"):
        return "Offline fixture corpus"
    return item.get("source", "source")


def khulasa(item: dict) -> str:
    """Rule-based Roman Urdu one-liner. Never invents facts."""
    title = item.get("title", "")
    source = display_source(item)
    date = item.get("published") or "date nahi mili"
    cat = item.get("category", "Custom Watchlist")
    return (f"{source} ki ye maloomat {date} par aayi hai. "
            f"Title mein darga hai: {util.truncate(title, 150)}. "
            f"{HINTS.get(cat, HINTS['Custom Watchlist'])}")


def _markdown(query, items, diagnostics, cfg, plan_result, audit, metrics,
              duration_ms, mode, blocked=None) -> str:
    date_checked = util.now_iso()
    categories: dict[str, list[dict]] = {}
    for item in items:
        categories.setdefault(item.get("category", "Custom Watchlist"), []).append(item)
    verified = [i for i in items if i.get("verified")]
    unverified = [i for i in items if not i.get("verified")]
    lines = [
        "# JIN Agent - Research Brief",
        "",
        f"**Query:** {query}",
        f"**Date checked:** {date_checked}",
        f"**Mode:** {mode} | **Duration:** {duration_ms} ms",
        f"**Policy:** {policy.POLICY_ID} | **Tor:** {cfg.get('tor_mode', 'links_only')}",
        "",
        "## Executive Summary",
        "",
    ]
    if blocked:
        lines += [
            "Ye request **Sahulat & Safe Service Policy** ke tahat block hai. "
            "Koi live search nahi ki gayi aur koi device operation nahi kiya gaya.",
            "",
            f"**Wajah:** {blocked['reason']}",
            "",
            "**Official route:** " + ", ".join(blocked.get("official_links") or []),
            "",
        ]
    else:
        top_sources = sorted({display_source(i) for i in items})[:6]
        merged = int((metrics or {}).get("duplicate_rows_merged", 0) or 0)
        dropped = int((metrics or {}).get("off_topic_dropped", 0) or 0)
        lines += [
            (f"Is run mein **{len(items)}** unique stories mile, jin mein **{len(verified)}** "
             f"verified citation ke sath aur **{len(unverified)}** abhi verify nahi hue. "
             f"Kaam karne wale sources: {', '.join(top_sources) if top_sources else 'koi nahi'}. "
             f"Zyada tar maloomat {len(categories)} categories mein aayi."),
            "",
            ("Sabse aham baat: har natija neeche apne source, date checked aur confidence "
             "ke sath darj hai. Jin article URLs ko agent ne khud fetch nahi kiya, unhen "
             "'Not Verified' mein wazeh kiya gaya hai — inhen tasdeeq ke baghair customer "
             "ko haqiqat ke tor par na batayein."),
            "",
        ]
        if merged or dropped:
            lines += [
                (f"**{merged}** duplicate source records ko aik hi story mein jorr kar dikhaya "
                 f"gaya hai aur **{dropped}** zero-relevance records brief se nikaale gaye; "
                 "archive mein har record apne source ke sath maujood hai. Offline fixtures "
                 "ya link-only records ko kabhi 'cross-verified' nahi kaha jata."),
                "",
            ]
    lines += ["## Scope & Method", "",
              ("Agent ne pehle tool plan banaya, har tool call ko validate kiya, phir "
               "allowlisted public adapters se maloomat la kar plain text mein badli. "
               "LLM ko kabhi raw internet nahi mila. Provenance, dedupe, trust score aur "
               "cross-verification ke baad ye report bani."),
              "",
              f"**Planner:** {(plan_result or {}).get('source', 'n/a')} | "
              f"**Tools used:** {', '.join(c['tool'] for c in (plan_result or {}).get('calls', [])) or 'none'}",
              f"**Rejected tool calls:** {len((plan_result or {}).get('rejected', []))}",
              ""]
    if blocked:
        lines += ["## Safe Next Steps", ""]
        lines += [f"- {step}" for step in blocked.get("safe_steps", [])]
        lines += ["", "## Recommendations", "",
                  "Sirf official manufacturer route aur malik ki tasdeeq ke sath aage barhein. "
                  "Is agent mein koi bypass automation ya step-by-step tareeqa maujood nahi.", ""]
    else:
        lines += ["## Facts by Category", ""]
        if not items:
            lines += ["Is query par koi item nahi mila. Offline ya network failure ki soorat "
                      "mein agent khali natija deta hai, koi banawati khabar nahi banata.", ""]
        for category in sorted(categories):
            rows = categories[category][:5]
            lines += [f"### {category}", ""]
            for item in rows:
                meta = item.get("meta") or {}
                if item.get("cross_verified"):
                    cross = "yes"
                elif meta.get("offline") or item.get("link_only"):
                    cross = "no (offline fixture / link-only: independent corroboration nahi)"
                else:
                    cross = "no"
                lines += [
                    f"- **{item.get('title', '')}**",
                    (f"  - Source: {display_source(item)} | Tier: {item.get('tier', '')} | "
                     f"Date checked: {item.get('date_checked', '')} | "
                     f"Published: {item.get('published') or 'n/a'} | "
                     f"Confidence: {item.get('confidence', 0)} | "
                     f"Trust: {item.get('trust_label', '')} | Score: {item.get('score', 0)}"),
                    f"  - URL: {item.get('url', '')}",
                    f"  - Khulasa: {khulasa(item)}",
                    (f"  - Why it matters: {HINTS.get(category, HINTS['Custom Watchlist'])}"),
                    (f"  - Cross-verified: {cross}"),
                    "",
                ]
                if item.get("also_sources"):
                    label = ("Fixture replayed by" if meta.get("offline")
                             else "Also reported by")
                    lines.insert(
                        len(lines) - 1,
                        f"  - {label}: {', '.join(item['also_sources'])} "
                        f"({item.get('duplicate_count', 1)} source records merged)",
                    )
            if len(categories[category]) > 5:
                lines += [f"_Is category mein mazid {len(categories[category]) - 5} items archive mein hain._", ""]
        lines += ["## Recommendations", ""]
        recs = []
        for category in sorted(categories):
            if category in RECOMMENDATIONS:
                recs.append(f"- **{category}:** {RECOMMENDATIONS[category]}")
        recs += [
            "- Har customer case mein official route, consent aur local record rakhein.",
            "- Koi bhi FRP / MDM / account / activation lock bypass step is agent se mat maangein; ye policy ke khilaf hai.",
        ]
        lines += recs + [""]
    lines += ["## Not Verified / Limitations", ""]
    if unverified:
        lines += [f"- **{len(unverified)}** items abhi verified nahi: article URL agent ne khud fetch nahi kiya; ye adapter ke citation hain."]
    else:
        lines += ["- Is run mein koi unresolved item nahi."]
    if audit and audit.get("link_only"):
        lines += [f"- **{audit['link_only']}** onion links sirf display ke liye hain; " + policy.DARK_WEB_RULE]
    if audit and audit.get("offline_fixtures"):
        lines += [f"- **{audit['offline_fixtures']}** offline evaluation fixtures hain — ye asli citations nahi."]
    lines += [
        "- Koi bhi agent duniya ki 100% khabarain hasil nahi kar sakta; ye defined source universe ka best-effort natija hai.",
        "- Har fact ka URL aur date checked darj hai; recommendations alag section mein hain.",
        "- LLM band hone par rule-based Roman Urdu khulasa chalata hai; ye bug nahi, by-design fallback hai.",
        "",
        "## Sources & Diagnostics", "",
        "| Source | Tier | Status | Items | Note |", "|---|---|---|---|---|",
    ]
    for diag in diagnostics or []:
        lines.append(f"| {diag.get('name', '')} | {diag.get('tier', '')} | "
                     f"{'OK' if diag.get('ok') else 'FAIL'} | {diag.get('count', 0)} | "
                     f"{util.truncate(diag.get('error', ''), 90).replace('|', '/')} |")
    if not diagnostics:
        lines.append("| (none) | - | - | 0 | Blocked request par koi fetch nahi hua |")
    lines += ["", "## Provenance", "",
              f"- Items: {audit.get('total', 0) if audit else 0}",
              f"- With URL: {audit.get('with_url', 0) if audit else 0}",
              f"- With date checked: {audit.get('with_date', 0) if audit else 0}",
              f"- With source: {audit.get('with_source', 0) if audit else 0}",
              f"- Provenance: {audit.get('provenance_pct', 100) if audit else 100}%",
              f"- Fabricated citations: {audit.get('fabricated', 0) if audit else 0}",
              f"- Source register: {len(policy.register())} entries, date checked {policy.DATE_CHECKED}",
              "",
              "## Metrics", "",
              "```json", json.dumps(metrics or {}, ensure_ascii=False, indent=2), "```", ""]
    return "\n".join(lines)


def _csv(items: list[dict]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["title", "url", "source", "source_key", "tier", "trust_label",
                     "category", "published", "date_checked", "confidence",
                     "score", "verified", "cross_verified", "link_only",
                     "also_sources", "duplicate_count"])
    for item in items:
        row = [item.get(k, "") for k in
               ("title", "url", "source", "source_key", "tier", "trust_label",
                "category", "published", "date_checked", "confidence",
                "score", "verified", "cross_verified", "link_only")]
        row += [" | ".join(item.get("also_sources") or []),
                item.get("duplicate_count", 1)]
        writer.writerow(row)
    return buf.getvalue()


def build(query: str, items: list[dict], diagnostics: list[dict],
          cfg: dict | None = None, plan_result: dict | None = None,
          audit: dict | None = None, metrics: dict | None = None,
          duration_ms: int = 0, mode: str = "offline",
          blocked: dict | None = None) -> dict:
    cfg = cfg or config.load()
    markdown = _markdown(query, items, diagnostics, cfg, plan_result, audit,
                         metrics, duration_ms, mode, blocked)
    structured = {
        "query": query, "date_checked": util.now_iso(), "mode": mode,
        "policy_id": policy.POLICY_ID, "tor_mode": cfg.get("tor_mode"),
        "planner": (plan_result or {}).get("source", "n/a"),
        "tools": [c["tool"] for c in (plan_result or {}).get("calls", [])],
        "items": items, "diagnostics": diagnostics, "audit": audit,
        "metrics": metrics, "blocked": blocked or None,
    }
    return {
        "title": f"JIN Agent Brief - {util.truncate(query, 60)}",
        "markdown": markdown,
        "csv": _csv(items),
        "json": json.dumps(structured, ensure_ascii=False, indent=2),
        "facts_count": len(items),
        "verified_count": sum(1 for i in items if i.get("verified")),
        "not_verified_count": sum(1 for i in items if not i.get("verified")),
        "categories": sorted({i.get("category", "") for i in items}),
    }


def save(built: dict, query: str, metrics: dict | None = None) -> dict:
    """Write Markdown + CSV + JSON, then register them in the archive."""
    stamp = util.now_iso().replace(":", "").replace("-", "").replace("Z", "")
    stem = util.safe_filename("brief-" + stamp)
    folder = config.reports_dir()
    paths = {}
    for fmt, key in (("md", "markdown"), ("csv", "csv"), ("json", "json")):
        path = folder / f"{stem}.{fmt}"
        path.write_text(built[key], encoding="utf-8")
        paths[fmt] = str(path)
    record = store.save_report(built["title"], query, paths["md"], "md", metrics)
    return {"id": record["id"], **paths}
