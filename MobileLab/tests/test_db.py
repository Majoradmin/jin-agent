"""PHASE 8 - db.py CRUD / transaction / migration characterization tests.

All state lives in the harness throwaway DB; reset with H.reset_db() in setUp.
"""
from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _harness as H

import db                # noqa: E402

_HTTPD = None
_PORT = 0


def setUpModule():
    global _HTTPD, _PORT
    _HTTPD, _PORT = H.start()


def tearDownModule():
    global _HTTPD
    H.stop(_HTTPD)
    _HTTPD = None


def _scan(name, files=None):
    return {
        "root": "X:/" + name,
        "files": files if files is not None else [],
        "total_size": 0,
        "meta": {"oem": "", "model": name, "platform": "",
                 "chipset": "", "storage": ""},
    }


def _table_names():
    return [r["name"] for r in db.rows(
        "SELECT name FROM sqlite_master WHERE type='table'")]


class TestDb(unittest.TestCase):
    def setUp(self):
        H.reset_db()

    def test_save_package_single_txn(self):
        files = [
            {"relpath": "a.bin", "size": 10, "fingerprint": "fa",
             "kind": "binary", "meta": {}},
            {"relpath": "b.img", "size": 20, "fingerprint": "fb",
             "kind": "partition_image", "meta": {}},
            {"relpath": "c.xml", "size": 5, "fingerprint": "fc",
             "kind": "qcom_rawprogram", "meta": {}},
        ]
        pid = db.save_package(_scan("pkg", files), {"health": 90}, name="pkg")
        self.assertGreater(pid, 0)
        self.assertEqual(db.counts()["packages"], 1)
        self.assertEqual(db.counts()["files"], 3)
        detail = db.package_detail(pid)
        self.assertEqual(len(detail["files"]), 3)
        self.assertEqual(detail["report"]["health"], 90)

        # Atomic rollback: one malformed file row leaves NO half-written package.
        H.reset_db()
        bad = {"root": "X:/bad", "files": [{"size": 1}],
               "total_size": 1, "meta": {}}
        with self.assertRaises(Exception):
            db.save_package(bad, {"health": 50})
        self.assertEqual(db.counts()["packages"], 0)
        self.assertEqual(db.counts()["files"], 0)

    def test_duplicate_guid_is_idempotent(self):
        item = {"guid": "g1", "title": "T", "url": "u", "source": "s",
                "score": 1.0, "excerpt": "old", "khulasa": "k",
                "matched": "m", "published": "", "category": "general"}
        db.upsert_articles([item])
        db.upsert_articles([{**item, "score": 9.0, "excerpt": "new"}])
        self.assertEqual(db.counts()["articles"], 1)
        row = db.one("SELECT score, excerpt FROM articles WHERE guid=?", ("g1",))
        self.assertEqual(row["score"], 9.0)
        self.assertEqual(row["excerpt"], "new")

    def test_model_upsert(self):
        for oem in ("First", "Second"):
            code, _, body = H.post_json(
                _PORT, "/api/models",
                {"model": "SM-S918B", "oem": oem, "chipset": "SM8550"})
            self.assertEqual(code, 200)
            self.assertIs(body["ok"], True)
        rows = db.rows("SELECT model, oem FROM models")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["oem"], "Second")

    def test_job_validation_failure(self):
        code, _, body = H.post_json(_PORT, "/api/jobs", {})
        self.assertEqual(code, 400)
        self.assertIn("IMEI", body["error"])
        self.assertEqual(db.counts()["jobs"], 0)
        code, _, body = H.post_json(_PORT, "/api/jobs", {"imei": "123456"})
        self.assertEqual(code, 200)
        self.assertEqual(db.counts()["jobs"], 1)

    def test_package_delete_not_found(self):
        code, _, body = H.delete_json(_PORT, "/api/packages/999999")
        self.assertEqual(code, 404)
        self.assertIn("error", body)
        # A real delete still works and removes the row.
        pid = db.save_package(_scan("todelete"), {"health": 100}, name="todelete")
        code, _, body = H.delete_json(_PORT, "/api/packages/%d" % pid)
        self.assertEqual(code, 200)
        self.assertEqual(body["deleted"], pid)
        self.assertEqual(db.counts()["packages"], 0)

    def test_additive_migration_recreates_dropped_table(self):
        # An existing DB missing one table gains it back on init().
        db.execute("DROP TABLE models")
        self.assertNotIn("models", _table_names())
        db.init()
        self.assertIn("models", _table_names())
        # init() is idempotent and keeps the full 7-table schema.
        db.init()
        names = _table_names()
        for t in ("packages", "package_files", "articles", "models",
                  "jobs", "cases", "settings"):
            self.assertIn(t, names)


if __name__ == "__main__":
    unittest.main(verbosity=2)
