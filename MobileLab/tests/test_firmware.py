"""PHASE 8 - firmware scanner / validator characterization tests (stdlib).

Read-only boundary: these tests only SCAN, PARSE and VALIDATE synthetic / demo
packages. No device write / erase / flash operation is performed or expected.
"""
from __future__ import annotations

import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _harness as H

BASE = H.BASE
import firmware as fw            # noqa: E402

MTK = BASE / "samples" / "MTK_Demo_MT6899_UFS"
QCOM = BASE / "samples" / "QCOM_Demo_SM8650_UFS"

_HTTPD = None
_PORT = 0


def setUpModule():
    global _HTTPD, _PORT
    _HTTPD, _PORT = H.start()


def tearDownModule():
    global _HTTPD
    H.stop(_HTTPD)
    _HTTPD = None


class TestFirmwareScan(unittest.TestCase):
    def setUp(self):
        H.reset_db()

    def test_scan_valid_mtk_package_happy_path(self):
        scan = fw.scan_folder(str(MTK))
        self.assertEqual(len(scan["files"]), 9)
        self.assertIsNotNone(scan["scatter"])
        self.assertTrue(scan["scatter"]["ok"])
        self.assertEqual(scan["scatter"]["platform"], "MT6899")
        self.assertEqual(scan["scatter"]["storage"], "UFS")
        self.assertEqual(len(scan["scatter"]["partitions"]), 8)
        self.assertEqual(scan["programs"], [])
        meta = scan["meta"]
        self.assertEqual(meta["platform"], "MediaTek")
        self.assertEqual(meta["chipset"], "MT6899")
        self.assertEqual(meta["storage"], "UFS")

        report = fw.validate(scan)
        self.assertEqual(report["platform"], "MediaTek")
        for key in ("health", "issues", "checks", "counts", "scanned_at"):
            self.assertIn(key, report)
        self.assertGreaterEqual(report["health"], 0)
        self.assertLessEqual(report["health"], 100)

        # Sensitive (identity / ownership) partitions are FLAGGED as info only,
        # never written or erased (Sahulat & Safe Service Policy boundary).
        self.assertIn("frp", fw.SENSITIVE_PARTITIONS)
        self.assertIn("nvram", fw.SENSITIVE_PARTITIONS)
        sens = [i for i in report["issues"] if i["code"] == "SENSITIVE_PARTITIONS"]
        self.assertTrue(sens)
        self.assertTrue(all(i["level"] == "info" for i in sens))

        # Characterization of the read-only scan boundary: the scanner module
        # contains no destructive / device-write call capability.
        src = (BASE / "firmware.py").read_text(encoding="utf-8")
        for bad in ("os.remove", "os.system", "os.popen", "subprocess",
                    "shutil.rmtree", "os.startfile"):
            self.assertNotIn(bad, src, bad)

    def test_scan_valid_qcom_package_happy_path(self):
        scan = fw.scan_folder(str(QCOM))
        self.assertEqual(len(scan["files"]), 8)
        self.assertIsNone(scan["scatter"])
        self.assertEqual(scan["meta"]["platform"], "Qualcomm")
        self.assertEqual(scan["meta"]["chipset"], "SM8650")
        self.assertEqual(scan["meta"]["storage"], "mixed")

        self.assertTrue(scan["programs"])
        prog = scan["programs"][0]
        self.assertTrue(prog["ok"])
        self.assertEqual(len(prog["entries"]), 7)
        self.assertEqual(prog["sector_size"], 4096)
        self.assertEqual(prog["luns"], ["0"])
        self.assertTrue(scan["patches"])
        self.assertTrue(scan["patches"][0]["ok"])
        self.assertEqual(scan["patches"][0]["count"], 2)

        report = fw.validate(scan)
        self.assertEqual(report["platform"], "Qualcomm")
        self.assertIn("health", report)
        sens = [i for i in report["issues"] if i["code"] == "SENSITIVE_PARTITIONS"]
        self.assertTrue(sens)
        self.assertTrue(all(i["level"] == "info" for i in sens))

    def test_dtd_entity_rejected(self):
        # _xml_precheck returns a Roman-Urdu safe error for every DTD/entity form.
        bad_samples = {
            "doctype": b'<?xml version="1.0"?><!DOCTYPE data [<!ENTITY x "y">]><data/>',
            "entity": b'<!ENTITY xxe SYSTEM "file:///etc/passwd">',
            "notation": b'<!NOTATION foo SYSTEM "foo">',
            "system": b'<!DOCTYPE data SYSTEM "http://evil/x.dtd">',
            "public": b'<!DOCTYPE data PUBLIC "-//x//y" "http://evil/x.dtd">',
            "external_id": b'<!ELEMENT x SYSTEM "foo">',
        }
        for label, data in bad_samples.items():
            with self.subTest(kind=label):
                self.assertTrue(fw._xml_precheck(data))
        # Safe content passes (empty string); SYSTEM inside a comment is data.
        self.assertEqual(fw._xml_precheck(b'<?xml version="1.0"?><data><program/></data>'), "")
        self.assertEqual(fw._xml_precheck(b'<!-- SYSTEM evil --><data/>'), "")
        self.assertEqual(fw._xml_precheck("<data/>"), "")

        # Parsers reject a DTD-bearing file before any Expat parsing (no resolve).
        with tempfile.TemporaryDirectory(prefix="p8_dtd_") as d:
            rp = os.path.join(d, "rawprogram0.xml")
            with open(rp, "w", encoding="utf-8") as f:
                f.write('<?xml version="1.0"?><!DOCTYPE data [<!ENTITY xxe SYSTEM '
                        '"file:///etc/passwd">]><data><program label="x" filename="a.bin" '
                        'SECTOR_SIZE_IN_BYTES="4096"/></data>')
            parsed = fw.parse_program_xml(rp)
            self.assertFalse(parsed["ok"])
            self.assertIn("XML safe-check", parsed["error"])

            pp = os.path.join(d, "patch0.xml")
            with open(pp, "w", encoding="utf-8") as f:
                f.write('<!DOCTYPE patches [<!ENTITY e "x">]><patches><patch/></patches>')
            p2 = fw.parse_patch_xml(pp)
            self.assertFalse(p2["ok"])
            self.assertIn("XML safe-check", p2["error"])

    def test_file_count_boundary_4000(self):
        self.assertEqual(fw.MAX_FILES, 4000)
        with tempfile.TemporaryDirectory(prefix="p8_boundary_") as d:
            for i in range(fw.MAX_FILES + 5):
                with open(os.path.join(d, "f%04d.bin" % i), "wb") as f:
                    f.write(b"x")
            scan = fw.scan_folder(d)
            self.assertEqual(len(scan["files"]), fw.MAX_FILES)
            self.assertEqual(scan["total_size"], fw.MAX_FILES)


class TestFirmwareHelpers(unittest.TestCase):
    def test_human_size(self):
        self.assertEqual(fw.human_size(0), "0 B")
        self.assertEqual(fw.human_size(512), "512 B")
        self.assertEqual(fw.human_size(1024), "1.0 KB")
        self.assertEqual(fw.human_size(1536), "1.5 KB")
        self.assertEqual(fw.human_size(1024 * 1024), "1.0 MB")
        self.assertEqual(fw.human_size(5 * 1024 ** 3), "5.0 GB")

    def test_classify(self):
        cases = {
            "MT6899_Android_scatter.txt": "mtk_scatter",
            "preloader_mt6899.bin": "mtk_preloader",
            "MTK_AllInOne_DA.bin": "mtk_da",
            "auth_sv5.auth": "mtk_auth",
            "prog_ufs_firehose.elf": "qcom_firehose",
            "rawprogram0.xml": "qcom_rawprogram",
            "patch0.xml": "qcom_patch",
            "gpt_main0.bin": "qcom_gpt",
            "boot.img": "partition_image",
            "xbl_a.mbn": "qcom_image",
            "notes.md": "text_doc",
            "weird.xyz": "other",
        }
        for name, kind in cases.items():
            with self.subTest(name=name):
                self.assertEqual(fw.classify(name), kind)

    def test_detect_storage(self):
        cases = {"UFS": "UFS", "emmc": "eMMC", "HW_STORAGE_UFS": "UFS",
                 "NAND": "NAND", "spinor": "SPI-NOR", "nothing": ""}
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(fw.detect_storage(text), expected)

    def test_parse_program_and_patch_xml_real_samples(self):
        p = fw.parse_program_xml(str(QCOM / "rawprogram0.xml"))
        self.assertTrue(p["ok"])
        self.assertEqual(len(p["entries"]), 7)
        self.assertEqual(p["sector_size"], 4096)
        self.assertEqual(p["luns"], ["0"])
        q = fw.parse_patch_xml(str(QCOM / "patch0.xml"))
        self.assertTrue(q["ok"])
        self.assertEqual(q["count"], 2)

    def test_infer_meta(self):
        scan = {
            "root": str(MTK),
            "files": [{"name": "preloader_mt6899.bin", "kind": "mtk_preloader"}],
            "scatter": {"platform": "MT6899", "storage": "UFS", "partitions": []},
            "programs": [],
            "meta": {},
        }
        meta = fw.infer_meta(scan)
        self.assertEqual(meta["platform"], "MediaTek")
        self.assertEqual(meta["chipset"], "MT6899")
        self.assertEqual(meta["storage"], "UFS")

    def test_validate_unknown_package_is_flagged_not_error(self):
        with tempfile.TemporaryDirectory(prefix="p8_empty_") as d:
            scan = fw.scan_folder(d)
            report = fw.validate(scan)
        codes = [i["code"] for i in report["issues"]]
        self.assertIn("UNKNOWN_PACKAGE", codes)
        self.assertEqual(report["counts"]["error"], 0)
        self.assertGreaterEqual(report["health"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
