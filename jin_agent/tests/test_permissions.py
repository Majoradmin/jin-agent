"""P0-3 - DB/data permissions, .gitignore sidecars, Docker VOLUME."""

import os
import stat
import tempfile
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]

from jin_agent import store  # noqa: E402


def setUpModule():
    os.environ["JIN_AGENT_DATA"] = tempfile.mkdtemp(prefix="jin-perm-")
    store.init_db()


@unittest.skipIf(os.name == "nt", "POSIX permissions Windows par meaning nahi")
class TestSecurePermissions(unittest.TestCase):
    def test_data_dir_and_db_modes(self):
        store.secure_permissions()
        d = store.config.data_dir()
        db = store.config.db_path()
        self.assertEqual(stat.S_IMODE(d.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(db.stat().st_mode), 0o600)

    def test_connect_enforces_db_mode(self):
        # connect() ke foran baad bhi DB 0600 hona chahiye.
        con = store.connect()
        con.close()
        db = store.config.db_path()
        self.assertEqual(stat.S_IMODE(db.stat().st_mode), 0o600)

    def test_result_reports_modes(self):
        out = store.secure_permissions()
        self.assertEqual(out["dir"], 0o700)
        self.assertEqual(out["db"], 0o600)
        self.assertEqual(out["warnings"], [])

    def test_owner_only_helper(self):
        # Apne file par mode badalta hai (non-owner path test nahi ho sakta —
        # non-root process kisi aur ka file nahi bana sakta).
        p = Path(tempfile.mkdtemp(prefix="jin-perm-own-")) / "x.db"
        p.write_bytes(b"x")
        self.assertEqual(store._set_owner_only(p, 0o600), "")
        self.assertEqual(stat.S_IMODE(p.stat().st_mode), 0o600)


class TestRepoGuards(unittest.TestCase):
    def test_gitignore_sidecars_and_env(self):
        text = (BASE / ".gitignore").read_text(encoding="utf-8")
        for pattern in ("jin_agent/data/*.db-shm", "jin_agent/data/*.db-wal",
                        "*.sqlite-wal", "*.sqlite-shm", "*.db-journal", ".env*"):
            self.assertIn(pattern, text)

    def test_dockerfile_volume_and_mode(self):
        text = (BASE / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("VOLUME /app/jin_agent/data", text)
        self.assertIn("chmod 0700 /app/jin_agent/data", text)


if __name__ == "__main__":
    unittest.main()
