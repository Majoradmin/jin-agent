"""Legal source register, SSRF/allowlist guard and the unchanged safe-service boundary.

Facts (URL + date checked = 2026-11-14) and recommendations are kept separate.
No illegal marketplace, stolen data, credential dump, leaked firmware, bypass
service, malware sample or private database is part of the source universe.
"""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlsplit

POLICY_ID = "SAHULAT-SAFE-SERVICE-v1"
DATE_CHECKED = "2026-11-14"
TOR_MODES = ("links_only", "off")

DARK_WEB_RULE = (
    "Legal onion discovery only. Onion links may be DISPLAYED as citations; "
    "they are never fetched, crawled or resolved by this agent."
)

# Adapter hosts only. LLM loopback endpoints are handled separately in llm.py.
ALLOWED_HOSTS = frozenset({
    "news.google.com", "hn.algolia.com", "api.github.com", "github.com",
    "www.gsmarena.com", "www.xda-developers.com", "xda-developers.com",
    "www.androidauthority.com", "www.androidpolice.com", "9to5google.com",
    "www.sammobile.com", "www.apple.com", "source.android.com",
    "security.samsungmobile.com", "support.apple.com",
    "api.gdeltproject.org", "t.me", "telegram.me", "api.telegram.org",
    "html.duckduckgo.com", "lite.duckduckgo.com",
    "ahmia.fi", "api.openalex.org", "api.crossref.org", "export.arxiv.org",
    "www.google.com", "patents.google.com",
    # P27 retrieval breadth
    "www.reddit.com", "reddit.com", "en.wikipedia.org", "www.wikidata.org",
    "archive.org", "web.archive.org", "services.nvd.nist.gov",
    "api.search.brave.com", "api.bing.microsoft.com",
})

# key, name, url, tier, category, trust, auto_fetch, notes
SOURCE_REGISTER = [
    {"key": "android-bulletin", "name": "Android Security Bulletin", "url": "https://source.android.com/docs/security/bulletin", "tier": "T0", "category": "Security", "trust": 1.0, "auto": True, "notes": "Official monthly platform + vendor patches. Registry-only: no RSS endpoint, verified manually."},
    {"key": "samsung-smr", "name": "Samsung Security (SMR)", "url": "https://security.samsungmobile.com/securityUpdate.smsb", "tier": "T0", "category": "Security", "trust": 1.0, "auto": True, "notes": "Official SMR page. Registry-only: HTML, not a stable feed."},
    {"key": "apple-security", "name": "Apple Security Releases", "url": "https://support.apple.com/100100", "tier": "T0", "category": "iOS", "trust": 1.0, "auto": True, "notes": "Official iOS/iPadOS security releases. Registry-only."},
    {"key": "apple-newsroom", "name": "Apple Newsroom", "url": "https://www.apple.com/newsroom/rss-feed.rss", "tier": "T0", "category": "iOS", "trust": 0.9, "auto": True, "notes": "Official RSS adapter."},
    {"key": "gsmarena", "name": "GSMArena", "url": "https://www.gsmarena.com/rss-news-reviews.php3", "tier": "T0", "category": "Mobile & Firmware", "trust": 0.7, "auto": True, "notes": "RSS adapter."},
    {"key": "xda", "name": "XDA Developers", "url": "https://www.xda-developers.com/feed/", "tier": "T0", "category": "Tools & Reverse Engineering", "trust": 0.6, "auto": True, "notes": "RSS adapter."},
    {"key": "androidauthority", "name": "Android Authority", "url": "https://www.androidauthority.com/feed/", "tier": "T0", "category": "Android", "trust": 0.7, "auto": True, "notes": "RSS adapter."},
    {"key": "androidpolice", "name": "Android Police", "url": "https://www.androidpolice.com/feed/", "tier": "T0", "category": "Android", "trust": 0.7, "auto": True, "notes": "RSS adapter."},
    {"key": "9to5google", "name": "9to5Google", "url": "https://9to5google.com/feed/", "tier": "T0", "category": "Android", "trust": 0.7, "auto": True, "notes": "RSS adapter."},
    {"key": "sammobile", "name": "SamMobile", "url": "https://www.sammobile.com/feed/", "tier": "T0", "category": "Mobile & Firmware", "trust": 0.7, "auto": True, "notes": "RSS adapter."},
    {"key": "gnews", "name": "Google News RSS", "url": "https://news.google.com/rss/search", "tier": "T0", "category": "World", "trust": 0.8, "auto": True, "notes": "Search adapter, no API key."},
    {"key": "hn", "name": "Hacker News (Algolia)", "url": "https://hn.algolia.com/api/v1/search_by_date", "tier": "T0", "category": "Tools & Reverse Engineering", "trust": 0.7, "auto": True, "notes": "Search adapter, no API key."},
    {"key": "github", "name": "GitHub Releases", "url": "https://api.github.com/repos", "tier": "T0", "category": "Tools & Reverse Engineering", "trust": 0.9, "auto": True, "notes": "3 firmware-tool repositories, unauthenticated."},
    {"key": "github-search", "name": "GitHub Search", "url": "https://api.github.com/search/repositories", "tier": "T0", "category": "Tools & Reverse Engineering", "trust": 0.8, "auto": True, "notes": "P27 unauthenticated repository search; optional github_token raises the free-tier limit. Rate-limit aware."},
    {"key": "reddit", "name": "Reddit (public JSON)", "url": "https://www.reddit.com/r/android/search.json", "tier": "T1", "category": "Android", "trust": 0.45, "auto": True, "notes": "P27 read-only public subreddit search JSON. No login, no posting, no private subreddit."},
    {"key": "wikipedia", "name": "Wikipedia Search", "url": "https://en.wikipedia.org/w/api.php", "tier": "T3", "category": "World", "trust": 0.8, "auto": True, "notes": "P27 MediaWiki search API, no key."},
    {"key": "wikidata", "name": "Wikidata Search", "url": "https://www.wikidata.org/w/api.php", "tier": "T3", "category": "World", "trust": 0.75, "auto": True, "notes": "P27 entity search API, no key."},
    {"key": "gnews-topic", "name": "Google News RSS (topic)", "url": "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY", "tier": "T0", "category": "World", "trust": 0.8, "auto": True, "notes": "P27 topic headlines RSS, no key."},
    {"key": "wayback", "name": "Wayback Machine", "url": "https://archive.org/wayback/available", "tier": "T1", "category": "World", "trust": 0.7, "auto": True, "notes": "P27 availability + CDX. Links only: snapshots are cited, never re-fetched/crawled."},
    {"key": "nvd", "name": "NVD CVE API", "url": "https://services.nvd.nist.gov/rest/json/cves/2.0", "tier": "T0", "category": "Security", "trust": 0.95, "auto": True, "notes": "P27 official NVD 2.0 JSON feed, no key; public rate limit respected."},
    {"key": "sitemap", "name": "Sitemap discovery", "url": "https://source.android.com/sitemap.xml", "tier": "T0", "category": "World", "trust": 0.8, "auto": True, "notes": "P27 robots.txt + sitemap.xml discovery, bounded depth and URL cap. Allowlisted hosts only."},
    {"key": "brave-search", "name": "Brave Search API", "url": "https://api.search.brave.com/res/v1/web/search", "tier": "T1", "category": "World", "trust": 0.75, "auto": False, "notes": "P27 optional keyed adapter. No brave_key = disabled silently (free tier friendly)."},
    {"key": "bing-search", "name": "Bing Web Search API", "url": "https://api.bing.microsoft.com/v7.0/search", "tier": "T1", "category": "World", "trust": 0.75, "auto": False, "notes": "P27 optional keyed adapter. No bing_key = disabled silently (free tier friendly)."},
    {"key": "gdelt", "name": "GDELT DOC 2.0", "url": "https://api.gdeltproject.org/api/v2/doc/doc", "tier": "T1", "category": "World", "trust": 0.7, "auto": True, "notes": "Free global news index; can be flaky, graceful degradation."},
    {"key": "openalex", "name": "OpenAlex", "url": "https://api.openalex.org/works", "tier": "T3", "category": "Science", "trust": 0.85, "auto": True, "notes": "Legal scholarly index, no key."},
    {"key": "crossref", "name": "Crossref", "url": "https://api.crossref.org/works", "tier": "T3", "category": "Science", "trust": 0.85, "auto": True, "notes": "Legal DOI metadata, no key."},
    {"key": "arxiv", "name": "arXiv", "url": "https://export.arxiv.org/api/query", "tier": "T3", "category": "Science", "trust": 0.9, "auto": True, "notes": "Legal preprints, Atom API, no key."},
    {"key": "telegram-public", "name": "Telegram Public Preview", "url": "https://t.me/s/", "tier": "T2", "category": "Telecom", "trust": 0.4, "auto": False, "notes": "Only public channels explicitly added in Settings. No login, no userbot, no MTProto, no history scrape."},
    {"key": "ahmia", "name": "Ahmia onion index", "url": "https://ahmia.fi/search/", "tier": "T4", "category": "Custom Watchlist", "trust": 0.5, "auto": False, "notes": DARK_WEB_RULE + " Clearnet index only, links-only."},
    {"key": "patents", "name": "Google Patents", "url": "https://patents.google.com/", "tier": "T3", "category": "Science", "trust": 0.8, "auto": False, "notes": "N/A adapter: no keyless stable API; JS-heavy page. Link-only registry entry, documented in PHASES.md P17."},
    {"key": "virustotal", "name": "VirusTotal", "url": "https://www.virustotal.com/", "tier": "T3", "category": "Security", "trust": 0.9, "auto": False, "notes": "N/A adapter: API key required; no paid/credential dependency allowed (C20)."},
    {"key": "urlscan", "name": "urlscan.io", "url": "https://urlscan.io/", "tier": "T3", "category": "Security", "trust": 0.8, "auto": False, "notes": "N/A adapter: API key / submission writes out of scope for a read-only agent."},
]

TRUST_LABELS = ((0.9, "Official"), (0.8, "Verified"), (0.6, "Reported"),
                (0.4, "Unverified"), (0.0, "Rumor"))

# Narrow ACTION-intent patterns only. Merely mentioning FRP / activation lock
# in a research query is legitimate and must NOT be blocked.
BLOCK_PATTERNS = [
    (r"\bfrp\s*(bypass|remove|reset|off|unlock|erase|hata|hatana)\b", "google"),
    (r"\b(erase|write|reset)\s+(the\s+)?(frp|persistent|seccfg|devinfo|modemst)\b", "google"),
    (r"\b(fmi|activation lock|icloud lock)\s*(off|remove|bypass|unlock|hata)\b", "apple"),
    (r"\b(huawei id|samsung account|knox guard|mdm)\s*(bypass|remove|unlock|off)\b", "oem"),
    (r"\b(unlock code|imei change|imei repair|blacklist clean|blacklist remove|carrier unlock kar do)\b", "oem"),
    (r"\b(gsx|icloud)\s*(login|account|lookup)\b.*\b(bypass|crack|without)\b", "apple"),
]

OFFICIAL_LINKS = {
    "google": "https://support.google.com/android/answer/6160491",
    "apple": "https://support.apple.com/108794",
    "oem": "https://support.google.com/android/answer/6160491",
}

BLOCK_REASON = (
    "Ye server-side ownership control hai; is ka koi bypass automation ya "
    "step-by-step tareeqa is agent mein nahi. Sahulat & Safe Service Policy "
    "(POLICY_ID = SAHULAT-SAFE-SERVICE-v1) barqarar hai."
)


def check_url(url, extra_hosts=()) -> tuple[bool, str]:
    """DNS-free, allowlist-based SSRF guard. Re-validated on every redirect."""
    if not isinstance(url, str) or not url.strip():
        return False, "URL khali hai"
    raw = url.strip()
    if len(raw) > 2000:
        return False, "URL bohat lamba hai"
    try:
        p = urlsplit(raw)
    except Exception:
        return False, "URL parse nahi hua"
    if p.scheme.lower() not in ("http", "https"):
        return False, "Sirf http/https allowed hain"
    if p.username or p.password:
        return False, "URL mein credentials allowed nahi"
    host = (p.hostname or "").lower().rstrip(".")
    if not host:
        return False, "Host nahi mila"
    if host.endswith(".onion"):
        return False, "Onion links sirf display ke liye hain; fetch mana hai"
    if host in ("localhost", "metadata.google.internal") or host.endswith(
            (".local", ".internal", ".localhost", ".localdomain")):
        return False, "Internal host blocked hai"
    try:
        ip = ipaddress.ip_address(host)
        if not ip.is_global or ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_reserved:
            return False, "Private / IP-literal address blocked hai"
    except ValueError:
        pass
    try:
        if p.port is not None and p.port not in (80, 443):
            return False, "Port allowed nahi"
    except ValueError:
        return False, "Port ghalat hai"
    allowed = set(ALLOWED_HOSTS) | set(extra_hosts or ())
    if host not in allowed and not any(host.endswith("." + h) for h in allowed):
        return False, "Host allowlist mein nahi: " + host
    return True, ""


def trusted_public_endpoint(url: str) -> bool:
    """Less strict check for a USER-supplied custom LLM host (no IP literals)."""
    try:
        p = urlsplit(str(url or "").strip())
        if p.scheme.lower() != "https" or p.username or p.password:
            return False
        host = (p.hostname or "").lower().rstrip(".")
        if not host or "." not in host:
            return False
        if host.endswith(".onion") or host in ("localhost", "metadata.google.internal"):
            return False
        if host.endswith((".local", ".internal", ".localhost")):
            return False
        try:
            ipaddress.ip_address(host)
            return False
        except ValueError:
            pass
        if p.port is not None and p.port not in (80, 443):
            return False
        return True
    except Exception:
        return False


def classify(text) -> dict:
    """Return a verdict for a user request. No bypass steps are ever produced."""
    s = str(text or "")[:4000]
    low = s.lower()
    for pattern, brand in BLOCK_PATTERNS:
        if re.search(pattern, low, re.I):
            return {
                "verdict": "blocked",
                "reason": BLOCK_REASON,
                "official_links": [OFFICIAL_LINKS[brand]],
                "safe_steps": [
                    "Malik ka purchase proof / identity verify karain.",
                    "Official manufacturer support route par case open karain.",
                    "Case aur consent ka local record rakhein.",
                ],
                "matched_rule": pattern,
            }
    educational = bool(re.search(r"\b(dark web|deep web|onion|tor|ahmia)\b", low, re.I))
    return {
        "verdict": "allowed",
        "reason": "",
        "official_links": [],
        "safe_steps": [],
        "matched_rule": "",
        "note": DARK_WEB_RULE if educational else "",
        "tor_mode": "links_only",
    }


def trust_label(score: float) -> str:
    for threshold, label in TRUST_LABELS:
        if score >= threshold:
            return label
    return "Rumor"


def register() -> list[dict]:
    return [dict(row, date_checked=DATE_CHECKED) for row in SOURCE_REGISTER]


def adapter_hosts() -> frozenset:
    return ALLOWED_HOSTS
