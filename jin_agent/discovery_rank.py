"""P45 - Discovery ranking + safety filters (stdlib-only).

Ye module **ranking** (query relevance) aur **spam/scam** pehchan karta hai.
Ownership-control patterns (FRP / FMI / HuaweiID / Knox / MDM / IMEI /
carrier-bypass) P47 me retire ho gaye — bot ab research/educational queries
par rokta nahi. Spam/scam channel-title filter qayam hai. Koi nayi dependency NAHI.
"""

from __future__ import annotations

import re

from . import policy, util

__all__ = [
    "relevance",
    "relevance_detail",
    "relevance_reason",
    "spam_reason",
    "dedupe_handles",
]


# --------------------------------------------------------------------------
# Relevance: query terms -> title / handle / descr / preview
# --------------------------------------------------------------------------

def _query_terms(query) -> list[str]:
    """Query ke lafz — ``util.terms`` (latin) ya fallback (Urdu/Arabic/Cyrillic)."""
    out = util.terms(query, 12)
    if out:
        return out
    raw = str(query or "").strip().lower()
    if not raw:
        return []
    toks = re.findall(r"[^\W\d_]+|[\d]+", raw, re.UNICODE)
    return list(dict.fromkeys(t for t in toks if len(t) >= 2))[:12]


def relevance_detail(query, text) -> dict:
    """``{"score": 0-10, "matched": [...]}`` — query terms ke matches.

    - har matched term +2 (max 6)
    - poori query phrase mil jaye to +2
    - coverage (matched / total terms) max +2
    """
    terms = _query_terms(query)
    body = str(text or "")
    if not terms or not body:
        return {"score": 0, "matched": []}
    low = body.lower()
    matched = [t for t in terms if t in low]
    if not matched:
        return {"score": 0, "matched": []}
    score = min(6, 2 * len(matched))
    if str(query or "").strip().lower() in low:
        score += 2
    score += min(2, int(round(2.0 * len(matched) / max(1, len(terms)))))
    return {"score": max(0, min(10, score)), "matched": matched[:2]}


def relevance(query, text) -> int:
    """Relevance score 0-10."""
    return int(relevance_detail(query, text)["score"])


def relevance_reason(query, text, limit: int = 2) -> str:
    """Chhota reason — konse query terms match hue (max ``limit``)."""
    matched = relevance_detail(query, text)["matched"]
    return ", ".join(matched[:max(1, int(limit))])


# --------------------------------------------------------------------------
# Spam / scam filter (query-independent)
# --------------------------------------------------------------------------

#: (regex, label) — English + Roman Urdu + Urdu/Arabic lafz. FRP/FMI/MDM/...
#: patterns is mein NAHI (wo ``policy.py`` ka kaam hai).
_SPAM_PATTERNS = [
    (r"\bfree\s+(money|cash|paisa|paise)\b", "free money"),
    (r"\bearn\s+(money|paisa|paise|cash)\b", "earn money"),
    (r"\b(paisa|paise)\s+(kamai|kama|double|badh)\w*", "paisa kamai"),
    (r"\b(daily|monthly|weekly|rozana)\s+(earning|income|paisa)\b", "daily earning"),
    (r"\bcrypto\s+giveaway\b", "crypto giveaway"),
    (r"\b(coin|token|btc|usdt|bnb|eth)\s+giveaway\b", "crypto giveaway"),
    (r"\bsend\s+(btc|usdt|bnb|eth|coin)\b", "send crypto"),
    (r"\bdouble\s+your\s+(btc|usdt|crypto|money)\b", "double crypto"),
    (r"\b(casino|gambling|betting|jackpot|lottery)\b", "casino/gambling"),
    (r"\b100\s*%\s*free\b", "100% free"),
    (r"\b(ipo|loan|loans|credit\s+loan|car\s+loan|home\s+loan)\b", "ipo/loan"),
    (r"\b(adult|porn|pornhub|xxx|escort|onlyfans)\b", "adult"),
    (r"\binvite\s+only\b", "invite only"),
    (r"\bwhatsapp\s+(number|link)\b", "whatsapp"),
    # Urdu / Arabic script (mojy zahem chhote, saaf lafz)
    (r"\b(كازينو|يانصيب)\b", "casino/lottery"),
    (r"\b(إباحي|اباحي|كبار)\b", "adult"),
    (r"\b(قرض|قروض)\b", "loan"),
    (r"\bتربح\s+المال\b", "win money"),
    (r"\bرقم\s+واتساب\b", "whatsapp number"),
]


def spam_reason(text) -> str:
    """Spam/scam label — na ho to ``""``."""
    s = str(text or "")
    for pattern, label in _SPAM_PATTERNS:
        if re.search(pattern, s, re.I):
            return label
    return ""


def blocked_reason(text) -> str:
    """P47: query/title-level block retire — hamesha ``""`` (safety net).

    Purani kahani: ``policy.BLOCK_PATTERNS`` se blocked rule. Ab koi block
    pattern nahi, is liye ye function hamesha khali deta hai.
    """
    return ""# --------------------------------------------------------------------------
# Dedupe (Telegram handles case-insensitive hote hain)
# --------------------------------------------------------------------------

def dedupe_handles(handles) -> list[str]:
    """``clean_handle`` ki tarah normalize nahi, sirf case-insensitive dedupe.

    Pehli milti handle barqarar rehti hai (bada/chhota harf) — Telegram par
    ``@Foo`` aur ``@foo`` aik hi channel hain.
    """
    out: list[str] = []
    seen: set[str] = set()
    for raw in handles or []:
        h = str(raw or "").strip()
        if not h:
            continue
        key = h.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(h)
    return out
