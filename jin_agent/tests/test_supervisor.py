"""Hosted supervisor: console + bot ek saath, auto-restart, clean shutdown.

Context: bot akele long polling karta hai aur port nahi kholta — hosted
reverse proxy ko 502 milta tha. Supervisor dono child chalata hai.
"""

import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("JIN_AGENT_DATA", tempfile.mkdtemp(prefix="jin-sup-"))

from jin_agent import supervisor  # noqa: E402

BASE = Path(__file__).resolve().parents[2]


class FakeProc:
    pid = 99

    def __init__(self, exits=False, code=1):
        self._exits = exits
        self.code = code
        self.terminated = False
        self.killed = False

    def poll(self):
        return self.code if self._exits else None

    def terminate(self):
        self.terminated = True
        self._exits = True

    def kill(self):
        self.killed = True
        self._exits = True

    def wait(self, timeout=None):
        if not self._exits:
            raise RuntimeError("abhi chal raha hai")
        return self.code


class TestCommands(unittest.TestCase):
    def test_console_and_bot_commands(self):
        cmds = supervisor.commands(port=8766, host=None)
        self.assertIn("serve", cmds["console"])
        self.assertIn("bot", cmds["bot"])
        self.assertIn("--port", cmds["console"])
        self.assertIn("8766", cmds["console"])

    def test_host_only_passed_when_explicit(self):
        cmds = supervisor.commands(port=8766, host=None)
        self.assertNotIn("--host", cmds["console"])  # loopback default
        cmds = supervisor.commands(port=8766, host="0.0.0.0")
        self.assertIn("--host", cmds["console"])
        self.assertIn("0.0.0.0", cmds["console"])

    def test_port_from_env(self):
        with mock.patch.dict(os.environ, {"PORT": "9999"}):
            cmds = supervisor.commands(host=None)
        self.assertIn("9999", cmds["console"])


class TestRun(unittest.TestCase):
    def test_spawns_both_and_terminates_on_stop(self):
        stop = threading.Event()
        procs = []

        def spawn(cmd):
            p = FakeProc()
            procs.append(p)
            if len(procs) >= 2:
                stop.set()
            return p

        rc = supervisor.run(interval=2, stop=stop, spawn=spawn,
                            sleep_fn=lambda s: None)
        self.assertEqual(rc, 0)
        self.assertEqual(len(procs), 2)
        self.assertTrue(all(p.terminated for p in procs))

    def test_restarts_exited_child(self):
        clock = [100.0]
        stop = threading.Event()
        procs = []

        def spawn(cmd):
            p = FakeProc(exits=True)
            procs.append(cmd)
            if len(procs) >= 3:
                stop.set()
            return p

        with mock.patch.object(supervisor.time, "monotonic",
                               lambda: clock[0]):
            rc = supervisor.run(interval=2, max_backoff=10, stop=stop,
                                spawn=spawn,
                                sleep_fn=lambda s: clock.__setitem__(
                                    0, clock[0] + s))
        self.assertEqual(rc, 0)
        console_spawns = [c for c in procs if "serve" in c]
        bot_spawns = [c for c in procs if "bot" in c]
        self.assertGreaterEqual(len(console_spawns), 2)  # restart hua
        self.assertGreaterEqual(len(bot_spawns), 1)

    def test_main_signature(self):
        self.assertTrue(callable(supervisor.main))


class TestDeploymentConfig(unittest.TestCase):
    def test_fadehost_shim_uses_supervisor(self):
        src = (BASE / "bot.py").read_text(encoding="utf-8")
        self.assertIn("supervisor", src)

    def test_dockerfile_cmd_is_supervisor(self):
        src = (BASE / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("supervisor", src)
        self.assertIn("EXPOSE 8766", src)

    def test_render_healthcheck(self):
        text = (BASE / "render.yaml").read_text(encoding="utf-8")
        self.assertIn("healthCheckPath: /api/health", text)
        self.assertIn("JIN_AGENT_HOST", text)

    def test_railway_healthcheck(self):
        data = json.loads((BASE / "railway.json").read_text(encoding="utf-8"))
        self.assertEqual(data["deploy"]["healthcheckPath"], "/api/health")

    def test_deploy_doc_exists(self):
        self.assertTrue((BASE / "DEPLOY.md").is_file())


if __name__ == "__main__":
    unittest.main()
