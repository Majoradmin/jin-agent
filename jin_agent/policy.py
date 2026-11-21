"""Legal source register, SSRF/allowlist guard and the unchanged safe-service boundary.

Facts (URL + date checked = 2026-11-14) and recommendations are kept separate.
No illegal marketplace, stolen data, credential dump, leaked firmware, bypass
service, malware sample or private database is part of the source universe.
"""

from __future__ import annotations

import ipaddress
import re
import socket
from urllib.parse import urlsplit

POLICY_ID = "SAHULAT-SAFE-SERVICE-v1"
DATE_CHECKED = "2026-11-14"
TOR_MODES = ("links_only", "off")

DARK_WEB_RULE = (
    "Legal onion discovery only. Onion links may be DISPLAYED as citations; "
    "they are never fetched, crawled or resolved by this agent."
)

# Sirf in queries par onion index activate hota hai (warna noise).
DARK_QUERY_RE = re.compile(
    r"\b(dark\s?web|deep\s?web|onion|tor|ahmia|hidden\s?service)\b", re.I)


def wants_onion(query: str) -> bool:
    """Query dark/deep web related hai? (Ahmia link-only activation)."""
    return bool(DARK_QUERY_RE.search(str(query or "")))


# Adapter hosts only. LLM loopback endpoints are handled separately in llm.py.
ALLOWED_HOSTS = frozenset({
    "news.google.com", "hn.algolia.com", "api.github.com", "github.com",
    "www.gsmarena.com", "www.xda-developers.com", "xda-developers.com",
    "www.androidauthority.com", "www.androidpolice.com", "9to5google.com",
    "www.sammobile.com", "www.apple.com", "source.android.com",
    "security.samsungmobile.com", "support.apple.com",
    "api.gdeltproject.org", "t.me", "telegram.me", "api.telegram.org",
    "html.duckduckgo.com", "lite.duckduckgo.com",
    # P39: channel discovery ka keyless HTML search engine (DDG fallback ke saath)
    "www.bing.com",
    "ahmia.fi", "api.openalex.org", "api.crossref.org", "export.arxiv.org",
    "www.google.com", "patents.google.com",
    # P27 retrieval breadth
    "www.reddit.com", "reddit.com", "en.wikipedia.org", "www.wikidata.org",
    "archive.org", "web.archive.org", "services.nvd.nist.gov",
    "api.search.brave.com", "api.bing.microsoft.com",
    # P29 deep web (indexed databases, no login)
    "eutils.ncbi.nlm.nih.gov",
    # P2.1 legal/public institutional sources (registry-only)
    "www.who.int", "news.un.org", "data.un.org", "data.europa.eu",
    "op.europa.eu", "data.worldbank.org", "www.oecd.org", "www.cdc.gov",
    "www.nasa.gov", "ourworldindata.org", "pmc.ncbi.nlm.nih.gov",
    "www.imf.org",
    # P40 key-free engine list (jo engine block/key wale nahi bhi hain, unke
    # hosts bhi allowlisted hain — seedha link display/verification ke liye)
    # Web
    "www.mojeek.com", "search.marginalia.nu", "marginalia-search.com",
    "searx.be", "gibiru.com",
    "www.ecosia.org", "www.qwant.com", "www.startpage.com", "swisscows.com",
    "presearch.com",
    # Regional
    "yandex.ru", "www.baidu.com", "www.sogou.com", "search.naver.com",
    "search.daum.net", "search.yahoo.com", "search.yahoo.co.jp",
    "search.seznam.cz", "nova.rambler.ru",
    # Academic
    "api.semanticscholar.org", "doaj.org", "www.ebi.ac.uk",
    "api.biorxiv.org", "api.unpaywall.org", "api.core.ac.uk",
    "api.base-search.net",
    # Patents
    "worldwide.espacenet.com", "patentscope.wipo.int", "api.uspto.gov",
    # OSS
    "gitlab.com", "codeberg.org", "sourceforge.net", "huggingface.co",
    "api.stackexchange.com", "pypi.org", "registry.npmjs.org", "crates.io",
    # Archive / News / Social / TG dirs
    "openlibrary.org", "gutendex.com", "www.googleapis.com", "news.yahoo.com",
    "public.api.bsky.app", "mastodon.social", "tgstat.com", "telemetr.io",
    # P41 — dork + extra engines (news RSS / academic / patents / data / web / social)
    "feeds.bbci.co.uk", "www.aljazeera.com", "feeds.arstechnica.com",
    "www.wired.com", "techcrunch.com", "www.theverge.com", "www.zdnet.com",
    "www.cnet.com", "rss.nytimes.com", "feeds.washingtonpost.com",
    "feeds.npr.org", "www.reutersagency.com", "ground.news",
    "api.datacite.org", "pub.orcid.org", "api.scilit.net", "api.fatcat.wiki",
    "api.openaire.eu", "api.archives-ouvertes.fr", "citeseerx.ist.psu.edu",
    "ideas.repec.org", "econpapers.repec.org", "philpapers.org",
    "pubpsych.zpid.de", "search.ipaustralia.gov.au", "j-platpat.inpit.go.jp",
    "kris.kipris.or.kr", "index.commoncrawl.org", "www.loc.gov",
    "search.worldcat.org", "earthquake.usgs.gov", "api.weather.gov",
    "api.reliefweb.int", "wiby.me", "rightdao.com", "lyzem.com", "lemmy.ml", "a.4cdn.org",
    "8kun.top",
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
    {"key": "bing-web", "name": "Bing Search (HTML)", "url": "https://www.bing.com/search", "tier": "T1", "category": "World", "trust": 0.7, "auto": True, "notes": "P39 keyless HTML search — Telegram channel discovery (t.me/s <topic>). ck/a base64 result URLs decode hote hain; anti-bot anomaly par DDG html/lite fallback."},
    {"key": "gdelt", "name": "GDELT DOC 2.0", "url": "https://api.gdeltproject.org/api/v2/doc/doc", "tier": "T1", "category": "World", "trust": 0.7, "auto": True, "notes": "Free global news index; can be flaky, graceful degradation."},
    {"key": "openalex", "name": "OpenAlex", "url": "https://api.openalex.org/works", "tier": "T3", "category": "Science", "trust": 0.85, "auto": True, "notes": "Legal scholarly index, no key."},
    {"key": "crossref", "name": "Crossref", "url": "https://api.crossref.org/works", "tier": "T3", "category": "Science", "trust": 0.85, "auto": True, "notes": "Legal DOI metadata, no key."},
    {"key": "arxiv", "name": "arXiv", "url": "https://export.arxiv.org/api/query", "tier": "T3", "category": "Science", "trust": 0.9, "auto": True, "notes": "Legal preprints, Atom API, no key."},
    {"key": "telegram-public", "name": "Telegram Public Preview", "url": "https://t.me/s/", "tier": "T2", "category": "Telecom", "trust": 0.4, "auto": False, "notes": "Only public channels explicitly added in Settings. No login, no userbot, no MTProto, no history scrape."},
    {"key": "ahmia", "name": "Ahmia onion index", "url": "https://ahmia.fi/search/", "tier": "T4", "category": "Custom Watchlist", "trust": 0.5, "auto": False, "notes": DARK_WEB_RULE + " Ahmia 2026 me JS-only hai, is liye adapter sirf prefilled search link deta hai (fetch nahi)."},
    {"key": "pubmed", "name": "PubMed (NLM E-utilities)", "url": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/", "tier": "T1", "category": "Science", "trust": 0.9, "auto": True, "notes": "P29 deep-web database: esearch + esummary JSON, no key, 3 req/sec limit respected."},
    {"key": "patents", "name": "Google Patents", "url": "https://patents.google.com/", "tier": "T3", "category": "Science", "trust": 0.8, "auto": False, "notes": "N/A adapter: no keyless stable API; JS-heavy page. Link-only registry entry, documented in PHASES.md P17."},
    {"key": "virustotal", "name": "VirusTotal", "url": "https://www.virustotal.com/", "tier": "T3", "category": "Security", "trust": 0.9, "auto": False, "notes": "N/A adapter: API key required; no paid/credential dependency allowed (C20)."},
    {"key": "urlscan", "name": "urlscan.io", "url": "https://urlscan.io/", "tier": "T3", "category": "Security", "trust": 0.8, "auto": False, "notes": "N/A adapter: API key / submission writes out of scope for a read-only agent."},
    # P2.1 - legal/public institutional sources. Adapter abhi nahi, magar
    # source universe me khule ki jati hain (kabhi bypass/carrier ke pattern
    # wale gair-legal sources add nahi hote).
    {"key": "who", "name": "World Health Organization", "url": "https://www.who.int/news", "tier": "T1", "category": "Science", "trust": 0.9, "auto": False, "notes": "P2.1 official WHO news/rooms. Registry-only: no adapter yet."},
    {"key": "un-news", "name": "UN News", "url": "https://news.un.org/en/", "tier": "T1", "category": "World", "trust": 0.85, "auto": False, "notes": "P2.1 official UN News. Registry-only: no adapter yet."},
    {"key": "un-data", "name": "UN Data Portal", "url": "https://data.un.org/", "tier": "T3", "category": "World", "trust": 0.8, "auto": False, "notes": "P2.1 UN statistical data portal. Registry-only: no adapter yet."},
    {"key": "eu-open-data", "name": "EU Open Data Portal", "url": "https://data.europa.eu/", "tier": "T1", "category": "World", "trust": 0.85, "auto": False, "notes": "P2.1 official EU open data. Registry-only: no adapter yet."},
    {"key": "eu-publications", "name": "EU Publications Office", "url": "https://op.europa.eu/", "tier": "T3", "category": "World", "trust": 0.8, "auto": False, "notes": "P2.1 EU publications/legislation. Registry-only: no adapter yet."},
    {"key": "worldbank", "name": "World Bank Open Data", "url": "https://data.worldbank.org/", "tier": "T1", "category": "World", "trust": 0.85, "auto": False, "notes": "P2.1 official development indicators. Registry-only: no adapter yet."},
    {"key": "oecd", "name": "OECD", "url": "https://www.oecd.org/", "tier": "T1", "category": "World", "trust": 0.8, "auto": False, "notes": "P2.1 official OECD data/news. Registry-only: no adapter yet."},
    {"key": "cdc", "name": "US CDC", "url": "https://www.cdc.gov/", "tier": "T1", "category": "Science", "trust": 0.9, "auto": False, "notes": "P2.1 official US health guidance. Registry-only: no adapter yet."},
    {"key": "nasa", "name": "NASA", "url": "https://www.nasa.gov/", "tier": "T1", "category": "Science", "trust": 0.85, "auto": False, "notes": "P2.1 official NASA news/releases. Registry-only: no adapter yet."},
    {"key": "ourworldindata", "name": "Our World in Data", "url": "https://ourworldindata.org/", "tier": "T3", "category": "Science", "trust": 0.8, "auto": False, "notes": "P2.1 research data visualisation. Registry-only: no adapter yet."},
    {"key": "pmc", "name": "PubMed Central", "url": "https://pmc.ncbi.nlm.nih.gov/", "tier": "T1", "category": "Science", "trust": 0.9, "auto": False, "notes": "P2.1 open-access full-text archive. Registry-only: no adapter yet."},
    {"key": "imf", "name": "IMF", "url": "https://www.imf.org/", "tier": "T1", "category": "World", "trust": 0.8, "auto": False, "notes": "P2.1 official IMF data/publications. Registry-only: no adapter yet."},
    # P40 - key-free engine list. Live check 2026-11-19 (JIN-Agent UA).
    # auto=True sirf woh engine jis ka keyless adapter asli results deta hai;
    # blocked (anomaly/429/captcha/Cloudflare/JS) ya key wale auto=False + wajah.
    # --- Web ---
    {"key": "mojeek", "name": "Mojeek", "url": "https://www.mojeek.com/search", "tier": "T1", "category": "World", "trust": 0.6, "auto": False, "notes": "P40 keyless HTML search. Live: anti-bot captcha page — auto=False."},
    {"key": "marginalia", "name": "Marginalia Search", "url": "https://search.marginalia.nu/search", "tier": "T1", "category": "World", "trust": 0.7, "auto": False, "notes": "P40 keyless HTML search. Live: 302 -> JS shell (parser drift) — auto=False."},
    {"key": "searx-be", "name": "searx.be", "url": "https://searx.be/search", "tier": "T1", "category": "World", "trust": 0.6, "auto": False, "notes": "P40 metasearch. Live: captcha — auto=False."},
    {"key": "gibiru", "name": "Gibiru", "url": "https://gibiru.com/results.html", "tier": "T1", "category": "World", "trust": 0.55, "auto": False, "notes": "P40 keyless HTML search. Live: JS shell, 0 parseable result — auto=False."},
    {"key": "ecosia", "name": "Ecosia", "url": "https://www.ecosia.org/search", "tier": "T1", "category": "World", "trust": 0.65, "auto": False, "notes": "P40 keyless HTML search. Live: HTTP 403 Cloudflare — auto=False."},
    {"key": "qwant", "name": "Qwant", "url": "https://www.qwant.com/", "tier": "T1", "category": "World", "trust": 0.6, "auto": False, "notes": "P40 keyless HTML search. Live: JS-rendered, parser ko result nahi — auto=False."},
    {"key": "startpage", "name": "Startpage", "url": "https://www.startpage.com/sp/search", "tier": "T1", "category": "World", "trust": 0.6, "auto": False, "notes": "P40 keyless HTML search. Live: Anubis anti-bot challenge — auto=False."},
    {"key": "swisscows", "name": "Swisscows", "url": "https://swisscows.com/en/web", "tier": "T1", "category": "World", "trust": 0.6, "auto": False, "notes": "P40 keyless HTML search. Live: JS shell, 0 result — auto=False."},
    {"key": "presearch", "name": "Presearch", "url": "https://presearch.com/search", "tier": "T1", "category": "World", "trust": 0.5, "auto": False, "notes": "P40 keyless HTML search. Live: HTTP 530 — auto=False."},
    # --- Regional ---
    {"key": "yandex", "name": "Yandex Search", "url": "https://yandex.ru/yandsearch", "tier": "T1", "category": "World", "trust": 0.6, "auto": False, "notes": "P40 regional keyless. Live: SmartCaptcha — auto=False."},
    {"key": "baidu", "name": "Baidu Search", "url": "https://www.baidu.com/s", "tier": "T1", "category": "World", "trust": 0.55, "auto": False, "notes": "P40 regional keyless. Live: JS-rendered, 0 parseable result — auto=False."},
    {"key": "sogou", "name": "Sogou Search", "url": "https://www.sogou.com/web", "tier": "T1", "category": "World", "trust": 0.55, "auto": False, "notes": "P40 regional keyless. Live: JS shell — auto=False."},
    {"key": "naver", "name": "Naver Search", "url": "https://search.naver.com/search.naver", "tier": "T1", "category": "World", "trust": 0.6, "auto": False, "notes": "P40 regional keyless. Live: ad-heavy HTML (ader.naver.com), results noisy — auto=False."},
    {"key": "daum", "name": "Daum Search", "url": "https://search.daum.net/search", "tier": "T1", "category": "World", "trust": 0.55, "auto": False, "notes": "P40 regional keyless. Live: ad-heavy HTML — auto=False."},
    {"key": "yahoo", "name": "Yahoo Search", "url": "https://search.yahoo.com/search", "tier": "T1", "category": "World", "trust": 0.65, "auto": False, "notes": "P40 keyless HTML search. Live: HTTP 500 — auto=False."},
    {"key": "yahoojp", "name": "Yahoo! Japan Search", "url": "https://search.yahoo.co.jp/search", "tier": "T1", "category": "World", "trust": 0.65, "auto": True, "notes": "P40 keyless HTML search; parser yahoo/nav links exclude karta hai. Live: asli results."},
    {"key": "seznam", "name": "Seznam.cz Search", "url": "https://search.seznam.cz/", "tier": "T1", "category": "World", "trust": 0.6, "auto": True, "notes": "P40 keyless HTML search; parser shopping/nav exclude karta hai. Live: asli results."},
    {"key": "rambler", "name": "Rambler Nova", "url": "https://nova.rambler.ru/search", "tier": "T1", "category": "World", "trust": 0.5, "auto": False, "notes": "P40 regional keyless. Live: 0 parseable result — auto=False."},
    # --- Academic ---
    {"key": "semanticscholar", "name": "Semantic Scholar API", "url": "https://api.semanticscholar.org/graph/v1/paper/search", "tier": "T1", "category": "Science", "trust": 0.85, "auto": False, "notes": "P40 keyless academic API. Live: HTTP 429 rate limit (key optional) — auto=False."},
    {"key": "doaj", "name": "DOAJ Articles", "url": "https://doaj.org/api/search/articles", "tier": "T1", "category": "Science", "trust": 0.85, "auto": True, "notes": "P40 keyless open-access article API. Live: JSON results."},
    {"key": "europepmc", "name": "Europe PMC", "url": "https://www.ebi.ac.uk/europepmc/webservices/rest/search", "tier": "T1", "category": "Science", "trust": 0.9, "auto": True, "notes": "P40 keyless Europe PMC REST. Live: JSON results."},
    {"key": "biorxiv", "name": "bioRxiv", "url": "https://api.biorxiv.org/details/biorxiv", "tier": "T1", "category": "Science", "trust": 0.85, "auto": False, "notes": "P40 preprint API sirf recent-papers feed hai (query search nahi; 30 items/call) — auto=False."},
    {"key": "unpaywall", "name": "Unpaywall", "url": "https://api.unpaywall.org/v2/", "tier": "T1", "category": "Science", "trust": 0.85, "auto": False, "notes": "P40 academic OA API. Email required (key-like) — auto=False."},
    {"key": "core", "name": "CORE API", "url": "https://api.core.ac.uk/v3/search/works", "tier": "T1", "category": "Science", "trust": 0.85, "auto": False, "notes": "P40 academic aggregator. Live: HTTP 429 / API key required — auto=False."},
    {"key": "base-search", "name": "BASE Search", "url": "https://api.base-search.net/cgi-bin/BaseHttpSearchInterface.fcgi", "tier": "T1", "category": "Science", "trust": 0.8, "auto": False, "notes": "P40 academic aggregator. Live: access denied (IP/UA) — auto=False."},
    # --- Patents ---
    {"key": "espacenet", "name": "Espacenet", "url": "https://worldwide.espacenet.com/searchResults", "tier": "T2", "category": "Science", "trust": 0.8, "auto": False, "notes": "P40 patent search. Live: HTTP 403 Cloudflare — auto=False."},
    {"key": "patentscope", "name": "WIPO PatentScope", "url": "https://patentscope.wipo.int/search/en/result.jsf", "tier": "T2", "category": "Science", "trust": 0.8, "auto": False, "notes": "P40 patent search. Live: JS/session-driven — auto=False."},
    {"key": "uspto", "name": "USPTO Patent API", "url": "https://api.uspto.gov/api/v1/patent/applications/search", "tier": "T2", "category": "Science", "trust": 0.85, "auto": False, "notes": "P40 patent API. Live: HTTP 401 (API key) — auto=False."},
    # --- OSS ---
    {"key": "gitlab", "name": "GitLab Projects", "url": "https://gitlab.com/api/v4/projects", "tier": "T1", "category": "Tools & Reverse Engineering", "trust": 0.8, "auto": True, "notes": "P40 keyless GitLab API. Live: JSON results."},
    {"key": "codeberg", "name": "Codeberg", "url": "https://codeberg.org/api/v1/repos/search", "tier": "T1", "category": "Tools & Reverse Engineering", "trust": 0.7, "auto": False, "notes": "P40 keyless Forgejo API. Live: HTTP 429 — auto=False."},
    {"key": "sourceforge", "name": "SourceForge", "url": "https://sourceforge.net/directory/", "tier": "T1", "category": "Tools & Reverse Engineering", "trust": 0.6, "auto": False, "notes": "P40 keyless HTML directory. Live: nav-only HTML, 0 result — auto=False."},
    {"key": "huggingface", "name": "Hugging Face Models", "url": "https://huggingface.co/api/models", "tier": "T1", "category": "Tools & Reverse Engineering", "trust": 0.75, "auto": True, "notes": "P40 keyless HF API. Live: JSON results."},
    {"key": "stackexchange", "name": "Stack Exchange API", "url": "https://api.stackexchange.com/2.3/search/advanced", "tier": "T1", "category": "Tools & Reverse Engineering", "trust": 0.75, "auto": True, "notes": "P40 keyless Stack Exchange API. Live: JSON results."},
    {"key": "pypi", "name": "PyPI", "url": "https://pypi.org/pypi", "tier": "T3", "category": "Tools & Reverse Engineering", "trust": 0.75, "auto": False, "notes": "P40 package index. Koi keyless search API nahi (per-package JSON only) — auto=False."},
    {"key": "npm", "name": "npm Registry", "url": "https://registry.npmjs.org/-/v1/search", "tier": "T1", "category": "Tools & Reverse Engineering", "trust": 0.7, "auto": True, "notes": "P40 keyless npm search. Live: JSON results."},
    {"key": "crates", "name": "crates.io", "url": "https://crates.io/api/v1/crates", "tier": "T1", "category": "Tools & Reverse Engineering", "trust": 0.7, "auto": True, "notes": "P40 keyless crates search. Live: JSON results."},
    # --- Archive ---
    {"key": "archive-search", "name": "Internet Archive Search", "url": "https://archive.org/advancedsearch.php", "tier": "T1", "category": "World", "trust": 0.75, "auto": True, "notes": "P40 keyless archive metadata API. Live: JSON results."},
    {"key": "openlibrary", "name": "Open Library", "url": "https://openlibrary.org/search.json", "tier": "T1", "category": "World", "trust": 0.75, "auto": True, "notes": "P40 keyless book search. Live: JSON results."},
    {"key": "gutendex", "name": "Gutendex", "url": "https://gutendex.com/books/", "tier": "T1", "category": "World", "trust": 0.7, "auto": False, "notes": "P40 keyless Gutenberg API. Live: read timeout — auto=False."},
    {"key": "googlebooks", "name": "Google Books API", "url": "https://www.googleapis.com/books/v1/volumes", "tier": "T1", "category": "World", "trust": 0.75, "auto": False, "notes": "P40 keyless Books API. Live: HTTP 429 quota — auto=False."},
    # --- News ---
    {"key": "bing-news", "name": "Bing News", "url": "https://www.bing.com/news/search", "tier": "T1", "category": "World", "trust": 0.7, "auto": True, "notes": "P40 keyless news HTML. Live: asli results."},
    {"key": "yahoo-news", "name": "Yahoo News", "url": "https://news.yahoo.com/search", "tier": "T1", "category": "World", "trust": 0.65, "auto": False, "notes": "P40 keyless news HTML. Live: HTTP 404 — auto=False."},
    # --- Social ---
    {"key": "bsky", "name": "Bluesky Public API", "url": "https://public.api.bsky.app/xrpc/", "tier": "T2", "category": "World", "trust": 0.6, "auto": False, "notes": "P40 public ATProto API. Live: search endpoint 501 — auto=False."},
    {"key": "mastodon", "name": "Mastodon Search", "url": "https://mastodon.social/api/v2/search", "tier": "T2", "category": "World", "trust": 0.55, "auto": False, "notes": "P40 federated search. Live: unauthenticated search empty — auto=False."},
    # --- TG dirs ---
    {"key": "tgstat", "name": "TGStat", "url": "https://tgstat.com/search", "tier": "T2", "category": "Telecom", "trust": 0.5, "auto": False, "notes": "P40 Telegram directory. Live: JS app shell, 0 result — auto=False."},
    {"key": "telemetr", "name": "Telemetr", "url": "https://telemetr.io/search", "tier": "T2", "category": "Telecom", "trust": 0.5, "auto": False, "notes": "P40 Telegram directory. Live: HTTP 403 Cloudflare — auto=False."},
    # P41 — dork + extra engines. Live check 2026-11-19 (JIN-Agent UA).
    # --- News RSS ---
    {"key": "bbc-news", "name": "BBC News", "url": "https://feeds.bbci.co.uk/news/rss.xml", "tier": "T0", "category": "World", "trust": 0.85, "auto": True, "notes": "P41 news RSS. Live: asli feed."},
    {"key": "aljazeera", "name": "Al Jazeera", "url": "https://www.aljazeera.com/xml/rss/all.xml", "tier": "T0", "category": "World", "trust": 0.8, "auto": True, "notes": "P41 news RSS. Live: asli feed."},
    {"key": "arstechnica", "name": "Ars Technica", "url": "https://feeds.arstechnica.com/arstechnica/index", "tier": "T0", "category": "World", "trust": 0.8, "auto": True, "notes": "P41 news RSS. Live: asli feed."},
    {"key": "wired", "name": "Wired", "url": "https://www.wired.com/feed", "tier": "T0", "category": "World", "trust": 0.8, "auto": True, "notes": "P41 news RSS. Live: asli feed."},
    {"key": "techcrunch", "name": "TechCrunch", "url": "https://techcrunch.com/feed/", "tier": "T0", "category": "World", "trust": 0.75, "auto": True, "notes": "P41 news RSS. Live: asli feed."},
    {"key": "theverge", "name": "The Verge", "url": "https://www.theverge.com/rss/index.xml", "tier": "T0", "category": "World", "trust": 0.75, "auto": True, "notes": "P41 news Atom. Live: asli feed."},
    {"key": "zdnet", "name": "ZDNet", "url": "https://www.zdnet.com/news/rss.xml", "tier": "T0", "category": "World", "trust": 0.7, "auto": True, "notes": "P41 news Atom. Live: asli feed."},
    {"key": "cnet", "name": "CNET", "url": "https://www.cnet.com/rss/news/", "tier": "T0", "category": "World", "trust": 0.7, "auto": True, "notes": "P41 news Atom. Live: asli feed."},
    {"key": "nytimes", "name": "New York Times", "url": "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml", "tier": "T0", "category": "World", "trust": 0.85, "auto": True, "notes": "P41 news RSS. Live: asli feed."},
    {"key": "wapo", "name": "Washington Post", "url": "https://feeds.washingtonpost.com/rss/technology", "tier": "T0", "category": "World", "trust": 0.85, "auto": False, "notes": "P41 news RSS. Live: HTTP 404 — auto=False."},
    {"key": "npr", "name": "NPR", "url": "https://feeds.npr.org/1001/rss.xml", "tier": "T0", "category": "World", "trust": 0.8, "auto": True, "notes": "P41 news RSS. Live: asli feed."},
    {"key": "reuters", "name": "Reuters", "url": "https://www.reutersagency.com/feed/", "tier": "T0", "category": "World", "trust": 0.9, "auto": False, "notes": "P41 news RSS. Live: HTTP 404 — auto=False."},
    {"key": "groundnews", "name": "Ground News", "url": "https://ground.news/rss", "tier": "T1", "category": "World", "trust": 0.6, "auto": False, "notes": "P41 news RSS. Live: HTTP 404 — auto=False."},
    # --- Academic ---
    {"key": "datacite", "name": "DataCite", "url": "https://api.datacite.org/dois", "tier": "T1", "category": "Science", "trust": 0.85, "auto": True, "notes": "P41 keyless DOI metadata API. Live: JSON results."},
    {"key": "orcid", "name": "ORCID", "url": "https://pub.orcid.org/v3.0/search", "tier": "T1", "category": "Science", "trust": 0.85, "auto": False, "notes": "P41 ORCID search. Live: sirf profiles (koi title/publication nahi) — auto=False."},
    {"key": "scilit", "name": "Scilit", "url": "https://api.scilit.net/api/publications", "tier": "T1", "category": "Science", "trust": 0.8, "auto": False, "notes": "P41 academic API. Live: HTTP 403 access denied — auto=False."},
    {"key": "fatcat", "name": "Fatcat", "url": "https://api.fatcat.wiki/v0/release/lookup", "tier": "T1", "category": "Science", "trust": 0.8, "auto": False, "notes": "P41 scholarly API. Live: timeout — auto=False."},
    {"key": "openaire", "name": "OpenAIRE", "url": "https://api.openaire.eu/search/publications", "tier": "T1", "category": "Science", "trust": 0.85, "auto": True, "notes": "P41 keyless OpenAIRE JSON. Live: results milte hain."},
    {"key": "hal", "name": "HAL Archives Ouvertes", "url": "https://api.archives-ouvertes.fr/search/", "tier": "T1", "category": "Science", "trust": 0.85, "auto": True, "notes": "P41 keyless HAL JSON. Live: results milte hain."},
    {"key": "citeseerx", "name": "CiteSeerX", "url": "https://citeseerx.ist.psu.edu/search", "tier": "T1", "category": "Science", "trust": 0.8, "auto": False, "notes": "P41 academic search. Live: HTTP 404 — auto=False."},
    {"key": "repec", "name": "IDEAS/RePEc", "url": "https://ideas.repec.org/cgi-bin/htsearch", "tier": "T1", "category": "Science", "trust": 0.75, "auto": False, "notes": "P41 RePEc search. Live: direct query URL results nahi deta (form/session) — auto=False."},
    {"key": "econpapers", "name": "EconPapers", "url": "https://econpapers.repec.org/scripts/search.pf", "tier": "T1", "category": "Science", "trust": 0.75, "auto": False, "notes": "P41 EconPapers search. Live: direct query URL results nahi deta (form/session) — auto=False."},
    {"key": "philpapers", "name": "PhilPapers", "url": "https://philpapers.org/advancedsearch", "tier": "T1", "category": "Science", "trust": 0.85, "auto": False, "notes": "P41 philosophy index. Live: HTTP 403 Cloudflare — auto=False."},
    {"key": "pubpsych", "name": "PubPsych", "url": "https://pubpsych.zpid.de/api/v1/search", "tier": "T1", "category": "Science", "trust": 0.8, "auto": False, "notes": "P41 psychology index. Live: HTTP 404 — auto=False."},
    # --- Patents ---
    {"key": "ipaustralia", "name": "IP Australia", "url": "https://search.ipaustralia.gov.au/patents/search", "tier": "T2", "category": "Science", "trust": 0.8, "auto": False, "notes": "P41 patent search. Live: HTTP 503 — auto=False."},
    {"key": "jplatpat", "name": "J-PlatPat", "url": "https://j-platpat.inpit.go.jp/", "tier": "T2", "category": "Science", "trust": 0.8, "auto": False, "notes": "P41 patent search. Live: timeout — auto=False."},
    {"key": "kipris", "name": "KIPRIS", "url": "https://kris.kipris.or.kr/", "tier": "T2", "category": "Science", "trust": 0.8, "auto": False, "notes": "P41 patent search. Live: connection refused — auto=False."},
    # --- Archive / data ---
    {"key": "commoncrawl", "name": "Common Crawl Index", "url": "https://index.commoncrawl.org/", "tier": "T1", "category": "World", "trust": 0.7, "auto": False, "notes": "P41 web index. Live: HTTP 504 — auto=False."},
    {"key": "loc", "name": "Library of Congress", "url": "https://www.loc.gov/search/", "tier": "T1", "category": "World", "trust": 0.85, "auto": False, "notes": "P41 library search. Live: HTTP 403 Cloudflare — auto=False."},
    {"key": "worldcat", "name": "WorldCat", "url": "https://search.worldcat.org/", "tier": "T1", "category": "World", "trust": 0.75, "auto": False, "notes": "P41 library search. Live: HTTP 403 Cloudflare — auto=False."},
    {"key": "usgs", "name": "USGS Earthquakes", "url": "https://earthquake.usgs.gov/fdsnws/event/1/query", "tier": "T1", "category": "World", "trust": 0.85, "auto": True, "notes": "P41 keyless GeoJSON feed. Live: results milte hain."},
    {"key": "weather", "name": "NOAA Weather Alerts", "url": "https://api.weather.gov/alerts", "tier": "T1", "category": "World", "trust": 0.85, "auto": True, "notes": "P41 keyless alerts JSON. Live: results milte hain."},
    {"key": "reliefweb", "name": "ReliefWeb", "url": "https://api.reliefweb.int/v2/reports", "tier": "T1", "category": "World", "trust": 0.8, "auto": False, "notes": "P41 humanitarian API. Live: HTTP 403 approved appname zaroori — auto=False."},
    # --- Web ---
    {"key": "wiby", "name": "Wiby", "url": "https://wiby.me/", "tier": "T1", "category": "World", "trust": 0.6, "auto": True, "notes": "P41 keyless indie web search. Live: results milte hain."},
    {"key": "rightdao", "name": "RightDAO", "url": "https://rightdao.com/search", "tier": "T1", "category": "World", "trust": 0.55, "auto": True, "notes": "P41 keyless web search. Live: results milte hain."},
    {"key": "lyzem", "name": "Lyzem", "url": "https://lyzem.com/search", "tier": "T1", "category": "Telecom", "trust": 0.55, "auto": True, "notes": "P43 Telegram-wide search engine (channel/group/bot/post/article) — bina login, bina key. `channels.web_search_probe` isko discovery ke liye use karta hai; content items ka adapter nahi."},
    # --- TG / social ---
    {"key": "lemmy", "name": "Lemmy", "url": "https://lemmy.ml/api/v3/search", "tier": "T2", "category": "World", "trust": 0.6, "auto": True, "notes": "P41 keyless Lemmy community search. Live: JSON results."},
    {"key": "4cdn", "name": "4chan", "url": "https://a.4cdn.org/", "tier": "T2", "category": "Telecom", "trust": 0.5, "auto": False, "notes": "P41 imageboard. Live: HTTP 404 (search endpoint nahi) — auto=False."},
    {"key": "8kun", "name": "8kun", "url": "https://8kun.top/", "tier": "T2", "category": "Telecom", "trust": 0.4, "auto": False, "notes": "P41 imageboard. Live: HTTP 404 — auto=False."},
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


def _resolved_addresses(host: str, port: int) -> list[str]:
    """Hostname ko DNS se resolve karo (socket.getaddrinfo, SOCK_STREAM)."""
    for item in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM):
        yield item[4][0]


def trusted_public_endpoint(url: str) -> bool:
    """Less strict check for a USER-supplied custom LLM host (no IP literals).

    **SSRF (P1-5):** hostname ke saare resolved IP ``ipaddress`` par chalte
    hain — koi bhi IP private / loopback / link-local / reserved / multicast /
    unspecified ho to reject. DNS fail hon to bhi reject. Taake ``foo.example``
    jaisa host jo ``169.254.169.254`` par resolve ho, pass na ho.
    """
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
        try:
            port = int(p.port) if p.port is not None else 443
        except ValueError:
            return False
        if port not in (80, 443):
            return False
        try:
            addresses = list(_resolved_addresses(host, port))
        except (socket.gaierror, OSError, ValueError):
            return False
        if not addresses:
            return False
        for raw in addresses:
            try:
                ip = ipaddress.ip_address(str(raw).split("%")[0])
            except ValueError:
                return False
            if (ip.is_private or ip.is_loopback or ip.is_link_local or
                    ip.is_reserved or ip.is_multicast or ip.is_unspecified or
                    not ip.is_global):
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
