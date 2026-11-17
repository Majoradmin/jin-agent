"""Normalizer: one raw adapter item -> one canonical archive record."""

from __future__ import annotations

import re

from . import canonical, config, util

TOPIC_RULES = [
    ("Security", ["security", "bulletin", "cve-", "vulnerability", "patch", "exploit",
                  "malware", "attestation", "smr", "secure boot"]),
    ("Hardware & Chipsets", ["chipset", "mediatek", "mtk", "dimensity", "qualcomm",
                             "snapdragon", "firehose", "edl", "9008", "sahara", "soc", "silicon"]),
    ("Tools & Reverse Engineering", ["github", "mtkclient", "qfil", "sp flash", "odin",
                                     "loader", "tool", "release v", "rawprogram", "ipsw"]),
    ("iOS", ["iphone", "ipad", "ios ", "apple", "ipsw", "activation lock"]),
    ("Android", ["android", "one ui", "pixel", "emui", "harmonyos", "huawei", "kirin", "samsung"]),
    ("AI & Local LLM", ["llm", "ollama", "lm studio", "qwen", "llama", "prompt injection",
                        "model", "embedding", "ai agent"]),
    ("Telecom", ["telecom", "carrier", "5g", "modem", "sim", "network operator"]),
    ("Business & Policy", ["policy", "regulator", "compliance", "business", "right-to-repair", "law"]),
    ("Science", ["arxiv", "paper", "study", "research", "preprint", "doi", "academic"]),
    ("World", ["world", "global", "gdelt", "news index", "international"]),
    ("Mobile & Firmware", ["firmware", "ota", "stock rom", "rollout", "preloader", "scatter",
                           "build number", "binary revision", "flash"]),
]

ENTITY_PATTERNS = [
    ("cve", re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.I)),
    ("model", re.compile(r"\b(?:SM-[A-Z0-9]{4,10}|CPH\d{4}|MT\d{4,5}|SDM?\d{3,4}|ELE-[A-Z0-9]+)\b", re.I)),
    ("version", re.compile(r"\b(?:v\d+\.\d+(?:\.\d+)?|Android\s?1\d|EMUI\s?\d+|One\s?UI\s?\d+|iOS\s?\d+)\b", re.I)),
    ("brand", re.compile(r"\b(?:MediaTek|Qualcomm|Samsung|Huawei|Apple|Google|Xiaomi|Oppo|Vivo|OnePlus)\b", re.I)),
]


def infer_category(text: str, fallback: str = "Custom Watchlist") -> str:
    blob = str(text or "").lower()
    best, hits = fallback, 0
    for category, keywords in TOPIC_RULES:
        n = sum(1 for kw in keywords if kw in blob)
        if n > hits:
            best, hits = category, n
    return best


def extract_entities(text: str) -> list[dict]:
    out, seen = [], set()
    for kind, pattern in ENTITY_PATTERNS:
        for match in pattern.findall(str(text or ""))[:8]:
            value = str(match).strip()
            key = (kind, value.lower())
            if key in seen or not value:
                continue
            seen.add(key)
            out.append({"kind": kind, "value": value[:120]})
    return out[:24]


def normalize(raw: dict, date_checked: str = "", cfg: dict | None = None) -> dict | None:
    """Return a canonical record, or None for unusable input."""
    cfg = cfg or config.load()
    title = util.truncate(util.clean_text(raw.get("title"), 300), 240)
    url = str(raw.get("url") or "").strip()[:1000]
    if not title or not url:
        return None
    excerpt = util.clean_text(raw.get("excerpt"), 600)
    body = util.clean_text(raw.get("body") or excerpt, 8000)
    source = str(raw.get("source") or "Unknown")[:120]
    source_key = str(raw.get("source_key") or "unknown")[:60]
    canonical_url = canonical.canonicalize(url)
    fp = util.fingerprint(title, canonical_url or url)
    blob = title + " " + excerpt
    category = infer_category(blob, str(raw.get("category") or "Custom Watchlist"))
    link_only = bool(raw.get("link_only"))
    offline = bool(raw.get("offline"))
    return {
        "guid": source_key + ":" + fp,
        "url": url, "canonical": canonical_url or url, "title": title,
        "source": source, "source_key": source_key,
        "tier": str(raw.get("tier") or "T0")[:4],
        "trust": util.clamp(raw.get("trust"), 0.0, 1.0, 0.5),
        "trust_label": "",
        "category": category,
        "published": util.parse_date(raw.get("published")),
        "date_checked": date_checked or util.now_iso(),
        "fetched_at": util.now_iso(),
        "excerpt": excerpt, "body": body,
        "fingerprint": fp,
        "content_hash": canonical.content_hash(title, excerpt, body),
        "entities": extract_entities(blob),
        "score": 0.0, "reasons": [], "confidence": 0.0,
        "verified": False, "cross_verified": False,
        "link_only": link_only, "useful": 0,
        "meta": {"kind": raw.get("kind", ""), "offline": offline,
                 "url_fetched": False, "adapter": source_key},
    }
