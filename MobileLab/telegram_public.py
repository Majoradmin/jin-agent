"""Telegram public-preview reader (P13) - no account, no private data.

Telegram exposes a public, server-rendered preview for public channels at
``https://t.me/s/<channel>`` (and ``?q=<query>`` for in-channel search). This
module reads only that page with a normal HTTP GET, validates the URL through
the existing SSRF guard, caps the response size and parses message text,
timestamp and permalink.

What this module deliberately does NOT do
------------------------------------------
* no Telegram account, phone number, session or MTProto userbot
* no private groups / chats / invite links (``t.me/+...``)
* no login, no cookies, no scraping of authenticated content
* no writes, no joins, no message sending

Standard library only.
"""
from __future__ import annotations

import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser

from research import clean_text, validate_url

TIMEOUT = 10
MAX_BYTES = 2_000_000
ALLOWED_HOSTS = frozenset({"t.me", "www.t.me", "telegram.me", "www.telegram.me"})
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) MobileLab/1.0 (public telegram preview)"

_CHANNEL_RE = re.compile(r"^[A-Za-z0-9_]{3,64}$")
_VOID_TAGS = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
})


def normalize_channel(raw: str) -> str:
    """Accept @name, name, t.me/name or t.me/s/name and return the username."""
    text = str(raw or "").strip()
    text = re.sub(r"^https?://", "", text, flags=re.I)
    text = re.sub(r"^(?:www\.)?(?:t|telegram)\.me/", "", text, flags=re.I)
    text = text.split("?", 1)[0].split("#", 1)[0].strip().strip("/").lstrip("@")
    if text.lower().startswith("s/"):
        text = text[2:]
    text = text.strip().strip("/").lstrip("@")
    if not _CHANNEL_RE.fullmatch(text):
        raise ValueError("Telegram channel username ghalat hai "
                         "(sirf letters, numbers, _; 3-64 characters)")
    return text


def preview_url(channel: str, query: str = "") -> str:
    ch = normalize_channel(channel)
    url = "https://t.me/s/" + ch
    q = str(query or "").strip()
    if q:
        url += "?q=" + urllib.parse.quote(q[:120])
    return url


class _PreviewParser(HTMLParser):
    """Extract message text, datetime and permalink from a t.me/s preview page."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.items: list[dict] = []
        self._stack: list[tuple[str, str]] = []
        self._cur: dict | None = None

    # -- helpers ---------------------------------------------------------
    def _flush(self):
        cur = self._cur
        self._cur = None
        if not cur:
            return
        text = clean_text(cur.get("text", ""))
        if not text:
            return
        self.items.append({
            "text": text[:4000],
            "published": cur.get("datetime", ""),
            "url": cur.get("url", ""),
            "views": cur.get("views", ""),
        })

    # -- HTMLParser API --------------------------------------------------
    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        cls = a.get("class", "")
        if tag not in _VOID_TAGS:
            self._stack.append((tag, cls))
        depth = len(self._stack)

        if tag == "div" and "tgme_widget_message_wrap" in cls:
            self._flush()
            self._cur = {"text": "", "datetime": "", "url": "", "views": "",
                         "_base": depth}
        if self._cur is None:
            return
        if tag == "div" and "tgme_widget_message_text" in cls:
            self._cur["_text_depth"] = depth
        if tag == "br" and "_text_depth" in self._cur:
            self._cur["text"] += "\n"
        if tag == "time" and a.get("datetime") and not self._cur.get("datetime"):
            self._cur["datetime"] = a["datetime"]
        if tag == "a" and "tgme_widget_message_date" in cls and a.get("href"):
            self._cur["url"] = a["href"]
        if "tgme_widget_message_views" in cls:
            self._cur["_views_tag"] = (tag, depth)

    def handle_startendtag(self, tag, attrs):
        # <br/> style tags: feed through the normal start path, no stack push.
        a = {k: (v or "") for k, v in attrs}
        if tag == "br" and self._cur is not None and "_text_depth" in self._cur:
            self._cur["text"] += "\n"

    def handle_data(self, data):
        cur = self._cur
        if cur is None or not data:
            return
        if "_text_depth" in cur:
            cur["text"] += data
        elif "_views_tag" in cur:
            cur["views"] = (cur.get("views", "") + data).strip()

    def handle_endtag(self, tag):
        cur = self._cur
        depth = len(self._stack)
        if cur is not None:
            if tag == "div" and cur.get("_text_depth") == depth:
                cur.pop("_text_depth", None)
            vt = cur.get("_views_tag")
            if vt and vt[0] == tag and vt[1] == depth:
                cur.pop("_views_tag", None)
            if tag == "div" and cur.get("_base") == depth:
                self._flush()
        if self._stack:
            self._stack.pop()

    def close(self):
        super().close()
        self._flush()


def parse_preview(html_text: str) -> list[dict]:
    """Parse a Telegram public preview page. Never raises on malformed HTML."""
    parser = _PreviewParser()
    try:
        parser.feed(html_text or "")
        parser.close()
    except Exception:
        pass
    return parser.items


_ISO_TS = re.compile(r"^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})")


def _iso(raw: str) -> str:
    text = str(raw or "").strip()
    m = _ISO_TS.match(text)
    if not m:
        return text[:40]
    return f"{m.group(1)} {m.group(2)} UTC"


def _now_text() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def fetch_channel(channel: str, query: str = "", limit: int = 20,
                  timeout: int = TIMEOUT) -> dict:
    """Fetch one public channel preview and return normalized message items.

    Network / HTTP failures are returned as ``ok: false`` (never raised) so the
    UI can show a clear diagnostic. An invalid channel username raises
    :class:`ValueError` because it is a caller/input error.
    """
    ch = normalize_channel(channel)
    try:
        limit = max(1, min(100, int(limit or 20)))
    except (TypeError, ValueError):
        limit = 20
    url = preview_url(ch, query)
    base = {"channel": ch, "url": url, "query": str(query or "").strip(),
            "fetched_at": _now_text()}
    try:
        validate_url(url, allowlist=ALLOWED_HOSTS)
        req = urllib.request.Request(url, headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,*/*",
            "Accept-Language": "en-US,en;q=0.9",
        })
        with urllib.request.urlopen(req, timeout=timeout) as r:
            status = int(getattr(r, "status", 200) or 200)
            raw = r.read(MAX_BYTES) or b""
        if status >= 400:
            return {**base, "ok": False, "count": 0, "items": [],
                    "error": f"Telegram HTTP {status}"}
        items = parse_preview(raw.decode("utf-8", "replace"))
        items = [{"text": i["text"], "published": _iso(i.get("published", "")),
                  "url": i.get("url", ""), "views": i.get("views", "")}
                 for i in items[:limit]]
        return {**base, "ok": True, "count": len(items), "items": items, "error": ""}
    except ValueError as e:
        return {**base, "ok": False, "count": 0, "items": [],
                "error": str(e)[:300]}
    except Exception as e:
        return {**base, "ok": False, "count": 0, "items": [],
                "error": f"{type(e).__name__}: {str(e)[:200]}"}
