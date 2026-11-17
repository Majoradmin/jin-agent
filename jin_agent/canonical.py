"""P27 - URL canonicalisation, content hashing and near-duplicate detection.

The archive is a firehose: the same story arrives from many adapters with
different tracking parameters, redirect wrappers and headline wording. This
module gives the pipeline ONE deterministic answer for:

  * "is this the same URL?"      -> :func:`canonicalize`
  * "is this the same content?"  -> :func:`content_hash`
  * "is this the same headline?" -> :func:`near_duplicate_titles` (token Jaccard)

Everything here is pure and offline: no sockets, no DNS, no redirect following.
Known redirector wrappers are unwrapped by reading their query string only.
"""

from __future__ import annotations

import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from . import util

# Query parameters that never change what a page says.
TRACKING_PREFIXES = ("utm_", "pk_", "mtm_", "hsa_", "mc_", "vero_", "oly_",
                     "at_", "_hs")
TRACKING_KEYS = frozenset({
    "fbclid", "gclid", "dclid", "gbraid", "wbraid", "msclkid", "yclid",
    "igshid", "twclid", "ttclid", "li_fat_id", "ref", "ref_src", "ref_url",
    "source", "spm", "cmpid", "campaign", "ncid", "sr_share", "_ga", "_gl",
})

# Hosts whose whole job is to wrap another URL in a query parameter.
REDIRECT_HOSTS = frozenset({
    "www.google.com", "google.com", "l.facebook.com", "lm.facebook.com",
    "out.reddit.com", "html.duckduckgo.com", "duckduckgo.com",
    "www.youtube.com", "youtube.com",
})
REDIRECT_PARAMS = ("url", "u", "q", "target", "dest", "destination",
                   "redirect", "redirect_uri", "to", "uddg", "r")

DEFAULT_NEAR_DUP = 0.72
MAX_URL_CHARS = 2000


def _unwrap(url: str, depth: int = 0) -> str:
    """Read a redirector's query string and return the wrapped target (offline)."""
    if depth > 2:
        return url
    try:
        p = urlsplit(url)
    except Exception:
        return url
    host = (p.hostname or "").lower().rstrip(".")
    if host not in REDIRECT_HOSTS:
        return url
    pairs = dict(parse_qsl(p.query, keep_blank_values=True))
    for key in REDIRECT_PARAMS:
        target = str(pairs.get(key) or "").strip()
        if target.lower().startswith(("http://", "https://")):
            return _unwrap(target, depth + 1)
    return url


def canonicalize(url: str, resolve_redirects: bool = True) -> str:
    """Return a stable http(s) URL, or ``""`` when the input is unusable.

    Lowercases the host, drops default ports / fragments / trailing slashes,
    removes tracking parameters, sorts the remaining query and unwraps common
    redirectors without any network access.
    """
    raw = str(url or "").strip()
    if not raw or len(raw) > MAX_URL_CHARS:
        return ""
    if resolve_redirects:
        raw = _unwrap(raw)
    try:
        p = urlsplit(raw)
    except Exception:
        return ""
    scheme = p.scheme.lower()
    if scheme not in ("http", "https") or not p.netloc:
        return ""
    if p.username or p.password:
        return ""
    host = (p.hostname or "").lower().rstrip(".")
    if not host:
        return ""
    port = ""
    try:
        if p.port and not ((p.port == 80 and scheme == "http") or
                           (p.port == 443 and scheme == "https")):
            port = ":" + str(p.port)
    except ValueError:
        return ""
    path = re.sub(r"/{2,}", "/", p.path or "/")
    path = re.sub(r"/+$", "", path) or "/"
    query = []
    for key, value in parse_qsl(p.query, keep_blank_values=True):
        low = key.lower()
        if low in TRACKING_KEYS or low.startswith(TRACKING_PREFIXES):
            continue
        query.append((key, value))
    query.sort(key=lambda kv: (kv[0].lower(), kv[1]))
    return urlunsplit((scheme, host + port, path,
                       urlencode(query, doseq=True), ""))


def same_url(a: str, b: str) -> bool:
    """Two raw URLs point at the same canonical resource."""
    ca, cb = canonicalize(a), canonicalize(b)
    return bool(ca and cb and ca == cb)


def content_hash(title: str, excerpt: str = "", body: str = "",
                 limit: int = 4000) -> str:
    """Hash of the normalised visible text (case / spacing insensitive)."""
    blob = " ".join(
        (str(title or "") + " " + str(excerpt or "") + " " + str(body or ""))
        .lower().split())[:limit]
    return hashlib.sha256(blob.encode("utf-8", "replace")).hexdigest()


def title_tokens(title: str) -> set[str]:
    """Significant lowercase tokens of a headline (stop words removed)."""
    return set(util.terms(title, 30))


def jaccard(a: str, b: str) -> float:
    """Token-set Jaccard similarity in [0.0, 1.0]."""
    ta, tb = title_tokens(a), title_tokens(b)
    if not ta or not tb:
        return 0.0
    return round(len(ta & tb) / len(ta | tb), 4)


def near_duplicate_titles(a: str, b: str, threshold: float = DEFAULT_NEAR_DUP) -> bool:
    """Same story with slightly different wording (not an exact match)."""
    left, right = str(a or "").strip(), str(b or "").strip()
    if not left or not right:
        return False
    if left.lower() == right.lower():
        return True
    return jaccard(left, right) >= float(threshold)


def dedupe_key(item: dict, threshold: float = DEFAULT_NEAR_DUP) -> str:
    """Stable identity for a record: canonical URL, else fingerprint / guid."""
    canonical = canonicalize(item.get("canonical") or item.get("url") or "")
    if canonical:
        return canonical
    return (str(item.get("fingerprint") or "").strip()
            or str(item.get("guid") or "").strip()
            or util.fingerprint(item.get("title", ""), item.get("url", "")))


def dedupe_records(records: list[dict],
                   threshold: float = DEFAULT_NEAR_DUP) -> list[dict]:
    """Drop exact-URL and near-duplicate-title records, keeping the first.

    Order is preserved (callers rank before calling this where ranking matters).
    """
    kept: list[dict] = []
    urls: set[str] = set()
    for rec in records or []:
        canonical = canonicalize(rec.get("canonical") or rec.get("url") or "")
        title = str(rec.get("title") or "")
        if canonical and canonical in urls:
            continue
        if any(near_duplicate_titles(title, other.get("title", ""), threshold)
               for other in kept):
            continue
        if canonical:
            urls.add(canonical)
        kept.append(rec)
    return kept
