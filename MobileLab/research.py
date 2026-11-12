"""Real-time mobile-software research agent (Python 3.13 stdlib only).

Fetches a FIXED allowlist of public RSS / Atom / JSON feed sources (GSMArena,
XDA, Android Authority, Android Police, 9to5Google, SamMobile, Apple Newsroom,
Google News RSS, HN Algolia and GitHub Releases) with an 8-16 worker
ThreadPoolExecutor and a 10s timeout. Items are filtered by query terms,
exclude words, category, age (days) and a minimum score, then ranked by the
recency/term/category score in :func:`score_item`. Every result gets a
deterministic Roman-Urdu "khulasa" from :func:`make_khulasa`; an optional
OpenAI-compatible LLM may rewrite the top notes (:func:`llm_rewrite`).

Outbound URLs are SSRF-validated before any urlopen (see :func:`validate_url`).
The run degrades gracefully OFFLINE: each source is isolated, so timeouts,
non-2xx responses, unreachable hosts and malformed content are reported in the
``diagnostics`` list instead of crashing. With ZERO network the app still
returns a well-formed (possibly empty) structured result.
"""
from __future__ import annotations

import gzip
import html
import ipaddress
import json
import logging
import os
import re
import socket
import ssl
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

log = logging.getLogger(__name__)

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) MobileLab/1.0 (local research agent)"
TIMEOUT = 10

# Optional LLM: local runtimes use APP-OWNED loopback URLs, never a URL typed by
# the user. This keeps the QA #6 SSRF guard intact for user-supplied endpoints
# while still allowing a fully local Ollama / LM Studio model (C7 / C11).
LOCAL_LLM_ENDPOINTS = {
    "ollama": "http://127.0.0.1:11434/v1",
    "lmstudio": "http://127.0.0.1:1234/v1",
}
LLM_PROVIDERS = ("off", "ollama", "lmstudio", "custom")


def _public_endpoint_ok(url: str) -> bool:
    """Cheap, DNS-free safety check for a user-supplied custom LLM endpoint."""
    try:
        p = urllib.parse.urlsplit(str(url or "").strip())
        if p.scheme not in ("http", "https") or p.username or p.password:
            return False
        host = (p.hostname or "").lower().rstrip(".")
        if (not host or host in ("localhost", "metadata", "metadata.google.internal",
                                 "instance-data", "metadata.goog")
                or host.endswith(".localhost") or host.endswith(".internal")):
            return False
        try:
            ip = ipaddress.ip_address(host)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return False
        except ValueError:
            pass                      # public hostname: no live DNS (offline app)
        return True
    except Exception:
        return False


def resolve_llm(settings: dict) -> dict:
    """Resolve a SAFE description of the optional LLM configuration.

    ``off`` / empty  -> rule-based Roman Urdu (default, zero network).
    ``ollama`` / ``lmstudio`` -> app-owned loopback URL, NO API key needed.
    ``custom`` -> user endpoint + key + model, public http/https only.
    """
    s = settings or {}
    provider = str(s.get("llm_provider") or "").strip().lower()
    model = str(s.get("llm_model") or "").strip()
    key = str(s.get("llm_key") or "").strip()
    endpoint = str(s.get("llm_endpoint") or "").strip().rstrip("/")

    if not provider and endpoint:
        provider = "custom"           # backward compatibility (pre-P14 settings)
    if provider not in LLM_PROVIDERS:
        provider = "off"

    base, key_required, reason = "", False, ""
    if provider in LOCAL_LLM_ENDPOINTS:
        base, key_required = LOCAL_LLM_ENDPOINTS[provider], False
    elif provider == "custom":
        key_required = True                 # only a custom remote endpoint needs a key
        if not endpoint:
            reason = "Custom provider chuna hai magar endpoint khali hai."
        elif not _public_endpoint_ok(endpoint):
            reason = "Custom endpoint SSRF guard se block hua (sirf public http/https)."
        else:
            base = endpoint
    else:
        reason = ("Model band hai: koi provider set nahi. Rule-based Roman Urdu "
                  "khulasa chal raha hai (ye bug nahi).")

    if base and not model:
        reason = "Model ka naam khali hai (maslan qwen2.5:0.5b ya gpt-4o-mini)."
    elif base and key_required and not key:
        reason = "Custom endpoint ke liye API key zaroori hai."

    enabled = bool(base and model and (key or not key_required))
    return {
        "enabled": enabled,
        "provider": provider,
        "base": base,
        "model": model,
        "key_required": key_required,
        "key_present": bool(key),
        "mode": "llm" if enabled else "rule_based",
        "reason": "" if enabled else (reason or "Model configuration adhoori hai."),
    }


def llm_status(settings: dict) -> dict:
    """Public, key-free LLM diagnostics for ``/api/status`` and Settings UI."""
    c = resolve_llm(settings)
    return {k: c[k] for k in ("enabled", "provider", "model", "mode", "reason",
                              "key_required")} | {"endpoint": c["base"]}


def llm_probe(settings: dict, timeout: float = 8) -> dict:
    """Test the configured model with one tiny request. Never leaks the key."""
    c = resolve_llm(settings)
    info = {"ok": False, "provider": c["provider"], "model": c["model"],
            "endpoint": c["base"], "mode": c["mode"]}
    if not c["enabled"]:
        info["error"] = c["reason"] or "Model configure nahi hai."
        return info
    url = c["base"] if c["base"].endswith("/chat/completions") else c["base"] + "/chat/completions"
    payload = {"model": c["model"],
               "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
               "temperature": 0, "max_tokens": 8}
    headers = {"Content-Type": "application/json", "User-Agent": UA}
    key = str(settings.get("llm_key") or "").strip()
    if key:
        headers["Authorization"] = "Bearer " + key
    started = time.monotonic()
    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                     headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
        info.update({"ok": True,
                     "reply": str(data["choices"][0]["message"]["content"]).strip()[:80],
                     "latency_ms": round((time.monotonic() - started) * 1000)})
    except Exception as e:
        log.warning("LLM probe failed (%s): %s", type(e).__name__, e)
        info.update({"ok": False,
                     "error": ("Model se rabta nahi ho saka (%s). Local runtime chal raha "
                               "hai aur model download hua hai?" % type(e).__name__),
                     "latency_ms": round((time.monotonic() - started) * 1000)})
    return info

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
# HTTP helpers (SSRF-safe)
# ---------------------------------------------------------------------------

def _feed_host_allowlist() -> frozenset:
    """Return the FIXED feed-host allowlist, derived from the source config.

    No new hosts are introduced here. The three query-source hosts mirror the
    URLs built in :func:`_build_jobs` (Google News RSS, HN Algolia, GitHub
    Releases); the rest come from :data:`RSS_SOURCES`.
    """
    hosts = set()
    for s in RSS_SOURCES:
        h = urllib.parse.urlsplit(s["url"]).hostname
        if h:
            hosts.add(h.lower())
    hosts.update(("news.google.com", "hn.algolia.com", "api.github.com"))
    return frozenset(hosts)


FEED_HOSTS = _feed_host_allowlist()

_BLOCKED_HOST_NAMES = frozenset({
    "localhost", "metadata", "metadata.google.internal", "metadata.goog",
})
_BLOCKED_HOST_SUFFIXES = (".localhost", ".local", ".internal")


def _is_public_ip(ip) -> bool:
    """True only for globally-routable unicast IPs (blocks all SSRF ranges)."""
    return not (ip.is_private or ip.is_loopback or ip.is_link_local or
                ip.is_multicast or ip.is_reserved or ip.is_unspecified) and ip.is_global


def validate_url(url: str, *, allowlist: frozenset | None = None) -> str:
    """Validate an outbound URL before any urlopen (QA #6 SSRF policy).

    Enforces http/https only, rejects IP-literal hosts and private / loopback /
    link-local / metadata hostnames, optionally requires an allowlisted host,
    and validates every RESOLVED destination IP via :mod:`socket` +
    :mod:`ipaddress`. Returns the URL on success; raises ValueError with a
    clear Roman-Urdu reason otherwise. When DNS resolution itself fails (e.g.
    offline) the URL is left to urlopen so the failure degrades gracefully.
    """
    text = url if isinstance(url, str) else str(url or "")
    parts = urllib.parse.urlsplit(text.strip())
    scheme = parts.scheme.lower()
    if scheme not in ("http", "https"):
        raise ValueError("URL sirf http ya https ho sakta hai; doosri scheme mana hai.")
    try:
        host = (parts.hostname or "").lower()
        port = parts.port
    except ValueError as e:
        raise ValueError("URL ka host/port theek nahi: %s" % e)
    host = host.rstrip(".")
    if not host:
        raise ValueError("URL mein host maujood nahi hai.")
    # IP-literal hosts (v4/v6) are never allowed; feeds use hostnames only.
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError("Host IP literal nahi ho sakta (SSRF policy): %s" % host)
    if (host in _BLOCKED_HOST_NAMES or host.endswith(_BLOCKED_HOST_SUFFIXES)
            or "metadata" in host):
        raise ValueError("Local / metadata host mana hai (SSRF policy): %s" % host)
    if allowlist is not None and host not in allowlist:
        raise ValueError("Yeh host feed allowlist mein nahi hai: %s" % host)
    # Validate the RESOLVED destination IP(s). Fail open only when DNS itself
    # fails, so offline runs still reach urlopen and are reported gracefully.
    try:
        infos = socket.getaddrinfo(host, port or (443 if scheme == "https" else 80),
                                   type=socket.SOCK_STREAM)
    except OSError:
        return text
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not _is_public_ip(ip):
            raise ValueError("Resolved IP %s private/loopback/link-local/metadata range mein hai." % ip)
    return text


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Re-validate every redirect target; ban internal / non-http(s) redirects."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl)  # raises ValueError on an unsafe redirect target
        return super().redirect_request(req, fp, code, msg, headers, newurl)


# One process-wide opener so the module-level urllib.request.urlopen (which
# tests mock) still uses our redirect handler. HTTPS keeps default certificate
# verification via an explicit create_default_context().
_SSL_CONTEXT = ssl.create_default_context()
_SAFE_OPENER = urllib.request.build_opener(
    urllib.request.HTTPSHandler(context=_SSL_CONTEXT), _SafeRedirectHandler())
urllib.request.install_opener(_SAFE_OPENER)


def fetch(url: str, timeout: int = TIMEOUT) -> str:
    """Fetch one allowlisted feed URL over http/https after SSRF validation.

    Calls :func:`validate_url` with the fixed :data:`FEED_HOSTS` allowlist
    before any urlopen. Rejections and network errors propagate so
    :func:`_run_job` can report them in diagnostics instead of crashing.
    """
    validate_url(url, allowlist=FEED_HOSTS)
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/rss+xml, application/atom+xml, application/xml, application/json, text/xml, */*",
        "Accept-Language": "en-US,en;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
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
    """Parse an RSS/Atom feed string into normalized item dicts (never raises)."""
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
    """Parse a GitHub Releases JSON array into normalized item dicts."""
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
    """Parse an HN Algolia JSON response into normalized item dicts."""
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
    """Split a query into lowercased, de-stopworded search terms."""
    q = re.sub(r'"([^"]+)"', r" \1 ", q or "")
    parts = re.split(r"\s+OR\s+|\s+or\s+|[,;|]+|\s+", q, flags=re.I)
    out = []
    for p in parts:
        t = p.strip().lower().strip("()\"'")
        if len(t) >= 3 and t not in STOPWORDS and t not in out:
            out.append(t)
    return out[:14]


def category_of(text: str) -> str:
    """Classify text into one of the fixed category ids (or ``general``)."""
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
    """Score an item by matched terms, category and recency; return (score, matched)."""
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
    """Build the deterministic Roman-Urdu one-paragraph khulasa for an item."""
    src = rec.get("source", "Source")
    when = rec.get("published") or "haal hi mein"
    terms = ", ".join(matched[:5]) if matched else CATEGORY_LABELS.get(cat, "mobile software")
    base = (f"{src} ki ye khabar {when} par aayi hai. Is mein {terms} ka zikr hai. "
            f"Zaroori baat: {ROMAN_URDU_HINT.get(cat, ROMAN_URDU_HINT['general'])}")
    if score >= 6:
        base += " Ye aap ke kaam se kaafi mutaliqa hai — pehle isay parhein."
    return base


def llm_rewrite(text: str, settings: dict) -> str | None:
    """Optional OpenAI-compatible rewrite of a Roman-Urdu khulasa.

    Local providers (Ollama / LM Studio) need NO API key; custom public
    endpoints still need one. Returns None when the model is off or the call
    fails. Any runtime failure is logged (QA #12), never silently swallowed.
    """
    c = resolve_llm(settings or {})
    if not c["enabled"]:
        return None
    url = c["base"] if c["base"].endswith("/chat/completions") else c["base"] + "/chat/completions"
    payload = {
        "model": c["model"],
        "messages": [
            {"role": "system", "content": "Rewrite the given mobile-software news note in natural Roman Urdu (Urdu written in Latin script). Keep technical terms like firmware, firehose, preloader, bootloader, FRP, EMUI in English. Be concise, 2 sentences. Never add facts that are not in the source."},
            {"role": "user", "content": text},
        ],
        "temperature": 0.2, "max_tokens": 180,
    }
    headers = {"Content-Type": "application/json", "User-Agent": UA}
    key = str((settings or {}).get("llm_key") or "").strip()
    if key:
        headers["Authorization"] = "Bearer " + key
    try:
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"),
            headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=25) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        log.warning("LLM rewrite failed (%s): %s", type(e).__name__, e)
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
    """Fetch + parse one source; always return (items, diagnostic), never raise.

    Timeouts, non-2xx responses, unreachable hosts, rejected URLs and malformed
    content all produce a structured diagnostic so the run degrades gracefully.
    """
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
        if not text or not text.strip() or not items:
            diag["error"] = "malformed ya khali content (0 items)"
            return [], diag
        diag.update(ok=True, count=len(items))
        return items, diag
    except Exception as e:
        diag["error"] = f"{type(e).__name__}: {str(e)[:110]}"
        return [], diag


_CACHE: dict[str, tuple[float, dict]] = {}


def research(params: dict, settings: dict | None = None) -> dict:
    """Run the full research pipeline and return a structured result.

    Filters, scores and summarizes feed items, optionally rewrites the top
    khulasa via an LLM, and always reports per-source success/failure in
    ``diagnostics``. Never raises on network failure; works with ZERO network.
    """
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
            try:
                items, diag = fu.result()
            except Exception as e:  # last-resort guard: a run must never crash
                items, diag = [], {"source": "unknown", "ok": False, "count": 0,
                                   "error": f"{type(e).__name__}: {str(e)[:110]}"}
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

    # Optional LLM rewrite for top items only (local providers need no API key)
    if resolve_llm(settings or {})["enabled"]:
        for r in results[:12]:
            better = llm_rewrite(r["khulasa"] + " | Source: " + r["title"], settings)
            if better:
                r["khulasa"] = better
                r["llm"] = True

    sources_ok = sum(1 for d in diagnostics if d["ok"])
    out = {
        "query": query, "preset": preset["id"], "category": want_cat,
        "items": results, "total": len(unique), "returned": len(results),
        "terms": terms, "diagnostics": sorted(diagnostics, key=lambda d: d["source"]),
        "sources_total": len(diagnostics), "sources_ok": sources_ok,
        "sources_failed": len(diagnostics) - sources_ok,
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "cached": False,
    }
    _CACHE[key] = (time.time(), out)
    return out
