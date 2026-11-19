"""Multi-turn chat context (P38) — chhote follow-up sawal pichhle query se jodo.

Abhi bot har sawal ko akele samajhta tha. User aksar chhota follow-up poochta
hai ("aur", "iske baare me", "phir") — bina pichhle context ke agent ko pura
sawal dobara likhna parta. Ye module maloom karta hai ke matn follow-up hai,
aur ``store.chat_context`` se aakhri sawal prompt me jodta hai (max 1 pichhla
sawal — zyada history noise barhati hai).
"""

from __future__ import annotations

import re

from . import store

MAX_FOLLOWUP_WORDS = 4
# "aur" jaise lafz word-boundary par — "suraj" / "meraun" jaisay lafz na match hon.
_HINT_RE = re.compile(
    r"(?:\b(?:aur|more|continue|phir|then)\b|iske\s+baare\s+me|uske\s+baare\s+me)",
    re.I,
)


def is_followup(text: str) -> bool:
    """Chhota matn (<=4 words) YA follow-up lafz → pichhla context munasib.

    Note: ye sirf *pehfiyat* hai — asli context ``attach`` me check hota hai,
    is liye bina history wale chhote sawal bhi query ko as-is chhod dete hain.
    """
    s = " ".join(str(text or "").split())
    if not s:
        return False
    if len(s.split()) <= MAX_FOLLOWUP_WORDS:
        return True
    return bool(_HINT_RE.search(s))


def attach(chat_id: int, query: str) -> str:
    """Follow-up par pichhla sawal jodo (``prev | current``); warna as-is."""
    q = str(query or "").strip()
    if not is_followup(q):
        return q
    prev = store.last_chat_query(chat_id)
    if not prev or prev == q:
        return q
    return f"{prev} | {q}"


def note(chat_id: int, query: str) -> None:
    """Maujooda sawal ko agli follow-up ke liye pichhla query bana do."""
    store.save_chat_query(chat_id, query)


def clear(chat_id: int) -> int:
    """``/new`` par chat context saaf karo — hataaye gaye rows (0 ya 1)."""
    return store.clear_chat_context(chat_id)
