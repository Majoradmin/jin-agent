"""MobileLab - Service Brief & Official Status Checks (PHASE 12).

Python standard library only. This module provides three safe capabilities:

1. ``build_status_report``  -- an OFFICIAL device status-check worksheet for
   Apple iPhone / Android (blacklist, carrier / SIM lock, Find My / Activation
   Lock, warranty / coverage). The app does NOT query any carrier, OEM, Apple
   or government database; it produces a blank, clearly-labelled worksheet
   that a technician fills from authorized channels.
2. ``build_gsx_worksheet`` -- an Apple GSX *REQUEST* worksheet. Apple GSX is
   restricted to technicians at Apple-authorized service facilities. This app
   NEVER connects to GSX, NEVER stores GSX credentials and NEVER fabricates
   GSX findings. It only outputs a template with an explicit disclaimer.
3. ``build_problem_brief`` -- a Roman Urdu research & service brief built from
   the existing verified-feed research pipeline plus official service routes.
   Facts (with URL + date checked) and recommendations are kept separate;
   nothing is invented when the network is unavailable.

SAHULAT & SAFE SERVICE POLICY (unchanged): no account / activation-lock bypass
automation, no step-by-step lock-removal instructions, no device write / erase
/ flash / IMEI operation, no unauthorized data access, no full-IMEI storage.
"""
from __future__ import annotations

import re
import time
from typing import Any

import sahulat

POLICY_ID = sahulat.POLICY_ID
DATE_CHECKED = "2026-11-09"
P1_DATE_CHECKED = "2026-11-08"      # PHASE 1 source register S1-S16
VERSION = "1.2.0"

MODES = ("auto", "status", "gsx", "brief")
BRANDS = ("auto", "apple", "android", "other")

MAX_QUERY_CHARS = 2000
MAX_FIELD_CHARS = 200
MAX_ID_CHARS = 40

DISCLAIMER = (
    "MobileLab sirf OFFICIAL status-check / service-request documentation "
    "tayyar karta hai. Ye app kisi device ka asli status khud query nahi karti, "
    "Apple GSX, carrier, OEM ya sarkari database tak nahi pahunchti, aur koi "
    "natija (blacklist, SIM lock, Find My / Activation Lock, warranty) "
    "fabricate nahi karti. Khali fields sirf authorized technician apne jaez / "
    "official channel se hasil karda maloomat se bhare. Is mein koi bypass, "
    "unlock code, FMI-off tareeqa, IMEI tabdeeli ya device write / erase "
    "operation nahi hai."
)

GSX_DISCLAIMER = (
    "YE APPLE GSX REPORT NAHI HAI. Ye sirf aik KHALI request / case worksheet "
    "hai. Apple GSX (Global Service Exchange) ka access sirf Apple-authorized "
    "service facility ke technicians ko un ke apne GSX account se milta hai "
    "(S19). MobileLab GSX par login nahi karta, koi credential store nahi karta, "
    "koi third-party GSX / 'report seller' service use nahi karta, aur koi "
    "finding, model, colour, replacement ya activation status apni taraf se "
    "nahi likhta. Jo data aap authorized channel se hasil karein, woh khud "
    "neeche wale fields mein darj karein; is document par 'MobileLab verified' "
    "ka koi dawa nahi hai."
)

PRIVACY_NOTE = (
    "Privacy: app full IMEI / serial store ya print nahi karta. Sirf aakhri 4 "
    "harkat (masked) worksheet mein aati hain; poora identifier aap ke apne "
    "case file / official portal par hi rakhein."
)

# ---------------------------------------------------------------------------
# Verified source register (C16 / C22). Every new URL was checked on 2026-11-09.
# Facts and recommendations are kept separate downstream; no URL is invented.
# ---------------------------------------------------------------------------
SOURCES = [
    {"id": "S17", "label": "Apple Support - Activation Lock for iPhone and iPad",
     "url": "https://support.apple.com/en-us/108794",
     "purpose": "Official explanation that Find My / Activation Lock is stored on Apple activation servers; includes the pre-owned-device status check.",
     "date_checked": DATE_CHECKED},
    {"id": "S18", "label": "Apple - AppleCare & Warranty coverage check",
     "url": "https://checkcoverage.apple.com/",
     "purpose": "Official Apple serial / device coverage lookup (country selection page).",
     "date_checked": DATE_CHECKED},
    {"id": "S19", "label": "Apple Support - How to access ATLAS",
     "url": "https://support.apple.com/en-us/102263",
     "purpose": "Documents that an active GSX account is limited to technicians working at Apple-authorized service facilities.",
     "date_checked": DATE_CHECKED},
    {"id": "S20", "label": "Apple - Find Locations",
     "url": "https://locate.apple.com/",
     "purpose": "Official Apple Stores / Apple Authorized Service Providers / Online Support locator.",
     "date_checked": DATE_CHECKED},
    {"id": "S21", "label": "PTA DIRBS - Device Verification System",
     "url": "https://dirbs.pta.gov.pk/",
     "purpose": "Official Pakistan Telecommunication Authority IMEI / device status verification (DVS, SMS 8484).",
     "date_checked": DATE_CHECKED},
    # Re-used from the PHASE 1 verified register (S1-S16). No new citation is
    # invented here: the URL and its original check date are carried over.
    {"id": "S22", "label": "GSMA (IMEI / industry information)",
     "url": "https://www.gsma.com/",
     "purpose": "Industry body reference used by the existing carrier / SIM-lock official route.",
     "date_checked": P1_DATE_CHECKED, "verified_in": "PHASE 1 (S1-S16)"},
    {"id": "S23", "label": "Google Account Recovery",
     "url": "https://accounts.google.com/signin/recovery",
     "purpose": "Official account recovery route used by the existing Google / FRP official route.",
     "date_checked": P1_DATE_CHECKED, "verified_in": "PHASE 1 (S1-S16)"},
    {"id": "S24", "label": "Android FRP help",
     "url": "https://support.google.com/android/answer/9450130",
     "purpose": "Official Android Factory Reset Protection help page.",
     "date_checked": P1_DATE_CHECKED, "verified_in": "PHASE 1 (S1-S16)"},
]

# Research honesty: a checked-but-dead URL is explicitly excluded, never cited.
EXCLUDED_SOURCES = [
    {"url": "https://www.icloud.com/activationlock/",
     "reason": "Checked 2026-11-09: returns 'iCloud can't find that page'. Retired / unavailable; excluded from all citations."},
]

SOURCE_BY_ID = {s["id"]: s for s in SOURCES}


def _link(label: str, sid: str) -> list[str]:
    return [label, SOURCE_BY_ID[sid]["url"]]


# ---------------------------------------------------------------------------
# Official status checks. ``how`` is documentation only -- never a bypass step.
# ---------------------------------------------------------------------------
CHECKS = {
    "apple": [
        {"id": "blacklist", "label": "Blacklist / chori-shuda report status",
         "where": "Apne carrier ka official device-check page ya PTA DIRBS DVS (Pakistan)",
         "how": "Malik ki tasdeeq ke baad official portal par device identifier darj karain; wahan jo status aaye, woh worksheet mein likhein.",
         "links": [_link("PTA DIRBS DVS", "S21")],
         "note": "MobileLab kisi 'blacklist cleanup' ya IMEI repair service ko support nahi karta."},
        {"id": "carrier", "label": "Carrier / SIM lock status",
         "where": "iPhone Settings > General > About > Carrier Lock, ya carrier ka official unlock-eligibility page",
         "how": "Device par 'No SIM restrictions' ya carrier ka naam dekhein; official carrier page par eligibility check karain.",
         "links": [_link("GSMA (IMEI / industry information)", "S22"),
                   _link("Apple - Find Locations", "S20")],
         "note": "Sirf status / eligibility check apne carrier ke official page par. Koi unlock code, server request ya third-party unlock service nahi."},
        {"id": "fmi", "label": "Find My / Activation Lock (FMI) ON / OFF",
         "where": "Apple Support 108794 + device ki 'iPhone Locked to Owner' / Hello screen",
         "how": "Apple ke official guide ke mutabiq second-hand device lene se pehle Hello screen aur previous owner ka account removal verify karain.",
         "links": [_link("Apple Support - Activation Lock", "S17")],
         "note": "FMI / Activation Lock Apple ke activation SERVER par rehta hai. App isay band nahi karta, na is ka koi tareeqa deta hai."},
        {"id": "warranty", "label": "Warranty / AppleCare coverage",
         "where": "checkcoverage.apple.com (malik khud serial darj kare)",
         "how": "Official coverage page par serial / device identifier darj karain aur wahan mila result worksheet mein note karein.",
         "links": [_link("Apple coverage check", "S18")],
         "note": "Local tool se warranty status ka andaza nahi lagaya jata."},
    ],
    "android": [
        {"id": "blacklist", "label": "Blacklist / IMEI status",
         "where": "PTA DIRBS DVS (Pakistan) ya apne carrier ka official device-check page",
         "how": "Official DVS / carrier portal par IMEI ka status dekhein; natija worksheet mein darj karein.",
         "links": [_link("PTA DIRBS DVS", "S21")],
         "note": "Koi IMEI cleanup / repair / change service support nahi."},
        {"id": "carrier", "label": "Carrier / SIM lock status",
         "where": "Carrier ka official unlock-eligibility page ya device Settings",
         "how": "Official carrier page par eligibility check karain aur status note karein.",
         "links": [_link("GSMA (IMEI / industry information)", "S22")],
         "note": "Sirf status / eligibility. Koi unlock code ya bypass nahi."},
        {"id": "fmi", "label": "Google FRP / Device Protection state",
         "where": "Google Android FRP help + official account recovery",
         "how": "Sirf ye verify karein ke device asli malik ke Google account se linked hai ya nahi; tafseel official help se len.",
         "links": [_link("Android FRP help", "S24"), _link("Google Account Recovery", "S23")],
         "note": "FRP server-side / account-linked hai. App isay hatane ka koi step nahi deta."},
        {"id": "warranty", "label": "OEM warranty / model information",
         "where": "OEM ka official warranty-check page ya MobileLab Model Brief",
         "how": "Apne brand ke official support page par model / identifier darj karein; MobileLab ka Model Brief sirf local catalog information deta hai.",
         "links": [],
         "note": "Koi generic OEM URL verified nahi hai, is liye koi banawati link nahi diya. Model Brief local data hai, koi live OEM lookup nahi."},
    ],
    "other": [
        {"id": "blacklist", "label": "Blacklist / device status",
         "where": "PTA DIRBS DVS ya apne carrier ka official page",
         "how": "Official portal par status dekhein aur worksheet mein darj karein.",
         "links": [_link("PTA DIRBS DVS", "S21")],
         "note": "Koi cleanup service nahi."},
        {"id": "warranty", "label": "Manufacturer warranty / support",
         "where": "Manufacturer ka official support page",
         "how": "Official support page par model aur identifier se coverage check karein.",
         "links": [],
         "note": "Brand pata na ho to pehle apne brand ka official support page dhoondein. Is ke liye koi verified generic URL nahi, is liye koi link fabricate nahi kiya gaya."},
    ],
}

CHECK_IDS = {c["id"] for brand in CHECKS.values() for c in brand}


# ---------------------------------------------------------------------------
# Input hygiene
# ---------------------------------------------------------------------------
def _clean(value: Any, limit: int = MAX_FIELD_CHARS) -> str:
    s = str(value if value is not None else "").strip()
    s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", s)
    return s[:limit]


def mask_identifier(raw: Any) -> tuple[str, bool]:
    """Return (masked_last4, full_identifier_supplied).

    A full IMEI / serial is NEVER echoed back. Only the last four digits are
    kept, so a pasted 15-digit IMEI cannot leak into a worksheet or a response.
    """
    text = _clean(raw, MAX_ID_CHARS)
    digits = re.sub(r"\D", "", text)
    if not digits:
        return "", False
    return "•••• " + digits[-4:], len(digits) > 4


def _proof(data: dict) -> tuple[list[str], list[str], bool]:
    raw = data.get("proof", [])
    if not isinstance(raw, (list, tuple)):
        raw = []
    kept = sorted({str(x) for x in raw if str(x) in sahulat.CHECKLIST_IDS})
    missing = sorted(sahulat.REQUIRED_IDS - set(kept))
    return kept, missing, not missing


def _date() -> str:
    return time.strftime("%d %B %Y")


def _official_links_for(brand: str) -> list[list[str]]:
    out: list[list[str]] = []
    for c in CHECKS.get(brand, CHECKS["other"]):
        for pair in c.get("links", []):
            if len(pair) == 2 and str(pair[1]).startswith("https://") and pair not in out:
                out.append(list(pair))
    return out


def _validate_common(data: dict, require_proof: bool) -> tuple[dict, list[str]]:
    cleaned = {
        "customer": _clean(data.get("customer")),
        "contact": _clean(data.get("contact")),
        "model": _clean(data.get("model")),
        "brand": _clean(data.get("brand"), 20).lower(),
        "issue": _clean(data.get("issue") or data.get("q")),
        "notes": _clean(data.get("notes"), 1000),
        "consent": bool(data.get("consent")),
    }
    if cleaned["brand"] not in ("apple", "android", "other"):
        cleaned["brand"] = "other"
    cleaned["identifier_masked"], cleaned["full_identifier_supplied"] = mask_identifier(data.get("device_id"))
    cleaned["proof"], cleaned["missing_proof"], cleaned["proof_ok"] = _proof(data)
    errors: list[str] = []
    if not cleaned["customer"]:
        errors.append("Customer ka naam zaroori hai")
    if not cleaned["consent"]:
        errors.append("Customer consent zaroori hai (consent form par dastkhat)")
    if require_proof and not cleaned["proof_ok"]:
        labels = ", ".join(next(c["label"] for c in sahulat.CHECKLIST if c["id"] == m)
                           for m in cleaned["missing_proof"])
        errors.append("Pehle zaroori proof items tick karain: " + labels)
    return cleaned, errors


def _worksheet_header(d: dict, kind: str) -> str:
    return (
        "MOBILELAB - " + kind + "\n"
        "========================================================\n"
        "Tareekh            : " + _date() + "\n"
        "Customer           : " + (d["customer"] or "____________________") + "\n"
        "Contact            : " + (d["contact"] or "____________________") + "\n"
        "Platform / brand   : " + d["brand"].upper() + "\n"
        "Model              : " + (d["model"] or "____________________") + "\n"
        "Masked identifier  : " + (d["identifier_masked"] or "____________________") + "\n"
        "Case / request no  : ____________________\n"
        "Technician / shop  : ____________________\n"
        "Policy             : " + POLICY_ID + "\n"
        "--------------------------------------------------------\n"
    )


# ---------------------------------------------------------------------------
# 1. Official status-check worksheet
# ---------------------------------------------------------------------------
def build_status_report(data: dict) -> dict:
    """Build a blank official status-check worksheet. Never asserts a result."""
    d, errors = _validate_common(data, require_proof=False)
    if errors:
        raise ValueError("; ".join(errors))

    requested = data.get("checks", [])
    if not isinstance(requested, (list, tuple)):
        requested = []
    wanted = {str(x) for x in requested if str(x) in CHECK_IDS}
    checks = [c for c in CHECKS[d["brand"]] if not wanted or c["id"] in wanted]
    if not checks:
        checks = list(CHECKS[d["brand"]])

    lines = [_worksheet_header(d, "OFFICIAL DEVICE STATUS CHECK - WORKSHEET"),
             "Ye KHALI worksheet hai. Neeche har check ka OFFICIAL raasta diya gaya hai;",
             "asli natija sirf aap authorized channel se hasil kar ke bharein.\n"]
    for i, c in enumerate(checks, 1):
        lines.append(f"{i}. {c['label']}")
        lines.append("   Official source : " + c["where"])
        lines.append("   Kaise check karein : " + c["how"])
        lines.append("   Status (khali)  : [ ] ON / locked   [ ] OFF / unlocked   [ ] Not available")
        lines.append("   Result / reference no : ____________________")
        lines.append("   Verified by (technician) : ____________________")
        lines.append("   Note : " + c["note"])
        for label, url in c["links"]:
            lines.append("   Link : " + label + " - " + url)
        lines.append("")

    lines.append("VERIFIED OFFICIAL LINKS (checked " + DATE_CHECKED + ")")
    for label, url in _official_links_for(d["brand"]):
        lines.append("  - " + label + " : " + url)
    lines.append("")
    lines.append("PROOF OF OWNERSHIP")
    for c in sahulat.CHECKLIST:
        mark = "[x]" if c["id"] in d["proof"] else "[ ]"
        lines.append("  " + mark + " " + c["label"] + (" (required)" if c["required"] else ""))
    if not d["proof_ok"]:
        lines.append("  WARNING: zaroori proof items abhi pooray nahi hue - official request bhejne se pehle mukammal karein.")
    lines.append("")
    lines.append("DISCLAIMER / HADD")
    lines.append(DISCLAIMER)
    lines.append(PRIVACY_NOTE)

    return {
        "ok": True, "kind": "status", "report": "\n".join(lines),
        "brand": d["brand"], "checks": checks,
        "official_links": _official_links_for(d["brand"]),
        "proof": d["proof"], "missing_proof": d["missing_proof"],
        "proof_ok": d["proof_ok"], "identifier_masked": d["identifier_masked"],
        "full_identifier_supplied": d["full_identifier_supplied"],
        "privacy_note": PRIVACY_NOTE, "disclaimer": DISCLAIMER,
        "policy": POLICY_ID, "date_checked": DATE_CHECKED,
    }


# ---------------------------------------------------------------------------
# 2. Apple GSX REQUEST worksheet (no access, no fabricated findings)
# ---------------------------------------------------------------------------
def build_gsx_worksheet(data: dict) -> dict:
    """Build a blank GSX request / case worksheet, never a GSX report."""
    d, errors = _validate_common(data, require_proof=True)
    if errors:
        raise ValueError("; ".join(errors))

    lines = [_worksheet_header(d, "APPLE GSX REQUEST / CASE WORKSHEET (NOT A GSX REPORT)"),
             "!! " + GSX_DISCLAIMER + "\n",
             "ELIGIBILITY / ACCESS",
             "  - GSX accounts are limited to technicians working at Apple-authorized service facilities (S19).",
             "  - Agar aap authorized nahi hain to Apple Authorized Service Provider se rabta karein (S20).",
             "  - MobileLab koi GSX credential mangta, store ya bhejta nahi.\n",
             "REQUEST DETAILS (technician bharein)",
             "  Request type        : [ ] Device history   [ ] Coverage / warranty   [ ] Service eligibility",
             "  Authorized facility : ____________________",
             "  GSX case / repair ID: ____________________   (sirf official channel se mila hua)",
             "  Reason for request  : ____________________",
             "  Ownership proof attached : [ ] Invoice  [ ] Owner ID  [ ] Consent  [ ] Last-4 identifier\n",
             "FINDINGS - SIRF AUTHORIZED CHANNEL SE HASIL KARDA DATA (khali chhorhein agar na ho)",
             "  Reported model / colour / storage : ____________________",
             "  Activation / Find My status       : ____________________",
             "  Warranty / coverage status        : ____________________",
             "  Replacement / refurbished flag    : ____________________",
             "  Blacklist / carrier status        : ____________________",
             "  Source of above data              : ____________________",
             "  Technician signature / date       : ____________________\n",
             "  >> Koi bhi upar wala field MobileLab ne KHUD nahi bhara. Agar koi field khali hai",
             "     to is ka matlab hai: app ne koi natija claim nahi kiya.\n",
             "OFFICIAL LINKS (checked " + DATE_CHECKED + ")"]
    for s in SOURCES:
        lines.append("  - " + s["label"] + " : " + s["url"] + "  [" + s["id"] + "]")
    lines.append("")
    lines.append("BOUNDARY")
    lines.append(DISCLAIMER)
    lines.append(PRIVACY_NOTE)

    return {
        "ok": True, "kind": "gsx", "worksheet": "\n".join(lines),
        "is_gsx_report": False, "gsx_access_performed": False,
        "credentials_stored": False, "eligibility_note":
            "GSX access sirf Apple-authorized service facility ke technicians ko un ke apne account se milta hai (S19).",
        "official_links": [[s["label"], s["url"]] for s in SOURCES],
        "sources": SOURCES, "proof": d["proof"], "proof_ok": d["proof_ok"],
        "identifier_masked": d["identifier_masked"],
        "full_identifier_supplied": d["full_identifier_supplied"],
        "disclaimer": GSX_DISCLAIMER, "privacy_note": PRIVACY_NOTE,
        "policy": POLICY_ID, "date_checked": DATE_CHECKED,
    }


# ---------------------------------------------------------------------------
# 3. Problem -> Research & Service Brief
# ---------------------------------------------------------------------------
_BYPASS_RE = re.compile(
    r"\bbypass\b|\bremove\s+(?:id|account|lock)\b|\bclean\s+imei\b|"
    r"\bimei\s*(?:change|repair|tamper)\b|\bfmi\s*off\b|\bunlock\s+code\b|"
    r"\bunlocktool\b|\bchimera\b|\bflash\s+frp\b", re.I)

# Any CHANGE / REMOVAL / BYPASS intent. This is intentionally broader than the
# legacy gate: phrases such as "FMI off kar do", "unlock kar do" or "blacklist
# clean karo" are not in sahulat.BANNED_PATTERNS and must never slip through.
# "fmi off on check" is an ON/OFF *status enumeration*, so the negative
# lookahead keeps that legitimate wording out of the action list.
_ACTION_RE = re.compile(
    r"\bbypass\w*|\bcrack\w*|\bremove\w*|\bhata\w*|\bband\s+kar\w*|"
    r"\boff\s+kar\w*|\bturn\s+off\b|\bdisable\w*|\breset\s+(?:frp|lock)\b|"
    r"\bunlock\s*(?:kar|karo|karain|karein|code|service|tool)\b|\bunlocktool\b|"
    r"\bchimera\b|"
    r"\b(?:imei|blacklist)\s*(?:change|repair|clean|tamper|rewrite|clear|remove|hata)\w*\b|"
    r"\b(?:change|repair|clean|tamper|rewrite|clear|remove|hata)\w*\s+(?:imei|blacklist)\b|"
    r"\b(?:erase|write|flash)\s+frp\b|\berase\s+persistent\b|\bwrite\s+seccfg\b|"
    r"\bfmi\s*off\b(?!\s*on\b)|\btareeqa\b|"
    r"\bkaise\s+(?:karein|karain|karo|kar)\b|"
    r"\bserver\s+(?:change|edit|update|badal)\w*", re.I)

# Wording that can only mean "read / verify / document", never "change".
_STATUS_INTENT_RE = re.compile(
    r"\bcheck\w*|\bstatus\b|\breport\b|\bworksheet\b|\bverify\w*|"
    r"\binfo(?:rmation)?\b|\bconfirm\w*|\bjaanch\b|\bpata\s+kar\w*|"
    r"\bmaloom\b|\bdekh\w*|\bkhulasa\b|\bnews\b|\bkhabar\w*|\bbrief\b|"
    r"\bon\s*(?:/|ya|or)\s*off\b|\boff\s*(?:/|ya|or)\s*on\b|"
    r"\bnikal\s+(?:ke|kar|do|de)\b|\bbata\w*|\bservice\b", re.I)

# Account / activation / ownership-control topics always keep the strict gate,
# even when "status" words are present. No brand-specific diagnosis is guessed.
_STRONG_RE = re.compile(
    r"\bfrp\b|factory reset protection|huawei\s*(?:id|account)|"
    r"emui.*(?:id|account)|\bknox\b|kg\s*lock|samsung\s*account|"
    r"\bmdm\b|mobile enrollment|\bicloud\b|activation\s*lock|"
    r"apple\s*id.*(?:remove|bypass)|\bbypass\b|"
    r"imei\s*(?:change|repair|clean|tamper)|"
    r"erase\s*(?:frp|persistent)|write\s*(?:frp|seccfg)|"
    r"firehose.*(?:erase|frp)", re.I)

STATUS_EXCEPTION_NOTE = (
    "Ye aik OFFICIAL STATUS CHECK / documentation request hai, is liye app "
    "khali worksheet aur verified official links deta hai. App khud koi status "
    "query nahi karta aur koi natija claim nahi karta."
)

_APPLE_RE = re.compile(r"\biphone\b|\bapple\b|\bios\b|\bipad\b|\bgsx\b", re.I)
_ANDROID_RE = re.compile(
    r"\bandroid\b|\bsamsung\b|\bpixel\b|\bhuawei\b|\bxiaomi\b|\boneplus\b|"
    r"\boppo\b|\bvivo\b|\btecno\b|\binfinix\b|\bmotorola\b|\bnokia\b", re.I)
_GSX_RE = re.compile(r"\bgsx\b|global service exchange", re.I)
_STATUS_RE = re.compile(
    r"\bblacklist\b|\bcarrier\b|\bsim\s*lock\b|\block\s+status\b|\bfmi\b|"
    r"\bfind\s*my\b|activation\s*lock|\bwarranty\b|\bcoverage\b|\bimei\b|"
    r"\bcheck\s+status\b|\bstatus\s+check\b", re.I)

_STOP = {"main", "mujhe", "mera", "meri", "ka", "ki", "ke", "ko", "aur", "ya",
         "hai", "hain", "ho", "gaya", "gayi", "karo", "karein", "kar", "de",
         "do", "batao", "bataein", "likho", "please", "the", "a", "an", "of",
         "for", "to", "in", "on", "is", "my", "me", "check", "report"}


def _terms(query: str) -> list[str]:
    words = re.findall(r"[\w.-]{3,}", query.lower())
    out: list[str] = []
    for w in words:
        if w in _STOP or w.isdigit() or w in out:
            continue
        if _BYPASS_RE.search(w):
            continue
        out.append(w)
        if len(out) >= 8:
            break
    return out


def terms_for(query: str) -> list[str]:
    """Public, network-free term extraction for the research pipeline."""
    return _terms(_clean(query, MAX_QUERY_CHARS))


def _forced_refusal() -> dict:
    """Refuse P12-only action wording the legacy gate does not know about."""
    return {
        "blocked": True, "policy": POLICY_ID,
        "reason": (
            "Ye status check nahi, balkay koi lock / ownership record BADALNE ki "
            "darkhwast hai. Account / activation aur carrier locks manufacturer "
            "ya operator ke SERVER par rehte hain — koi local tool inhe durable "
            "taur par nahi badal sakta. MobileLab is ka koi step, code ya service "
            "generate nahi karta."
        ),
        "official_route": "Apne manufacturer / carrier ka official support route",
        "route_id": "", "documents": [c["label"] for c in sahulat.CHECKLIST if c["required"]],
        "official_links": [_link("Apple Support - Activation Lock", "S17"),
                           _link("Apple - Find Locations", "S20"),
                           _link("PTA DIRBS DVS", "S21")],
        "safe_next_steps": [
            "Proof-of-ownership checklist poori karain aur consent form par dastkhat len.",
            "Device ka ON / OFF ya lock STATUS sirf official channel se verify karain; worksheet khali rakhein.",
            "Agar malik ki tasdeeq chahiye to upar wale official links par service request shuru karain.",
            "Sahulat / Official Route view mein service-request letter aur case register istemal karain.",
        ],
        "refusal_line": "Is ka koi bypass automation ya step-by-step tareeqa app mein nahi hai — lekin official raasta poori madad ke saath neeche maujood hai.",
        "status_check_exception": False,
    }


def _gate(text: str) -> dict:
    """Return a refusal-shaped dict. ``sahulat.check_request`` stays unchanged.

    Narrow exception: a genuine status/verification request (``_STATUS_INTENT_RE``)
    with NO change intent and NO account/activation topic may reach the blank
    worksheet. Everything else goes through the strict legacy gate; if the
    legacy gate does not recognise P12-only action wording, an explicit refusal
    with reason + official links is returned instead of silent acceptance.
    """
    q = _clean(text, MAX_QUERY_CHARS)
    if _ACTION_RE.search(q) or _STRONG_RE.search(q):
        strict = sahulat.check_request(q)
        strict["status_check_exception"] = False
        if strict.get("blocked"):
            return strict
        return _forced_refusal()
    if _STATUS_INTENT_RE.search(q):
        return {
            "blocked": False, "policy": POLICY_ID,
            "reason": STATUS_EXCEPTION_NOTE,
            "official_route": "", "route_id": "", "official_links": [],
            "documents": [],
            "safe_next_steps": [
                "Status Check worksheet banayein aur har field authorized official channel se bharein.",
                "GSX ki zaroorat ho to sirf request / case worksheet use karain (koi GSX report nahi).",
                "Masla likh kar Problem Brief se verified news + official service routes len.",
                "Case register aur proof-of-ownership checklist ka record rakhein.",
            ],
            "refusal_line": "", "status_check_exception": True,
        }
    strict = sahulat.check_request(q)
    strict["status_check_exception"] = False
    return strict


def classify(text: str) -> dict:
    """Classify a free-text customer request into a safe mode / brand.

    Action / bypass wording is always refused with reason + official links;
    only a genuine official status-check request receives the narrow P12
    exception that routes it to a blank worksheet.
    """
    gate = _gate(text)
    status_exception = bool(gate.get("status_check_exception"))
    if gate.get("blocked"):
        return {
            "blocked": True, "suggested_mode": "", "suggested_brand": "",
            "terms": [], "policy": POLICY_ID,
            "reason": gate["reason"], "official_links": gate["official_links"],
            "safe_next_steps": gate["safe_next_steps"],
            "refusal_line": gate["refusal_line"],
            "status_check_exception": False,
        }
    q = _clean(text, MAX_QUERY_CHARS)
    if _APPLE_RE.search(q):
        brand = "apple"
    elif _ANDROID_RE.search(q):
        brand = "android"
    else:
        brand = "other"
    if _GSX_RE.search(q):
        mode = "gsx"
    elif _STATUS_RE.search(q):
        mode = "status"
    else:
        mode = "brief"
    return {
        "blocked": False, "suggested_mode": mode, "suggested_brand": brand,
        "terms": _terms(q), "policy": POLICY_ID,
        "reason": gate["reason"], "official_links": [],
        "safe_next_steps": gate["safe_next_steps"], "refusal_line": "",
        "status_check_exception": status_exception,
    }


def _facts_from(research_result: dict) -> list[dict]:
    facts: list[dict] = []
    for item in (research_result or {}).get("items", [])[:12]:
        url = _clean(item.get("url"), 500)
        if not url.startswith("https://"):
            continue
        facts.append({
            "fact_or_recommendation": "fact",
            "title": _clean(item.get("title")),
            "url": url,
            "source": _clean(item.get("source")),
            "published": _clean(item.get("published"), 40),
            "khulasa": _clean(item.get("khulasa"), 600),
            "date_checked": DATE_CHECKED,
        })
    return facts


def _routes_for(query: str) -> list[dict]:
    ql = query.lower()
    out: list[dict] = []
    for route in sahulat.ROUTES:
        blob = (route["brand"] + " " + route["issue"]).lower()
        rid = route["id"]
        hit = (rid == "apple" and _APPLE_RE.search(ql)) or \
              (rid == "google" and "frp" in ql) or \
              (rid == "huawei" and "huawei" in ql) or \
              (rid == "samsung" and "samsung" in ql) or \
              (rid == "carrier" and ("carrier" in ql or "sim" in ql)) or \
              any(w in ql for w in re.findall(r"[a-z]{4,}", blob)[:6])
        if not hit:
            continue
        for label, url in route.get("links", []):
            if str(url).startswith("https://"):
                out.append({
                    "fact_or_recommendation": "recommendation",
                    "label": _clean(label) + " - " + _clean(route["brand"]),
                    "url": url, "reason": _clean(route["note"], 400),
                    "date_checked": "2026-11-08",  # P1 verified S1-S16 register
                })
    seen: set[str] = set()
    uniq = []
    for r in out:
        if r["url"] not in seen:
            seen.add(r["url"])
            uniq.append(r)
    return uniq[:8]


def build_problem_brief(query: str, research_result: dict) -> dict:
    """Build a Roman Urdu brief. Facts and recommendations never mix."""
    q = _clean(query, MAX_QUERY_CHARS)
    if not q:
        raise ValueError("Masla / sawaal likhein")
    gate = _gate(q)
    facts = _facts_from(research_result)
    routes = _routes_for(q)
    diag = list((research_result or {}).get("diagnostics", []))
    sources_ok = int((research_result or {}).get("sources_ok", 0) or 0)
    offline = sources_ok == 0
    blocked = bool(gate.get("blocked"))

    lines = [
        "MOBILELAB - SERVICE BRIEF / MASLA KI REPORT",
        "========================================================",
        "Tareekh      : " + _date(),
        "Aap ka masla : " + q,
        "Policy       : " + POLICY_ID,
        "--------------------------------------------------------",
    ]
    if blocked:
        lines += ["YE REQUEST BLOCK HAI - sirf official raasta diya jayega.",
                  "Wajah: " + gate["reason"], "",
                  "Official links:"]
        for label, url in gate["official_links"]:
            lines.append("  - " + label + " : " + url)
        lines += ["", "Agla jaez qadam:"]
        lines += ["  - " + s for s in gate["safe_next_steps"]]
        lines += ["", gate["refusal_line"]]
    else:
        if offline:
            lines += ["OFFLINE MODE: abhi koi feed se natija nahi mila (network",
                      "ya source dastiyab nahi). Is liye koi khabar ka dawa nahi",
                      "kiya gaya - neeche sirf verified official routes hain.", ""]
        lines.append("1) FACTS - verified feeds se mili khabarain (har aik ka URL + date checked)")
        if not facts:
            lines.append("   (koi feed item nahi mila / offline - koi banawati khabar nahi likhi gayi)")
        for i, f in enumerate(facts, 1):
            lines.append(f"   {i}. {f['title']}")
            lines.append("      Source: " + f["source"] + " | Published: " + (f["published"] or "-"))
            lines.append("      URL: " + f["url"] + " | date checked: " + f["date_checked"])
            if f["khulasa"]:
                lines.append("      Khulasa: " + f["khulasa"])
        lines += ["", "2) RECOMMENDATIONS - official service routes (ye FACTS nahi, tajveez hain)"]
        if not routes:
            lines.append("   (is masle ke liye koi specific official route map nahi hua)")
        for i, r in enumerate(routes, 1):
            lines.append(f"   {i}. {r['label']}")
            lines.append("      " + r["url"] + " | date checked: " + r["date_checked"])
            if r["reason"]:
                lines.append("      Wajah: " + r["reason"])
        lines += ["", "3) VERIFIED SOURCE REGISTER (new checks " + DATE_CHECKED + ")"]
        for s in SOURCES:
            lines.append("   [" + s["id"] + "] " + s["label"] + " - " + s["url"])
        lines += ["", "4) HADD / DISCLAIMER", DISCLAIMER]
    lines.append("")
    lines.append("Note: Roman Urdu text = information; links English surface hain (C19/D22).")

    return {
        "ok": True, "kind": "brief", "brief": "\n".join(lines), "query": q,
        "blocked": blocked, "offline": offline,
        "status_check_exception": bool(gate.get("status_check_exception")),
        "facts": [] if blocked else facts,
        "recommendations": [] if blocked else routes,
        "official_links": gate["official_links"] if blocked else _official_links_for("other"),
        "diagnostics": diag, "sources_ok": sources_ok,
        "sources_failed": int((research_result or {}).get("sources_failed", 0) or 0),
        "terms": (research_result or {}).get("terms", []) or _terms(q),
        "sources": SOURCES, "excluded_sources": EXCLUDED_SOURCES,
        "disclaimer": DISCLAIMER, "policy": POLICY_ID,
        "date_checked": DATE_CHECKED,
    }


def overview() -> dict:
    """Static metadata for the Service Brief view."""
    return {
        "policy": sahulat.POLICY, "policy_id": POLICY_ID, "version": VERSION,
        "modes": list(MODES), "brands": list(BRANDS), "checks": CHECKS,
        "check_ids": sorted(CHECK_IDS), "sources": SOURCES,
        "excluded_sources": EXCLUDED_SOURCES,
        "date_checked": DATE_CHECKED, "p1_date_checked": P1_DATE_CHECKED,
        "disclaimer": DISCLAIMER, "gsx_disclaimer": GSX_DISCLAIMER,
        "privacy_note": PRIVACY_NOTE, "gate_note": STATUS_EXCEPTION_NOTE,
        "checklist": sahulat.CHECKLIST, "consent_text": sahulat.CONSENT_TEXT,
        "gsx_is_report": False, "gsx_access_performed": False,
    }
