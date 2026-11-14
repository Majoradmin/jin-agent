"""Adapter layer - the ONLY way JIN Agent reaches the network.

Contract (opencode plan P15):
    search(query, days, limit) -> list[raw item dict]
    health() -> status dict
    provenance(item) -> dict
    rate_limit / cost are declared per adapter

Every URL passes policy.check_url() before and after redirects. Responses are
size-capped, time-limited and parsed with the stdlib. A failing adapter never
crashes a run: it returns a structured diagnostic.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import config, policy, util

UA = "JIN-Agent/2.0 (local research; stdlib urllib)"


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        ok, reason = policy.check_url(newurl, policy.adapter_hosts())
        if not ok:
            raise urllib.error.HTTPError(newurl, code, "Blocked redirect: " + reason,
                                         headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_SafeRedirect())


def fetch(url: str, cfg: dict | None = None, extra_hosts=()) -> str:
    """GET a validated public URL. No POST, no shell, no file access."""
    cfg = cfg or config.load()
    ok, reason = policy.check_url(url, policy.adapter_hosts() | set(extra_hosts or ()))
    if not ok:
        raise ValueError(reason)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    cap = util.clamp(cfg.get("max_fetch_bytes"), 1024, 8_000_000, 2_000_000)
    timeout = util.clamp(cfg.get("fetch_timeout"), 1, 60, 10)
    with _OPENER.open(req, timeout=timeout) as resp:
        raw = resp.read(cap + 1)
    if len(raw) > cap:
        raw = raw[:cap]
    return raw.decode("utf-8", "replace")


# --------------------------------------------------------------------------
# Parsers (all stdlib, all defensive)
# --------------------------------------------------------------------------

def _xml_precheck(text: str) -> bool:
    head = text[:2048].lower()
    return "<!doctype" not in head and "<!entity" not in head


def _local_tag(tag) -> str:
    return str(tag).split("}")[-1].lower()


def _child(node, name):
    for child in list(node):
        if _local_tag(child.tag) == name:
            return child
    return None


def _node_text(node) -> str:
    if node is None:
        return ""
    return " ".join("".join(node.itertext()).split())


def parse_feed(text: str, source: str, source_key: str, category: str,
               trust: float, tier: str = "T0") -> list[dict]:
    if not text or not _xml_precheck(text):
        return []
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []
    out = []
    for node in root.iter():
        tag = _local_tag(node.tag)
        if tag not in ("item", "entry"):
            continue
        title = _node_text(_child(node, "title"))
        link = ""
        for child in list(node):
            if _local_tag(child.tag) == "link":
                href = child.get("href")
                if href:
                    link = href
                    break
                if not link:
                    link = _node_text(child)
        published = (_node_text(_child(node, "pubDate")) or
                     _node_text(_child(node, "published")) or
                     _node_text(_child(node, "updated")) or
                     _node_text(_child(node, "dc:date")))
        excerpt = (_node_text(_child(node, "description")) or
                   _node_text(_child(node, "summary")) or
                   _node_text(_child(node, "content")))
        if not title or not link:
            continue
        out.append({
            "title": util.truncate(title, 240), "url": link.strip(),
            "source": source, "source_key": source_key,
            "published": util.parse_date(published),
            "excerpt": util.clean_text(excerpt, 600),
            "body": util.clean_text(excerpt, 4000),
            "category": category, "trust": trust, "tier": tier,
            "kind": "rss", "link_only": False,
        })
    return out


def parse_hn(text: str) -> list[dict]:
    try:
        data = json.loads(text)
    except ValueError:
        return []
    out = []
    for hit in data.get("hits", [])[:40]:
        title = hit.get("title") or hit.get("story_title")
        url = hit.get("url") or ("https://news.ycombinator.com/item?id=" + str(hit.get("objectID", "")))
        if not title:
            continue
        out.append({
            "title": util.truncate(title, 240), "url": url,
            "source": "Hacker News (Algolia)", "source_key": "hn",
            "published": util.parse_date(hit.get("created_at")),
            "excerpt": util.clean_text(hit.get("story_text") or "", 600),
            "body": util.clean_text(hit.get("story_text") or "", 4000),
            "category": "Tools & Reverse Engineering", "trust": 0.7,
            "tier": "T0", "kind": "search", "link_only": False,
        })
    return out


def parse_github(text: str, repo: str, label: str) -> list[dict]:
    try:
        data = json.loads(text)
    except ValueError:
        return []
    if not isinstance(data, list):
        return []
    out = []
    for rel in data[:10]:
        title = (rel.get("name") or rel.get("tag_name") or "").strip()
        url = rel.get("html_url") or ""
        if not title or not url:
            continue
        out.append({
            "title": util.truncate(f"{label} {title}", 240), "url": url,
            "source": "GitHub Releases", "source_key": "github",
            "published": util.parse_date(rel.get("published_at") or rel.get("created_at")),
            "excerpt": util.clean_text(rel.get("body") or "", 600),
            "body": util.clean_text(rel.get("body") or "", 4000),
            "category": "Tools & Reverse Engineering", "trust": 0.9,
            "tier": "T0", "kind": "release", "link_only": False,
        })
    return out


def parse_gdelt(text: str) -> list[dict]:
    try:
        data = json.loads(text)
    except ValueError:
        return []
    out = []
    for art in (data.get("articles") or [])[:40]:
        title, url = art.get("title"), art.get("url")
        if not title or not url:
            continue
        out.append({
            "title": util.truncate(title, 240), "url": url,
            "source": "GDELT DOC 2.0", "source_key": "gdelt",
            "published": util.parse_date(art.get("seendate")),
            "excerpt": util.clean_text(art.get("domain") or "", 300),
            "body": "", "category": "World", "trust": 0.7,
            "tier": "T1", "kind": "search", "link_only": False,
        })
    return out


def parse_openalex(text: str) -> list[dict]:
    try:
        data = json.loads(text)
    except ValueError:
        return []
    return _papers(data.get("results") or [], "OpenAlex",
                   lambda x: x.get("display_name") or x.get("title"),
                   lambda x: x.get("doi") or x.get("id"),
                   lambda x: x.get("publication_date"))


def parse_crossref(text: str) -> list[dict]:
    try:
        data = json.loads(text)
    except ValueError:
        return []
    items = (data.get("message") or {}).get("items") or []
    return _papers(items, "Crossref",
                   lambda x: (x.get("title") or [""])[0],
                   lambda x: x.get("URL") or ("https://doi.org/" + str(x.get("DOI", ""))),
                   lambda x: "-".join(str(v) for v in (x.get("published") or {}).get("date-parts", [[]])[0][:3]))


def _papers(rows, source, title_fn, url_fn, date_fn) -> list[dict]:
    out = []
    for row in rows[:25]:
        try:
            title, url = title_fn(row), url_fn(row)
        except Exception:
            continue
        if not title or not url:
            continue
        out.append({
            "title": util.truncate(title, 240), "url": url,
            "source": source, "source_key": source.lower(),
            "published": util.parse_date(date_fn(row)),
            "excerpt": util.clean_text(row.get("abstract") or row.get("subtitle") or "", 600),
            "body": "", "category": "Science", "trust": 0.85,
            "tier": "T3", "kind": "paper", "link_only": False,
        })
    return out


def parse_arxiv(text: str) -> list[dict]:
    if not text or not _xml_precheck(text):
        return []
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []
    out = []
    for entry in root.iter():
        if _local_tag(entry.tag) != "entry":
            continue
        title = _node_text(_child(entry, "title"))
        link = ""
        for child in list(entry):
            if _local_tag(child.tag) == "id":
                link = _node_text(child)
                break
        if not title or not link:
            continue
        out.append({
            "title": util.truncate(title, 240), "url": link,
            "source": "arXiv", "source_key": "arxiv",
            "published": util.parse_date(_node_text(_child(entry, "published"))),
            "excerpt": util.clean_text(_node_text(_child(entry, "summary")), 600),
            "body": "", "category": "Science", "trust": 0.9,
            "tier": "T3", "kind": "paper", "link_only": False,
        })
    return out


def parse_telegram(html: str, channel: str) -> list[dict]:
    """Public t.me/s/ preview only. No login, no userbot, no history scrape."""
    if not html:
        return []
    posts = re.findall(r'data-post="([^"]+)"', html)[:30]
    texts = re.findall(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>',
                       html, re.S)[:30]
    out = []
    for i, text in enumerate(texts):
        clean = util.clean_text(text, 600)
        if not clean:
            continue
        post = posts[i] if i < len(posts) else ""
        url = f"https://t.me/s/{post}" if "/" in post else f"https://t.me/s/{channel}"
        out.append({
            "title": util.truncate(clean.split(".")[0], 200), "url": url,
            "source": f"Telegram public @{channel}", "source_key": "telegram-public",
            "published": "", "excerpt": clean, "body": clean,
            "category": "Telecom", "trust": 0.4, "tier": "T2",
            "kind": "telegram", "link_only": False,
        })
    return out


def parse_ahmia(html: str, query: str) -> list[dict]:
    """Legal onion discovery. LINKS ONLY - the .onion URL is never fetched."""
    if not html:
        return []
    links = re.findall(r"https?://[a-z2-7]{16,56}\.onion[^\s\"'<>]*", html, re.I)[:20]
    out = []
    seen = set()
    for link in links:
        base = link.split("?")[0].rstrip("/")
        if base in seen:
            continue
        seen.add(base)
        out.append({
            "title": f"Legal onion index result for: {util.truncate(query, 80)}",
            "url": base, "source": "Ahmia onion index", "source_key": "ahmia",
            "published": "", "excerpt": policy.DARK_WEB_RULE, "body": "",
            "category": "Custom Watchlist", "trust": 0.5, "tier": "T4",
            "kind": "onion-link", "link_only": True,
        })
    return out


# --------------------------------------------------------------------------
# Adapter contract
# --------------------------------------------------------------------------

class Adapter:
    key = ""
    name = ""
    tier = "T0"
    category = "World"
    trust = 0.7
    enabled = True
    frequency = 15
    rate_limit = 0
    cost = 0.0

    def build(self, query: str, days: int, limit: int, cfg: dict) -> str:
        return ""

    def parse(self, text: str, query: str, cfg: dict) -> list[dict]:
        return []

    def search(self, query: str, days: int = 7, limit: int = 25,
               cfg: dict | None = None, offline: bool = False) -> list[dict]:
        cfg = cfg or config.load()
        if offline:
            return _offline_items(self, query, limit)
        url = self.build(query, days, limit, cfg)
        if not url:
            return []
        return self.parse(fetch(url, cfg), query, cfg)

    def health(self) -> dict:
        return {"key": self.key, "name": self.name, "tier": self.tier,
                "category": self.category, "trust": self.trust,
                "enabled": self.enabled, "frequency": self.frequency,
                "rate_limit": self.rate_limit, "cost": self.cost}

    def provenance(self, item: dict) -> dict:
        return {"adapter": self.key, "tier": self.tier, "trust": self.trust,
                "url": item.get("url", ""), "date_checked": util.now_iso()}


class RSSAdapter(Adapter):
    def __init__(self, key, name, url, category, trust, tier="T0"):
        self.key, self.name, self.url = key, name, url
        self.category, self.trust, self.tier = category, trust, tier
        self.frequency = 15

    def build(self, query, days, limit, cfg):
        return self.url

    def parse(self, text, query, cfg):
        return parse_feed(text, self.name, self.key, self.category, self.trust, self.tier)


class GoogleNewsAdapter(Adapter):
    key, name, category, trust, tier, frequency = "gnews", "Google News RSS", "World", 0.8, "T0", 15

    def build(self, query, days, limit, cfg):
        q = urllib.parse.quote(str(query or "technology news")[:300])
        return f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"

    def parse(self, text, query, cfg):
        return parse_feed(text, self.name, self.key, self.category, self.trust, self.tier)


class HackerNewsAdapter(Adapter):
    key, name, category, trust, tier, frequency = "hn", "Hacker News (Algolia)", "Tools & Reverse Engineering", 0.7, "T0", 15

    def build(self, query, days, limit, cfg):
        short = " ".join(util.terms(query)[:5])
        return ("https://hn.algolia.com/api/v1/search_by_date?query=" +
                urllib.parse.quote(short) + f"&tags=story&hitsPerPage={min(50, max(10, limit))}")

    def parse(self, text, query, cfg):
        return parse_hn(text)


class GitHubAdapter(Adapter):
    key, name, category, trust, tier, frequency = "github", "GitHub Releases", "Tools & Reverse Engineering", 0.9, "T0", 60
    REPOS = [("bkerler/mtkclient", "MTK client"), ("bkerler/edl", "Qualcomm EDL client"),
             ("blacktop/ipsw", "Apple IPSW tooling")]

    def build(self, query, days, limit, cfg):
        return f"https://api.github.com/repos/{self.REPOS[0][0]}/releases"

    def search(self, query, days=7, limit=25, cfg=None, offline=False):
        cfg = cfg or config.load()
        if offline:
            return _offline_items(self, query, limit)
        out = []
        for repo, label in self.REPOS:
            try:
                out.extend(self.parse(fetch(self._url(repo), cfg), query, cfg))
            except Exception:
                continue
        return out

    def _url(self, repo):
        return f"https://api.github.com/repos/{repo}/releases"

    def parse(self, text, query, cfg):
        return parse_github(text, "", "Open-source firmware tool")


class GDELTAdapter(Adapter):
    key, name, category, trust, tier, frequency = "gdelt", "GDELT DOC 2.0", "World", 0.7, "T1", 15

    def build(self, query, days, limit, cfg):
        timespan = f"{max(1, min(90, days * 24))}h" if days else "24h"
        return ("https://api.gdeltproject.org/api/v2/doc/doc?query=" +
                urllib.parse.quote(str(query)[:200]) +
                f"&mode=artlist&format=json&maxrecords={min(75, max(10, limit))}&timespan={timespan}")

    def parse(self, text, query, cfg):
        return parse_gdelt(text)


class OpenAlexAdapter(Adapter):
    key, name, category, trust, tier, frequency = "openalex", "OpenAlex", "Science", 0.85, "T3", 360

    def build(self, query, days, limit, cfg):
        return ("https://api.openalex.org/works?search=" +
                urllib.parse.quote(str(query)[:200]) + f"&per-page={min(25, max(5, limit))}")

    def parse(self, text, query, cfg):
        return parse_openalex(text)


class CrossrefAdapter(Adapter):
    key, name, category, trust, tier, frequency = "crossref", "Crossref", "Science", 0.85, "T3", 360

    def build(self, query, days, limit, cfg):
        return ("https://api.crossref.org/works?query=" +
                urllib.parse.quote(str(query)[:200]) + f"&rows={min(25, max(5, limit))}")

    def parse(self, text, query, cfg):
        return parse_crossref(text)


class ArxivAdapter(Adapter):
    key, name, category, trust, tier, frequency = "arxiv", "arXiv", "Science", 0.9, "T3", 360

    def build(self, query, days, limit, cfg):
        return ("https://export.arxiv.org/api/query?search_query=all:" +
                urllib.parse.quote(str(query)[:150]) +
                f"&start=0&max_results={min(25, max(5, limit))}")

    def parse(self, text, query, cfg):
        return parse_arxiv(text)


class TelegramAdapter(Adapter):
    key, name, category, trust, tier, frequency = "telegram-public", "Telegram Public Preview", "Telecom", 0.4, "T2", 30
    enabled = False  # opt-in: only channels explicitly listed in Settings

    def search(self, query, days=7, limit=25, cfg=None, offline=False):
        cfg = cfg or config.load()
        channels = [str(c).strip().lstrip("@") for c in cfg.get("telegram_channels", [])]
        channels = [c for c in channels if re.fullmatch(r"[A-Za-z0-9_]{3,40}", c)]
        if offline:
            return _offline_items(self, query, limit) if channels else []
        out = []
        for channel in channels[:10]:
            try:
                url = f"https://t.me/s/{channel}"
                out.extend(parse_telegram(fetch(url, cfg), channel))
            except Exception:
                continue
        return out[:limit]


class AhmiaAdapter(Adapter):
    key, name, category, trust, tier, frequency = "ahmia", "Ahmia onion index", "Custom Watchlist", 0.5, "T4", 1440
    enabled = False  # links-only, never auto-fetched

    def search(self, query, days=7, limit=25, cfg=None, offline=False):
        cfg = cfg or config.load()
        if str(cfg.get("tor_mode", "links_only")) == "off":
            return []
        if offline:
            return _offline_items(self, query, limit)
        try:
            url = "https://ahmia.fi/search/?q=" + urllib.parse.quote(str(query)[:150])
            return parse_ahmia(fetch(url, cfg), query)[:limit]
        except Exception:
            return []


RSS_FEEDS = [
    ("gsmarena", "GSMArena", "https://www.gsmarena.com/rss-news-reviews.php3", "Mobile & Firmware", 0.7),
    ("xda", "XDA Developers", "https://www.xda-developers.com/feed/", "Tools & Reverse Engineering", 0.6),
    ("androidauthority", "Android Authority", "https://www.androidauthority.com/feed/", "Android", 0.7),
    ("androidpolice", "Android Police", "https://www.androidpolice.com/feed/", "Android", 0.7),
    ("9to5google", "9to5Google", "https://9to5google.com/feed/", "Android", 0.7),
    ("sammobile", "SamMobile", "https://www.sammobile.com/feed/", "Mobile & Firmware", 0.7),
    ("apple-newsroom", "Apple Newsroom", "https://www.apple.com/newsroom/rss-feed.rss", "iOS", 0.9),
]

ADAPTERS: list[Adapter] = [RSSAdapter(*row) for row in RSS_FEEDS] + [
    GoogleNewsAdapter(), HackerNewsAdapter(), GitHubAdapter(), GDELTAdapter(),
    OpenAlexAdapter(), CrossrefAdapter(), ArxivAdapter(),
    TelegramAdapter(), AhmiaAdapter(),
]
BY_KEY = {a.key: a for a in ADAPTERS}


# --------------------------------------------------------------------------
# Deterministic offline corpus for the evaluation harness (no live internet)
# --------------------------------------------------------------------------

FIXTURE = [
    ("MediaTek preloader DA v2 released for Dimensity", ["mediatek", "mtk", "preloader", "scatter", "dimensity"], "Mobile & Firmware"),
    ("MTK scatter config_version mismatch causes BROM errors", ["mtk", "scatter", "brom", "preloader"], "Mobile & Firmware"),
    ("Qualcomm firehose loader UFS LUN coverage updated", ["qualcomm", "qcom", "firehose", "edl", "9008", "sahara"], "Hardware & Chipsets"),
    ("EDL 9008 Sahara handshake fails on new security patch", ["edl", "9008", "sahara", "qfil"], "Hardware & Chipsets"),
    ("Huawei EMUI 16 rollout starts for Mate series", ["huawei", "emui", "harmonyos", "honor", "kirin"], "Mobile & Firmware"),
    ("HarmonyOS build region variants documented", ["harmonyos", "huawei", "region"], "Mobile & Firmware"),
    ("iPhone activation policy server-side explained", ["iphone", "ios", "apple", "activation", "ipsw"], "iOS"),
    ("iOS security release patches WebKit vulnerability", ["ios", "apple", "security", "cve"], "iOS"),
    ("Android Security Bulletin November 2026 published", ["android", "security", "bulletin", "patch", "cve"], "Security"),
    ("CVE-2026-44120 bootloader vulnerability analysis", ["cve", "bootloader", "vulnerability", "security"], "Security"),
    ("Samsung SMR monthly maintenance release notes", ["samsung", "smr", "one ui", "firmware"], "Security"),
    ("SP Flash Tool version 6.2 changelog", ["sp flash", "tool", "loader", "flash"], "Tools & Reverse Engineering"),
    ("QFIL rawprogram XML schema validation guide", ["qfil", "rawprogram", "tool", "xml"], "Tools & Reverse Engineering"),
    ("mtkclient GitHub release adds new chipset support", ["mtkclient", "github", "release", "tool"], "Tools & Reverse Engineering"),
    ("Firmware OTA rollout and binary revision matching", ["firmware", "ota", "rollout", "stock", "rom"], "Mobile & Firmware"),
    ("One UI 8 build number and CSC region check", ["one ui", "build", "csc", "region", "firmware"], "Mobile & Firmware"),
    ("Local LLM quantization Q4 7B on 8 GB VRAM", ["llm", "local", "qwen", "ollama", "model", "ai"], "AI & Local LLM"),
    ("Prompt injection defense for tool-calling agents", ["prompt", "injection", "agent", "tool", "ai"], "AI & Local LLM"),
    ("5G modem firmware and carrier policy update", ["modem", "telecom", "carrier", "5g"], "Telecom"),
    ("Telecom regulator publishes device compliance rules", ["telecom", "policy", "regulator", "compliance"], "Business & Policy"),
    ("Chipset supply and hardware roadmap briefing", ["chipset", "hardware", "silicon", "soc"], "Hardware & Chipsets"),
    ("arXiv preprint on firmware provenance hashing", ["arxiv", "paper", "firmware", "provenance", "science"], "Science"),
    ("Academic study on secure boot attestation", ["study", "paper", "secure boot", "attestation", "science"], "Science"),
    ("Global tech policy and right-to-repair update", ["world", "policy", "repair", "global", "business"], "World"),
    ("GDELT global news index coverage notes", ["gdelt", "news", "world", "global"], "World"),
    ("Custom watchlist keyword alert example", ["watchlist", "custom", "alert"], "Custom Watchlist"),
]


def _offline_items(adapter: Adapter, query: str, limit: int) -> list[dict]:
    words = set(util.terms(query, 20))
    matched = [row for row in FIXTURE if words.intersection(row[1])]
    if not matched:
        matched = FIXTURE[:3]
    out = []
    for title, keys, category in matched[: max(3, min(limit, 12))]:
        url = "https://example.org/" + util.fingerprint(title)[:12]
        out.append({
            "title": title, "url": url, "source": adapter.name,
            "source_key": adapter.key, "published": util.now_iso(),
            "excerpt": "Offline fixture for pipeline evaluation: " + title,
            "body": "Offline fixture corpus. No live network access was used.",
            "category": category, "trust": adapter.trust, "tier": adapter.tier,
            "kind": "fixture", "link_only": adapter.key == "ahmia",
            "offline": True,
        })
    if adapter.key == "ahmia":
        for item in out:
            item["url"] = "http://example" + util.fingerprint(item["title"])[:16] + ".onion"
            item["excerpt"] = policy.DARK_WEB_RULE
    return out


def _safe_search(adapter: Adapter, query, days, limit, cfg, offline):
    started = time.monotonic()
    diag = {"key": adapter.key, "name": adapter.name, "tier": adapter.tier,
            "ok": False, "count": 0, "error": "", "offline": offline,
            "elapsed_ms": 0}
    try:
        items = adapter.search(query, days, limit, cfg, offline)
        diag["count"] = len(items)
        diag["ok"] = True
        if not items:
            diag["error"] = "0 results (valid response, koi match nahi)"
        return items, diag
    except Exception as exc:
        diag["error"] = f"{type(exc).__name__}: {util.truncate(str(exc), 140)}"
        return [], diag
    finally:
        diag["elapsed_ms"] = round((time.monotonic() - started) * 1000)


def run(query: str, keys=None, days: int = 7, limit: int = 25,
        cfg: dict | None = None, offline: bool = False,
        include_opt_in: bool = False) -> tuple[list[dict], list[dict]]:
    """Run selected adapters in parallel. Never raises on network failure."""
    cfg = cfg or config.load()
    if keys:
        wanted = set(keys)
        selected = [a for a in ADAPTERS
                    if a.key in wanted and (a.enabled or include_opt_in or a.key in wanted)]
    else:
        selected = [a for a in ADAPTERS if a.enabled]
        if include_opt_in:
            selected = list(ADAPTERS)
    if not selected:
        return [], []
    items: list[dict] = []
    diagnostics: list[dict] = []
    workers = max(1, min(12, len(selected)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_safe_search, a, query, days, limit, cfg, offline): a
                   for a in selected}
        for future in as_completed(futures):
            try:
                got, diag = future.result()
            except Exception as exc:
                got, diag = [], {"key": futures[future].key, "name": futures[future].name,
                                 "tier": futures[future].tier, "ok": False, "count": 0,
                                 "error": f"{type(exc).__name__}: {exc}", "offline": offline,
                                 "elapsed_ms": 0}
            items.extend(got)
            diagnostics.append(diag)
    diagnostics.sort(key=lambda d: d["key"])
    return items, diagnostics
