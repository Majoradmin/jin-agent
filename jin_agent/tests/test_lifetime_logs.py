"""Lifetime fix (logs): plain-append logs bounded (G5).

``supervisor.log``, ``supervisor-child.log`` (pipe pump) aur ``alerts.log``
pehle unbounded barte the. Ab 2MB x 3 rotation ``logging_setup`` se aati hai.
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("JIN_AGENT_DATA", tempfile.mkdtemp(prefix="jin-life-log-"))

from jin_agent import alerts, logging_setup, supervisor  # noqa: E402


class TestBoundedAppend(unittest.TestCase):
    def test_rotates_at_size_cap(self):
        root = Path(tempfile.mkdtemp(prefix="jin-bounded-"))
        path = root / "supervisor.log"
        for i in range(200):
            logging_setup.bounded_append(path, "x" * 100, max_bytes=500, backups=3)
        files = sorted(p.name for p in root.iterdir())
        # base + .1 + .2 + .3 — 4 se zyada file nahi
        self.assertLessEqual(len(files), 4)
        total = sum(p.stat().st_size for p in root.iterdir())
        self.assertLess(total, 500 + 4 * 700)   # bounded, unbounded nahi

    def test_rotate_if_needed_small_file_noop(self):
        root = Path(tempfile.mkdtemp(prefix="jin-bounded-"))
        path = root / "alerts.log"
        path.write_text("hello\n", encoding="utf-8")
        self.assertFalse(logging_setup.rotate_if_needed(path, max_bytes=500))
        self.assertTrue(path.is_file())

    def test_rotate_if_needed_big_file_rotates(self):
        root = Path(tempfile.mkdtemp(prefix="jin-bounded-"))
        path = root / "alerts.log"
        path.write_text("y" * 600, encoding="utf-8")
        self.assertTrue(logging_setup.rotate_if_needed(path, max_bytes=500, backups=2))
        self.assertTrue((root / "alerts.log.1").is_file())

    def test_append_failure_returns_false_not_crash(self):
        # path parent ek file hai -> mkdir/open fail; exception nahi phootna chahiye
        root = Path(tempfile.mkdtemp(prefix="jin-bounded-"))
        blocker = root / "blocker"
        blocker.write_text("x", encoding="utf-8")
        self.assertFalse(logging_setup.bounded_append(blocker / "a.log", "line"))


class TestCallersUseBoundedWriter(unittest.TestCase):
    def test_supervisor_log_uses_bounded_append(self):
        with mock.patch.object(supervisor.logging_setup, "bounded_append",
                               return_value=True) as m:
            supervisor._log("lifetime test")
        self.assertEqual(m.call_count, 1)
        self.assertIn("lifetime test", m.call_args[0][1])

    def test_supervisor_log_falls_back_to_stderr(self):
        with mock.patch.object(supervisor.logging_setup, "bounded_append",
                               return_value=False), \
                mock.patch.object(supervisor.sys, "stderr") as err:
            supervisor._log("fallback")
        self.assertTrue(err.write.called)

    def test_alerts_notify_uses_bounded_append(self):
        with mock.patch.object(alerts.logging_setup, "bounded_append",
                               return_value=True) as m:
            alerts.notify("lifetime alert")
        self.assertEqual(m.call_count, 1)
        self.assertIn("lifetime alert", m.call_args[0][1])


if __name__ == "__main__":
    unittest.main()
