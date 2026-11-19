"""P42 - light commands ke liye alag bounded control pool (research ke peeche na atkein).

Live test me 10-45s lag tha: 2 busy research workers ke peeche chhote commands
queue me atkte the. Ab ``/status`` / ``/help`` / callbacks / baqi light commands
alag control pool par chalte hain; sirf research/explore/digest main pool par.
"""

import os
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

from jin_agent import telegram_bot as tb


class TestControlPool(unittest.TestCase):
    def tearDown(self):
        tb._shutdown_control_pool()

    def test_update_control_workers_default_and_env(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("JIN_AGENT_CONTROL_WORKERS", None)
            self.assertEqual(tb.update_control_workers(), 4)
        with mock.patch.dict(os.environ, {"JIN_AGENT_CONTROL_WORKERS": "7"}):
            self.assertEqual(tb.update_control_workers(), 7)
        with mock.patch.dict(os.environ, {"JIN_AGENT_CONTROL_WORKERS": "abc"}):
            self.assertEqual(tb.update_control_workers(), 4)
        with mock.patch.dict(os.environ, {"JIN_AGENT_CONTROL_WORKERS": "0"}):
            self.assertEqual(tb.update_control_workers(), 1)       # clamp min
        with mock.patch.dict(os.environ, {"JIN_AGENT_CONTROL_WORKERS": "99"}):
            self.assertEqual(tb.update_control_workers(), 16)      # clamp max

    def test_is_heavy_command(self):
        for cmd in ("research", "deep", "explore", "digest"):
            self.assertTrue(tb._is_heavy_command(cmd), cmd)
        for cmd in ("status", "help", "channels", "dork", "stop", "new", ""):
            self.assertFalse(tb._is_heavy_command(cmd), cmd)

    def test_submit_control_real_pool_runs_fn(self):
        done = threading.Event()

        def work():
            done.set()
            return 7

        main = ThreadPoolExecutor(max_workers=1)
        try:
            fut = tb._submit_control(main, work)
            self.assertEqual(fut.result(timeout=5), 7)
            self.assertTrue(done.is_set())
            self.assertIsNotNone(tb._control_pool)
            # control pool env size par bana (private attr — size ka ho)
            self.assertEqual(tb._control_pool._max_workers, tb.update_control_workers())
        finally:
            tb._shutdown_control_pool()
            main.shutdown(wait=False)

    def test_submit_control_fake_pool_uses_submit(self):
        """Tests ka injected pool — usi par submit (koi asli pool nahi)."""

        class FakePool:
            def __init__(self):
                self.calls = []

            def submit(self, fn, *a, **k):
                self.calls.append((fn, a, k))
                return "ok"

        fake = FakePool()
        self.assertEqual(tb._submit_control(fake, lambda: 1), "ok")
        self.assertEqual(len(fake.calls), 1)
        self.assertIsNone(tb._control_pool)

    def test_shutdown_control_pool_resets(self):
        tb._get_control_pool()
        self.assertIsNotNone(tb._control_pool)
        tb._shutdown_control_pool()
        self.assertIsNone(tb._control_pool)
        # dobara shutdown be-zaar
        tb._shutdown_control_pool()
        self.assertIsNone(tb._control_pool)


if __name__ == "__main__":
    unittest.main()
