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
import os
import time

from . import config, highlight, llm, policy, store, util, verifier

# Category-level guidance — sirf recommendations/disclaimer ke tor par.
# Per-item khulasa me NA (warna item se unrelated jumla lagta hai); tests isay
# item output se door rakhne ki tameen istemal karte hain.
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

# P1.6 - 12 variti categories ko 4 beginner-friendly buckets me group karo.
# Report sirf 4 heading dikhata hai; asli category har item ki metadata me
# rehti hai, is liye detail qayam hai. config.TOPICS waise ke waise rehte hain.
CATEGORY_BUCKETS: dict[str, tuple[str, ...]] = {
    "Technical": ("Mobile & Firmware", "Android", "iOS", "AI & Local LLM",
                  "Hardware & Chipsets", "Tools & Reverse Engineering", "Telecom"),
    "Security": ("Security",),
    "Science & World": ("Science", "World", "Business & Policy"),
    "Watchlist": ("Custom Watchlist",),
}
BUCKET_ORDER: tuple[str, ...] = tuple(CATEGORY_BUCKETS)


def bucket_for(category: str) -> str:
    """Item category ka beginner bucket. Na-maloom category Watchlist hai."""
    cat = str(category or "Custom Watchlist").strip()
    for bucket, members in CATEGORY_BUCKETS.items():
        if cat in members:
            return bucket
    return "Watchlist"


def display_source(item: dict) -> str:
    """A synthetic fixture is never presented as a real publisher attribution."""
    meta = item.get("meta") or {}
    if isinstance(meta, dict) and meta.get("offline"):
        return "Offline fixture corpus"
    return item.get("source", "source")


def query_diagnostics(diagnostics: list[dict] | None,
                      items: list[dict] | None) -> list[dict]:
    """Sources table sirf is query ke sources dikhaye — jin se items aaye.

    Raw adapter ``count`` (off-topic filter ke baad bhi bara dikhta tha) ki
    jagah is query ke ranked items ka count use hota hai. Is tarah GSMArena
    jaisa source 20 raw items ke baawajood 0 report items par table se gayab.
    """
    counts: dict[str, int] = {}
    for item in items or []:
        key = str(item.get("source_key") or "").strip()
        if key:
            counts[key] = counts.get(key, 0) + 1
        name = str(item.get("source") or "").strip().lower()
        if name:
            counts.setdefault(name, 0)
    out: list[dict] = []
    seen: set[str] = set()
    for diag in diagnostics or []:
        if not isinstance(diag, dict):
            continue
        key = str(diag.get("key") or "").strip()
        name = str(diag.get("name") or "").strip().lower()
        ident = key if key in counts else (name if name in counts else "")
        if not ident or ident in seen:
            continue
        seen.add(ident)
        row = dict(diag)
        row["count"] = int(counts.get(ident) or 0)
        row["query_items"] = int(row["count"])
        out.append(row)
    out.sort(key=lambda d: (-int(d.get("count") or 0),
                            str(d.get("name") or "")))
    return out


def _item_key(item: dict) -> str:
    """Item ka stable cache key (guid, ya title+url)."""
    guid = str(item.get("guid") or "").strip()
    if guid:
        return guid
    return str(item.get("title") or "") + "|" + str(item.get("url") or "")


def _rule_khulasa(item: dict) -> str:
    """Item ke apne fields se Roman Urdu one-liner. Kabhi facts nahi banata."""
    source = display_source(item)
    date = item.get("published") or item.get("date_checked") or "date nahi mili"
    parts = [f"{source} ki ye maloomat {date} par aayi hai."]
    title = util.truncate(str(item.get("title") or ""), 150)
    if title:
        parts.append(f"Title: {title}.")
    excerpt = util.clean_text(
        item.get("excerpt") or item.get("snippet") or item.get("description") or "", 300)
    if excerpt:
        parts.append(f"Item ka khulasa: {util.truncate(excerpt, 300)}")
    entities = item.get("entities") or []
    values: list[str] = []
    for ent in entities:
        value = ent.get("value") if isinstance(ent, dict) else ent
        value = str(value or "").strip()
        if value and value not in values:
            values.append(value)
    if values:
        parts.append("Darj entities: " + ", ".join(values[:5]) + ".")
    return " ".join(parts)


def _llm_khulasa(item: dict, cfg: dict) -> str:
    """LLM se item ki asli summary — sirf item ke fields diye hote hain.

    Model ko koi URL/path/socket nahi milta; prompt me sirf item ki apni
    maloomat hoti hai. Fail hone par "" lauta aata hai (rule-based fallback).
    """
    entities = item.get("entities") or []
    values = [str(e.get("value") if isinstance(e, dict) else e) for e in entities]
    values = [v.strip() for v in values if str(v or "").strip()][:6]
    excerpt = util.truncate(
        util.clean_text(item.get("excerpt") or item.get("snippet")
                        or item.get("description") or "", 800), 800)
    prompt = (
        "Summarize this ONE research item in 1-2 sentences of natural Roman Urdu. "
        "Use ONLY the fields below. Never invent facts, URLs, dates or citations. "
        "Keep technical terms in English.\n\n"
        f"Title: {item.get('title', '')}\n"
        f"Source: {display_source(item)}\n"
        f"Published: {item.get('published') or 'n/a'}\n"
        f"Date checked: {item.get('date_checked') or 'n/a'}\n"
        f"Category: {item.get('category', '')}\n"
        f"Excerpt: {excerpt or 'n/a'}\n"
        f"Entities: {', '.join(values) if values else 'n/a'}"
    )
    try:
        out = llm.chat(cfg, llm.SYSTEM_RESEARCH, prompt, timeout=20)
    except Exception:
        return ""
    text = str((out or {}).get("text") or "").strip()
    return util.truncate(text, 500) if text else ""


def summarize_items(items: list[dict], cfg: dict) -> dict[str, str]:
    """LLM mode me har item ki summary cache banata hai; off ho to {}.

    Cache ``khulasa`` aur report export isi se parhte hain, taake HTML/MD
    ek hi summary dobara na likhein.
    """
    if not items:
        return {}
    try:
        mode = llm.resolve(cfg).get("mode")
    except Exception:
        return {}
    if mode != "llm":
        return {}
    out: dict[str, str] = {}
    for item in items:
        text = _llm_khulasa(item, cfg)
        if text:
            out[_item_key(item)] = text
    return out


def khulasa(item: dict, cfg: dict | None = None,
            cache: dict[str, str] | None = None) -> str:
    """Item-specific Roman Urdu summary.

    - ``cache`` mojood ho to wahi summary (build/report export ek hi natija).
    - LLM enabled ho to asli summary; fail par rule-based fallback.
    - LLM off ho to sirf item ke apne fields — category ki canned jumla nahi.
    """
    key = _item_key(item)
    if isinstance(cache, dict) and key in cache:
        cached = str(cache[key] or "").strip()
        if cached:
            return cached
    base = _rule_khulasa(item)
    if cfg is not None:
        try:
            mode = llm.resolve(cfg).get("mode")
        except Exception:
            mode = "rule_based"
        if mode == "llm":
            text = _llm_khulasa(item, cfg)
            if text:
                if isinstance(cache, dict):
                    cache[key] = text
                return text
    return base


def _markdown(query, items, diagnostics, cfg, plan_result, audit, metrics,
              duration_ms, mode, blocked=None,
              summaries: dict[str, str] | None = None) -> str:
    date_checked = util.now_iso()
    terms = highlight.terms(query)
    qdiagnostics = query_diagnostics(diagnostics, items)
    categories: dict[str, list[dict]] = {}
    for item in items:
        categories.setdefault(item.get("category", "Custom Watchlist"), []).append(item)
    verified = [i for i in items if i.get("verified")]
    unverified = [i for i in items if not i.get("verified")]
    conf = verifier.aggregate_confidence(items)
    lines = [
        "# JIN Agent - Research Brief",
        "",
        f"**Query:** {highlight.highlight_markdown(query, terms)}",
        f"**Date checked:** {date_checked}",
        f"**Mode:** {mode} | **Duration:** {duration_ms} ms",
        f"**Policy:** {policy.POLICY_ID} | **Tor:** {cfg.get('tor_mode', 'links_only')}",
        f"**Confidence:** {conf['label']} ({conf['value']}) — "
        f"{conf['cross_verified']} cross-verified / {conf['verified']} verified "
        f"/ {conf['items']} items",
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
        buckets: dict[str, list[str]] = {}
        for category in categories:
            buckets.setdefault(bucket_for(category), []).append(category)
        for bucket in BUCKET_ORDER:
            members = buckets.get(bucket)
            if not members:
                continue
            lines += [f"### {bucket}", ""]
            for category in sorted(members):
                for item in categories[category]:
                    meta = item.get("meta") or {}
                    if item.get("cross_verified"):
                        cross = "yes"
                    elif meta.get("offline") or item.get("link_only"):
                        cross = "no (offline fixture / link-only: independent corroboration nahi)"
                    else:
                        cross = "no"
                    title = str(item.get("title") or "")
                    htitle = highlight.highlight_markdown(title, terms)
                    title_line = f"- {htitle}" if htitle != title else f"- **{title}**"
                    lines += [
                        title_line,
                        (f"  - Source: {display_source(item)} | Category: {category} | "
                         f"Tier: {item.get('tier', '')} | "
                         f"Date checked: {item.get('date_checked', '')} | "
                         f"Published: {item.get('published') or 'n/a'} | "
                         f"Confidence: {item.get('confidence', 0)} | "
                         f"Trust: {item.get('trust_label', '')} | Score: {item.get('score', 0)}"),
                        f"  - URL: {item.get('url', '')}",
                        (f"  - Khulasa: "
                         f"{highlight.highlight_markdown(khulasa(item, cfg, summaries), terms)}"),
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
        repeated = verifier.repeated_claims(items)
        if repeated:
            lines += ["## Repeated Claims", ""]
            for row in repeated[:8]:
                where = ", ".join(row["channels"][:3]) or ", ".join(row["sources"][:3]) or "-"
                lines.append(f"- {row['label']} · {row['count']}× · "
                             f"{util.truncate(row['title'], 90)} ({where})")
            lines.append("")
        lines += ["## Recommendations", ""]
        recs = []
        for category in sorted(categories):
            if category in RECOMMENDATIONS:
                recs.append(f"- **{category}:** {RECOMMENDATIONS[category]}")
        recs += [
            "- Har customer case mein official route, consent aur local record rakhein.",
            "- Ye report sirf research / educational maqsad ke liye hai; kisi b operation ke liye official route use karein.",
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
    for diag in qdiagnostics:
        lines.append(f"| {diag.get('name', '')} | {diag.get('tier', '')} | "
                     f"{'OK' if diag.get('ok') else 'FAIL'} | {diag.get('count', 0)} | "
                     f"{util.truncate(diag.get('error', ''), 90).replace('|', '/')} |")
    if not qdiagnostics:
        note = ("Blocked request par koi fetch nahi hua" if blocked
                else "Is query par koi source item nahi diya")
        lines.append(f"| (none) | - | - | 0 | {note} |")
    lines += ["", "## Provenance", "",
              f"- Items: {audit.get('total', 0) if audit else 0}",
              f"- With URL: {audit.get('with_url', 0) if audit else 0}",
              f"- With date checked: {audit.get('with_date', 0) if audit else 0}",
              f"- With source: {audit.get('with_source', 0) if audit else 0}",
              f"- Provenance: {audit.get('provenance_pct', 100) if audit else 100}%",
              f"- Fabricated citations: {audit.get('fabricated', 0) if audit else 0}",
              f"- Source register: {len(policy.register())} entries, date checked {policy.DATE_CHECKED}",
              "",
              "## Disclaimer", "",
              ("Ye report sirf **research / educational** maqsad ke liye tayyar ki gayi hai. "
               "JIN Agent kisi b masle (FRP / MDM / account / activation lock waghera) ka "
               "operation, bypass ya step-by-step tareeqa nahi deta; is par agent ki zimmedari nahi hoti. "
               "Koi b qanooni ya technical kaam ke liye official manufacturer / regulator route use karein."),
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
    summaries = summarize_items(items, cfg)
    markdown = _markdown(query, items, diagnostics, cfg, plan_result, audit,
                         metrics, duration_ms, mode, blocked, summaries)
    confidence = verifier.aggregate_confidence(items)
    repeated = verifier.repeated_claims(items)
    structured = {
        "query": query, "date_checked": util.now_iso(), "mode": mode,
        "policy_id": policy.POLICY_ID, "tor_mode": cfg.get("tor_mode"),
        "planner": (plan_result or {}).get("source", "n/a"),
        "tools": [c["tool"] for c in (plan_result or {}).get("calls", [])],
        "items": items, "diagnostics": diagnostics, "audit": audit,
        "metrics": metrics, "blocked": blocked or None,
        "summaries": summaries,
        "confidence": confidence, "repeated_claims": repeated,
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
        "confidence": confidence["value"],
        "confidence_label": confidence["label"],
        "repeated_claims": repeated,
    }


def report_days() -> int:
    """Reports dir retention (din). Default 90, env ``JIN_AGENT_REPORT_DAYS``."""
    try:
        days = int(str(os.environ.get("JIN_AGENT_REPORT_DAYS", "90") or 90))
    except (TypeError, ValueError):
        days = 90
    return max(1, days)


def prune_reports(days: int | None = None) -> int:
    """``data/reports/`` se purane ``.md/.csv/.json`` hatao (disk bounded)."""
    days = report_days() if days is None else max(1, int(days))
    folder = config.reports_dir()
    cutoff = time.time() - days * 86400
    pruned = 0
    try:
        entries = list(folder.iterdir())
    except OSError:
        return 0
    for path in entries:
        if path.suffix.lower() not in (".md", ".csv", ".json"):
            continue
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
                pruned += 1
        except OSError:
            continue
    return pruned


def save(built: dict, query: str, metrics: dict | None = None) -> dict:
    """Write Markdown + CSV + JSON, register + purane reports prune karo."""
    stamp = util.now_iso().replace(":", "").replace("-", "").replace("Z", "")
    stem = util.safe_filename("brief-" + stamp)
    folder = config.reports_dir()
    paths = {}
    for fmt, key in (("md", "markdown"), ("csv", "csv"), ("json", "json")):
        path = folder / f"{stem}.{fmt}"
        path.write_text(built[key], encoding="utf-8")
        paths[fmt] = str(path)
    record = store.save_report(built["title"], query, paths["md"], "md", metrics)
    pruned = prune_reports()
    return {"id": record["id"], "pruned_reports": int(pruned), **paths}
