"""Lifetime fix (server): hosted par scheduler auto-start (G1)."""

import os
import tempfile
import unittest
from unittest import mock

from jin_agent import server  # noqa: E402


def setUpModule():
    os.environ["JIN_AGENT_DATA"] = tempfile.mkdtemp(prefix="jin-life-srv-")


class FakeScheduler:
    instances = []

    def __init__(self, cfg=None, offline=True):
        self.offline = offline
        self._alive = False
        FakeScheduler.instances.append(self)

    def start(self):
        self._alive = True

    def is_alive(self):
        return self._alive

    def stop(self):
        self._alive = False


class FakeHTTPD:
    def __init__(self):
        self.server_address = ("127.0.0.1", 0)

    def serve_forever(self, poll_interval=0.4):
        raise KeyboardInterrupt

    def server_close(self):
        pass


class TestSchedulerAutoStart(unittest.TestCase):
    def tearDown(self):
        FakeScheduler.instances = []

    def test_enabled_by_default(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("JIN_AGENT_SCHEDULER", None)
            self.assertTrue(server._scheduler_enabled())
        for value in ("off", "0", "false", "no"):
            with mock.patch.dict(os.environ, {"JIN_AGENT_SCHEDULER": value}):
                self.assertFalse(server._scheduler_enabled(), value)

    def test_start_scheduler_off_returns_none(self):
        with mock.patch.dict(os.environ, {"JIN_AGENT_SCHEDULER": "off"}):
            self.assertIsNone(server._start_scheduler())

    def test_serve_starts_and_stops_scheduler(self):
        with mock.patch.object(server, "make_server",
                               lambda port, host=None: FakeHTTPD()), \
                mock.patch.object(server.scheduler, "Scheduler", FakeScheduler), \
                mock.patch.object(server, "_SCHEDULER", None):
            server.serve(0)
        self.assertEqual(len(FakeScheduler.instances), 1)
        self.assertTrue(FakeScheduler.instances[0]._alive is False)

    def test_serve_respects_off(self):
        with mock.patch.object(server, "make_server",
                               lambda port, host=None: FakeHTTPD()), \
                mock.patch.object(server.scheduler, "Scheduler", FakeScheduler), \
                mock.patch.object(server, "_SCHEDULER", None), \
                mock.patch.dict(os.environ, {"JIN_AGENT_SCHEDULER": "off"}):
            server.serve(0)
        self.assertEqual(FakeScheduler.instances, [])


if __name__ == "__main__":
    unittest.main()
