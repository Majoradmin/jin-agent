"""P0-4 - Backup RESTORE: confirm gate, integrity/schema checks, atomic replace,
CLI aur /api/restore."""

import json
import os
import sqlite3
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]

from jin_agent import __main__ as cli  # noqa: E402
from jin_agent import server, store, util  # noqa: E402

HTTPD = None
THREAD = None
PORT = 0


def setUpModule():
    global HTTPD, THREAD, PORT
    os.environ["JIN_AGENT_DATA"] = tempfile.mkdtemp(prefix="jin-restore-")
    os.environ["JIN_AGENT_ADMIN_TOKEN"] = "jin-restore-admin"
    store.init_db()
    HTTPD = server.make_server(0)
    PORT = HTTPD.server_address[1]
    THREAD = threading.Thread(target=HTTPD.serve_forever,
                              kwargs={"poll_interval": 0.2}, daemon=True)
    THREAD.start()


def tearDownModule():
    HTTPD.shutdown()
    HTTPD.server_close()
    THREAD.join(5)


def post(path, body):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"http://127.0.0.1:{PORT}{path}", data=data, method="POST",
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + os.environ["JIN_AGENT_ADMIN_TOKEN"]})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def rec(title, key):
    return {
        "guid": key + ":" + util.fingerprint(title),
        "title": title,
        "url": "https://news.google.com/" + util.fingerprint(title)[:10],
        "canonical": "", "source": "Test", "source_key": key,
        "category": "Security", "published": util.now_iso(),
        "date_checked": util.now_iso(), "fetched_at": util.now_iso(),
        "excerpt": "restore round-trip", "body": "",
        "fingerprint": util.fingerprint(title),
        "content_hash": util.sha256(title), "entities": [],
        "score": 1.0, "reasons": ["test"], "confidence": 0.8,
        "verified": True, "cross_verified": False, "link_only": False,
        "useful": 0, "meta": {},
    }


class TestRestore(unittest.TestCase):
    def test_round_trip(self):
        store.upsert_items([rec("Restore round trip item", "restore")])
        before = store.counts()["items"]
        self.assertGreaterEqual(before, 1)
        backup = store.backup()
        self.assertTrue(Path(backup["path"]).is_file())

        with store.session() as con:
            con.execute("DELETE FROM items")
        self.assertEqual(store.counts()["items"], 0)

        out = store.restore(backup["path"], confirm=True)
        self.assertEqual(out["items"], before)
        self.assertEqual(store.counts()["items"], before)
        self.assertIsNotNone(out["safety_backup"])
        self.assertEqual(out["integrity"], "ok")
        self.assertEqual(Path(out["path"]), store.config.db_path())

    def test_confirm_false_rejected(self):
        backup = store.backup()
        with self.assertRaises(ValueError) as ctx:
            store.restore(backup["path"])
        self.assertIn("confirm=True", str(ctx.exception))

    def test_missing_file(self):
        with self.assertRaises(ValueError) as ctx:
            store.restore("/nonexistent/jin_agent.db", confirm=True)
        self.assertIn("mojood nahi", str(ctx.exception))

    def test_path_traversal_rejected(self):
        with self.assertRaises(ValueError):
            store.restore("../jin_agent.db", confirm=True)

    def test_corrupt_file(self):
        bad = Path(tempfile.mkdtemp(prefix="jin-restore-bad-")) / "bad.db"
        bad.write_text("ye sqlite database nahi hai", encoding="utf-8")
        with self.assertRaises(ValueError) as ctx:
            store.restore(str(bad), confirm=True)
        self.assertIn("corrupt", str(ctx.exception))

    def test_restore_survives_retention_prune(self):
        # Source restore ke waqt tak mojood ho, magar safety backup ke andar
        # _prune_backups use delete kar de — staging copy bachati hai.
        store.upsert_items([rec("Prune survivor", "prunesurvivor")])
        old = store.backup()["path"]
        self.assertTrue(Path(old).is_file())
        for i in range(6):
            store.upsert_items([rec(f"filler {i}", f"filler{i}")])
            store.backup()
        self.assertTrue(Path(old).is_file())  # keep=7: abhi sab mojood
        with store.session() as con:
            con.execute("DELETE FROM items")
        out = store.restore(old, confirm=True)
        self.assertEqual(out["items"], 1)

    def test_missing_tables(self):
        empty = Path(tempfile.mkdtemp(prefix="jin-restore-empty-")) / "empty.db"
        con = sqlite3.connect(str(empty))
        con.execute("CREATE TABLE dummy(x)")
        con.commit()
        con.close()
        with self.assertRaises(ValueError) as ctx:
            store.restore(str(empty), confirm=True)
        self.assertIn("required tables", str(ctx.exception))


class TestRestoreCLI(unittest.TestCase):
    def test_without_confirm_returns_1(self):
        backup = store.backup()
        self.assertEqual(cli.main(["restore", "--from", backup["path"]]), 1)
        self.assertEqual(cli.main(["restore", backup["path"]]), 1)

    def test_with_confirm_returns_0(self):
        store.upsert_items([rec("CLI restore item", "clirestore")])
        backup = store.backup()
        with store.session() as con:
            con.execute("DELETE FROM items")
        self.assertEqual(cli.main(["restore", "--from", backup["path"],
                                   "--confirm"]), 0)
        self.assertGreaterEqual(store.counts()["items"], 1)


class TestRestoreHTTP(unittest.TestCase):
    def test_requires_confirm(self):
        backup = store.backup()
        code, body = post("/api/restore", {"path": backup["path"]})
        self.assertEqual(code, 400)
        self.assertFalse(body.get("ok"))

    def test_missing_path(self):
        code, body = post("/api/restore", {"confirm": True})
        self.assertEqual(code, 400)

    def test_restore_ok(self):
        store.upsert_items([rec("HTTP restore item", "httprestore")])
        backup = store.backup()
        with store.session() as con:
            con.execute("DELETE FROM items")
        code, body = post("/api/restore", {"path": backup["path"],
                                           "confirm": True})
        self.assertEqual(code, 200)
        self.assertTrue(body.get("ok"))
        self.assertEqual(body["result"]["integrity"], "ok")
        self.assertGreaterEqual(store.counts()["items"], 1)


if __name__ == "__main__":
    unittest.main()
