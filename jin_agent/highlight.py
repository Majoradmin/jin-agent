"""Query-term highlighting aur entity-safe HTML chunking (report/content layer).

Umeed (caller ka contract):
  - ``html`` pehle se escaped ho — ``telegram_bot.markdown_to_html()`` se aata hai.
  - ``terms`` plain-text query ke lafz hain (``terms()`` se bante hain).

Ye module sirf text nodes me replace karta hai; tag ke andar (``<a href="...">``
ke URL samet) kabhi nahi. HTML entities (``&amp;``) ko bhi nahi chhoo-ta takke
output wohi reh-jaye. Sab functions pure hain: koi I/O, koi global state nahi.
"""

from __future__ import annotations

import re

from .util import STOP_WORDS

# Void (self-contained) tags — inhen stack me push nahi karte.
VOID_TAGS = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
})

_TAG_NAME_RE = re.compile(r"<\s*(/?)\s*([a-zA-Z][a-zA-Z0-9]*)")
_ENTITY_RE = re.compile(
    r"&(?:[a-zA-Z][a-zA-Z0-9]{1,31}|#\d{1,10}|#x[0-9a-fA-F]{1,8});")


def terms(query: str, limit: int = 20) -> list[str]:
    """Query se meaningful terms nikalo.

    - case-insensitive, stopwords hatao, length >= 2, dedupe.
    - ``longest-first`` taake highlight ke waqt overlap na ho.
    - sab se lambi ``limit`` terms lauta aata hai.
    """
    try:
        limit = max(0, int(limit))
    except (TypeError, ValueError):
        limit = 20
    words = re.findall(r"[a-z0-9][a-z0-9._-]{1,}", str(query or "").lower())
    seen: set[str] = set()
    out: list[str] = []
    for word in words:
        if len(word) < 2 or word in STOP_WORDS or word in seen:
            continue
        seen.add(word)
        out.append(word)
    out.sort(key=lambda w: (-len(w), w))
    return out[:limit]


def _tokenize(html: str) -> list[tuple[bool, str]]:
    """HTML ko ``(is_tag, text)`` tokens me todo.

    ``<`` escaped HTML me hamesha tag delimiter hai, is liye quoted attribute
    values (``href="a>b"``) ke andar ka ``>`` bhi theek se samjha jata hai.
    """
    tokens: list[tuple[bool, str]] = []
    i, n = 0, len(html)
    while i < n:
        lt = html.find("<", i)
        if lt < 0:
            tokens.append((False, html[i:]))
            break
        if lt > i:
            tokens.append((False, html[i:lt]))
        j = lt + 1
        quote: str | None = None
        while j < n:
            ch = html[j]
            if quote is not None:
                if ch == quote:
                    quote = None
            elif ch in "\"'":
                quote = ch
            elif ch == ">":
                break
            j += 1
        if j >= n:  # adhura tag — text ki tarah barqarar
            tokens.append((False, html[lt:]))
            break
        tokens.append((True, html[lt:j + 1]))
        i = j + 1
    return tokens


def _parse_tag(tag: str) -> tuple[str, bool, bool]:
    """Tag se ``(name, closing, self_closing)`` nikalo."""
    m = _TAG_NAME_RE.match(tag)
    if not m:
        return "", False, False
    name = m.group(2).lower()
    closing = bool(m.group(1))
    self_closing = tag.rstrip().endswith("/>")
    return name, closing, self_closing


def _ulen(text: str) -> int:
    """UTF-16 code units — Telegram ki asli worst-case limit isi par hai."""
    return len(text.encode("utf-16-le", "surrogatepass")) // 2


def _safe_cut(text: str, max_units: int) -> int:
    """``max_units`` UTF-16 units ka code-point index; adhuri entity par na ruke."""
    units = 0
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        w = 2 if ord(ch) > 0xFFFF else 1
        if units + w > max_units:
            break
        units += w
        i += 1
    if i >= n:
        return n
    seg = text[:i]
    amp = seg.rfind("&")
    if amp > seg.rfind(";"):  # entity ke andar cut nahi
        i = amp
    if i <= 0:
        return 1 if n else 0
    return i


def _highlight_segment(text: str, ordered: list[str], used: set[str]) -> str:
    """Aik text segment (bina entities) me terms wrap karo; har term ek dafa."""
    spans: list[tuple[int, int]] = []
    pos = 0
    while True:
        active = [t for t in ordered if t.lower() not in used]
        if not active:
            break
        pattern = re.compile("|".join(re.escape(t) for t in active),
                             re.IGNORECASE)
        m = pattern.search(text, pos)
        if not m:
            break
        s, e = m.start(), m.end()
        key = m.group(0).lower()
        if any(not (e <= os_ or s >= oe) for os_, oe in spans):
            # pehle se highlight-shuda hissa — uske baahar se dobara khojein
            pos = min(oe for os_, oe in spans if not (e <= os_ or s >= oe))
            continue
        spans.append((s, e))
        used.add(key)
        pos = e
    if not spans:
        return text
    out: list[str] = []
    prev = 0
    for s, e in spans:
        out.append(text[prev:s])
        out.append("<b>" + text[s:e] + "</b>")
        prev = e
    out.append(text[prev:])
    return "".join(out)


def _highlight_text(text: str, ordered: list[str], used: set[str]) -> str:
    """Entities ko hifazat se alag rakho, baqi text par highlight karo."""
    segments: list[tuple[bool, str]] = []
    pos = 0
    for m in _ENTITY_RE.finditer(text):
        if m.start() > pos:
            segments.append((False, text[pos:m.start()]))
        segments.append((True, m.group(0)))
        pos = m.end()
    if pos < len(text):
        segments.append((False, text[pos:]))
    out: list[str] = []
    for is_entity, seg in segments:
        if is_entity:
            out.append(seg)
        else:
            out.append(_highlight_segment(seg, ordered, used))
    return "".join(out)


def highlight_html(html: str, terms: list[str]) -> str:
    """HTML ke **text nodes** me terms ko ``<b>...</b>`` se wrap karo.

    - HTML pehle se escaped hai; hum isay waisa hi rehte hain (kch unescape nahi).
    - tags ke andar (URL/attributes) replace nahi hota.
    - case-insensitive; har term sirf **ek dafa** (pehli occurrence) wrap hota hai.
    - koi match nahi to html waisa hi lauta aata hai.
    """
    raw = str(html or "")
    if not raw:
        return raw
    if isinstance(terms, str):
        terms = [terms]
    uniq: dict[str, str] = {}
    for t in terms or []:
        s = str(t or "").strip()
        if s:
            uniq.setdefault(s.lower(), s)
    ordered = sorted(uniq.values(), key=lambda s: (-len(s), s))
    if not ordered:
        return raw

    used: set[str] = set()
    out: list[str] = []
    for is_tag, text in _tokenize(raw):
        if is_tag:
            out.append(text)
        else:
            out.append(_highlight_text(text, ordered, used))
    return "".join(out)


def _split_lines(text: str) -> list[str]:
    """Text ko newline par todo, newline peechay wale hissay ke saath rahe."""
    parts = text.split("\n")
    out: list[str] = []
    for i, part in enumerate(parts):
        if i < len(parts) - 1:
            out.append(part + "\n")
        elif part:
            out.append(part)
    return out


def _close_tags(buf: str, stack: list[tuple[str, str]]) -> str:
    return buf + "".join(f"</{name}>" for name, _ in reversed(stack))


def _reopen_tags(stack: list[tuple[str, str]]) -> str:
    return "".join(opening for _, opening in stack)


def _has_text(chunk: str) -> bool:
    return bool(re.sub(r"<[^>]*>", "", chunk).strip())


def split_html(html: str, limit: int = 4096) -> list[str]:
    """Entity-safe, tag-balanced chunks (Telegram ``4096`` limit).

    - newline par todne ki tarah; dar jur limit par.
    - har chunk me tags **balanced** hain (koi ``<b>`` adhora nahi rehta).
    - limit UTF-16 code units me gini jati hai, taake emoji wala chunk bhi safe rahe.
    """
    raw = str(html or "")
    if not raw:
        return []
    try:
        limit = max(1, int(limit))
    except (TypeError, ValueError):
        limit = 4096

    chunks: list[str] = []
    buf = ""
    stack: list[tuple[str, str]] = []  # (name, opening tag — attributes ke saath)

    def overhead() -> int:
        """Is par close hone wale tags ki UTF-16 length (chunk me jagah chhore)."""
        return _ulen(_close_tags("", stack))

    def flush() -> None:
        nonlocal buf
        if buf:
            chunks.append(_close_tags(buf, stack))
        buf = _reopen_tags(stack)

    for is_tag, tok in _tokenize(raw):
        if is_tag:
            name, closing, self_closing = _parse_tag(tok)
            if not name:
                buf += tok
                continue
            if buf and _ulen(buf) + _ulen(tok) + overhead() > limit:
                flush()
            buf += tok
            if closing:
                if stack and stack[-1][0] == name:
                    stack.pop()
            elif not self_closing and name not in VOID_TAGS:
                stack.append((name, tok))
            if _ulen(tok) > limit and _ulen(buf) > limit:
                # Aik hi tag limit se bara hai (vahyat) — alag chunk kar ke
                # text loop ko hamesha progress dete rahena hai.
                chunks.append(_close_tags(buf, stack))
                buf = ""
                stack = []
            continue

        for part in _split_lines(tok):
            if not part:
                continue
            while part:
                room = limit - _ulen(buf) - overhead()
                if room <= 0:
                    flush()
                    continue
                if _ulen(part) <= room:
                    buf += part
                    break
                cut = _safe_cut(part, room)
                if cut <= 0:
                    flush()
                    continue
                buf += part[:cut]
                part = part[cut:]
                if _ulen(buf) + overhead() >= limit:
                    flush()

    if buf:
        chunks.append(_close_tags(buf, stack))
    return [c for c in chunks if _has_text(c)]
