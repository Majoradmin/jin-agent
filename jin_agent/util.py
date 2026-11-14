"""Small, dependency-free helpers shared by every JIN Agent module."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

STOP_WORDS = frozenset({
    "or", "and", "the", "a", "an", "of", "in", "on", "for", "to", "with",
    "is", "are", "new", "latest", "about", "ka", "ke", "ki", "kya",
    "hai", "mein", "par", "se", "aur", "kaise", "kro", "karo",
})


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def epoch() -> float:
    return datetime.now(timezone.utc).timestamp()


def parse_date(raw) -> str:
    """Best-effort RFC822 / ISO8601 / plain-date parser. Never fabricates."""
    s = str(raw or "").strip()
    if not s:
        return ""
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    except ValueError:
        pass
    try:
        d = parsedate_to_datetime(s)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    except Exception:
        pass
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d %b %Y", "%Y%m%d"):
        try:
            d = datetime.strptime(s[:19], fmt).replace(tzinfo=timezone.utc)
            return d.isoformat().replace("+00:00", "Z")
        except ValueError:
            continue
    return ""


def days_since(iso: str):
    if not iso:
        return None
    try:
        d = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - d).total_seconds() / 86400.0)
    except Exception:
        return None


def sha256(text) -> str:
    return hashlib.sha256(str(text or "").encode("utf-8", "replace")).hexdigest()


def canonical_url(url: str) -> str:
    try:
        p = urlsplit(str(url or "").strip())
        if p.scheme.lower() not in ("http", "https") or not p.netloc:
            return ""
        query = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
                 if not k.lower().startswith(("utm_", "fbclid", "gclid", "igshid", "mc_"))]
        host = (p.hostname or "").lower().rstrip(".")
        port = ""
        try:
            if p.port and p.port not in (80, 443):
                port = ":" + str(p.port)
        except ValueError:
            return ""
        path = re.sub(r"/+$", "", p.path) or "/"
        return urlunsplit((p.scheme.lower(), host + port, path, urlencode(query), ""))
    except Exception:
        return ""


def fingerprint(title: str, url: str = "") -> str:
    norm = re.sub(r"[^a-z0-9]+", " ", str(title or "").lower()).strip()[:180]
    return sha256(norm or canonical_url(url))[:24]


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "svg", "head"):
            self.skip += 1
        if tag in ("p", "br", "div", "li", "h1", "h2", "h3", "h4", "tr", "section"):
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg", "head") and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)

    def text(self) -> str:
        return " ".join("".join(self.parts).split())


def strip_html(raw, limit: int = 20000) -> str:
    parser = _TextExtractor()
    try:
        parser.feed(str(raw or "")[:limit])
        return parser.text()[:limit]
    except Exception:
        return " ".join(re.sub(r"<[^>]+>", " ", str(raw or "")).split())[:limit]


def clean_text(raw, limit: int = 8000) -> str:
    s = strip_html(raw, limit)
    s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", s)
    s = re.sub(r"[ \t]{2,}", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()[:limit]


def terms(query, maxn: int = 12) -> list[str]:
    words = re.findall(r"[a-z0-9][a-z0-9._-]{1,}", str(query or "").lower())
    out: list[str] = []
    for word in words:
        if len(word) < 2 or word in STOP_WORDS or word in out:
            continue
        out.append(word)
        if len(out) >= maxn:
            break
    return out


def clamp(value, lo, hi, default):
    try:
        x = type(default)(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, x))


def truncate(text, n: int = 320) -> str:
    s = str(text or "").strip()
    return s if len(s) <= n else s[: n - 1].rstrip() + "\u2026"


def safe_filename(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", str(name or "report")).strip("-")[:80] or "report"
