"""Firmware package scanner + validator.

Handles MediaTek (scatter / preloader / DA) and Qualcomm
(Sahara-Firehose programmer / rawprogram / patch / GPT) flash packages.

Scope note: this module INSPECTS and VALIDATES packages. It never generates
erase/write scripts for account, FRP, IMEI or ownership partitions.
"""
from __future__ import annotations

import hashlib
import os
import re
import xml.etree.ElementTree as ET

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_FILES = 4000
MAX_DEPTH = 6
FINGERPRINT_CHUNK = 512 * 1024

SKIP_DIRS = {".git", "node_modules", "__pycache__", "$recycle.bin", "system volume information"}

# Partitions that carry identity / ownership / anti-theft state. We only FLAG
# them so a technician double-checks legality and does not destroy calibration.
SENSITIVE_PARTITIONS = {
    "frp": "FRP / Google account state (server-side ownership check)",
    "persistent": "Persist / sensor calibration & DRM keys",
    "config": "Modem / device config",
    "devinfo": "Device identity & unlock flags",
    "modemst1": "Modem EFS copy 1 (IMEI / network calibration)",
    "modemst2": "Modem EFS copy 2 (IMEI / network calibration)",
    "fsc": "Modem file system cookie",
    "fsg": "Modem file system golden copy",
    "fsi": "Modem file system image",
    "sec": "Secure / provisioning data",
    "keystore": "Key store",
    "nvram": "MTK NVRAM (IMEI, WiFi/BT, calibration)",
    "nvdata": "MTK NVDATA",
    "nvcfg": "MTK NVCFG",
    "protect1": "MTK protected partition 1",
    "protect2": "MTK protected partition 2",
    "seccfg": "MTK security configuration",
    "proinfo": "Product / barcode info",
    "oem": "OEM reserved / unlock tokens",
    "misc": "Bootloader control block",
    "metadata": "Encryption metadata",
    "para": "Parameter / calibration",
    "otp": "One-time-programmed calibration",
}

CHIPSET_PATTERNS = [
    (r"(?<![a-z0-9])(sm[0-9]{4,5}|sdm[0-9]{3,4}|msm[0-9]{4,5}|qcm[0-9]{4}|qcs[0-9]{4}|"
     r"sd[0-9]{3,4}g?|snapdragon[ _-]?[0-9a-z+]{2,12})(?![a-z0-9])", "Qualcomm"),
    (r"(?<![a-z0-9])(mt[0-9]{4,5}|dimensity[ _-]?[0-9]{3,5}|helio[ _-]?[a-z0-9]{1,8})(?![a-z0-9])", "MediaTek"),
    (r"(?<![a-z0-9])(exynos[ _-]?[0-9]{3,5})(?![a-z0-9])", "Samsung Exynos"),
    (r"(?<![a-z0-9])(kirin[ _-]?[0-9]{3,5}[a-z]?|hi[0-9]{4})(?![a-z0-9])", "HiSilicon Kirin"),
    (r"(?<![a-z0-9])(unisoc|spreadtrum|ums[0-9]{3,4}|t[0-9]{3})(?![a-z0-9])", "UNISOC"),
    (r"(?<![a-z0-9])(a1[0-9]|apple[ _-]?a[0-9]{2})(?![a-z0-9])", "Apple Silicon"),
]

OEM_PATTERNS = [
    ("huawei", "Huawei"), ("honor", "Honor"), ("emui", "Huawei"), ("harmonyos", "Huawei"),
    ("samsung", "Samsung"), ("galaxy", "Samsung"), ("sm-", "Samsung"),
    ("xiaomi", "Xiaomi"), ("redmi", "Xiaomi"), ("poco", "Xiaomi"),
    ("oppo", "OPPO"), ("realme", "realme"), ("oneplus", "OnePlus"),
    ("vivo", "vivo"), ("iqoo", "iQOO"), ("tecno", "TECNO"),
    ("infinix", "Infinix"), ("motorola", "Motorola"), ("moto", "Motorola"),
    ("nokia", "Nokia"), ("hmd", "HMD Global"), ("apple", "Apple"),
    ("iphone", "Apple"), ("google", "Google"), ("pixel", "Google"),
    ("sony", "Sony"), ("xperia", "Sony"), ("lg", "LG"), ("asus", "ASUS"),
]


def human_size(n: int) -> str:
    n = float(n or 0)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


# ---------------------------------------------------------------------------
# Classification / fingerprint
# ---------------------------------------------------------------------------

def classify(name: str) -> str:
    n = name.lower()
    if "scatter" in n and n.endswith((".txt", ".ini", ".cfg")):
        return "mtk_scatter"
    if re.search(r"preloader.*\.(bin|img|mbn)$", n) or n.startswith("preloader"):
        return "mtk_preloader"
    if ("allinone_da" in n or "da_" in n or "download_agent" in n or "da_" in n) and n.endswith((".bin", ".img")):
        return "mtk_da"
    if n.endswith(".auth") or "auth_sv" in n or n.endswith(".cert"):
        return "mtk_auth"
    if "firehose" in n or re.search(r"^prog_.*\.(mbn|elf|bin)$", n):
        return "qcom_firehose"
    if n.startswith("rawprogram") and n.endswith(".xml"):
        return "qcom_rawprogram"
    if n.startswith("patch") and n.endswith(".xml"):
        return "qcom_patch"
    if re.search(r"^gpt_(main|backup|both)", n) or "primarygpt" in n or "backupgpt" in n:
        return "qcom_gpt"
    if n.endswith(".mbn") or n.endswith(".elf"):
        return "qcom_image"
    if n.endswith(".xml"):
        return "xml_other"
    if n.endswith(".img"):
        return "partition_image"
    if n.endswith((".bin", ".mbn", ".hex", ".elf")):
        return "binary"
    if n.endswith((".txt", ".md", ".log", ".cfg", ".ini")):
        return "text_doc"
    return "other"


def fingerprint(path: str) -> str:
    """Fast, stable fingerprint: size + first/last 512 KB. Not a full SHA-256."""
    try:
        size = os.path.getsize(path)
        h = hashlib.sha256()
        h.update(str(size).encode())
        with open(path, "rb") as f:
            h.update(f.read(FINGERPRINT_CHUNK))
            if size > FINGERPRINT_CHUNK * 2:
                f.seek(-FINGERPRINT_CHUNK, os.SEEK_END)
                h.update(f.read(FINGERPRINT_CHUNK))
        return h.hexdigest()[:32]
    except OSError:
        return ""


def detect_storage(text: str) -> str:
    t = text.lower()
    if "ufs" in t:
        return "UFS"
    if "emmc" in t or "mmc" in t:
        return "eMMC"
    if "nand" in t:
        return "NAND"
    if "spinor" in t or "nor" in t:
        return "SPI-NOR"
    return ""


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def parse_scatter(text: str) -> dict:
    out: dict = {"platform": "", "storage": "", "project": "", "config_version": "",
                 "partitions": [], "ok": False, "error": ""}
    try:
        general = re.search(r"-\s*platform:\s*(\S+)", text, re.I)
        if general:
            out["platform"] = general.group(1).strip()
        st = re.search(r"-\s*storage:\s*(\S+)", text, re.I)
        if st:
            out["storage"] = st.group(1).strip().upper().replace("HW_STORAGE_", "")
        pr = re.search(r"-\s*project:\s*(\S+)", text, re.I)
        if pr:
            out["project"] = pr.group(1).strip()
        cv = re.search(r"-\s*config_version:\s*(\S+)", text, re.I)
        if cv:
            out["config_version"] = cv.group(1).strip()

        blocks = re.split(r"(?=^\s*-\s*partition_index\s*:)", text, flags=re.M)
        for block in blocks:
            if not re.search(r"^\s*-\s*partition_index\s*:", block, re.M):
                continue
            part: dict = {}
            for key in ("partition_index", "partition_name", "file_name", "is_download",
                        "type", "linear_start_addr", "physical_start_addr", "partition_size",
                        "region", "storage", "operation_type", "is_reserved", "boundary_check"):
                m = re.search(rf"^\s*-?\s*{key}\s*:\s*(.+?)\s*$", block, re.M | re.I)
                if m:
                    part[key] = m.group(1).strip()
            if part.get("partition_name"):
                out["partitions"].append(part)
        out["ok"] = bool(out["partitions"])
        if not out["ok"]:
            out["error"] = "Scatter file mein koi partition block nahi mila."
    except Exception as e:  # pragma: no cover
        out["error"] = f"Scatter parse error: {e}"
    return out


def parse_program_xml(path: str) -> dict:
    out: dict = {"entries": [], "sector_size": 0, "luns": set(), "ok": False, "error": ""}
    try:
        tree = ET.parse(path)
        for el in tree.iter():
            if el.tag.lower().split("}")[-1] != "program":
                continue
            a = {k.lower(): v for k, v in el.attrib.items()}
            out["entries"].append(a)
            ss = int(a.get("sector_size_in_bytes", "0") or 0)
            if ss and not out["sector_size"]:
                out["sector_size"] = ss
            lun = a.get("physical_partition_number") or a.get("lun") or "0"
            out["luns"].add(str(lun))
        out["luns"] = sorted(out["luns"])
        out["ok"] = True
    except Exception as e:
        out["error"] = f"XML parse error: {e}"
    return out


def parse_patch_xml(path: str) -> dict:
    out: dict = {"count": 0, "ok": False, "error": ""}
    try:
        tree = ET.parse(path)
        out["count"] = sum(1 for el in tree.iter() if el.tag.lower().split("}")[-1] == "patch")
        out["ok"] = True
    except Exception as e:
        out["error"] = f"Patch XML parse error: {e}"
    return out


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

def _read_text(path: str, limit: int = 3_000_000) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read(limit)
    except OSError:
        return ""


def scan_folder(root: str) -> dict:
    root = os.path.abspath(root)
    if not os.path.isdir(root):
        raise ValueError("Yeh folder maujood nahi hai: " + root)

    files: list[dict] = []
    for dirpath, dirnames, filenames in os.walk(root):
        rel_depth = os.path.relpath(dirpath, root).count(os.sep)
        if rel_depth >= MAX_DEPTH:
            dirnames[:] = []
            continue
        dirnames[:] = [d for d in dirnames if d.lower() not in SKIP_DIRS and not d.startswith(".")]
        for fn in filenames:
            if len(files) >= MAX_FILES:
                break
            full = os.path.join(dirpath, fn)
            try:
                size = os.path.getsize(full)
            except OSError:
                continue
            rel = os.path.relpath(full, root).replace("\\", "/")
            item = {"relpath": rel, "name": fn, "size": size,
                    "kind": classify(fn), "fingerprint": fingerprint(full),
                    "meta": {}}
            files.append(item)
        if len(files) >= MAX_FILES:
            break

    scan = {"root": root, "files": files, "total_size": sum(f["size"] for f in files),
            "scatter": None, "programs": [], "patches": [], "meta": {}}

    # Parse scatter (first one found)
    for f in files:
        if f["kind"] == "mtk_scatter":
            parsed = parse_scatter(_read_text(os.path.join(root, f["relpath"])))
            f["meta"] = {"partitions": len(parsed["partitions"]), "ok": parsed["ok"]}
            scan["scatter"] = {"relpath": f["relpath"], **parsed}
            break

    # Parse Qualcomm XMLs
    for f in files:
        full = os.path.join(root, f["relpath"])
        if f["kind"] == "qcom_rawprogram":
            parsed = parse_program_xml(full)
            parsed["relpath"] = f["relpath"]
            f["meta"] = {"entries": len(parsed["entries"]), "ok": parsed["ok"],
                         "sector_size": parsed["sector_size"]}
            scan["programs"].append(parsed)
        elif f["kind"] == "qcom_patch":
            parsed = parse_patch_xml(full)
            parsed["relpath"] = f["relpath"]
            f["meta"] = parsed
            scan["patches"].append(parsed)

    scan["meta"] = infer_meta(scan)
    return scan


def infer_meta(scan: dict) -> dict:
    haystack = " ".join([os.path.basename(scan["root"])] +
                        [f["name"] for f in scan["files"]]).lower()
    if scan["scatter"] and scan["scatter"].get("platform"):
        haystack += " " + scan["scatter"]["platform"].lower()

    oem = ""
    for needle, label in OEM_PATTERNS:
        if needle in haystack:
            oem = label
            break

    chipset = ""
    platform = ""
    for pattern, label in CHIPSET_PATTERNS:
        m = re.search(pattern, haystack, re.I)
        if m:
            chipset = m.group(0).strip().upper()
            platform = label
            break
    if scan["scatter"] and scan["scatter"].get("platform"):
        platform = platform or "MediaTek"
        chipset = chipset or scan["scatter"]["platform"].upper()

    kinds = {f["kind"] for f in scan["files"]}
    if "mtk_scatter" in kinds:
        platform = platform or "MediaTek"
    elif "qcom_firehose" in kinds or scan["programs"]:
        platform = platform or "Qualcomm"

    storage = ""
    if scan["scatter"] and scan["scatter"].get("storage"):
        storage = detect_storage(scan["scatter"]["storage"])
    if not storage and scan["scatter"]:
        for p in scan["scatter"]["partitions"]:
            storage = detect_storage(p.get("region", "")) or detect_storage(p.get("storage", ""))
            if storage:
                break
    if not storage:
        loader_storages = {detect_storage(f["name"]) for f in scan["files"]
                           if f["kind"] == "qcom_firehose" and detect_storage(f["name"])}
        if len(loader_storages) == 1:
            storage = next(iter(loader_storages))
        elif len(loader_storages) > 1:
            storage = "mixed"
    if not storage and scan["programs"]:
        storage = detect_storage(" ".join(f["name"] for f in scan["files"]))

    model = ""
    m = re.search(r"\b(sm-[a-z0-9]{5,8}|[a-z]{3,5}-[al][a-z0-9]{2,6}|"
                  r"cph[0-9]{4}|rmx[0-9]{4}|v[0-9]{4}[a-z]{0,2}|[0-9]{5}[a-z0-9]{2,4})\b",
                  os.path.basename(scan["root"]).lower())
    if m:
        model = m.group(0).upper()
    if not model:
        model = os.path.basename(scan["root"])[:48]

    return {"oem": oem, "model": model, "chipset": chipset,
            "platform": platform, "storage": storage}


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

def _issue(level: str, code: str, msg: str, detail: str = "") -> dict:
    return {"level": level, "code": code, "msg": msg, "detail": detail}


def validate(scan: dict) -> dict:
    issues: list[dict] = []
    checks: list[dict] = []
    files = scan["files"]
    by_name: dict[str, list[dict]] = {}
    for f in files:
        by_name.setdefault(f["name"].lower(), []).append(f)
    kinds = [f["kind"] for f in files]

    is_mtk = "mtk_scatter" in kinds or "mtk_preloader" in kinds
    is_qcom = "qcom_firehose" in kinds or bool(scan["programs"])

    checks.append({"name": "Package type", "value": ("MTK + Qualcomm (mixed)" if is_mtk and is_qcom
                                                     else "MediaTek" if is_mtk else
                                                     "Qualcomm" if is_qcom else "Unknown"), "ok": not (is_mtk and is_qcom)})
    if is_mtk and is_qcom:
        issues.append(_issue("error", "MIXED_PLATFORM",
                             "Package mein MTK aur Qualcomm dono ke files hain.",
                             "Aik package sirf aik chipset platform ka hona chahiye. Mix package galat loader select hone ka sabab banta hai."))

    def exists(filename: str) -> bool:
        return filename.strip().lower() in by_name

    # ---------------- MediaTek ----------------
    if is_mtk:
        sc = scan["scatter"]
        if not sc:
            issues.append(_issue("error", "NO_SCATTER",
                                 "MTK scatter file nahi mili.",
                                 "SP Flash Tool ko partition layout ke liye *_Android_scatter.txt zaroori hai."))
        else:
            checks.append({"name": "Scatter partitions", "value": len(sc["partitions"]), "ok": sc["ok"]})
            if not sc["ok"]:
                issues.append(_issue("error", "SCATTER_PARSE", "Scatter file parse nahi hui.", sc.get("error", "")))
            missing = []
            seen = set()
            sensitive = []
            for p in sc["partitions"]:
                pn = p.get("partition_name", "").strip().lower()
                if pn in SENSITIVE_PARTITIONS:
                    sensitive.append(pn)
                if pn and pn in seen:
                    issues.append(_issue("warn", "DUP_PARTITION",
                                         f"Partition '{pn}' scatter mein do dafa hai.",
                                         "Duplicate entry se flash tool galat address likh sakta hai."))
                seen.add(pn)
                fn = p.get("file_name", "").strip()
                dl = p.get("is_download", "true").lower() in ("true", "1", "yes")
                if dl and fn and fn.upper() != "NONE" and not exists(fn):
                    missing.append(fn)
            checks.append({"name": "Scatter referenced files", "value": len(sc["partitions"]), "ok": True})
            if missing:
                issues.append(_issue("error", "MISSING_IMAGES",
                                     f"{len(missing)} scatter images folder mein maujood nahi hain.",
                                     ", ".join(dict.fromkeys(missing))[:900]))
            if sensitive:
                issues.append(_issue("info", "SENSITIVE_PARTITIONS",
                                     f"Scatter mein {len(sensitive)} hassas (identity/ownership) partitions hain.",
                                     "; ".join(f"{p}: {SENSITIVE_PARTITIONS[p]}" for p in dict.fromkeys(sensitive))[:900]))
            if sc.get("platform"):
                checks.append({"name": "Scatter platform", "value": sc["platform"], "ok": True})
            # storage cross-check
            st = detect_storage(sc.get("storage", ""))
            regions = " ".join(p.get("region", "") + " " + p.get("storage", "") for p in sc["partitions"])
            rst = detect_storage(regions)
            if st and rst and st != rst:
                issues.append(_issue("error", "STORAGE_MISMATCH_MTK",
                                     f"General storage '{st}' aur partition region '{rst}' alag hain.",
                                     "eMMC vs UFS mismatch preloader ko fail karta hai ya device brick kar sakta hai."))
            checks.append({"name": "Storage declaration", "value": st or rst or "unknown", "ok": bool(st or rst)})

        pre = [f for f in files if f["kind"] == "mtk_preloader"]
        checks.append({"name": "Preloader binaries", "value": len(pre), "ok": bool(pre)})
        if not pre:
            issues.append(_issue("error", "NO_PRELOADER",
                                 "preloader_*.bin file nahi mili.",
                                 "Preloader ke baghair BROM handoff nahi hota. Sahi model ka preloader zaroori hai."))
        else:
            for p in pre:
                if p["size"] < 20 * 1024:
                    issues.append(_issue("warn", "TINY_PRELOADER",
                                         f"Preloader '{p['name']}' sirf {human_size(p['size'])} ka hai.",
                                         "Aksar truncated / incomplete download ki nishani hai. Dobara hasil karain."))
            if len(pre) > 1:
                issues.append(_issue("warn", "MULTI_PRELOADER",
                                     f"{len(pre)} preloader files hain — konsi sahi hai confirm karain.",
                                     "Galat preloader = DRAM init fail, port aate hi chala jata hai."))
            # Preloader chipset vs scatter platform
            if scan["scatter"] and scan["scatter"].get("platform"):
                plat = scan["scatter"]["platform"].lower()
                for p in pre:
                    m = re.search(r"(mt[0-9]{4,5})", p["name"].lower())
                    if m and m.group(1) not in plat:
                        issues.append(_issue("warn", "PRELOADER_CHIPSET",
                                             f"Preloader '{p['name']}' ka chipset scatter platform '{plat}' se match nahi karta.",
                                             "Model-specific preloader hi use karain."))
                        break

        da = [f for f in files if f["kind"] in ("mtk_da", "mtk_auth")]
        checks.append({"name": "DA / auth files", "value": len(da), "ok": True})
        if not da:
            issues.append(_issue("info", "NO_DA",
                                 "Package mein DA / auth file nahi hai.",
                                 "Aksar flash tool apna MTK_AllInOne_DA khud provide karta hai; lekin naye security level ke liye matching DA + auth chahiye. Tool ke DA version check karain."))

    # ---------------- Qualcomm ----------------
    if is_qcom:
        fh = [f for f in files if f["kind"] == "qcom_firehose"]
        checks.append({"name": "Firehose programmers", "value": len(fh), "ok": bool(fh)})
        if not fh:
            issues.append(_issue("error", "NO_FIREHOSE",
                                 "prog_*firehose*.mbn/.elf programmer nahi mila.",
                                 "Sahara ke baad Firehose loader upload zaroori hai; is ke baghair 9008 port bekaar hai."))
        else:
            storages = {detect_storage(f["name"]) or "unknown" for f in fh}
            checks.append({"name": "Loader storage", "value": ", ".join(sorted(storages)), "ok": len(storages) == 1})
            if len(storages) > 1:
                issues.append(_issue("error", "MIXED_LOADER",
                                     "eMMC aur UFS dono tarah ke Firehose loader aik hi folder mein hain.",
                                     "Galat storage ka loader upload karne se port rehta hai magar koi command respond nahi karti. Sirf device ke mutabiq loader rakhein."))
            for p in fh:
                if p["size"] < 30 * 1024:
                    issues.append(_issue("warn", "TINY_FIREHOSE",
                                         f"Firehose '{p['name']}' sirf {human_size(p['size'])} ka hai.",
                                         "Ye truncated ya corrupt ho sakta hai; official firmware se dobara nikalein."))

        progs = scan["programs"]
        checks.append({"name": "rawprogram XML", "value": len(progs), "ok": bool(progs)})
        if not progs:
            issues.append(_issue("error", "NO_RAWPROGRAM",
                                 "rawprogram*.xml nahi mila.",
                                 "QFIL / fh_loader ko partition map ke liye rawprogram XML chahiye."))
        else:
            sector_sizes = {p["sector_size"] for p in progs if p["sector_size"]}
            if len(sector_sizes) > 1:
                issues.append(_issue("error", "SECTOR_SIZE_MISMATCH",
                                     f"rawprogram XMLs mein mukhtalif SECTOR_SIZE_IN_BYTES: {sorted(sector_sizes)}",
                                     "Sab XML aik hi sector size use karne chahiye warna offsets shift ho jate hain."))
            all_entries = []
            for p in progs:
                if not p["ok"]:
                    issues.append(_issue("error", "RAWPROGRAM_PARSE",
                                         f"{p['relpath']} parse nahi hua.", p["error"]))
                for e in p["entries"]:
                    all_entries.append((p["relpath"], e))

            missing, oversized, sensitive = [], [], []
            for xml_name, e in all_entries:
                fn = (e.get("filename") or "").strip()
                label = (e.get("label") or "").strip().lower()
                if label in SENSITIVE_PARTITIONS or any(k in label for k in ("frp", "modemst", "nvram", "persist")):
                    sensitive.append(label)
                if fn and fn.upper() != "DISK" and not exists(fn.lower()):
                    missing.append(fn)
                if fn and exists(fn.lower()):
                    real = by_name[fn.lower()][0]["size"]
                    try:
                        alloc = int(e.get("num_partition_sectors", "0")) * int(e.get("sector_size_in_bytes", "0"))
                    except ValueError:
                        alloc = 0
                    if alloc and real > alloc * 1.02:
                        oversized.append(f"{fn}: file {human_size(real)} > allocated {human_size(alloc)}")
            if missing:
                issues.append(_issue("error", "MISSING_RAW_IMAGES",
                                     f"{len(missing)} rawprogram images folder mein nahi hain.",
                                     ", ".join(dict.fromkeys(missing))[:900]))
            if oversized:
                issues.append(_issue("error", "IMAGE_LARGER_THAN_PARTITION",
                                     f"{len(oversized)} image apni partition se bari hai.",
                                     "; ".join(oversized[:6])[:900]))
            if sensitive:
                issues.append(_issue("info", "SENSITIVE_PARTITIONS",
                                     f"{len(sensitive)} hassas (identity/ownership) partition entries hain.",
                                     ", ".join(sorted(set(sensitive)))[:600]))

            # Overlapping sector ranges (very common cause of silent corruption)
            ranges: dict[str, list] = {}
            for xml_name, e in all_entries:
                try:
                    start = int(str(e.get("start_sector", "0")), 0)
                    count = int(str(e.get("num_partition_sectors", "0")), 0)
                except ValueError:
                    continue
                if count <= 0:
                    continue
                lun = str(e.get("physical_partition_number") or e.get("lun") or "0")
                ranges.setdefault(lun, []).append((start, start + count, e.get("label", "?"), xml_name))
            overlaps = []
            for lun, rs in ranges.items():
                rs.sort()
                for i in range(1, len(rs)):
                    if rs[i][0] < rs[i - 1][1]:
                        overlaps.append(f"LUN {lun}: '{rs[i-1][2]}' aur '{rs[i][2]}' overlap")
            checks.append({"name": "Sector overlap check", "value": f"{len(overlaps)} overlap", "ok": not overlaps})
            if overlaps:
                issues.append(_issue("warn", "SECTOR_OVERLAP",
                                     f"{len(overlaps)} partition ranges aik doosre par charh rahe hain.",
                                     "; ".join(overlaps[:6])[:700]))

            luns = {str(l) for p in progs for l in p.get("luns", [])}
            checks.append({"name": "LUNs covered", "value": ", ".join(sorted(luns)) or "none", "ok": True})
            declared = scan["meta"].get("storage", "")
            has_ufs_loader = any(detect_storage(f["name"]) == "UFS" for f in fh)
            if (declared == "UFS" or has_ufs_loader) and luns == {"0"}:
                issues.append(_issue("warn", "UFS_SINGLE_LUN",
                                     "UFS package hai magar sirf LUN 0 ka XML hai.",
                                     "UFS firmware aksar kai LUN (0..5) use karta hai; sab rawprogram*.xml maujood hon chahiye."))

        patches = scan["patches"]
        checks.append({"name": "patch XML", "value": len(patches), "ok": bool(patches)})
        if not patches:
            issues.append(_issue("info", "NO_PATCH",
                                 "patch*.xml nahi mila.",
                                 "Har package mein patch XML zaroori nahi, lekin GPT/boot header patch ke liye aksar chahiye."))

        gpt = [f for f in files if f["kind"] == "qcom_gpt"]
        checks.append({"name": "GPT binaries", "value": len(gpt), "ok": bool(gpt)})
        if progs and not gpt:
            issues.append(_issue("warn", "NO_GPT",
                                 "GPT (gpt_main0 / gpt_backup0) file nahi mili.",
                                 "Agar rawprogram XML khud GPT likhta hai to theek hai; warna partition table nahi banegi."))

    # ---------------- General ----------------
    empties = [f["name"] for f in files if f["size"] == 0]
    if empties:
        issues.append(_issue("warn", "EMPTY_FILES", f"{len(empties)} zero-byte files hain.",
                             ", ".join(empties[:8])))
    checks.append({"name": "Total files", "value": len(files), "ok": bool(files)})
    checks.append({"name": "Package size", "value": human_size(scan["total_size"]), "ok": True})

    if not is_mtk and not is_qcom:
        issues.append(_issue("warn", "UNKNOWN_PACKAGE",
                             "Na MTK scatter/preloader aur na Qualcomm firehose/rawprogram mila.",
                             "Folder sirf loose images ya docs rakh raha hai; scan karne ke liye sahi firmware package point karain."))

    errors = sum(1 for i in issues if i["level"] == "error")
    warns = sum(1 for i in issues if i["level"] == "warn")
    health = max(0, 100 - errors * 14 - warns * 5)
    return {
        "health": health,
        "platform": scan["meta"].get("platform", "Unknown"),
        "issues": issues, "checks": checks,
        "counts": {"error": errors, "warn": warns,
                   "info": sum(1 for i in issues if i["level"] == "info")},
        "scanned_at": __import__("time").time(),
    }
