"""Real-time mobile-software research agent.

Fetches live RSS / Atom / JSON sources (no API key required), scores and
filters them, and writes a Roman-Urdu "khulasa" for every item.

Optional: if the user configures an OpenAI-compatible endpoint in Settings,
the khulasa is rewritten by that model. Otherwise a deterministic, offline
rule-based Roman Urdu summary is produced.
"""
from __future__ import annotations

import gzip
import html
import json
import os
import re
import ssl
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) MobileLab/1.0 (local research agent)"
TIMEOUT = 10

GITHUB_REPOS = [
    ("bkerler/mtkclient", "MTK client"),
    ("bkerler/edl", "Qualcomm EDL client"),
    ("blacktop/ipsw", "Apple IPSW tooling"),
]

RSS_SOURCES = [
    {"id": "gsmarena", "name": "GSMArena", "url": "https://www.gsmarena.com/rss-news-reviews.php3", "cat": "firmware"},
    {"id": "xda", "name": "XDA Developers", "url": "https://www.xda-developers.com/feed/", "cat": "tools"},
    {"id": "androidauthority", "name": "Android Authority", "url": "https://www.androidauthority.com/feed/", "cat": "firmware"},
    {"id": "androidpolice", "name": "Android Police", "url": "https://www.androidpolice.com/feed/", "cat": "firmware"},
    {"id": "9to5google", "name": "9to5Google", "url": "https://9to5google.com/feed/", "cat": "firmware"},
    {"id": "sammobile", "name": "SamMobile", "url": "https://www.sammobile.com/feed/", "cat": "firmware"},
    {"id": "apple", "name": "Apple Newsroom", "url": "https://www.apple.com/newsroom/rss-feed.rss", "cat": "apple"},
]

QUERY_SOURCES = [
    {"id": "gnews", "name": "Google News (live)", "kind": "gnews"},
    {"id": "hn", "name": "Hacker News (live)", "kind": "hn"},
    {"id": "github", "name": "Open-source tool releases", "kind": "github"},
]

ALL_SOURCES = QUERY_SOURCES + [
    {"id": s["id"], "name": s["name"], "kind": "rss"} for s in RSS_SOURCES
]

PRESETS = [
    {"id": "all", "label": "Sab kuch", "q": "mobile firmware OR smartphone update OR Android security patch"},
    {"id": "huawei", "label": "Huawei / EMUI 16", "q": "Huawei EMUI 16 OR HarmonyOS OR Huawei firmware update"},
    {"id": "mtk", "label": "MTK preloader / DA", "q": "MediaTek preloader OR MTK download agent OR scatter file OR Dimensity"},
    {"id": "qcom", "label": "Qualcomm Firehose / EDL", "q": "Qualcomm firehose OR EDL 9008 OR Sahara OR Snapdragon firmware"},
    {"id": "apple", "label": "iPhone / Activation", "q": "iPhone activation lock OR iOS update OR Apple security"},
    {"id": "security", "label": "Security patches", "q": "Android security bulletin OR bootloader vulnerability OR FRP"},
    {"id": "tools", "label": "Tools & loaders", "q": "SP Flash Tool OR QFIL OR mtkclient OR edl OR servicing tool"},
    {"id": "firmware", "label": "Firmware releases", "q": "firmware rollout OR OTA update OR stock ROM"},
]

CATEGORY_RULES = [
    ("huawei", ["huawei", "emui", "harmonyos", "honor", "kirin", "hisilicon", "pura", "nova", "mate "]),
    ("mtk", ["mediatek", "mtk", "preloader", "scatter", "dimensity", "download agent", "brom", "helio"]),
    ("qcom", ["qualcomm", "snapdragon", "firehose", "edl", "9008", "sahara", "qfil", "qpst", "mbn"]),
    ("apple", ["iphone", "ipad", "ios ", "apple", "activation lock", "icoud", "icloud", "ipsw", "checkm8"]),
    ("security", ["security patch", "vulnerability", "cve-", "exploit", "frp", "bootloader", "exploit", "malware", "bulletin"]),
    ("tools", ["tool", "loader", "firmware flash", "qfil", "sp flash", "odin", "mtkclient", "release v", "github", "update v"]),
    ("firmware", ["firmware", "ota", "rom", "rollout", "update", "build", "android 1", "one ui", "stock"]),
]

CATEGORY_LABELS = {
    "huawei": "Huawei / EMUI", "mtk": "MediaTek / Preloader", "qcom": "Qualcomm / Firehose",
    "apple": "Apple / iOS", "security": "Security / Patch", "tools": "Tools & Loaders",
    "firmware": "Firmware / OTA", "general": "General",
}

ROMAN_URDU_HINT = {
    "huawei": "EMUI / HarmonyOS ka build number aur region variant confirm karain. Account se mutaliq kisi bhi kaam ke liye sirf Huawei ka official raasta aur malik ki tasdeeq lazmi hai.",
    "mtk": "Chipset (MTxxxx), scatter ka config_version aur DA/auth ka version aik doosre se match honay chahiye. Naye security level purane DA ko reject kar dete hain.",
    "qcom": "Firehose loader ka storage type (eMMC ya UFS), LUN coverage aur sector size check karain. Galat loader 9008 port par koi command respond nahi karta.",
    "apple": "Activation aur carrier policy Apple ke server par rehti hai, device mein nahi. Is liye sirf Apple Support / purchase proof hi mustanad raasta hai.",
    "security": "Naya security patch purane loader, DA aur test-point flows ko na-qabil bana sakta hai. Apne firmware packages aur tool versions isi hisaab se update karain.",
    "tools": "Tool ka version, supported-model list aur changelog dekhain. Cracked builds se parhez karain — loader corruption aur brick ka sabse bara sabab yahi hai.",
    "firmware": "Flash karne se pehle exact model, region/Csc aur binary revision match karain. Downgrade aksar bootloop ya 'custom binary blocked' deta hai.",
    "general": "Model, region aur build number note kar lein; phir apne local package catalog mein usi model ka record update karain.",
}

# Small phrase map used to make the one-line Roman Urdu rendering readable.
PHRASES = [
    (r"rolls? out|rolling out|rollout", "rollout shuru"),
    (r"releases?|launches?|launched", "release kiya"),
    (r"announces?|unveils?", "ka elan kiya"),
    (r"updates?|updated", "update"),
    (r"fixes?|patched", "fix kiya"),
    (r"adds?|brings?|introduces?", "shamil kiya"),
    (r"now available|is available", "ab dastiyab hai"),
    (r"security patch", "security patch"),
    (r"new features?", "nayi features"),
]


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def fetch(url: str, timeout: int = TIMEOUT) -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/rss+xml, application/atom+xml, application/xml, application/json, text/xml, */*",
        "Accept-Language": "en-US,en;q=0.9",
    })
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        raw = r.read(4_000_000)
        if r.headers.get("Content-Encoding", "").lower() == "gzip":
            raw = gzip.decompress(raw)
        return raw.decode("utf-8", errors="replace")


def _local(tag: str) -> str:
    return tag.split("}")[-1].split(":")[-1].lower()


def clean_text(s: str) -> str:
    s = re.sub(r"<script.*?</script>|<style.*?</style>", " ", s or "", flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def _iso(raw: str) -> str:
    if not raw:
        return ""
    try:
        d = parsedate_to_datetime(raw)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        pass
    try:
        d = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return raw[:60]


def parse_feed(text: str, source: str, source_cat: str = "") -> list[dict]:
    items: list[dict] = []
    try:
        root = ET.fromstring(text.strip())
    except Exception:
        return items

    is_atom = _local(root.tag) == "feed"
    nodes = []
    if is_atom:
        nodes = [c for c in root if _local(c.tag) == "entry"]
    else:
        for ch in root.iter():
            if _local(ch.tag) == "item":
                nodes.append(ch)

    for node in nodes[:80]:
        rec = {"title": "", "url": "", "published": "", "excerpt": "", "guid": ""}
        for c in node:
            t = _local(c.tag)
            val = (c.text or "").strip()
            if t == "title" and not rec["title"]:
                rec["title"] = clean_text(val)
            elif t == "link":
                href = c.attrib.get("href") or val
                if href and not rec["url"] and (not c.attrib.get("rel") or c.attrib.get("rel") == "alternate"):
                    rec["url"] = href
            elif t in ("pubdate", "published", "updated", "date") and not rec["published"]:
                rec["published"] = _iso(val)
            elif t in ("description", "summary", "content", "encoded") and not rec["excerpt"]:
                rec["excerpt"] = clean_text(" ".join(c.itertext()))[:320]
            elif t in ("guid", "id") and not rec["guid"]:
                rec["guid"] = val
        if rec["title"]:
            rec["guid"] = rec["guid"] or rec["url"] or (source + ":" + rec["title"][:80])
            rec["source"] = source
            rec["source_cat"] = source_cat
            items.append(rec)
    return items


def parse_github(text: str, label: str) -> list[dict]:
    out = []
    try:
        data = json.loads(text)
        for rel in data[:4]:
            title = f"{label}: {rel.get('tag_name') or rel.get('name') or 'new release'}"
            out.append({
                "title": title, "url": rel.get("html_url", ""),
                "published": _iso(rel.get("published_at") or rel.get("created_at") or ""),
                "excerpt": clean_text((rel.get("body") or "")[:300]),
                "guid": str(rel.get("id") or rel.get("html_url")),
                "source": "GitHub Releases", "source_cat": "tools",
            })
    except Exception:
        pass
    return out


def parse_hn(text: str) -> list[dict]:
    out = []
    try:
        for hit in json.loads(text).get("hits", [])[:25]:
            out.append({
                "title": clean_text(hit.get("title") or hit.get("story_title") or ""),
                "url": hit.get("url") or hit.get("story_url") or
                       f"https://news.ycombinator.com/item?id={hit.get('objectID','')}",
                "published": _iso(hit.get("created_at") or ""),
                "excerpt": clean_text((hit.get("story_text") or "")[:300]),
                "guid": "hn:" + str(hit.get("objectID") or hit.get("url") or hit.get("title")),
                "source": "Hacker News", "source_cat": "tools",
            })
    except Exception:
        pass
    return [o for o in out if o["title"]]


# ---------------------------------------------------------------------------
# Classification, scoring, Roman Urdu khulasa
# ---------------------------------------------------------------------------

STOPWORDS = {"or", "and", "the", "a", "an", "of", "in", "for", "to", "on", "with", "is",
             "new", "latest", "about", "from", "at", "by", "news", "update"}


def query_terms(q: str) -> list[str]:
    q = re.sub(r'"([^"]+)"', r" \1 ", q or "")
    parts = re.split(r"\s+OR\s+|\s+or\s+|[,;|]+|\s+", q, flags=re.I)
    out = []
    for p in parts:
        t = p.strip().lower().strip("()\"'")
        if len(t) >= 3 and t not in STOPWORDS and t not in out:
            out.append(t)
    return out[:14]


def category_of(text: str) -> str:
    t = (text or "").lower()
    for cat, words in CATEGORY_RULES:
        if any(w in t for w in words):
            return cat
    return "general"


def _days_since(published: str) -> int | None:
    try:
        d = datetime.strptime(published, "%Y-%m-%d %H:%M UTC").replace(tzinfo=timezone.utc)
        return max(0, (datetime.now(timezone.utc) - d).days)
    except Exception:
        return None


def _has(term: str, text: str) -> bool:
    if len(term) <= 4:
        return re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", text) is not None
    return term in text


def score_item(rec: dict, terms: list[str], want_cat: str = "all") -> tuple[float, list[str]]:
    title = (rec.get("title") or "").lower()
    body = title + " " + (rec.get("excerpt") or "").lower()
    score, matched = 0.0, []
    for t in terms:
        if _has(t, body):
            score += 2.0 if _has(t, title) else 1.0
            matched.append(t)
    cat = category_of(body)
    if want_cat != "all" and cat == want_cat:
        score += 3.0
    if cat != "general":
        score += 0.5
    age = _days_since(rec.get("published", ""))
    if age is not None:
        if age <= 2:
            score += 3.0
        elif age <= 7:
            score += 2.0
        elif age <= 30:
            score += 1.0
    return round(score, 1), matched


def make_khulasa(rec: dict, cat: str, matched: list[str], score: float) -> str:
    src = rec.get("source", "Source")
    when = rec.get("published") or "haal hi mein"
    terms = ", ".join(matched[:5]) if matched else CATEGORY_LABELS.get(cat, "mobile software")
    base = (f"{src} ki ye khabar {when} par aayi hai. Is mein {terms} ka zikr hai. "
            f"Zaroori baat: {ROMAN_URDU_HINT.get(cat, ROMAN_URDU_HINT['general'])}")
    if score >= 6:
        base += " Ye aap ke kaam se kaafi mutaliqa hai — pehle isay parhein."
    return base


def llm_rewrite(text: str, settings: dict) -> str | None:
    """Optional OpenAI-compatible rewrite into natural Roman Urdu."""
    ep = (settings.get("llm_endpoint") or "").strip().rstrip("/")
    key = (settings.get("llm_key") or "").strip()
    model = (settings.get("llm_model") or "").strip()
    if not (ep and key and model):
        return None
    url = ep if ep.endswith("/chat/completions") else ep + "/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Rewrite the given mobile-software news note in natural Roman Urdu (Urdu written in Latin script). Keep technical terms like firmware, firehose, preloader, bootloader, FRP, EMUI in English. Be concise, 2 sentences. Never add facts that are not in the source."},
            {"role": "user", "content": text},
        ],
        "temperature": 0.2, "max_tokens": 180,
    }
    try:
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + key,
                     "User-Agent": UA}, method="POST")
        with urllib.request.urlopen(req, timeout=25) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
        return data["choices"][0]["message"]["content"].strip()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------

def _build_jobs(query: str, selected: list[str]) -> list[dict]:
    jobs = []
    enc = urllib.parse.quote(query)
    for s in QUERY_SOURCES:
        if s["id"] not in selected:
            continue
        if s["kind"] == "gnews":
            jobs.append({**s, "url": f"https://news.google.com/rss/search?q={enc}&hl=en-US&gl=US&ceid=US:en"})
        elif s["kind"] == "hn":
            short = " ".join(query_terms(query)[:4])
            jobs.append({**s, "url": "https://hn.algolia.com/api/v1/search_by_date?query=" +
                         urllib.parse.quote(short) + "&tags=story&hitsPerPage=25"})
        elif s["kind"] == "github":
            for repo, label in GITHUB_REPOS:
                jobs.append({"id": "github:" + repo, "name": "GitHub Releases", "kind": "github",
                             "url": f"https://api.github.com/repos/{repo}/releases",
                             "label": label})
    for s in RSS_SOURCES:
        if s["id"] in selected:
            jobs.append({"id": s["id"], "name": s["name"], "kind": "rss",
                         "url": s["url"], "source_cat": s["cat"]})
    return jobs


def _run_job(job: dict) -> tuple[list[dict], dict]:
    diag = {"source": job["name"], "ok": False, "count": 0, "error": ""}
    try:
        text = fetch(job["url"])
        if job["kind"] == "rss":
            items = parse_feed(text, job["name"], job.get("source_cat", ""))
        elif job["kind"] == "github":
            items = parse_github(text, job.get("label", "Tool"))
        elif job["kind"] == "hn":
            items = parse_hn(text)
        else:
            items = parse_feed(text, job["name"])
        diag.update(ok=True, count=len(items))
        return items, diag
    except Exception as e:
        diag["error"] = f"{type(e).__name__}: {str(e)[:110]}"
        return [], diag


_CACHE: dict[str, tuple[float, dict]] = {}


def research(params: dict, settings: dict | None = None) -> dict:
    settings = settings or {}
    preset = next((p for p in PRESETS if p["id"] == params.get("preset", "all")), PRESETS[0])
    user_q = (params.get("q") or "").strip()
    query = user_q or preset["q"]
    selected = params.get("sources") or [s["id"] for s in ALL_SOURCES]
    want_cat = params.get("category", "all")
    exclude = [w.strip().lower() for w in re.split(r"[,;\s]+", params.get("exclude", "") or "") if len(w.strip()) > 2]
    days = int(params.get("days") or 0)
    min_score = float(params.get("min_score") or 0)
    limit = min(200, max(5, int(params.get("limit") or 70)))
    refresh = bool(params.get("refresh"))
    cache_ttl = max(1, int(settings.get("cache_minutes") or 15)) * 60

    key = json.dumps([query, sorted(selected), want_cat, exclude, days, min_score, limit], sort_keys=True)
    if not refresh and key in _CACHE and time.time() - _CACHE[key][0] < cache_ttl:
        cached = dict(_CACHE[key][1])
        cached["cached"] = True
        return cached

    jobs = _build_jobs(query, selected)
    raw: list[dict] = []
    diagnostics: list[dict] = []
    with ThreadPoolExecutor(max_workers=max(8, min(16, len(jobs)))) as pool:
        futures = [pool.submit(_run_job, j) for j in jobs]
        for fu in as_completed(futures):
            items, diag = fu.result()
            raw.extend(items)
            diagnostics.append(diag)

    # Dedup
    seen: set[str] = set()
    unique = []
    for r in raw:
        norm = re.sub(r"[^a-z0-9]+", " ", (r.get("title") or "").lower()).strip()[:110]
        g = norm or r.get("guid", "")
        if not g or g in seen:
            continue
        seen.add(g)
        unique.append(r)

    terms = query_terms(query)
    results = []
    for r in unique:
        blob = ((r.get("title") or "") + " " + (r.get("excerpt") or "")).lower()
        if any(x in blob for x in exclude):
            continue
        if days:
            age = _days_since(r.get("published", ""))
            if age is None or age > days:
                continue
        cat = category_of(blob)
        if want_cat != "all" and cat != want_cat:
            continue
        sc, matched = score_item(r, terms, want_cat)
        if sc < min_score:
            continue
        results.append({
            "guid": (r.get("source", "src") + ":" + (r.get("guid") or r.get("title", "")[:70]))[:250],
            "title": r.get("title", ""), "url": r.get("url", ""),
            "source": r.get("source", ""), "published": r.get("published", ""),
            "category": cat, "category_label": CATEGORY_LABELS.get(cat, "General"),
            "score": sc, "matched": ", ".join(matched[:8]),
            "excerpt": (r.get("excerpt") or "")[:320],
            "khulasa": make_khulasa(r, cat, matched, sc),
            "age_days": _days_since(r.get("published", "")),
        })

    results.sort(key=lambda x: x["published"] or "", reverse=True)
    results.sort(key=lambda x: x["score"], reverse=True)  # stable: date breaks ties
    results = results[:limit]

    # Optional LLM rewrite for top items only
    if settings.get("llm_endpoint") and settings.get("llm_key") and settings.get("llm_model"):
        for r in results[:12]:
            better = llm_rewrite(r["khulasa"] + " | Source: " + r["title"], settings)
            if better:
                r["khulasa"] = better
                r["llm"] = True

    out = {
        "query": query, "preset": preset["id"], "category": want_cat,
        "items": results, "total": len(unique), "returned": len(results),
        "terms": terms, "diagnostics": sorted(diagnostics, key=lambda d: d["source"]),
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "cached": False,
    }
    _CACHE[key] = (time.time(), out)
    return out
