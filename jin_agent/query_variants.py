"""Multilingual query pipeline — detect, transliterate, translate, expand.

Maqsad: user ki bhi bhi zaban ka keyword (Urdu / Roman Urdu / English / Arabic /
kuch bhi) Telegram-wide discovery ke liye qabil-e-amal variants me badalna.

**Stdlib-only.** Koi nayi dependency nahi. Translation do tarah se hoti hai:

* LLM mojood ho (``llm.resolve(cfg)["enabled"]``) → us se asli translation.
* Warna ``_BUILTIN_PAIRS`` — chhota, saaf dictionary. Jhoot nahi bolta:
  samajh na aaye to khali list.

``detect_language`` script (Unicode ranges) + stopword scoring par based hai —
ML model nahi. Roman Urdu aur English ki tameez stopwords se hoti hai.
"""

from __future__ import annotations

import json
import re

from . import util

# --------------------------------------------------------------------------
# Script detection
# --------------------------------------------------------------------------

_ARABIC_RANGE = (
    (0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF),
    (0xFB50, 0xFDFF), (0xFE70, 0xFEFF),
)
_CYRILLIC_RANGE = ((0x0400, 0x04FF),)
_DEVANAGARI_RANGE = ((0x0900, 0x097F),)


def _in_ranges(cp: int, ranges) -> bool:
    return any(lo <= cp <= hi for lo, hi in ranges)


def script_of(text: str) -> str:
    """``arabic`` / ``cyrillic`` / ``devanagari`` / ``latin`` / ``mixed`` / ``other``."""
    counts = {"arabic": 0, "cyrillic": 0, "devanagari": 0, "latin": 0}
    for ch in str(text or ""):
        cp = ord(ch)
        if _in_ranges(cp, _ARABIC_RANGE):
            counts["arabic"] += 1
        elif _in_ranges(cp, _CYRILLIC_RANGE):
            counts["cyrillic"] += 1
        elif _in_ranges(cp, _DEVANAGARI_RANGE):
            counts["devanagari"] += 1
        elif (0x41 <= cp <= 0x5A) or (0x61 <= cp <= 0x7A):
            counts["latin"] += 1
    present = {k: v for k, v in counts.items() if v}
    if not present:
        return "other"
    if len(present) > 1:
        return "mixed"
    return next(iter(present))


# Roman Urdu (Latin script) — aam lafz jo English me kam mumkin.
_ROMAN_URDU_WORDS = frozenset({
    "hai", "hain", "ka", "ki", "ke", "kya", "kyun", "aur", "mein", "main",
    "se", "ko", "par", "nahi", "nahin", "haan", "acha", "accha", " achi",
    "karo", "karein", "kar", "chahiye", "mujhe", "bhai", "yaar",
    "mobail", "mobile", "fon", "phone", "secur", "secr", "khama", "khami",
    "dekho", "batao", "bata", "kaise", "kahan", "kab", "kyunke", "liye",
    "wala", "wali", "walay", "sath", "saath", "baare", "bare", "tasveer",
    "video", "aurat", "mard", "bacha", "bachay", "kaam", "paise", "paisay",
    "khana", "pina", "makan", "gari", "kitab", "duniya", "waqt", "din",
    "raat", "subah", "shaam", "hafte", "mahine", "saal", "abhi", "yahan",
    "wahan", "ye", "wo", "woo", "mera", "meri", "mere", "tera", "teri",
    "tere", "hamara", "aapka", "aapki", "unka", "unki", "sab", "kuch",
    "bahut", "thora", "zyada", "kam", "poora", "naya", "purana", "baras",
})

_ENGLISH_WORDS = frozenset({
    "the", "a", "an", "of", "in", "on", "for", "to", "with", "is", "are",
    "and", "or", "what", "how", "why", "when", "where", "which", "this",
    "that", "these", "those", "you", "your", "we", "our", "they", "their",
    "mobile", "security", "firmware", "android", "phone", "news", "best",
    "free", "guide", "update", "review", "tips", "tricks", "download",
})

# Arabic script lafz jo Urdu ki alamat hain (façade: ہے، کا، میں ...).
_URDU_MARKERS = (
    "ہے", "ہیں", "کا", "کی", "کے", "میں", "اور", "سے", "کو", "نہیں",
    "کہ", "یہ", "وہ", "بہت", "اچھا", "اچھی", "نیا", "پرانا", "کیا", "کون",
    "کب", "کہاں", "کیسے", "لیے", "ساتھ", "لیکن", "اگر", "پھر", "ابھی",
    "یہاں", "وہاں", "ہمارا", "تمہارا", "ان کا", "سب", "کچھ", "تھوڑا",
    # Urdu technical lafz (Roman/English moqabil se alagraaz)
    "موبائل", "سیکیورٹی", "فون", "نیوز", "ٹیکنالوجی", "مفت", "کرپٹو",
    "ہیکنگ", "اینڈروڈ", "انسٹال", "اپڈیٹ", "ڈاؤن",
)


def detect_language(text: str) -> dict:
    """Zaban + script + confidence. ML nahi — script ranges + stopwords.

    Waja: Telegram par Roman Urdu (Latin script) bohat hoti hai aur usay
    English se alag karna zaroori hai, warna discovery galat query par chalti hai.
    """
    s = str(text or "").strip()
    if not s:
        return {"lang": "unknown", "script": "none", "confidence": 0.0}

    script = script_of(s)
    if script == "arabic":
        markers = sum(s.count(m) for m in _URDU_MARKERS)
        return {"lang": "ur" if markers else "ar", "script": "arabic",
                "confidence": round(min(1.0, 0.7 + 0.05 * markers), 2)}

    if script == "cyrillic":
        return {"lang": "ru", "script": "cyrillic", "confidence": 0.9}
    if script == "devanagari":
        return {"lang": "hi", "script": "devanagari", "confidence": 0.9}

    if script == "mixed":
        return {"lang": "mixed", "script": "mixed",
                "confidence": 0.45}

    # latin script: Roman Urdu vs English
    words = [w for w in re.findall(r"[a-z']+", s.lower()) if len(w) > 1]
    rom = sum(1 for w in words if w in _ROMAN_URDU_WORDS)
    eng = sum(1 for w in words if w in _ENGLISH_WORDS)
    if rom and rom >= eng:
        return {"lang": "roman-urdu", "script": "latin",
                "confidence": round(min(1.0, 0.55 + 0.08 * rom), 2)}
    return {"lang": "en", "script": "latin",
            "confidence": round(min(1.0, 0.5 + 0.08 * eng), 2)}


# --------------------------------------------------------------------------
# Transliteration (Urdu Arabic <-> Roman Urdu)
# --------------------------------------------------------------------------

_AR_TO_LAT = {
    "ا": "a", "آ": "aa", "ب": "b", "پ": "p", "ت": "t", "ٹ": "tt",
    "ث": "s", "ج": "j", "چ": "ch", "ح": "h", "خ": "kh", "د": "d",
    "ڈ": "dd", "ذ": "z", "ر": "r", "ڑ": "rr", "ز": "z", "ژ": "zh",
    "س": "s", "ش": "sh", "ص": "s", "ض": "z", "ط": "t", "ظ": "z",
    "ع": "a", "غ": "gh", "ف": "f", "ق": "q", "ک": "k", "گ": "g",
    "ل": "l", "م": "m", "ن": "n", "ں": "n", "و": "w", "ہ": "h",
    "ھ": "h", "ء": "", "ی": "y", "ے": "e", "۰": "0", "۱": "1",
    "۲": "2", "۳": "3", "۴": "4", "۵": "5", "۶": "6", "۷": "7",
    "۸": "8", "۹": "9", "۔": ".", "،": ",", "؛": ";", "؟": "?",
    "٫": "/", " ": " ", "﻿": "",
}

# Roman Urdu -> Urdu (Arabic script) — lafz dar lafz. Chhoti qaelum.
_ROMAN_TO_URDU = {
    "mobail": "موبائل", "mobile": "موبائل", "fon": "فون", "phone": "فون",
    "securiti": "سیکیورٹی", "security": "سیکیورٹی", "secur": "سیکیور",
    "android": "اینڈروڈ", "firmware": "فریم ویر", "rom": "روم",
    "flash": "فلیش", "unlock": "ان لاک", "khula": "کھلا",
    "khabar": "خبر", "khabrain": "خبریں", "news": "نیوز",
    "technology": "ٹیکنالوجی", "tech": "ٹیک", "duniya": "دنیا",
    "waqt": "وقت", "din": "دن", "raat": "رات", "saal": "سال",
    "mahina": "مہینہ", "hafta": "ہفتہ", "abhi": "ابھی",
    "yahan": "یہاں", "wahan": "وہاں", "kaise": "کیسے", "kahan": "کہاں",
    "kya": "کیا", "kaun": "کون", "kab": "کب", "kyun": "کیوں",
    "mera": "میرا", "meri": "میری", "mere": "میرے", "tera": "تیرا",
    "teri": "تیری", "tere": "تیرے", "aapka": "آپ کا", "aapki": "آپ کی",
    "hamara": "ہمارا", "sab": "سب", "kuch": "کچھ", "bahut": "بہت",
    "zyada": "زیادہ", "kam": "کم", "naya": "نیا", "purana": "پرانا",
    "acha": "اچھا", "accha": "اچھا", "bura": "برا", "baras": "برس",
    "paisay": "پیسے", "paise": "پیسے", "kaam": "کام", "makan": "مکان",
    "gari": "گاڑی", "kitab": "کتاب", "aurat": "عورت", "mard": "مرد",
    "bacha": "بچہ", "bachay": "بچے", "khana": "کھانا", "pina": "پینا",
    "dekho": "دیکھو", "batao": "بتاؤ", "bata": "بتا", "kaise": "کیسے",
    "liye": "لیے", "sath": "ساتھ", "saath": "ساتھ", "wala": "والا",
    "wali": "والی", "walay": "والے", "tasveer": "تصویر", "video": "ویڈیو",
    "free": "مفت", "muft": "مفت", "guide": "گائیڈ", "update": "اپڈیٹ",
    "review": "ریویو", "tips": "ٹپس", "tricks": "ٹرکس", "download": "ڈاؤن لوڈ",
    "best": "بہترین", "new": "نیا", "purane": "پرانے", "qadeem": "قدیم",
    "maloomat": "معلومات", "ilm": "علم", "seekh": "سیکھ", "likh": "لکھ",
    "urdu": "اردو", "roman": "رومن", "english": "انگریزی", "arabic": "عربی",
    "hai": "ہے", "hain": "ہیں", "ka": "کا", "ki": "کی", "ke": "کے",
    "aur": "اور", "mein": "میں", "main": "میں", "se": "سے", "ko": "کو",
    "par": "پر", "nahi": "نہیں", "nahin": "نہیں", "haan": "ہاں",
    "karo": "کرو", "karein": "کریں", "kar": "کر", "chahiye": "چاہیے",
    "mujhe": "مجھے", "bhai": "بھائی", "yaar": "یار", "ye": "یہ",
    "wo": "وہ", "woo": "وہ", "to": "تو", "hi": "ہی", "bhi": "بھی",
    "ne": "نے", "kiya": "کیا", "kiye": "کیے", "raha": "رہا",
    "rahe": "رہے", "gaya": "گیا", "gaye": "گئے", "jayega": "جائے گا",
}

# Urdu (Arabic script) -> Roman Urdu — lafz dar lafz (char-map se behtar).
_UR_TO_ROMAN = {
    "موبائل": "mobail", "سیکیورٹی": "security", "فون": "phone",
    "اینڈروڈ": "android", "فریم": "frame", "فریم ویر": "firmware",
    "روم": "rom", "نیوز": "news", "خبر": "khabar", "خبریں": "khabrain",
    "مفت": "free", "ٹیکنالوجی": "technology", "ٹیک": "tech",
    "دنیا": "duniya", "وقت": "waqt", "دن": "din", "رات": "raat",
    "سال": "saal", "مہینہ": "mahina", "ہفتہ": "hafta", "ابھی": "abhi",
    "یہاں": "yahan", "وہاں": "wahan", "کیسے": "kaise", "کہاں": "kahan",
    "کیا": "kya", "کون": "kaun", "کب": "kab", "کیوں": "kyun",
    "میرا": "mera", "میری": "meri", "میرے": "mere", "تیرا": "tera",
    "ہمارا": "hamara", "سب": "sab", "کچھ": "kuch", "بہت": "bahut",
    "زیادہ": "zyada", "کم": "kam", "نیا": "naya", "پرانا": "purana",
    "اچھا": "acha", "پیسے": "paisay", "کام": "kaam", "مکان": "makan",
    "گاڑی": "gari", "کتاب": "kitab", "عورت": "aurat", "مرد": "mard",
    "بچہ": "bacha", "کھانا": "khana", "معلومات": "maloomat",
    "اردو": "urdu", "انگریزی": "english", "عربی": "arabi",
    "کرپٹو": "crypto", "ہیکنگ": "hacking", "سائبر": "cyber",
}

_LAT_TO_AR = {
    "a": "ا", "aa": "آ", "b": "ب", "p": "پ", "t": "ت", "tt": "ٹ",
    "s": "س", "j": "ج", "ch": "چ", "h": "ہ", "kh": "خ", "d": "د",
    "dd": "ڈ", "z": "ز", "r": "ر", "rr": "ڑ", "zh": "ژ", "sh": "ش",
    "gh": "غ", "f": "ف", "q": "ق", "k": "ک", "g": "گ", "l": "ل",
    "m": "م", "n": "ن", "w": "و", "y": "ی", "e": "ے", "o": "و",
    "i": "ی", "u": "و",
}


def transliterate(text: str, direction: str = "arabic-to-latin") -> str:
    """Urdu Arabic <-> Roman Urdu. Char-map + lafz-map; kabhi crash nahi.

    ``direction``: ``"arabic-to-latin"`` (default) ya ``"latin-to-arabic"``.
    Pehle qaelum qaeday band na ho to char-map fallback — jhoota result nahi.
    """
    s = str(text or "").strip()
    if not s:
        return ""
    if direction == "latin-to-arabic":
        out = []
        for word in re.split(r"(\s+)", s):
            if not word.strip():
                out.append(word)
                continue
            key = word.lower()
            if key in _ROMAN_TO_URDU:
                out.append(_ROMAN_TO_URDU[key])
                continue
            buf = ""
            i = 0
            while i < len(word):
                two = word[i:i + 2].lower()
                if two in _LAT_TO_AR:
                    buf += _LAT_TO_AR[two]
                    i += 2
                    continue
                one = word[i].lower()
                buf += _LAT_TO_AR.get(one, word[i])
                i += 1
            out.append(buf)
        return "".join(out).strip()
    # arabic-to-latin
    out = []
    for word in re.split(r"(\s+)", s):
        if not word.strip():
            out.append(word)
            continue
        if word in _UR_TO_ROMAN:
            out.append(_UR_TO_ROMAN[word])
            continue
        out.append("".join(_AR_TO_LAT.get(ch, ch) for ch in word))
    txt = "".join(out)
    txt = re.sub(r"[ ]{2,}", " ", txt)
    return txt.strip()


# --------------------------------------------------------------------------
# Translation (LLM optional, builtin fallback)
# --------------------------------------------------------------------------

# (src_lang, term) -> {target_lang: translation}. Chhota aur saaf.
_BUILTIN_PAIRS = {
    ("en", "mobile"): {"ur": "موبائل", "ar": "موبايل"},
    ("en", "security"): {"ur": "سیکیورٹی", "ar": "أمن"},
    ("en", "firmware"): {"ur": "فریم ویر", "ar": "برنامج ثابت"},
    ("en", "android"): {"ur": "اینڈروڈ", "ar": "أندرويد"},
    ("en", "phone"): {"ur": "فون", "ar": "هاتف"},
    ("en", "news"): {"ur": "نیوز", "ar": "أخبار"},
    ("en", "free"): {"ur": "مفت", "ar": "مجاني"},
    ("en", "tips"): {"ur": "ٹپس", "ar": "نصائح"},
    ("en", "tricks"): {"ur": "ٹرکس", "ar": "حيل"},
    ("en", "guide"): {"ur": "گائیڈ", "ar": "دليل"},
    ("en", "update"): {"ur": "اپڈیٹ", "ar": "تحديث"},
    ("en", "download"): {"ur": "ڈاؤن لوڈ", "ar": "تحميل"},
    ("en", "crypto"): {"ur": "کرپٹو", "ar": "عملة مشفرة"},
    ("en", "bitcoin"): {"ur": "بٹ کوائن", "ar": "بيتكوين"},
    ("en", "ai"): {"ur": "ای آئی", "ar": "ذكاء اصطناعي"},
    ("en", "python"): {"ur": "پائیتھون", "ar": "بايثون"},
    ("en", "unlocking"): {"ur": "ان لاک", "ar": "فتح القفل"},
    ("en", "scam"): {"ur": "اسکیم", "ar": "احتيال"},
    ("ur", "موبائل"): {"en": "mobile", "ar": "موبايل"},
    ("ur", "سیکیورٹی"): {"en": "security", "ar": "أمن"},
    ("ur", "فون"): {"en": "phone", "ar": "هاتف"},
    ("ur", "نیوز"): {"en": "news", "ar": "أخبار"},
    ("ur", "مفت"): {"en": "free", "ar": "مجاني"},
    ("ur", "خبر"): {"en": "news", "ar": "خبر"},
    ("ur", "ٹیکنالوجی"): {"en": "technology", "ar": "تكنولوجيا"},
    ("ur", "معلومات"): {"en": "information", "ar": "معلومات"},
    ("ar", "موبايل"): {"en": "mobile", "ur": "موبائل"},
    ("ar", "أمن"): {"en": "security", "ur": "سیکیورٹی"},
    ("ar", "هاتف"): {"en": "phone", "ur": "فون"},
    ("ar", "أخبار"): {"en": "news", "ur": "نیوز"},
    ("ar", "مجاني"): {"en": "free", "ur": "مفت"},
    ("ar", "تكنولوجيا"): {"en": "technology", "ur": "ٹیکنالوجی"},
}


def translate_query(text: str, targets, cfg: dict | None = None) -> dict:
    """``{target_lang: translation}``. LLM off ho to builtin dictionary.

    Jhoot nahi: kuch na milaye to khali dict. Translation ka matlab hai
    chuninda lafz ka mutarjam lafz — poora jumla nahi.
    """
    targets = [t for t in (targets or []) if t]
    if not targets:
        return {}
    s = str(text or "").strip()
    if not s:
        return {}
    cfg = cfg or {}
    src = detect_language(s)["lang"]
    out: dict[str, str] = {}

    # 1) LLM (agar user ne provider set kiya ho)
    try:
        from . import llm
        if cfg and llm.resolve(cfg).get("enabled"):
            prompt = (
                "Translate the search keyword(s) into: "
                + ", ".join(targets)
                + ". Reply ONLY JSON {\"en\": \"...\", \"ur\": \"...\"}. "
                  "Keep brand names as-is. Keyword only, no sentence.\n"
                  "Keyword: " + util.truncate(s, 200)
            )
            raw = llm.chat(cfg, "You are a concise translation engine.", prompt)
            data = json.loads(raw) if raw else {}
            if isinstance(data, dict):
                for t in targets:
                    v = str(data.get(t) or "").strip()
                    if v:
                        out[t] = v
    except Exception:
        out = {}

    # 2) builtin fallback (har target ke liye) — kuch keys azmo (ar/ur/roman)
    key = s.lower()
    keys = [src]
    if src in ("ar", "ur"):
        keys += ["ur", "ar"]
    if src == "roman-urdu":
        keys += ["en", "ur"]
    pair = None
    for k in keys:
        pair = _BUILTIN_PAIRS.get((k, key))
        if pair:
            break
    for t in targets:
        if t in out:
            continue
        if pair and t in pair:
            out[t] = pair[t]
    return out


# --------------------------------------------------------------------------
# Synonyms / related niche terms
# --------------------------------------------------------------------------

_SYNONYMS = {
    "en": {
        "firmware": ["rom", "flash", "scatter", "bootloader", "preloader"],
        "android": ["rom", "custom rom", "aosp", " lineageos", "grapheneos"],
        "security": ["vulnerability", "cve", "exploit", "patch", "malware"],
        "mobile": ["smartphone", "android", "ios", "phone"],
        "crypto": ["bitcoin", "ethereum", "token", "blockchain", "airdrop"],
        "ai": ["llm", "machine learning", "openai", "local model", "agent"],
        "scam": ["fraud", "phishing", "fake", "rugpull"],
    },
    "ur": {
        "موبائل": ["موبائل فون", "اسمارٹ فون", "فون", "موبائل سیکیورٹی"],
        "سیکیورٹی": ["موبائل سیکیورٹی", "سائبر سیکیورٹی", "ہیکنگ"],
        "فون": ["موبائل", "اسمارٹ فون", "موبائل فون"],
        "نیوز": ["خبریں", "خبر", "تازہ ترین"],
        "مفت": ["مفت ایپی آئی", "مفت سروس", "مفت"],
        "ٹیکنالوجی": ["ٹیک", "ٹیکنالوجی نیوز", "سائنس"],
    },
    "roman-urdu": {
        "mobail": ["mobail fon", "smartphone", "android", "mobail security"],
        "security": ["cyber security", "hacking", "vulnerability", "malware"],
        "fon": ["mobail", "smartphone", "mobail fon"],
        "news": ["khabrain", "khabar", "taza tareen"],
        "muft": ["free api", "muft service", "free"],
        "paisay": ["money", "free paisay", "earning"],
    },
}


def synonyms(text: str, lang: str = "en", cfg: dict | None = None) -> list[str]:
    """Related terms. LLM on ho to us se izafa, warna curated map."""
    s = str(text or "").strip()
    out: list[str] = []
    table = _SYNONYMS.get(lang) or _SYNONYMS.get("en") or {}
    low = s.lower()
    for key, vals in table.items():
        if key and (key in low or low in key):
            for v in vals:
                if v and v not in out:
                    out.append(v)
    if cfg:
        try:
            from . import llm
            if llm.resolve(cfg).get("enabled"):
                raw = llm.chat(
                    cfg, "You are a search assistant.",
                    "Given the keyword, list up to 5 closely related search "
                    "terms (JSON array of strings). Keyword: " + util.truncate(s, 120))
                import json as _json
                data = _json.loads(raw) if raw else []
                if isinstance(data, list):
                    for v in data:
                        v = str(v).strip()
                        if v and v not in out:
                            out.append(v)
        except Exception:
            pass
    return out[:8]


# --------------------------------------------------------------------------
# Variant generation — sab kuch jorta hai
# --------------------------------------------------------------------------

def variants(query: str, cfg: dict | None = None,
             max_variants: int = 12) -> list[dict]:
    """``[{"text","kind","lang"}, ...]`` — deduped, qeemti tarteeb.

    kind: ``original`` | ``transliteration`` | ``translation`` | ``synonym``
    """
    q = str(query or "").strip()
    if not q:
        return []
    cfg = cfg or {}
    lang = detect_language(q)
    seen: dict[str, dict] = {}

    def add(text, kind, lg) -> None:
        t = " ".join(str(text or "").split()).strip(" .,")
        if not t:
            return
        key = t.lower()
        if key in seen:
            return
        seen[key] = {"text": t, "kind": kind, "lang": lg}

    add(q, "original", lang["lang"])

    # Transliteration — Roman Urdu <-> Urdu dono taraf
    if lang["script"] == "arabic":
        add(transliterate(q, "arabic-to-latin"), "transliteration", "roman-urdu")
    elif lang["lang"] == "roman-urdu":
        add(transliterate(q, "latin-to-arabic"), "transliteration", "ur")

    # Translation
    targets = [t for t in ("en", "ur", "ar") if t != lang["lang"]]
    for t, txt in translate_query(q, targets, cfg).items():
        add(txt, "translation", t)

    # Synonyms / related
    for s in synonyms(q, lang["lang"], cfg):
        add(s, "synonym", lang["lang"])

    return list(seen.values())[:max_variants]


def variant_texts(query: str, cfg: dict | None = None,
                  max_variants: int = 12) -> list[str]:
    """Sirf lafz — ``run_discovery`` ke liye."""
    return [v["text"] for v in variants(query, cfg, max_variants)]
