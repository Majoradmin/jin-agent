"""Tool layer - the single most important design decision of the JIN plan.

    LLM (local) -> tool request -> AGENT VALIDATES -> adapter fetches
                -> clean plain text -> LLM summarizes

The model never receives a socket, a shell, a file path, or raw HTML. Tool
output is scrubbed for prompt-injection text and size-capped.
"""

from __future__ import annotations

import re

from . import adapters, config, llm, policy, snapshots, store, util, verifier

MAX_CALLS = 6
MAX_TOOL_TEXT = 6500

TOOLS = {
    "search_public": {
        "args": {"query": "str", "days": "int", "limit": "int"},
        "desc": "Search validated public news / RSS / code adapters.",
    },
    "fetch_url": {
        "args": {"url": "str"},
        "desc": "GET one allowlisted public URL as scrubbed plain text.",
    },
    "search_telegram": {
        "args": {"query": "str", "limit": "int"},
        "desc": "Read explicitly configured PUBLIC t.me/s/ channels only.",
    },
    "search_onion_index": {
        "args": {"query": "str"},
        "desc": "Legal Ahmia clearnet onion discovery - links only, never fetched.",
    },
    "search_papers": {
        "args": {"query": "str", "limit": "int"},
        "desc": "Legal scholarly indexes: OpenAlex / Crossref / arXiv.",
    },
    "search_social": {
        "args": {"query": "str", "limit": "int"},
        "desc": "Public Reddit search JSON (read-only subreddit search).",
    },
    "search_reference": {
        "args": {"query": "str", "limit": "int"},
        "desc": "Wikipedia / Wikidata reference search.",
    },
    "search_security": {
        "args": {"query": "str", "limit": "int"},
        "desc": "Official NVD CVE 2.0 feed (keyword search).",
    },
    "search_code": {
        "args": {"query": "str", "limit": "int"},
        "desc": "GitHub repository search (unauthenticated, rate-limit aware).",
    },
    "search_web_archive": {
        "args": {"query": "str", "limit": "int"},
        "desc": "Wayback availability / CDX snapshots - links only.",
    },
    "search_sitemap": {
        "args": {"query": "str", "limit": "int"},
        "desc": "robots.txt + sitemap.xml discovery on allowlisted hosts (bounded).",
    },
    "search_web": {
        "args": {"query": "str", "limit": "int"},
        "desc": "Optional keyed Brave / Bing web search; disabled without a key.",
    },
    "verify_source": {
        "args": {"url": "str"},
        "desc": "Validate a URL and report its provenance fields.",
    },
    "search_archive": {
        "args": {"query": "str", "limit": "int"},
        "desc": "Search the local SQLite FTS5 archive.",
    },
    "save_report": {
        "args": {"title": "str"},
        "desc": "Flag that the generated brief should be saved.",
    },
}

TOOL_NAMES = sorted(TOOLS)

INJECTION = re.compile(
    r"(ignore\s+(all\s+)?(previous|prior|above)|disregard\s+(the\s+)?(instructions|system)|"
    r"system\s*prompt|you are now|jailbreak|dan mode|act as\s+(a\s+)?(developer|admin)|"
    r"exfiltrat|run this|execute\s+(the\s+)?(command|script)|<\|.*?\|>|"
    r"do not tell\s+the\s+user|reveal\s+(your\s+)?(key|token|secret))", re.I)


class ToolRejected(ValueError):
    pass


def validate(call) -> dict:
    """Strict allowlist validation. Anything unexpected is rejected."""
    if not isinstance(call, dict):
        raise ToolRejected("Tool call object nahi hai")
    name = str(call.get("tool") or "").strip()
    if name not in TOOLS:
        raise ToolRejected("Unknown tool: " + name[:40])
    args = call.get("args") or {}
    if not isinstance(args, dict):
        raise ToolRejected("args object hona chahiye")
    spec = TOOLS[name]["args"]
    extra = set(args) - set(spec)
    if extra:
        raise ToolRejected("Extra args allowed nahi: " + ", ".join(sorted(extra))[:80])
    clean = {}
    for key, kind in spec.items():
        value = args.get(key, "" if kind == "str" else 0)
        if kind == "str":
            value = str(value)
            if len(value) > 4000:
                raise ToolRejected("Argument bohat lamba hai")
        elif kind == "int":
            value = util.clamp(value, 1, 90 if key == "days" else 50,
                               7 if key == "days" else 20)
        else:
            raise ToolRejected("Unknown arg type")
        clean[key] = value
    if "url" in clean:
        ok, reason = policy.check_url(clean["url"], policy.adapter_hosts())
        if not ok:
            raise ToolRejected(reason)
    if clean.get("query", "").strip() and policy.classify(clean["query"])["verdict"] == "blocked":
        raise ToolRejected("Request Sahulat & Safe Service Policy se blocked hai")
    return {"tool": name, "args": clean}


def scrub(text, limit: int = MAX_TOOL_TEXT) -> str:
    """Plain-text-only output with instruction-like fragments neutralised.

    ``clean_text`` collapses whitespace, so filtering whole *lines* would drop
    legitimate sentences that happen to sit beside an injected one. Substitute
    the matched fragment instead - the rest of the source text survives.
    """
    s = util.clean_text(text, limit)
    s = INJECTION.sub("[instruction-removed]", s)
    s = re.sub(r"\b[A-Za-z0-9+/]{180,}={0,2}\b", "[long-blob-removed]", s)
    return " ".join(s.split())[:limit]


def _lines(items: list[dict], n: int = 25) -> str:
    parts = []
    for i, item in enumerate(items[:n], 1):
        parts.append(f"[{i}] {item.get('title','')} | {item.get('source','')} | "
                     f"{item.get('published') or 'date n/a'} | {item.get('url','')}")
    return scrub("\n".join(parts))


def dispatch(call: dict, ctx: dict) -> dict:
    """Execute ONE validated tool call. Returns plain text + structured items."""
    from . import normalizer
    name, args = call["tool"], call["args"]
    cfg = ctx.get("cfg") or config.load()
    offline = bool(ctx.get("offline", True))
    result = {"tool": name, "args": args, "text": "", "items": [], "error": ""}
    try:
        if name == "search_public":
            keys = ["gsmarena", "xda", "androidauthority", "androidpolice",
                    "9to5google", "sammobile", "apple-newsroom", "gnews",
                    "gnews-topic", "hn", "github", "gdelt"]
            items, diag = adapters.run(args.get("query", ctx.get("query", "")),
                                       keys=keys, days=int(args.get("days", 7)),
                                       limit=int(args.get("limit", 20)),
                                       cfg=cfg, offline=offline)
            result["items"] = items
            result["text"] = _lines(items)
            result["diagnostics"] = diag
        elif name == "fetch_url":
            if offline:
                text = ""
            else:
                text = adapters.fetch(args["url"], cfg)
                try:
                    snapshots.record("fetch-url", args["url"], text, cfg)
                except Exception:
                    pass
            result["text"] = scrub(text)
        elif name == "search_telegram":
            items, diag = adapters.run(args.get("query", ctx.get("query", "")),
                                       keys=["telegram-public"],
                                       limit=int(args.get("limit", 20)),
                                       cfg=cfg, offline=offline, include_opt_in=True)
            result["items"] = items
            result["text"] = _lines(items)
            result["diagnostics"] = diag
        elif name == "search_onion_index":
            items, diag = adapters.run(args.get("query", ctx.get("query", "")),
                                       keys=["ahmia"], cfg=cfg, offline=offline,
                                       include_opt_in=True)
            result["items"] = items
            result["text"] = scrub(policy.DARK_WEB_RULE + "\n" + _lines(items))
            result["diagnostics"] = diag
        elif name == "search_papers":
            items, diag = adapters.run(args.get("query", ctx.get("query", "")),
                                       keys=["openalex", "crossref", "arxiv"],
                                       limit=int(args.get("limit", 20)),
                                       cfg=cfg, offline=offline)
            result["items"] = items
            result["text"] = _lines(items)
            result["diagnostics"] = diag
        elif name == "search_social":
            items, diag = adapters.run(args.get("query", ctx.get("query", "")),
                                       keys=["reddit"],
                                       limit=int(args.get("limit", 20)),
                                       cfg=cfg, offline=offline)
            result["items"] = items
            result["text"] = _lines(items)
            result["diagnostics"] = diag
        elif name == "search_reference":
            items, diag = adapters.run(args.get("query", ctx.get("query", "")),
                                       keys=["wikipedia", "wikidata"],
                                       limit=int(args.get("limit", 20)),
                                       cfg=cfg, offline=offline)
            result["items"] = items
            result["text"] = _lines(items)
            result["diagnostics"] = diag
        elif name == "search_security":
            items, diag = adapters.run(args.get("query", ctx.get("query", "")),
                                       keys=["nvd"],
                                       limit=int(args.get("limit", 20)),
                                       cfg=cfg, offline=offline)
            result["items"] = items
            result["text"] = _lines(items)
            result["diagnostics"] = diag
        elif name == "search_code":
            items, diag = adapters.run(args.get("query", ctx.get("query", "")),
                                       keys=["github-search"],
                                       limit=int(args.get("limit", 20)),
                                       cfg=cfg, offline=offline)
            result["items"] = items
            result["text"] = _lines(items)
            result["diagnostics"] = diag
        elif name == "search_web_archive":
            items, diag = adapters.run(args.get("query", ctx.get("query", "")),
                                       keys=["wayback"],
                                       limit=int(args.get("limit", 20)),
                                       cfg=cfg, offline=offline)
            result["items"] = items
            result["text"] = _lines(items)
            result["diagnostics"] = diag
        elif name == "search_sitemap":
            items, diag = adapters.run(args.get("query", ctx.get("query", "")),
                                       keys=["sitemap"],
                                       limit=int(args.get("limit", 20)),
                                       cfg=cfg, offline=offline)
            result["items"] = items
            result["text"] = _lines(items)
            result["diagnostics"] = diag
        elif name == "search_web":
            items, diag = adapters.run(args.get("query", ctx.get("query", "")),
                                       keys=["brave-search", "bing-search"],
                                       limit=int(args.get("limit", 20)),
                                       cfg=cfg, offline=offline)
            result["items"] = items
            result["text"] = _lines(items)
            result["diagnostics"] = diag
        elif name == "verify_source":
            ok, reason = policy.check_url(args["url"], policy.adapter_hosts())
            result["text"] = scrub(
                f"URL: {args['url']}\nAllowed: {ok}\nReason: {reason or 'OK'}\n"
                f"Date checked: {util.now_iso()}\nURL fetched: no (validation only)")
            result["provenance"] = {"url": args["url"], "allowed": ok,
                                    "date_checked": util.now_iso()}
        elif name == "search_archive":
            # Archive rows are ALREADY normalized; returning them as text keeps
            # them out of the raw-fetch normalization path (no double ingest).
            rows = store.search_archive(args.get("query", ""),
                                        int(args.get("limit", 20)))
            result["items"] = []
            result["text"] = _lines(rows)
        elif name == "save_report":
            result["text"] = scrub("Report save requested: " + args.get("title", ""))
            result["save_report"] = args.get("title", "")
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {util.truncate(str(exc), 160)}"
        result["text"] = scrub("Tool failed: " + result["error"])
    return result


def _deterministic_calls(query: str, cfg: dict) -> list[dict]:
    low = str(query or "").lower()
    calls = [
        {"tool": "search_public", "args": {"query": str(query)[:600], "days": 7, "limit": 25}},
        {"tool": "search_archive", "args": {"query": str(query)[:300], "limit": 10}},
    ]
    if re.search(r"\b(paper|research|study|arxiv|doi|academic|patent)\b", low):
        calls.append({"tool": "search_papers", "args": {"query": str(query)[:400], "limit": 15}})
    if re.search(r"\b(reddit|forum|community|discussion|social)\b", low):
        calls.append({"tool": "search_social", "args": {"query": str(query)[:400], "limit": 15}})
    if re.search(r"\b(wikipedia|wikidata|encyclopedia|reference|what is|who is|definition)\b", low):
        calls.append({"tool": "search_reference", "args": {"query": str(query)[:400], "limit": 15}})
    if re.search(r"\b(cve|nvd|vulnerability|exploit|security advisory|patch tuesday)\b", low):
        calls.append({"tool": "search_security", "args": {"query": str(query)[:400], "limit": 15}})
    if re.search(r"\b(github|repo|repository|source code|open source|sdk)\b", low):
        calls.append({"tool": "search_code", "args": {"query": str(query)[:400], "limit": 15}})
    if re.search(r"\b(wayback|archive\.org|archived|old version|snapshot|deleted page)\b", low):
        calls.append({"tool": "search_web_archive", "args": {"query": str(query)[:500], "limit": 15}})
    if re.search(r"\b(sitemap|robots\.txt|crawl|site index)\b", low):
        calls.append({"tool": "search_sitemap", "args": {"query": str(query)[:500], "limit": 15}})
    if str(cfg.get("brave_key") or "").strip() or str(cfg.get("bing_key") or "").strip():
        calls.append({"tool": "search_web", "args": {"query": str(query)[:400], "limit": 15}})
    if cfg.get("telegram_channels") or re.search(r"\btelegram|channel|t\.me\b", low):
        calls.append({"tool": "search_telegram", "args": {"query": str(query)[:400], "limit": 15}})
    if re.search(r"\b(dark web|deep web|onion|tor|ahmia)\b", low) and cfg.get("tor_mode") != "off":
        calls.append({"tool": "search_onion_index", "args": {"query": str(query)[:300]}})
    url_match = re.search(r"https?://[^\s]+", str(query or ""))
    if url_match:
        calls.append({"tool": "verify_source", "args": {"url": url_match.group(0)[:500]}})
    return calls[:MAX_CALLS]


def plan(query: str, cfg: dict | None = None) -> dict:
    """Build a VALIDATED tool plan. LLM is optional; fallback is deterministic."""
    cfg = cfg or config.load()
    source, rejected = "deterministic", []
    calls = None
    if llm.resolve(cfg)["enabled"]:
        raw = llm.tool_plan(cfg, query, TOOL_NAMES)
        if raw is not None:
            safe = []
            for call in raw[:MAX_CALLS]:
                try:
                    safe.append(validate(call))
                except ToolRejected as exc:
                    rejected.append({"call": call, "reason": str(exc)})
            if safe:
                calls, source = safe, "llm"
                store.add_event("planner", f"LLM planned {len(safe)} tools; "
                                           f"{len(rejected)} rejected")
    if calls is None:
        calls = _deterministic_calls(query, cfg)
        safe = []
        for call in calls:
            try:
                safe.append(validate(call))
            except ToolRejected as exc:
                rejected.append({"call": call, "reason": str(exc)})
        calls = safe
    return {"calls": calls, "source": source, "rejected": rejected,
            "allowed_tools": TOOL_NAMES, "max_calls": MAX_CALLS}


def execute(plan_result: dict, ctx: dict) -> dict:
    """Dispatch every validated call and merge plain-text tool output."""
    outputs, items, diagnostics = [], [], []
    save_title = ""
    for call in plan_result.get("calls", []):
        out = dispatch(call, ctx)
        outputs.append(out)
        items.extend(out.get("items") or [])
        diagnostics.extend(out.get("diagnostics") or [])
        if out.get("save_report"):
            save_title = out["save_report"]
    tool_text = scrub("\n\n".join(f"[{o['tool']}]\n{o.get('text','')}" for o in outputs),
                      MAX_TOOL_TEXT * 2)
    return {"outputs": outputs, "items": items, "diagnostics": diagnostics,
            "tool_text": tool_text, "save_title": save_title}
