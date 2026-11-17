"""P27.5 - Bot supervisor (watchdog): crash par restart, stop-aware."""

import os
import tempfile
import threading
import unittest

os.environ.setdefault("JIN_AGENT_DATA", tempfile.mkdtemp(prefix="jin-wd-"))

from jin_agent import watchdog


class FakeProc:
    pid = 4242

    def __init__(self, code=0):
        self.code = code

    def wait(self):
        return self.code

    def terminate(self):
        pass


class TestWatchdog(unittest.TestCase):
    def test_spawns_bot_and_stops(self):
        calls = []
        stop = threading.Event()

        def spawn():
            calls.append(1)
            stop.set()
            return FakeProc(0)

        rc = watchdog.run(interval=2, spawn=spawn, stop=stop)
        self.assertEqual(rc, 0)
        self.assertEqual(len(calls), 1)

    def test_spawn_failure_does_not_crash(self):
        calls = []
        stop = threading.Event()

        def spawn():
            calls.append(1)
            stop.set()
            raise RuntimeError("boom")

        rc = watchdog.run(interval=2, spawn=spawn, stop=stop)
        self.assertEqual(rc, 0)
        self.assertEqual(len(calls), 1)

    def test_restarts_after_exit(self):
        calls = []
        stop = threading.Event()

        def spawn():
            calls.append(1)
            if len(calls) >= 2:
                stop.set()
            return FakeProc(1)

        rc = watchdog.run(interval=2, spawn=spawn, stop=stop)
        self.assertEqual(rc, 0)
        self.assertGreaterEqual(len(calls), 2)

    def test_main_signature(self):
        self.assertTrue(callable(watchdog.main))
        self.assertEqual(watchdog.BOT_CMD[0], "-X")


if __name__ == "__main__":
    unittest.main()
