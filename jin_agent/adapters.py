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

import html
from html.parser import HTMLParser
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

from . import (canonical, config, logging_setup, metrics, policy, ratelimit,
               snapshots, util)

UA = "JIN-Agent/2.6 (local research; stdlib urllib)"


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        ok, reason = policy.check_url(newurl, policy.adapter_hosts())
        if not ok:
            raise urllib.error.HTTPError(newurl, code, "Blocked redirect: " + reason,
                                         headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_SafeRedirect())


def fetch(url: str, cfg: dict | None = None, extra_hosts=(),
          headers: dict | None = None) -> str:
    """GET a validated public URL. No POST, no shell, no file access.

    Per-host minimum interval + exponential backoff are enforced in memory
    (``ratelimit``). Optional headers are used only for free-tier API keys and
    are never logged or written to a snapshot.
    """
    cfg = cfg or config.load()
    ok, reason = policy.check_url(url, policy.adapter_hosts() | set(extra_hosts or ()))
    if not ok:
        raise ValueError(reason)
    host = ratelimit.host_of(url)
    ratelimit.wait(host, cfg)
    request_headers = {"User-Agent": UA, "Accept": "*/*"}
    for name, value in (headers or {}).items():
        clean_name = str(name or "").strip()
        clean_value = str(value or "").replace("\r", "").replace("\n", "")
        if clean_name and clean_value and len(clean_value) <= 2000:
            request_headers[clean_name] = clean_value
    req = urllib.request.Request(url, headers=request_headers)
    cap = util.clamp(cfg.get("max_fetch_bytes"), 1024, 8_000_000, 2_000_000)
    timeout = util.clamp(cfg.get("fetch_timeout"), 1, 60, 10)
    try:
        with _OPENER.open(req, timeout=timeout) as resp:
            raw = resp.read(cap + 1)
    except Exception:
        ratelimit.note_failure(host, cfg)
        raise
    ratelimit.note_success(host)
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


def parse_pubmed(esearch_json: str, esummary_json: str) -> list[dict]:
    """Deep-web DB: PubMed IDs + summaries -> normal items (no key)."""
    try:
        ids = (json.loads(esearch_json or "{}").get("esearchresult") or {}).get("idlist") or []
    except Exception:
        return []
    try:
        result = json.loads(esummary_json or "{}").get("result") or {}
    except Exception:
        result = {}
    out = []
    for pid in ids[:20]:
        pid = str(pid)
        row = result.get(pid) or {}
        title = util.clean_text(row.get("title") or "", 300)
        if not title:
            continue
        published = str(row.get("pubdate") or row.get("epubdate") or "")[:10]
        journal = str(row.get("fulljournalname") or row.get("source") or "")
        out.append({
            "title": title,
            "url": "https://pubmed.ncbi.nlm.nih.gov/" + pid + "/",
            "source": "PubMed (NLM)", "source_key": "pubmed",
            "published": published,
            "excerpt": util.clean_text(journal, 200),
            "body": "", "category": "Science", "trust": 0.9,
            "tier": "T1", "kind": "paper", "link_only": False,
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
# P27 retrieval breadth parsers (stdlib, defensive, offline-testable)
# --------------------------------------------------------------------------

def _epoch_iso(value) -> str:
    try:
        return datetime.fromtimestamp(float(value), timezone.utc).replace(
            microsecond=0).isoformat().replace("+00:00", "Z")
    except (TypeError, ValueError, OSError):
        return util.parse_date(value)


def _compact_date(value) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    for width, fmt in ((14, "%Y%m%d%H%M%S"), (8, "%Y%m%d")):
        if len(digits) >= width:
            try:
                parsed = datetime.strptime(digits[:width], fmt).replace(tzinfo=timezone.utc)
                return parsed.isoformat().replace("+00:00", "Z")
            except ValueError:
                continue
    return util.parse_date(value)


def parse_reddit(text: str) -> list[dict]:
    """Public subreddit search JSON. Read-only, no login, no private data."""
    try:
        data = json.loads(text)
    except ValueError:
        return []
    children = ((data.get("data") or {}).get("children") or [])[:40]
    out = []
    for child in children:
        row = child.get("data") or {}
        title = row.get("title")
        permalink = row.get("permalink")
        if not title or not permalink:
            continue
        link = urllib.parse.urljoin("https://www.reddit.com", str(permalink))
        body = util.clean_text(row.get("selftext") or "", 4000)
        out.append({
            "title": util.truncate(title, 240), "url": link,
            "source": "Reddit (public JSON)", "source_key": "reddit",
            "published": _epoch_iso(row.get("created_utc")),
            "excerpt": util.clean_text(body, 600), "body": body,
            "category": "Android", "trust": 0.45, "tier": "T1",
            "kind": "social", "link_only": False,
        })
    return out


def parse_wikipedia(text: str) -> list[dict]:
    try:
        data = json.loads(text)
    except ValueError:
        return []
    rows = ((data.get("query") or {}).get("search") or [])[:25]
    out = []
    for row in rows:
        title = str(row.get("title") or "").strip()
        if not title:
            continue
        page_id = row.get("pageid")
        link = ("https://en.wikipedia.org/?curid=" + str(page_id) if page_id
                else "https://en.wikipedia.org/wiki/" + urllib.parse.quote(
                    title.replace(" ", "_")))
        snippet = util.clean_text(html.unescape(str(row.get("snippet") or "")), 600)
        out.append({
            "title": util.truncate(title, 240), "url": link,
            "source": "Wikipedia Search", "source_key": "wikipedia",
            "published": util.parse_date(row.get("timestamp")),
            "excerpt": snippet, "body": "", "category": "World",
            "trust": 0.8, "tier": "T3", "kind": "reference", "link_only": False,
        })
    return out


def parse_wikidata(text: str) -> list[dict]:
    try:
        data = json.loads(text)
    except ValueError:
        return []
    out = []
    for row in (data.get("search") or [])[:25]:
        label = str(row.get("label") or row.get("id") or "").strip()
        entity_id = str(row.get("id") or "").strip()
        if not label:
            continue
        link = (str(row.get("concepturi") or "").strip()
                or "https://www.wikidata.org/wiki/" + entity_id)
        description = util.clean_text(html.unescape(str(row.get("description") or "")), 600)
        out.append({
            "title": util.truncate(label + (f" ({entity_id})" if entity_id else ""), 240),
            "url": link, "source": "Wikidata Search", "source_key": "wikidata",
            "published": "", "excerpt": description, "body": "",
            "category": "World", "trust": 0.75, "tier": "T3",
            "kind": "reference", "link_only": False,
        })
    return out


def parse_wayback(text: str, query: str) -> list[dict]:
    """Wayback availability JSON or CDX JSON. LINKS ONLY - never re-fetched."""
    try:
        data = json.loads(text)
    except ValueError:
        return []
    rows = []
    if isinstance(data, dict):
        closest = ((data.get("archived_snapshots") or {}).get("closest") or {})
        if closest.get("url"):
            rows.append({"url": closest.get("url"),
                         "timestamp": closest.get("timestamp"),
                         "original": closest.get("original") or query})
    elif isinstance(data, list):
        for row in data[1:21]:
            if isinstance(row, list) and len(row) >= 3:
                rows.append({"url": row[2], "timestamp": row[1],
                             "original": row[2]})
    out = []
    for row in rows:
        link = str(row.get("url") or "").strip()
        if not link:
            continue
        out.append({
            "title": util.truncate("Wayback snapshot of " +
                                   str(row.get("original") or query), 240),
            "url": link, "source": "Wayback Machine", "source_key": "wayback",
            "published": _compact_date(row.get("timestamp")),
            "excerpt": "Archived copy (links only; the snapshot was not re-fetched).",
            "body": "", "category": "World", "trust": 0.7, "tier": "T1",
            "kind": "archive", "link_only": True,
        })
    return out


def parse_github_search(text: str) -> list[dict]:
    try:
        data = json.loads(text)
    except ValueError:
        return []
    if not isinstance(data, dict):
        return []
    out = []
    for row in (data.get("items") or [])[:30]:
        full_name = str(row.get("full_name") or "").strip()
        link = str(row.get("html_url") or "").strip()
        if not full_name or not link:
            continue
        description = util.clean_text(row.get("description") or "", 600)
        stars = row.get("stargazers_count")
        excerpt = description + (f" | stars: {stars}" if stars is not None else "")
        out.append({
            "title": util.truncate(full_name + (f" - {description}" if description else ""), 240),
            "url": link, "source": "GitHub Search", "source_key": "github-search",
            "published": util.parse_date(row.get("updated_at")),
            "excerpt": util.clean_text(excerpt, 600), "body": "",
            "category": "Tools & Reverse Engineering", "trust": 0.8, "tier": "T0",
            "kind": "code", "link_only": False,
        })
    return out


def parse_nvd(text: str) -> list[dict]:
    try:
        data = json.loads(text)
    except ValueError:
        return []
    out = []
    for row in (data.get("vulnerabilities") or [])[:40]:
        cve = row.get("cve") or {}
        cve_id = str(cve.get("id") or "").strip()
        if not cve_id:
            continue
        description = ""
        for desc in cve.get("descriptions") or []:
            if str(desc.get("lang") or "").lower() == "en":
                description = str(desc.get("value") or "")
                break
        description = util.clean_text(description, 1200)
        out.append({
            "title": util.truncate(cve_id + (": " + description if description else ""), 240),
            "url": "https://nvd.nist.gov/vuln/detail/" + urllib.parse.quote(cve_id),
            "source": "NVD CVE API", "source_key": "nvd",
            "published": util.parse_date(cve.get("published")),
            "excerpt": util.clean_text(description, 600), "body": "",
            "category": "Security", "trust": 0.95, "tier": "T0",
            "kind": "cve", "link_only": False,
        })
    return out


def parse_robots(text: str) -> list[str]:
    """Sitemap: lines from robots.txt (deduped, order preserved)."""
    out = []
    for line in str(text or "").splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("sitemap:"):
            value = stripped.split(":", 1)[1].strip()
            if value and value not in out:
                out.append(value)
    return out[:10]


def parse_sitemap(text: str) -> dict:
    """Parse urlset / sitemapindex XML into URLs and child sitemaps (bounded)."""
    result = {"urls": [], "sitemaps": []}
    if not text or not _xml_precheck(text):
        return result
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return result
    for node in root.iter():
        tag = _local_tag(node.tag)
        if tag == "url":
            loc = _node_text(_child(node, "loc"))
            if loc:
                result["urls"].append({
                    "loc": loc,
                    "lastmod": _node_text(_child(node, "lastmod")),
                })
        elif tag == "sitemap":
            loc = _node_text(_child(node, "loc"))
            if loc:
                result["sitemaps"].append(loc)
        if len(result["urls"]) >= 2000:
            break
    return result


def sitemap_items(rows: list[dict], query: str) -> list[dict]:
    """Turn sitemap URL rows into records, preferring query-matching paths."""
    terms = set(util.terms(query, 12))
    matched = [row for row in rows
               if terms and terms.intersection(
                   set(util.terms(row.get("loc", ""), 20)))]
    picked = matched or rows
    out = []
    seen = set()
    for row in picked:
        loc = str(row.get("loc") or "").strip()
        if not loc or loc in seen:
            continue
        seen.add(loc)
        path = urllib.parse.urlsplit(loc).path.strip("/")
        name = urllib.parse.unquote(path.split("/")[-1]) if path else ""
        title = re.sub(r"[-_]+", " ", name).strip().title()
        out.append({
            "title": util.truncate(title or loc, 240), "url": loc,
            "source": "Sitemap discovery", "source_key": "sitemap",
            "published": util.parse_date(row.get("lastmod")),
            "excerpt": "Discovered via robots.txt / sitemap.xml (bounded depth).",
            "body": "", "category": "World", "trust": 0.8, "tier": "T0",
            "kind": "sitemap", "link_only": False,
        })
    return out


def parse_brave(text: str) -> list[dict]:
    try:
        data = json.loads(text)
    except ValueError:
        return []
    rows = ((data.get("web") or {}).get("results") or [])[:30]
    return _web_results(rows, "Brave Search API", "brave-search", "title", "url",
                        "description", "age")


def parse_bing(text: str) -> list[dict]:
    try:
        data = json.loads(text)
    except ValueError:
        return []
    rows = ((data.get("webPages") or {}).get("value") or [])[:30]
    return _web_results(rows, "Bing Web Search API", "bing-search", "name", "url",
                        "snippet", "dateLastCrawled")


def _web_results(rows, source, source_key, title_key, url_key,
                 excerpt_key, date_key) -> list[dict]:
    out = []
    for row in rows:
        title = str(row.get(title_key) or "").strip()
        link = str(row.get(url_key) or "").strip()
        if not title or not link:
            continue
        out.append({
            "title": util.truncate(title, 240), "url": link,
            "source": source, "source_key": source_key,
            "published": util.parse_date(row.get(date_key)),
            "excerpt": util.clean_text(row.get(excerpt_key) or "", 600),
            "body": "", "category": "World", "trust": 0.75, "tier": "T1",
            "kind": "web-search", "link_only": False,
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
    requires_key = False
    last_fetch = None

    def build(self, query: str, days: int, limit: int, cfg: dict) -> str:
        return ""

    def parse(self, text: str, query: str, cfg: dict) -> list[dict]:
        return []

    def search(self, query: str, days: int = 7, limit: int = 25,
               cfg: dict | None = None, offline: bool = False) -> list[dict]:
        cfg = cfg or config.load()
        self.last_fetch = None
        if offline:
            return _offline_items(self, query, limit)
        url = self.build(query, days, limit, cfg)
        if not url:
            return []
        text = fetch(url, cfg)
        self.last_fetch = {"url": url, "text": text, "ts": util.now_iso()}
        return self.parse(text, query, cfg)

    def health(self) -> dict:
        return {"key": self.key, "name": self.name, "tier": self.tier,
                "category": self.category, "trust": self.trust,
                "enabled": self.enabled, "frequency": self.frequency,
                "rate_limit": self.rate_limit, "cost": self.cost,
                "requires_key": self.requires_key}

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
                text = fetch(self._url(repo), cfg)
                self.last_fetch = {"url": self._url(repo), "text": text,
                                   "ts": util.now_iso()}
                out.extend(self.parse(text, query, cfg))
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


class RedditAdapter(Adapter):
    key, name, category, trust, tier, frequency = "reddit", "Reddit (public JSON)", "Android", 0.45, "T1", 30

    def build(self, query, days, limit, cfg):
        subs = [re.sub(r"[^A-Za-z0-9_]", "", str(s)) for s in
                (cfg.get("reddit_subreddits") or ["android"])]
        subs = [s for s in subs if s][:3] or ["android"]
        return ("https://www.reddit.com/r/" + "+".join(subs) + "/search.json?q=" +
                urllib.parse.quote(" ".join(util.terms(query, 6))[:150]) +
                f"&restrict_sr=1&sort=new&t=week&limit={min(50, max(5, limit))}")

    def parse(self, text, query, cfg):
        return parse_reddit(text)


class WikipediaAdapter(Adapter):
    key, name, category, trust, tier, frequency = "wikipedia", "Wikipedia Search", "World", 0.8, "T3", 120

    def build(self, query, days, limit, cfg):
        return ("https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch=" +
                urllib.parse.quote(str(query)[:200]) +
                f"&srlimit={min(25, max(3, limit))}&format=json&utf8=1")

    def parse(self, text, query, cfg):
        return parse_wikipedia(text)


class WikidataAdapter(Adapter):
    key, name, category, trust, tier, frequency = "wikidata", "Wikidata Search", "World", 0.75, "T3", 120

    def build(self, query, days, limit, cfg):
        return ("https://www.wikidata.org/w/api.php?action=wbsearchentities&search=" +
                urllib.parse.quote(str(query)[:120]) +
                f"&language=en&format=json&limit={min(25, max(3, limit))}")

    def parse(self, text, query, cfg):
        return parse_wikidata(text)


class GoogleNewsTopicAdapter(Adapter):
    key, name, category, trust, tier, frequency = "gnews-topic", "Google News RSS (topic)", "World", 0.8, "T0", 15
    TOPIC_RULES = (
        ("science", ("science", "paper", "research", "study", "arxiv")),
        ("business", ("business", "market", "policy", "regulator", "economy")),
        ("health", ("health", "medical", "hospital")),
        ("technology", ("android", "ios", "firmware", "security", "chipset",
                        "ai", "llm", "tool", "telecom")),
    )

    def build(self, query, days, limit, cfg):
        low = str(query or "").lower()
        topic = "WORLD"
        for name, keywords in self.TOPIC_RULES:
            if any(word in low for word in keywords):
                topic = name.upper()
                break
        return (f"https://news.google.com/rss/headlines/section/topic/{topic}"
                "?hl=en-US&gl=US&ceid=US:en")

    def parse(self, text, query, cfg):
        return parse_feed(text, self.name, self.key, self.category,
                          self.trust, self.tier)


class WaybackAdapter(Adapter):
    key, name, category, trust, tier, frequency = "wayback", "Wayback Machine", "World", 0.7, "T1", 120

    def _target(self, query):
        match = re.search(r"https?://[^\s\"'<>]+", str(query or ""))
        return match.group(0)[:1000] if match else ""

    def build(self, query, days, limit, cfg):
        target = self._target(query)
        if not target:
            return ""
        return ("https://archive.org/wayback/available?url=" +
                urllib.parse.quote(target, safe=""))

    def search(self, query, days=7, limit=25, cfg=None, offline=False):
        cfg = cfg or config.load()
        self.last_fetch = None
        if offline:
            return _offline_items(self, query, limit)
        target = self._target(query)
        if not target:
            return []
        items = []
        try:
            url = self.build(query, days, limit, cfg)
            text = fetch(url, cfg)
            self.last_fetch = {"url": url, "text": text, "ts": util.now_iso()}
            items = parse_wayback(text, target)
            if not items:
                cdx = ("https://web.archive.org/cdx/search/cdx?url=" +
                       urllib.parse.quote(target, safe="") +
                       "&output=json&limit=10&filter=statuscode:200")
                text = fetch(cdx, cfg)
                self.last_fetch = {"url": cdx, "text": text, "ts": util.now_iso()}
                items = parse_wayback(text, target)
        except Exception:
            return []
        return items[:limit]

    def parse(self, text, query, cfg):
        return parse_wayback(text, query)


class GitHubSearchAdapter(Adapter):
    key, name, category, trust, tier, frequency = "github-search", "GitHub Search", "Tools & Reverse Engineering", 0.8, "T0", 60
    _blocked_until = 0.0

    def build(self, query, days, limit, cfg):
        return ("https://api.github.com/search/repositories?q=" +
                urllib.parse.quote(" ".join(util.terms(query, 6))[:120] +
                                   " in:name,description,readme") +
                f"&sort=updated&order=desc&per_page={min(30, max(5, limit))}")

    def search(self, query, days=7, limit=25, cfg=None, offline=False):
        cfg = cfg or config.load()
        self.last_fetch = None
        if offline:
            return _offline_items(self, query, limit)
        if time.monotonic() < float(self._blocked_until or 0):
            return []
        headers = {"Accept": "application/vnd.github+json"}
        token = str(cfg.get("github_token") or "").strip()
        if token:
            headers["Authorization"] = "Bearer " + token
        url = self.build(query, days, limit, cfg)
        try:
            text = fetch(url, cfg, headers=headers)
        except urllib.error.HTTPError:
            self._blocked_until = time.monotonic() + 300
            raise
        self.last_fetch = {"url": url, "text": text, "ts": util.now_iso()}
        if "rate limit" in str(text).lower():
            self._blocked_until = time.monotonic() + 300
            return []
        return parse_github_search(text)

    def parse(self, text, query, cfg):
        return parse_github_search(text)


class NVDAdapter(Adapter):
    key, name, category, trust, tier, frequency = "nvd", "NVD CVE API", "Security", 0.95, "T0", 30

    def build(self, query, days, limit, cfg):
        return ("https://services.nvd.nist.gov/rest/json/cves/2.0?keywordSearch=" +
                urllib.parse.quote(" ".join(util.terms(query, 6))[:150]) +
                f"&resultsPerPage={min(40, max(5, limit))}")

    def parse(self, text, query, cfg):
        return parse_nvd(text)


class SitemapAdapter(Adapter):
    key, name, category, trust, tier, frequency = "sitemap", "Sitemap discovery", "World", 0.8, "T0", 360

    def _seed(self, query, cfg):
        match = re.search(r"https?://[^\s\"'<>]+", str(query or ""))
        if match:
            parts = urllib.parse.urlsplit(match.group(0))
            if parts.hostname:
                candidate = f"{parts.scheme or 'https'}://{parts.hostname}/sitemap.xml"
                if policy.check_url(candidate)[0]:
                    return candidate
        seed = str(cfg.get("sitemap_seed") or "https://source.android.com/sitemap.xml")
        return seed if policy.check_url(seed)[0] else ""

    def search(self, query, days=7, limit=25, cfg=None, offline=False):
        cfg = cfg or config.load()
        self.last_fetch = None
        if offline:
            return _offline_items(self, query, limit)
        seed = self._seed(query, cfg)
        if not seed:
            return []
        max_depth = util.clamp(cfg.get("sitemap_max_depth"), 1, 3, 2)
        max_urls = util.clamp(cfg.get("sitemap_max_urls"), 5, 200, 40)
        parts = urllib.parse.urlsplit(seed)
        base = f"{parts.scheme}://{parts.netloc}"
        queue = [seed]
        try:
            robots = fetch(base + "/robots.txt", cfg)
            self.last_fetch = {"url": base + "/robots.txt", "text": robots,
                               "ts": util.now_iso()}
            queue = parse_robots(robots) + queue
        except Exception:
            pass
        seen, found, fetched = set(), [], 0
        for _depth in range(max_depth):
            if not queue or fetched >= 5:
                break
            batch, queue = queue[:5], queue[5:]
            for url in batch:
                if url in seen or fetched >= 5:
                    continue
                seen.add(url)
                if not policy.check_url(url)[0]:
                    continue
                try:
                    text = fetch(url, cfg)
                except Exception:
                    continue
                self.last_fetch = {"url": url, "text": text, "ts": util.now_iso()}
                fetched += 1
                parsed = parse_sitemap(text)
                found.extend(parsed["urls"])
                for child in parsed["sitemaps"]:
                    if child not in seen and policy.check_url(child)[0]:
                        queue.append(child)
                if len(found) >= max_urls * 2:
                    break
        return sitemap_items(found[:max_urls], query)[:limit]

    def parse(self, text, query, cfg):
        return sitemap_items(parse_sitemap(text)["urls"], query)


class _KeyedAdapter(Adapter):
    """Optional paid/free-tier search - silently disabled when no key is set."""

    enabled = False
    requires_key = True
    key_field = ""
    header_name = ""

    def api_key(self, cfg: dict) -> str:
        return str((cfg or {}).get(self.key_field) or "").strip()

    def search(self, query, days=7, limit=25, cfg=None, offline=False):
        cfg = cfg or config.load()
        self.last_fetch = None
        key = self.api_key(cfg)
        if not key:
            return []
        if offline:
            return _offline_items(self, query, limit)
        url = self.build(query, days, limit, cfg)
        if not url:
            return []
        text = fetch(url, cfg, headers={self.header_name: key})
        self.last_fetch = {"url": url, "text": text, "ts": util.now_iso()}
        return self.parse(text, query, cfg)


class BraveSearchAdapter(_KeyedAdapter):
    key, name, category, trust, tier, frequency = "brave-search", "Brave Search API", "World", 0.75, "T1", 60
    key_field, header_name = "brave_key", "X-Subscription-Token"

    def build(self, query, days, limit, cfg):
        return ("https://api.search.brave.com/res/v1/web/search?q=" +
                urllib.parse.quote(str(query)[:300]) +
                f"&count={min(30, max(5, limit))}&safesearch=moderate")

    def parse(self, text, query, cfg):
        return parse_brave(text)


class BingSearchAdapter(_KeyedAdapter):
    key, name, category, trust, tier, frequency = "bing-search", "Bing Web Search API", "World", 0.75, "T1", 60
    key_field, header_name = "bing_key", "Ocp-Apim-Subscription-Key"

    def build(self, query, days, limit, cfg):
        return ("https://api.bing.microsoft.com/v7.0/search?q=" +
                urllib.parse.quote(str(query)[:300]) +
                f"&count={min(30, max(5, limit))}&mkt=en-US")

    def parse(self, text, query, cfg):
        return parse_bing(text)


class TelegramAdapter(Adapter):
    key, name, category, trust, tier, frequency = "telegram-public", "Telegram Public Preview", "Telecom", 0.4, "T2", 30
    enabled = False  # opt-in: only channels explicitly listed in Settings

    def search(self, query, days=7, limit=25, cfg=None, offline=False):
        cfg = cfg or config.load()
        # P23: manual config list + auto-discovered active channels (lazy import
        # to avoid channels <-> adapters import cycle).
        from . import channels as ch
        channels = ch.adapter_channels(cfg)
        channels = [c for c in channels if re.fullmatch(r"[A-Za-z0-9_]{3,40}", c)]
        self.last_fetch = None
        if offline:
            return _offline_items(self, query, limit) if channels else []
        out = []
        for channel in channels[:10]:
            try:
                url = f"https://t.me/s/{channel}"
                text = fetch(url, cfg)
                self.last_fetch = {"url": url, "text": text, "ts": util.now_iso()}
                out.extend(parse_telegram(text, channel))
            except Exception:
                continue
        return out[:limit]


class AhmiaAdapter(Adapter):
    key, name, category, trust, tier, frequency = "ahmia", "Ahmia onion index", "Custom Watchlist", 0.5, "T4", 1440
    enabled = True  # link-only: koi onion fetch NAHI, sirf prefilled search link

    def search(self, query, days=7, limit=25, cfg=None, offline=False):
        cfg = cfg or config.load()
        self.last_fetch = None
        if str(cfg.get("tor_mode", "links_only")) == "off":
            return []
        if not policy.wants_onion(query):
            return []  # sirf dark/deep queries par, warna report me noise
        q = urllib.parse.quote(str(query)[:150])
        return [{
            "title": "Ahmia — onion search (Tor browser me kholein)",
            "url": "https://ahmia.fi/search/?q=" + q,
            "source": "Ahmia onion index", "source_key": "ahmia",
            "published": "", "excerpt": policy.DARK_WEB_RULE + " Onion address: "
            "juhanurmihxlp77nkq76byazcldy2hlmovfu2epvl5ankdibsot4csyd.onion",
            "body": "", "category": "Custom Watchlist", "trust": 0.5,
            "tier": "T4", "kind": "onion-links", "link_only": True,
        }]


class PubMedAdapter(Adapter):
    key, name, category, trust, tier, frequency = "pubmed", "PubMed (NLM)", "Science", 0.9, "T1", 60

    def search(self, query, days=7, limit=25, cfg=None, offline=False):
        self.last_fetch = None
        if offline:
            return _offline_items(self, query, limit)
        term = urllib.parse.quote(str(query)[:200])
        n = min(10, max(3, limit))
        base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
        ids_text = fetch(base + "esearch.fcgi?db=pubmed&term=" + term +
                         f"&retmode=json&retmax={n}&sort=relevance", cfg)
        ids = (json.loads(ids_text or "{}").get("esearchresult") or {}).get("idlist") or []
        if not ids:
            return []
        summary = fetch(base + "esummary.fcgi?db=pubmed&id=" + ",".join(ids) +
                        "&retmode=json", cfg)
        self.last_fetch = {"url": base + "esearch.fcgi?term=" + term,
                           "text": summary, "ts": util.now_iso()}
        return parse_pubmed(ids_text, summary)[:limit]


# --------------------------------------------------------------------------
# P40: key-free engine list (data-driven, stdlib-only parsers)
# --------------------------------------------------------------------------

class _LinkCollector(HTMLParser):
    """<a href> + anchor text jama karo (HTML search results nikalne ke liye)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a" and self._href is None:
            self._href = dict(attrs).get("href")
            self._buf = []

    def handle_data(self, data):
        if self._href is not None:
            self._buf.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            text = " ".join("".join(self._buf).split())
            self.links.append((self._href, text))
            self._href = None
            self._buf = []


def parse_html_links(text, source, source_key, query, cfg, exclude_hosts=(),
                     min_text=14, limit=25, category="World", trust=0.6,
                     tier="T1") -> list[dict]:
    """HTML search page se result links — apni site/nav links exclude."""
    parser = _LinkCollector()
    try:
        parser.feed(str(text or ""))
    except Exception:
        pass
    ex = [str(h).lower().lstrip(".") for h in (exclude_hosts or ())]
    out, seen = [], set()
    for href, raw in parser.links:
        href = str(href or "").strip()
        if not href.startswith(("http://", "https://")):
            continue
        host = (urllib.parse.urlsplit(href).hostname or "").lower().lstrip(".")
        if not host:
            continue
        if any(host == e or host.endswith("." + e) for e in ex):
            continue
        title = util.clean_text(raw, 240)
        if len(title) < int(min_text):
            continue
        if title.lower().startswith(("http://", "https://", "www.")):
            continue
        if href in seen:
            continue
        seen.add(href)
        out.append({
            "title": title, "url": href, "source": source,
            "source_key": source_key, "published": "", "excerpt": "",
            "body": "", "category": category, "trust": trust, "tier": tier,
            "kind": "web-search", "link_only": False,
        })
        if len(out) >= int(limit):
            break
    return out


def parse_json_rows(text, source, source_key, query, cfg, rows_path=(),
                    title_key="title", url_key="url", excerpt_key="",
                    date_key="", limit=25, category="World", trust=0.7,
                    tier="T1") -> list[dict]:
    """JSON search API — rows_path ke andar list, title/url keys se items."""
    try:
        data = json.loads(text)
    except ValueError:
        return []
    rows = data
    for key in rows_path:
        if not isinstance(rows, dict):
            return []
        rows = rows.get(key) or []
    if not isinstance(rows, list):
        return []
    out = []
    for row in rows[:max(1, int(limit))]:
        if not isinstance(row, dict):
            continue
        title = util.truncate(str(row.get(title_key) or "").strip(), 240)
        url = str(row.get(url_key) or "").strip()
        if not title or not url.startswith(("http://", "https://")):
            continue
        out.append({
            "title": title, "url": url, "source": source,
            "source_key": source_key,
            "published": util.parse_date(row.get(date_key)),
            "excerpt": util.clean_text(row.get(excerpt_key) or "", 600),
            "body": "", "category": category, "trust": trust, "tier": tier,
            "kind": "web-search", "link_only": False,
        })
    return out


def _engine_item(title, url, source, source_key, excerpt="", published="",
                 category="World", trust=0.7, tier="T1") -> dict:
    return {
        "title": util.truncate(title, 240), "url": url, "source": source,
        "source_key": source_key, "published": util.parse_date(published),
        "excerpt": util.clean_text(excerpt, 600), "body": "",
        "category": category, "trust": trust, "tier": tier,
        "kind": "web-search", "link_only": False,
    }


def parse_doaj_rows(text, source, source_key, query, cfg, limit=25,
                    category="Science", trust=0.85, tier="T1", **_):
    try:
        data = json.loads(text)
    except ValueError:
        return []
    out = []
    for row in (data.get("results") or [])[:max(1, int(limit))]:
        if not isinstance(row, dict):
            continue
        bib = row.get("bibjson") or {}
        title = str(bib.get("title") or "").strip()
        links = bib.get("link") or []
        url = str((links[0] or {}).get("url") or "").strip() if links else ""
        if title and url:
            out.append(_engine_item(title, url, source, source_key,
                                    bib.get("abstract") or "", category=category,
                                    trust=trust, tier=tier))
    return out


def parse_europepmc_rows(text, source, source_key, query, cfg, limit=25,
                         category="Science", trust=0.9, tier="T1", **_):
    try:
        data = json.loads(text)
    except ValueError:
        return []
    rows = ((data.get("resultList") or {}).get("result") or [])[:max(1, int(limit))]
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or "").strip()
        doi = str(row.get("doi") or "").strip()
        url = ("https://doi.org/" + doi) if doi else ""
        if title and url:
            out.append(_engine_item(title, url, source, source_key,
                                    row.get("authorString") or "",
                                    row.get("firstPublicationDate"),
                                    category, trust, tier))
    return out


def parse_gitlab_rows(text, source, source_key, query, cfg, limit=25,
                      category="Tools & Reverse Engineering", trust=0.8,
                      tier="T1", **_):
    try:
        data = json.loads(text)
    except ValueError:
        return []
    if not isinstance(data, list):
        return []
    out = []
    for row in data[:max(1, int(limit))]:
        if not isinstance(row, dict):
            continue
        title = str(row.get("path_with_namespace") or row.get("name") or "").strip()
        url = str(row.get("web_url") or "").strip()
        if title and url:
            out.append(_engine_item(title, url, source, source_key,
                                    row.get("description") or "",
                                    category=category, trust=trust, tier=tier))
    return out


def parse_huggingface_rows(text, source, source_key, query, cfg, limit=25,
                           category="Tools & Reverse Engineering", trust=0.75,
                           tier="T1", **_):
    try:
        data = json.loads(text)
    except ValueError:
        return []
    if not isinstance(data, list):
        return []
    out = []
    for row in data[:max(1, int(limit))]:
        if not isinstance(row, dict):
            continue
        mid = str(row.get("id") or row.get("modelId") or "").strip()
        if mid:
            out.append(_engine_item(mid, "https://huggingface.co/" + mid,
                                    source, source_key,
                                    ",".join(row.get("tags") or [])[:200],
                                    category=category, trust=trust, tier=tier))
    return out


def parse_npm_rows(text, source, source_key, query, cfg, limit=25,
                   category="Tools & Reverse Engineering", trust=0.7,
                   tier="T1", **_):
    try:
        data = json.loads(text)
    except ValueError:
        return []
    out = []
    for row in (data.get("objects") or [])[:max(1, int(limit))]:
        pkg = row.get("package") or {}
        name = str(pkg.get("name") or "").strip()
        if not name:
            continue
        links = pkg.get("links") or {}
        url = str(links.get("repository") or
                  "https://www.npmjs.com/package/" + name).strip()
        out.append(_engine_item(name, url, source, source_key,
                                pkg.get("description") or "",
                                category=category, trust=trust, tier=tier))
    return out


def parse_crates_rows(text, source, source_key, query, cfg, limit=25,
                      category="Tools & Reverse Engineering", trust=0.7,
                      tier="T1", **_):
    try:
        data = json.loads(text)
    except ValueError:
        return []
    out = []
    for row in (data.get("crates") or [])[:max(1, int(limit))]:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or row.get("id") or "").strip()
        cid = str(row.get("id") or "").strip()
        url = ("https://crates.io/crates/" + cid) if cid else ""
        if name and url:
            out.append(_engine_item(name, url, source, source_key,
                                    row.get("description") or "",
                                    category=category, trust=trust, tier=tier))
    return out


def parse_archive_rows(text, source, source_key, query, cfg, limit=25,
                       category="World", trust=0.75, tier="T1", **_):
    try:
        data = json.loads(text)
    except ValueError:
        return []
    docs = (data.get("response") or {}).get("docs") or []
    out = []
    for row in docs[:max(1, int(limit))]:
        if not isinstance(row, dict):
            continue
        ident = str(row.get("identifier") or "").strip()
        title = str(row.get("title") or ident).strip()
        url = ("https://archive.org/details/" + ident) if ident else ""
        if title and url:
            out.append(_engine_item(title, url, source, source_key,
                                    category=category, trust=trust, tier=tier))
    return out


def parse_openlibrary_rows(text, source, source_key, query, cfg, limit=25,
                           category="World", trust=0.75, tier="T1", **_):
    try:
        data = json.loads(text)
    except ValueError:
        return []
    out = []
    for row in (data.get("docs") or [])[:max(1, int(limit))]:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or "").strip()
        key = str(row.get("key") or "").strip()
        url = ("https://openlibrary.org" + key) if key else ""
        if title and url:
            out.append(_engine_item(title, url, source, source_key,
                                    ", ".join(row.get("author_name") or [])[:200],
                                    category=category, trust=trust, tier=tier))
    return out


def parse_datacite_rows(text, source, source_key, query, cfg, limit=25,
                        category="Science", trust=0.85, tier="T1", **_):
    try:
        data = json.loads(text)
    except ValueError:
        return []
    out = []
    for row in (data.get("data") or [])[:max(1, int(limit))]:
        if not isinstance(row, dict):
            continue
        a = row.get("attributes") or {}
        titles = a.get("titles") or []
        title = str((titles[0] or {}).get("title") or "").strip() if titles else ""
        doi = str(a.get("doi") or "").strip()
        url = str(a.get("url") or ("https://doi.org/" + doi if doi else "")).strip()
        descs = a.get("descriptions") or []
        excerpt = str((descs[0] or {}).get("description") or "") if descs else ""
        if title and url:
            out.append(_engine_item(title, url, source, source_key, excerpt,
                                    category=category, trust=trust, tier=tier))
    return out


def _oa_value(value) -> str:
    if isinstance(value, dict):
        return str(value.get("$") or "").strip()
    if isinstance(value, list):
        return str((value[0] or {}).get("$") or "").strip() if value else ""
    return str(value or "").strip()


def parse_openaire_rows(text, source, source_key, query, cfg, limit=25,
                        category="Science", trust=0.85, tier="T1", **_):
    try:
        data = json.loads(text)
    except ValueError:
        return []
    rows = (((data.get("response") or {}).get("results") or {}).get("result") or [])
    out = []
    for row in rows[:max(1, int(limit))]:
        if not isinstance(row, dict):
            continue
        try:
            res = row["metadata"]["oaf:entity"]["oaf:result"]
        except (KeyError, TypeError):
            continue
        title = _oa_value(res.get("title"))
        pid = res.get("pid")
        doi = ""
        if isinstance(pid, dict):
            if pid.get("@classid") == "doi":
                doi = str(pid.get("$") or "")
        elif isinstance(pid, list):
            for p in pid:
                if isinstance(p, dict) and p.get("@classid") == "doi":
                    doi = str(p.get("$") or "")
                    break
        url = ("https://doi.org/" + doi) if doi else ""
        if title and url:
            out.append(_engine_item(title, url, source, source_key,
                                    _oa_value(res.get("description")),
                                    _oa_value(res.get("dateofacceptance")),
                                    category, trust, tier))
    return out


def parse_hal_rows(text, source, source_key, query, cfg, limit=25,
                   category="Science", trust=0.85, tier="T1", **_):
    try:
        data = json.loads(text)
    except ValueError:
        return []
    docs = (data.get("response") or {}).get("docs") or []
    out = []
    for row in docs[:max(1, int(limit))]:
        if not isinstance(row, dict):
            continue
        titles = row.get("title_s") or []
        title = str(titles[0] if titles else "").strip()
        url = str(row.get("uri_s") or "").strip()
        if title and url:
            out.append(_engine_item(title, url, source, source_key,
                                    published=row.get("producedDate_tdate") or "",
                                    category=category, trust=trust, tier=tier))
    return out


def parse_usgs_rows(text, source, source_key, query, cfg, limit=25,
                    category="World", trust=0.85, tier="T1", **_):
    try:
        data = json.loads(text)
    except ValueError:
        return []
    out = []
    for feat in (data.get("features") or [])[:max(1, int(limit))]:
        p = feat.get("properties") or {}
        title = str(p.get("title") or "").strip()
        url = str(p.get("url") or "").strip()
        if title and url:
            out.append(_engine_item(title, url, source, source_key,
                                    p.get("place") or "", category=category,
                                    trust=trust, tier=tier))
    return out


def parse_weather_rows(text, source, source_key, query, cfg, limit=25,
                       category="World", trust=0.85, tier="T1", **_):
    try:
        data = json.loads(text)
    except ValueError:
        return []
    out = []
    for feat in (data.get("features") or [])[:max(1, int(limit))]:
        p = feat.get("properties") or {}
        event = str(p.get("event") or "").strip()
        area = str(p.get("areaDesc") or "").strip()
        title = (event + (" — " + area if area else "")).strip()
        url = str(p.get("@id") or p.get("id") or "").strip()
        if title and url:
            out.append(_engine_item(title, url, source, source_key,
                                    p.get("headline") or p.get("description") or "",
                                    p.get("effective") or p.get("sent"),
                                    category, trust, tier))
    return out


def parse_wiby_rows(text, source, source_key, query, cfg, limit=25,
                    category="World", trust=0.6, tier="T1", **_):
    return parse_html_links(text, source, source_key, query, cfg,
                            exclude_hosts=("wiby.me",), min_text=12,
                            limit=limit, category=category, trust=trust,
                            tier=tier)


def parse_rightdao_rows(text, source, source_key, query, cfg, limit=25,
                        category="World", trust=0.55, tier="T1", **_):
    return parse_html_links(text, source, source_key, query, cfg,
                            exclude_hosts=("rightdao.com",), min_text=12,
                            limit=limit, category=category, trust=trust,
                            tier=tier)


def parse_lemmy_rows(text, source, source_key, query, cfg, limit=25,
                     category="World", trust=0.6, tier="T2", **_):
    try:
        data = json.loads(text)
    except ValueError:
        return []
    out = []
    for row in (data.get("communities") or [])[:max(1, int(limit))]:
        c = row.get("community") or {}
        name = str(c.get("name") or "").strip()
        if not name:
            continue
        title = str(c.get("title") or name).strip()
        out.append(_engine_item(title, "https://lemmy.ml/c/" + name,
                                source, source_key, c.get("description") or "",
                                c.get("published") or "", category, trust, tier))
    return out


_PARSERS = {
    "doaj": parse_doaj_rows,
    "europepmc": parse_europepmc_rows,
    "gitlab": parse_gitlab_rows,
    "huggingface": parse_huggingface_rows,
    "npm": parse_npm_rows,
    "crates": parse_crates_rows,
    "archive-search": parse_archive_rows,
    "openlibrary": parse_openlibrary_rows,
    "datacite": parse_datacite_rows,
    "openaire": parse_openaire_rows,
    "hal": parse_hal_rows,
    "usgs": parse_usgs_rows,
    "weather": parse_weather_rows,
    "wiby": parse_wiby_rows,
    "rightdao": parse_rightdao_rows,
    "lemmy": parse_lemmy_rows,
}


class SimpleEngineAdapter(Adapter):
    """P40 keyless engine — URL template + parser kind (stdlib-only)."""

    def __init__(self, key, name, url_template, kind, pconfig=None,
                 category="World", trust=0.6, tier="T1", frequency=60,
                 enabled=True):
        self.key, self.name = key, name
        self.url_template = url_template
        self.kind = kind
        self.pconfig = dict(pconfig or {})
        self.category, self.trust, self.tier = category, trust, tier
        self.frequency = frequency
        self.enabled = bool(enabled)

    def build(self, query, days, limit, cfg):
        q = urllib.parse.quote(str(query or "")[:200])
        n = str(min(25, max(3, int(limit or 10))))
        end = datetime.now(timezone.utc).date()
        start = end - timedelta(days=min(14, max(1, int(days or 7))))
        return (self.url_template.replace("{q}", q).replace("{n}", n)
                .replace("{from}", start.isoformat())
                .replace("{to}", end.isoformat()))

    def parse(self, text, query, cfg):
        if self.kind == "html":
            return parse_html_links(text, self.name, self.key, query, cfg,
                                    category=self.category, trust=self.trust,
                                    tier=self.tier, **self.pconfig)
        if self.kind == "json":
            return parse_json_rows(text, self.name, self.key, query, cfg,
                                   category=self.category, trust=self.trust,
                                   tier=self.tier, **self.pconfig)
        fn = _PARSERS.get(self.kind)
        if not fn:
            return []
        return fn(text, self.name, self.key, query, cfg,
                  category=self.category, trust=self.trust, tier=self.tier,
                  **self.pconfig)


# (key, name, url_template, parser kind, parser config, category, trust,
#  tier, auto) — auto=False engines ka adapter nahi banta (registry-only).
SIMPLE_ENGINES = [
    # Web
    ("marginalia", "Marginalia Search",
     "https://search.marginalia.nu/search?query={q}", "html",
     {"exclude_hosts": ("marginalia.nu", "github.com", "discord.com",
                        "discord.gg", "creativecommons.org", "ip2location.com"),
      "min_text": 15}, "World", 0.7, "T1", False),
    ("yahoojp", "Yahoo! Japan Search",
     "https://search.yahoo.co.jp/search?p={q}", "html",
     {"exclude_hosts": ("yahoo.co.jp", "yahoo-net.jp"), "min_text": 15},
     "World", 0.65, "T1", True),
    ("seznam", "Seznam.cz Search", "https://search.seznam.cz/?q={q}", "html",
     {"exclude_hosts": ("seznam.cz", "o-seznam.cz", "zbozi.cz", "alza.cz",
                        "youtube.com", "google.com"), "min_text": 15},
     "World", 0.6, "T1", True),
    ("bing-news", "Bing News", "https://www.bing.com/news/search?q={q}", "html",
     {"exclude_hosts": ("bing.com", "microsoft.com"), "min_text": 15},
     "World", 0.7, "T1", True),
    # Academic
    ("doaj", "DOAJ Articles",
     "https://doaj.org/api/search/articles/{q}?pageSize={n}", "doaj", {},
     "Science", 0.85, "T1", True),
    ("europepmc", "Europe PMC",
     "https://www.ebi.ac.uk/europepmc/webservices/rest/search?query={q}"
     "&format=json&pageSize={n}", "europepmc", {}, "Science", 0.9, "T1", True),
    ("biorxiv", "bioRxiv",
     "https://api.biorxiv.org/details/biorxiv/{from}/{to}", "biorxiv", {},
     "Science", 0.85, "T1", False),
    # OSS
    ("gitlab", "GitLab Projects",
     "https://gitlab.com/api/v4/projects?search={q}&per_page={n}", "gitlab", {},
     "Tools & Reverse Engineering", 0.8, "T1", True),
    ("huggingface", "Hugging Face Models",
     "https://huggingface.co/api/models?search={q}&limit={n}", "huggingface",
     {}, "Tools & Reverse Engineering", 0.75, "T1", True),
    ("stackexchange", "Stack Exchange API",
     "https://api.stackexchange.com/2.3/search/advanced?order=desc"
     "&sort=relevance&q={q}&site=stackoverflow&pagesize={n}", "json",
     {"rows_path": ("items",), "title_key": "title", "url_key": "link",
      "excerpt_key": "body"}, "Tools & Reverse Engineering", 0.75, "T1", True),
    ("npm", "npm Registry",
     "https://registry.npmjs.org/-/v1/search?text={q}&size={n}", "npm", {},
     "Tools & Reverse Engineering", 0.7, "T1", True),
    ("crates", "crates.io",
     "https://crates.io/api/v1/crates?q={q}&per_page={n}", "crates", {},
     "Tools & Reverse Engineering", 0.7, "T1", True),
    # Archive
    ("archive-search", "Internet Archive Search",
     "https://archive.org/advancedsearch.php?q={q}&fl[]=identifier&fl[]=title"
     "&rows={n}&output=json", "archive-search", {}, "World", 0.75, "T1", True),
    ("openlibrary", "Open Library",
     "https://openlibrary.org/search.json?q={q}&limit={n}", "openlibrary", {},
     "World", 0.75, "T1", True),
    # Academic (P41)
    ("datacite", "DataCite",
     "https://api.datacite.org/dois?query={q}&page[size]={n}", "datacite", {},
     "Science", 0.85, "T1", True),
    ("openaire", "OpenAIRE",
     "https://api.openaire.eu/search/publications?title={q}&format=json&size={n}",
     "openaire", {}, "Science", 0.85, "T1", True),
    ("hal", "HAL Archives Ouvertes",
     "https://api.archives-ouvertes.fr/search/?q={q}"
     "&fl=title_s,uri_s,producedDate_tdate&rows={n}&wt=json", "hal", {},
     "Science", 0.85, "T1", True),
    # Archive / data (P41)
    ("usgs", "USGS Earthquakes",
     "https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&limit={n}",
     "usgs", {}, "World", 0.85, "T1", True),
    ("weather", "NOAA Weather Alerts",
     "https://api.weather.gov/alerts?limit={n}", "weather", {},
     "World", 0.85, "T1", True),
    # Web (P41)
    ("wiby", "Wiby", "https://wiby.me/?q={q}", "wiby", {},
     "World", 0.6, "T1", True),
    ("rightdao", "RightDAO", "https://rightdao.com/search?q={q}", "rightdao",
     {}, "World", 0.55, "T1", True),
    # TG / social (P41)
    ("lemmy", "Lemmy",
     "https://lemmy.ml/api/v3/search?q={q}&type_=Communities&limit={n}",
     "lemmy", {}, "World", 0.6, "T2", True),
]

SIMPLE_ADAPTERS = [
    SimpleEngineAdapter(key=k, name=n, url_template=u, kind=kind, pconfig=pc,
                        category=cat, trust=tr, tier=tier, enabled=auto)
    for (k, n, u, kind, pc, cat, tr, tier, auto) in SIMPLE_ENGINES if auto
]


RSS_FEEDS = [
    ("gsmarena", "GSMArena", "https://www.gsmarena.com/rss-news-reviews.php3", "Mobile & Firmware", 0.7),
    ("xda", "XDA Developers", "https://www.xda-developers.com/feed/", "Tools & Reverse Engineering", 0.6),
    ("androidauthority", "Android Authority", "https://www.androidauthority.com/feed/", "Android", 0.7),
    ("androidpolice", "Android Police", "https://www.androidpolice.com/feed/", "Android", 0.7),
    ("9to5google", "9to5Google", "https://9to5google.com/feed/", "Android", 0.7),
    ("sammobile", "SamMobile", "https://www.sammobile.com/feed/", "Mobile & Firmware", 0.7),
    ("apple-newsroom", "Apple Newsroom", "https://www.apple.com/newsroom/rss-feed.rss", "iOS", 0.9),
    # P41 news RSS
    ("bbc-news", "BBC News", "https://feeds.bbci.co.uk/news/rss.xml", "World", 0.85),
    ("aljazeera", "Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml", "World", 0.8),
    ("arstechnica", "Ars Technica", "https://feeds.arstechnica.com/arstechnica/index", "World", 0.8),
    ("wired", "Wired", "https://www.wired.com/feed", "World", 0.8),
    ("techcrunch", "TechCrunch", "https://techcrunch.com/feed/", "World", 0.75),
    ("theverge", "The Verge", "https://www.theverge.com/rss/index.xml", "World", 0.75),
    ("zdnet", "ZDNet", "https://www.zdnet.com/news/rss.xml", "World", 0.7),
    ("cnet", "CNET", "https://www.cnet.com/rss/news/", "World", 0.7),
    ("nytimes", "New York Times", "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml", "World", 0.85),
    ("npr", "NPR", "https://feeds.npr.org/1001/rss.xml", "World", 0.8),
]

ADAPTERS: list[Adapter] = [RSSAdapter(*row) for row in RSS_FEEDS] + [
    GoogleNewsAdapter(), HackerNewsAdapter(), GitHubAdapter(), GDELTAdapter(),
    OpenAlexAdapter(), CrossrefAdapter(), ArxivAdapter(),
    # P27 retrieval++
    RedditAdapter(), WikipediaAdapter(), WikidataAdapter(),
    GoogleNewsTopicAdapter(), WaybackAdapter(), GitHubSearchAdapter(),
    NVDAdapter(), SitemapAdapter(), BraveSearchAdapter(), BingSearchAdapter(),
    TelegramAdapter(), AhmiaAdapter(), PubMedAdapter(),
] + SIMPLE_ADAPTERS
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
            "kind": "fixture", "synthetic": True, "offline": True,
            "link_only": adapter.key == "ahmia",
            "offline": True,
        })
    if adapter.key in ("ahmia", "wayback"):
        for item in out:
            item["link_only"] = True
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
        elif not offline:
            info = getattr(adapter, "last_fetch", None)
            if isinstance(info, dict) and info.get("text"):
                try:
                    snap = snapshots.record(adapter.key, info.get("url", ""),
                                            info["text"], cfg)
                    diag["change"] = {
                        "changed": bool(snap.get("changed")),
                        "new": bool(snap.get("new")),
                        "added_lines": int(snap.get("added_lines") or 0),
                        "removed_lines": int(snap.get("removed_lines") or 0),
                        "changed_lines": list(snap.get("changed_lines") or [])[:5],
                    }
                except Exception:
                    pass
        return items, diag
    except ratelimit.RateLimited as exc:
        metrics.inc("rate_limited")
        diag["error"] = f"RateLimited: {util.truncate(str(exc), 120)}"
        return [], diag
    except Exception as exc:
        diag["error"] = f"{type(exc).__name__}: {util.truncate(str(exc), 140)}"
        return [], diag
    finally:
        diag["elapsed_ms"] = round((time.monotonic() - started) * 1000)
        if not diag["ok"]:
            logging_setup.get_logger("adapters").warning(
                "adapter fetch failed",
                extra={"fields": {"adapter": adapter.key, "offline": bool(offline),
                                  "elapsed_ms": diag["elapsed_ms"],
                                  "error": diag["error"]}})


def adapter_enabled(adapter: Adapter, cfg: dict) -> bool:
    """Explicit ``source_enabled`` flag wins; otherwise the class default."""
    flags = (cfg or {}).get("source_enabled") or {}
    if adapter.key in flags:
        return bool(flags[adapter.key])
    return bool(adapter.enabled)


def adapter_ready(adapter: Adapter, cfg: dict) -> bool:
    """Enabled AND, for keyed adapters, a configured key (no key = no error)."""
    if not adapter_enabled(adapter, cfg):
        return False
    return key_ready(adapter, cfg)


def key_ready(adapter: Adapter, cfg: dict) -> bool:
    if not adapter.requires_key:
        return True
    field = getattr(adapter, "key_field", "")
    return bool(str((cfg or {}).get(field) or "").strip())


def run(query: str, keys=None, days: int = 7, limit: int = 25,
        cfg: dict | None = None, offline: bool = False,
        include_opt_in: bool = False,
        skip=None) -> tuple[list[dict], list[dict]]:
    """Run selected adapters in parallel. Never raises on network failure."""
    cfg = cfg or config.load()
    skip = {str(s) for s in (skip if skip is not None
                             else (cfg.get("skip_sources") or ()))}
    if keys:
        wanted = set(keys)
        # Explicit keys always honoured (opt-in included); a keyed adapter is
        # still skipped when its key is missing so no request is even built.
        selected = [a for a in ADAPTERS
                    if a.key in wanted and key_ready(a, cfg)]
    else:
        selected = [a for a in ADAPTERS if adapter_ready(a, cfg)]
        if include_opt_in:
            selected = [a for a in ADAPTERS if key_ready(a, cfg)]
    if skip:
        selected = [a for a in selected if a.key not in skip]
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
