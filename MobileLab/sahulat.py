"""MobileLab - Sahulat & Safe Service Toolkit (Python standard library only).

Maqsad: lawful owner / technician ki sahulat. Is module mein official-route
guidance, proof-of-ownership checklist, consent text, Roman Urdu + English
service-request letter templates aur aik "refusal with reason + official link"
helper hai.

*** SERVICE BOUNDARY (unchanged) ***
Is module mein koi bhi account / activation lock bypass automation,
step-by-step bypass tareeqa, exploit / loader trick, ya partition
write / erase command NAHI hai. Purana internal naam "HARD POLICY" tha;
PHASE 1B mein sirf naam aur andaaz badla gaya hai, qaida waisa ka waisa hai.
"""
from __future__ import annotations

import os
import re
import time

POLICY_ID = "SAHULAT-SAFE-SERVICE-v1"

POLICY = {
    "id": POLICY_ID,
    "name": "Sahulat & Safe Service Policy",
    "canonical": (
        "Purana internal naam: HARD POLICY. Sirf naam aur andaaz badla hai — "
        "qaida bilkul waisa ka waisa hai: koi bypass automation ya step-by-step "
        "tareeqa nahi. (ADR D19)"
    ),
    "lead": (
        "Hum logon ki sahulat ke liye kaam karte hain: sahi firmware tayyar karna, "
        "saaf documentation, aur jahan malik ki tasdeeq chahiye wahan seedha "
        "aur verified official raasta."
    ),
    "helps": [
        "Firmware package ki scan / validate: scatter, preloader, DA, Firehose, rawprogram, patch, GPT.",
        "Missing image, storage mismatch, sector overlap aur galat loader pehle se pakarna.",
        "Har kaam ka local case / asset register — IMEI, customer, proof aur route ka audit trail.",
        "Proof-of-ownership checklist aur customer consent form (Roman Urdu).",
        "Manufacturer / carrier ke liye service-request letter (Roman Urdu + English) tayyar karna.",
        "Brand-wise official links + required documents — 'ab kya karein' ka saaf jawab.",
        "Banned request par sirf 'nahi' nahi: wajah + official link + agla jaez qadam.",
        "Real-time research agent aur model brief — Roman Urdu khulasa ke saath.",
    ],
    "boundary": [
        "Huawei ID, Google FRP, Samsung Account / Knox Guard, MDM, carrier lock aur iCloud Activation Lock ka koi bypass automation ya step-by-step tareeqa nahi.",
        "Kisi bhi hassas partition (frp, persistent, config, devinfo, modemst1/2, nvram, nvdata, nvcfg, seccfg, proinfo, metadata) ko write / erase karne wali script ya command nahi.",
        "Server-side ownership record badalne ka dawa nahi — ye technologically bhi mumkin nahi.",
        "Cracked tools, leaked loaders / auth files, stolen credentials, blacklisted IMEI cleanup ya illegal sources ki support nahi.",
    ],
    "why": (
        "Account / activation locks anti-theft hain, sirf software bugs nahi. In ka faisla "
        "manufacturer ke server par hota hai, is liye local tool inhe durable taur par nahi "
        "hata sakta. Is liye app aap ka asli rukavat (firmware files) door karta hai aur "
        "malik ki tasdeeq wale kaam ke liye documented official raasta deta hai. Is se "
        "customer ko bhi madad milti hai aur aap ka record bhi mehfooz rehta hai."
    ),
}

# ---------------------------------------------------------------- official routes
# Steps are official recovery / support routes ONLY. No bypass procedure.
ROUTES = [
    {
        "id": "huawei",
        "brand": "Huawei / Honor",
        "issue": "Huawei ID ya device activation screen (EMUI / HarmonyOS)",
        "documents": [
            "Purchase invoice ya receipt (naam + IMEI ke saath)",
            "Device ka box / IMEI label",
            "Malik ka identity document (CNIC waghaira)",
            "Agar second-hand hai to pichhle malik ka contact ya release note",
            "Sarkari / department device: authorization letter",
        ],
        "steps": [
            "Pehle Huawei ID password recover karain: consumer.huawei.com > Support > HUAWEI ID.",
            "Agar device 'Activate device' screen par hai to Huawei Support ka official guide dekhein.",
            "Doosre haath ka phone hai to asli malik se Huawei ID, ya 'Find My Phone' se device remove karne ko kahein.",
            "Na-kamyabi par in documents ke saath Huawei Authorized Service Center jayein.",
        ],
        "links": [
            ["Huawei ID support", "https://consumer.huawei.com/en/support/mobile-services/huawei-id/"],
            ["Huawei Support home", "https://consumer.huawei.com/en/support/"],
        ],
        "note": "Huawei ka account system cloud-based hai — local flash se Huawei ID nahi hatta. Official support hi durable raasta hai.",
    },
    {
        "id": "google",
        "brand": "Google / Android (FRP)",
        "issue": "Google FRP / Device Protection screen",
        "documents": [
            "Asli Google account ka email",
            "Purchase invoice ya receipt",
            "Malik ka identity document",
            "Second-hand device: pichhle malik ka contact / account release",
        ],
        "steps": [
            "Asli Google account aur password se sign in karain.",
            "Password bhool gaye hon to accounts.google.com/signin/recovery par account recovery chalayein.",
            "Password abhi badla hai to Google 24 ghante baad retry ka mashwara deta hai.",
            "Second-hand device: pichhle malik se apna account device se remove karne ko kahein.",
            "Na-kamyabi par purchase proof ke saath authorized service center.",
        ],
        "links": [
            ["Google Account Recovery", "https://accounts.google.com/signin/recovery"],
            ["Android FRP help", "https://support.google.com/android/answer/9450130"],
        ],
        "note": "FRP, screen lock, MDM, carrier lock aur bootloader lock char alag cheezein hain — aik hatana doosre ko nahi hatata.",
    },
    {
        "id": "samsung",
        "brand": "Samsung",
        "issue": "Samsung Account / Knox Guard / MDM",
        "documents": [
            "Purchase invoice (IMEI ke saath)",
            "Malik ka identity document",
            "Knox Guard / finance case: registering party ka reference number",
            "MDM case: managing organization ka de-registration reference",
        ],
        "steps": [
            "Samsung Account recovery chalayein.",
            "Knox Guard (finance / rental / insurance): registering party ko console se unlock karna hota hai.",
            "MDM / Knox Mobile Enrollment: managing organization se de-registration mangwayein.",
            "Galat IMEI registration: invoice ke saath Samsung support ko de-registration request bhejein.",
        ],
        "links": [
            ["Samsung Support", "https://www.samsung.com/support/"],
        ],
        "note": "Knox 0x1 (bootloader unlock par eFuse trip) physically irreversible hai; koi software isay wapas nahi la sakta.",
    },
    {
        "id": "apple",
        "brand": "Apple iPhone / iPad",
        "issue": "iCloud Activation Lock",
        "documents": [
            "Original purchase receipt (Apple ya authorized reseller)",
            "Device ka box / IMEI ya serial",
            "Malik ka identity document",
            "Corporate / school device: IT admin ka MDM release reference",
        ],
        "steps": [
            "Apple Account aur password, ya device passcode darj karain.",
            "Pichhla malik iCloud.com > Find Devices se device apne account se remove karein.",
            "Corporate / school device: IT admin se MDM release karwayein.",
            "Purchase proof ke saath Apple Support se Activation Lock removal request.",
        ],
        "links": [
            ["Apple Activation Lock support", "https://al-support.apple.com/"],
            ["Apple: Activation Lock", "https://support.apple.com/en-us/108794"],
        ],
        "note": "Activation Lock Apple ke activation server par rehta hai; koi local Windows tool is database ko edit nahi kar sakta.",
    },
    {
        "id": "carrier",
        "brand": "Carrier / SIM network lock",
        "issue": "SIM network unlock ya carrier eligibility",
        "documents": [
            "Operator account details aur contract status",
            "Device IMEI",
            "Malik ka identity document",
            "Agar department device hai to official authorization letter",
        ],
        "steps": [
            "Apne operator se unlock eligibility check karayein (account paid, contract complete, device blacklisted na ho).",
            "Operator approval ke baad hi manufacturer / Apple server record update hota hai.",
            "Sarkari ya fleet device: department ke authorization letter ke saath operator ko request dein.",
        ],
        "links": [
            ["GSMA (IMEI / industry info)", "https://www.gsma.com/"],
        ],
        "note": "Blacklisted / stolen IMEI ko 'clean' karwana alag aur aksar ghair-qanooni kaam hai — is app mein is ki koi support nahi.",
    },
    {
        "id": "department",
        "brand": "Sarkari / enterprise device",
        "issue": "Department-owned device par MDM ya enrollment",
        "documents": [
            "Department ka official asset register entry",
            "Authorization / NOC letter (authorized signatory ke saath)",
            "Device IMEI aur asset tag",
            "IT admin ka de-registration reference",
        ],
        "steps": [
            "Apne department ke IT / MDM admin se device de-registration request karain.",
            "Asset register aur authorization letter case ke saath attach karain.",
            "Agar vendor / OEM support chahiye to official channel par ye documentation bhejein.",
            "Har qadam ka local case register mein note rakhein (audit trail).",
        ],
        "links": [],
        "note": "Sarkari kaam mein documentation hi sabse bari sahulat hai — case register isi liye hai. Koi private / bypass route nahi.",
    },
]

ROUTE_BY_ID = {r["id"]: r for r in ROUTES}

# ---------------------------------------------------------------- checklist
CHECKLIST = [
    {"id": "invoice", "label": "Purchase invoice / receipt", "required": True,
     "hint": "Naam, date aur IMEI nazar aaye to behtar."},
    {"id": "owner_id", "label": "Malik ka ID / CNIC copy", "required": True,
     "hint": "Sirf verify karain; copy app mein upload na karain."},
    {"id": "consent", "label": "Customer consent form par dastkhat", "required": True,
     "hint": "Neeche wala consent text print karwa kar sign karayein."},
    {"id": "device_id", "label": "IMEI / Serial note", "required": True,
     "hint": "Privacy ke liye sirf aakhri 4 harkat likhna kaafi hai."},
    {"id": "box", "label": "Device ka box ya IMEI label", "required": False,
     "hint": "Invoice na ho to madadgar."},
    {"id": "prev_owner", "label": "Pichhle malik ka contact / release note", "required": False,
     "hint": "Second-hand device ke liye."},
    {"id": "dept_auth", "label": "Department authorization / NOC letter", "required": False,
     "hint": "Sarkari ya enterprise device ke liye zaroori ho sakta hai."},
    {"id": "photos", "label": "Device aur bill ki tasveer", "required": False,
     "hint": "Apne pass rakhein; app mein upload nahi hota."},
]

CHECKLIST_IDS = {c["id"] for c in CHECKLIST}
REQUIRED_IDS = {c["id"] for c in CHECKLIST if c["required"]}

CONSENT_TEXT = (
    "CUSTOMER CONSENT / MALIK KI TASDEEQ\n"
    "------------------------------------\n"
    "Main tasdeeq karta/karti hun ke ye device meri milkiyat hai ya mujhe is ka "
    "jaez ikhtiyar hasil hai. Main ne MobileLab technician ko sirf firmware "
    "validation, documentation aur OFFICIAL manufacturer / carrier route ke liye "
    "madad dene ki ijazat di hai.\n\n"
    "Main samajhta/samajhti hun ke account / activation locks server-side "
    "anti-theft controls hain aur inhe kisi local tool se bypass nahi kiya jayega. "
    "Jo bhi documents main ne diye hain (invoice, ID, IMEI) sirf is case ke record "
    "ke liye istemal honge aur mere PC se bahar nahi bheje jayenge.\n\n"
    "Customer naam: ____________________  Dastkhat: ____________________\n"
    "Tareekh: ____________________  Contact: ____________________\n"
)

# Letters contain only a request for official support. No technical bypass steps.
LETTER_LANGS = ("roman", "english")


def _date() -> str:
    return time.strftime("%d %B %Y")


def letter_roman(d: dict) -> str:
    route = ROUTE_BY_ID.get(d.get("route_id", ""), {})
    docs = "\n".join("  - " + x for x in route.get("documents", [])) or "  - (documents attach karain)"
    return (
        "SERVICE REQUEST / MADAD KI DARKHWAST\n"
        "====================================\n"
        f"Tareekh: {_date()}\n"
        f"Case no: {d.get('case_no', '') or '(draft)'}\n"
        f"From: {d.get('technician', '') or 'Technician'} — {d.get('shop', '') or 'Local workspace'}\n\n"
        f"To: {d.get('brand', '') or 'Manufacturer / Carrier'} Authorized Support\n\n"
        "Assalam-o-Alaikum / Dear Support Team,\n\n"
        f"Mere customer ka device ({d.get('model', '') or 'model darj nahi'}, "
        f"IMEI/Serial: {d.get('device_id', '') or 'darj nahi'}) par "
        f"{d.get('issue_type', '') or route.get('issue', 'account / activation verification')} "
        "ka masla hai. Device ki milkiyat ki tasdeeq ke liye neeche diye gaye documents "
        "mushkilsa attachments hain.\n\n"
        "Attach / hazir documents:\n" + docs + "\n\n"
        "Darkhwast: baraye-meherbani apne OFFICIAL account recovery / de-registration / "
        "service-center process ke mutabiq is case ko check karain aur agla qadam batayein. "
        "Hum kisi bhi ghair-sarkari ya bypass tareeqe ki darkhwast nahi kar rahe; sirf "
        "manufacturer / carrier ke approved route par kaam chahiye.\n\n"
        f"Customer: {d.get('customer', '')}\n"
        f"Contact: {d.get('contact', '') or '—'}\n"
        f"Notes: {d.get('notes', '') or '—'}\n\n"
        "Shukriya.\n"
        f"{d.get('technician', '') or 'Technician'}\n"
        f"{d.get('shop', '') or 'MobileLab local workspace'}\n"
        "\n--- MobileLab ne ye letter tayyar kiya. Koi bypass step is mein nahi hai. ---\n"
    )


def letter_english(d: dict) -> str:
    route = ROUTE_BY_ID.get(d.get("route_id", ""), {})
    docs = "\n".join("  - " + x for x in route.get("documents", [])) or "  - (attach supporting documents)"
    return (
        "OFFICIAL SERVICE REQUEST\n"
        "========================\n"
        f"Date: {_date()}\n"
        f"Case no: {d.get('case_no', '') or '(draft)'}\n"
        f"From: {d.get('technician', '') or 'Technician'} — {d.get('shop', '') or 'Local workspace'}\n\n"
        f"To: {d.get('brand', '') or 'Manufacturer / Carrier'} Authorized Support\n\n"
        "Dear Support Team,\n\n"
        f"Our customer's device ({d.get('model', '') or 'model not recorded'}, "
        f"IMEI/Serial: {d.get('device_id', '') or 'not recorded'}) is affected by "
        f"{d.get('issue_type', '') or route.get('issue', 'account / activation verification')}. "
        "Proof of ownership is available and the documents listed below will be presented "
        "with this request.\n\n"
        "Supporting documents:\n" + docs + "\n\n"
        "Request: please review this case under your OFFICIAL account recovery, "
        "de-registration or service-centre process and advise the next step. We are "
        "expressly NOT requesting any unofficial or bypass method — only the "
        "manufacturer / carrier approved route.\n\n"
        f"Customer: {d.get('customer', '')}\n"
        f"Contact: {d.get('contact', '') or '-'}\n"
        f"Notes: {d.get('notes', '') or '-'}\n\n"
        "Thank you.\n"
        f"{d.get('technician', '') or 'Technician'}\n"
        f"{d.get('shop', '') or 'MobileLab local workspace'}\n"
        "\n--- Generated by MobileLab. Contains no bypass instructions. ---\n"
    )


def make_letter(data: dict, lang: str = "roman") -> str:
    """Build an official-route-only letter.

    ``validate_letter`` (not ``validate_case``) is intentional: a letter may only
    be produced once all four required proof-of-ownership items are ticked
    (AC-15 / AC-16). A case may still be saved as ``draft`` with incomplete proof.
    """
    cleaned, errors = validate_letter(data)
    if errors:
        raise ValueError("; ".join(errors))
    if lang not in LETTER_LANGS:
        raise ValueError("Language sirf 'roman' ya 'english' ho sakti hai")
    return (letter_roman if lang == "roman" else letter_english)(cleaned)


# ---------------------------------------------------------------- validation
MAX_LEN = {"default": 200, "notes": 1000, "device_id": 40, "issue_type": 200}
FIELDS = ("technician", "shop", "customer", "contact", "brand", "model",
          "device_id", "issue_type", "route_id", "notes", "case_no")


def _clean(value, limit: int) -> str:
    s = str(value if value is not None else "").strip()
    return s[:limit]


def validate_case(data: dict) -> tuple[dict, list[str]]:
    """Normalize a case payload. Returns (cleaned, errors)."""
    d = {k: _clean(data.get(k, ""), MAX_LEN.get(k, MAX_LEN["default"])) for k in FIELDS}
    errors: list[str] = []
    if not d["customer"]:
        errors.append("Customer ka naam zaroori hai")
    if not (d["model"] or d["brand"]):
        errors.append("Model ya brand mein se aik zaroori hai")
    if not data.get("consent"):
        errors.append("Customer consent zaroori hai (consent form par dastkhat)")
    raw_proof = data.get("proof", [])
    if not isinstance(raw_proof, (list, tuple)):
        raw_proof = []
    d["proof"] = sorted({str(x) for x in raw_proof if str(x) in CHECKLIST_IDS})
    missing = sorted(REQUIRED_IDS - set(d["proof"]))
    d["proof_ok"] = not missing
    d["missing_proof"] = missing
    if d["route_id"] and d["route_id"] not in ROUTE_BY_ID:
        d["route_id"] = ""
    d["consent"] = bool(data.get("consent"))
    return d, errors


def validate_letter(data: dict) -> tuple[dict, list[str]]:
    d, errors = validate_case(data)
    if not d["proof_ok"]:
        labels = ", ".join(next(c["label"] for c in CHECKLIST if c["id"] == m)
                           for m in d["missing_proof"])
        errors.append("Pehle zaroori proof items tick karain: " + labels)
    return d, errors


def make_case_no() -> str:
    return "ML-" + time.strftime("%Y%m%d") + "-" + os.urandom(3).hex().upper()


# ---------------------------------------------------------------- request check
# A refusal must always carry a reason + an official link + a safe next step.
BANNED_PATTERNS = [
    (r"\bfrp\b|factory reset protection", "google"),
    (r"huawei\s*id|huawei\s*account|emui.*(?:id|account)", "huawei"),
    (r"activation\s*lock|icloud|apple\s*id.*(?:remove|bypass)", "apple"),
    (r"knox|kg\s*lock|samsung\s*account|mdm|mobile enrollment", "samsung"),
    (r"carrier\s*(?:unlock|lock)|sim\s*(?:unlock|lock)|network\s*unlock", "carrier"),
    (r"imei\s*(?:change|repair|clean|tamper)|blacklist", "carrier"),
    (r"erase\s*(?:frp|persistent)|write\s*(?:frp|seccfg)|firehose.*(?:erase|frp)", "google"),
    # Generic wording has no brand: do NOT invent a brand-specific diagnosis.
    (r"\bbypass\b|\bremove\s+(?:id|account|lock)\b|\bunlocktool\b|\bchimera\b", ""),
]

# Reused only from ROUTES above — no new/unverified URLs (C16).
GENERIC_LINKS = [
    ["Google Account Recovery", "https://accounts.google.com/signin/recovery"],
    ["Huawei Support", "https://consumer.huawei.com/en/support/"],
    ["Samsung Support", "https://www.samsung.com/support/"],
    ["Apple Activation Lock support", "https://al-support.apple.com/"],
]


MAX_QUERY_CHARS = 4000


def check_request(text: str) -> dict:
    """Classify a customer request. Never returns bypass steps.

    Every blocked answer carries at least one official link (AC-13). A generic
    bypass wording returns an empty ``route_id`` instead of guessing a brand.

    The classification window is larger than the 500-char UI input field: if a
    long request were truncated first, a banned phrase placed after the cut-off
    would silently escape classification. The window is still hard-bounded to
    keep regex work constant and predictable.
    """
    raw = str(text if text is not None else "")[:MAX_QUERY_CHARS]
    low = raw.lower()
    matched = False
    route_id = ""
    for pattern, rid in BANNED_PATTERNS:
        if re.search(pattern, low):
            matched = True
            route_id = rid
            break
    if not matched:
        return {
            "blocked": False,
            "policy": POLICY_ID,
            "reason": "Ye kaam MobileLab ke andar hai — firmware / documentation / research.",
            "official_route": "",
            "route_id": "",
            "official_links": [],
            "documents": [],
            "safe_next_steps": [
                "Firmware Packages view mein folder scan + validate chalayein.",
                "Model Brief se model card aur mutaliqa live information dekhein.",
                "Research Agent se taaza firmware / security information len.",
                "Case register mein kaam ka record rakhein.",
            ],
            "refusal_line": "",
        }

    route = ROUTE_BY_ID.get(route_id)
    if route is None:
        official_route = "Account / activation ya ownership control — apne device ke brand ka official route chunein"
        official_links = [list(x) for x in GENERIC_LINKS]
        documents = [c["label"] for c in CHECKLIST if c["required"]]
    else:
        official_route = route["issue"]
        # Guarantee the link even for a route whose links list is empty.
        official_links = [list(x) for x in (route["links"] or GENERIC_LINKS)]
        documents = list(route["documents"])

    return {
        "blocked": True,
        "policy": POLICY_ID,
        "reason": (
            "Ye account / activation ya ownership control ka masla hai. Ye lock "
            "manufacturer ke SERVER par rehta hai, device ki local state mein nahi — "
            "is liye koi local tool isay durable taur par nahi hata sakta. Isi tarah "
            "ki automation chori-shuda ya galat haath mein gaye phone ko dobara "
            "chalane ke kaam aati hai, is liye MobileLab is ka koi step generate nahi karta."
        ),
        "official_route": official_route,
        "route_id": route["id"] if route else "",
        "official_links": official_links,
        "documents": documents,
        "safe_next_steps": [
            "Neeche wali proof-of-ownership checklist poori karain aur consent form par dastkhat len.",
            "Upar wale official links par jaa kar account recovery / service-center request shuru karain.",
            "Service-request letter (Roman Urdu ya English) tayyar karain aur case register mein save karain.",
            "Sarkari / department device ho to authorization / NOC letter attach karain.",
        ],
        "refusal_line": "Is ka koi bypass automation ya step-by-step tareeqa app mein nahi hai — lekin official raasta poori madad ke saath neeche maujood hai.",
    }


def overview() -> dict:
    return {
        "policy": POLICY,
        "routes": ROUTES,
        "checklist": CHECKLIST,
        "consent_text": CONSENT_TEXT,
        "letter_langs": list(LETTER_LANGS),
        "version": POLICY_ID,
    }
