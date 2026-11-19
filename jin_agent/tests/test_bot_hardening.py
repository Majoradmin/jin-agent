"""Bot hardening regressions: bounded update pool, research stop race,
research thread cleanup, scoped SOCKS patch, poll-failure cap.

Context (audit): per-update threads unbounded the, /stop aur /research race karte
the, research thread leak hota tha, SOCKS socket monkeypatch process-global tha,
aur poll failure cap env se configurable nahi tha.
"""

import json
import os
import socket
import tempfile
import threading
import time
import unittest
from unittest import mock

os.environ.setdefault("JIN_AGENT_DATA", tempfile.mkdtemp(prefix="jin-hard-"))

from jin_agent import store, telegram_bot as tb  # noqa: E402


def setUpModule():
    os.environ["JIN_AGENT_DATA"] = tempfile.mkdtemp(prefix="jin-hard-")
    store.init_db()


class FakeAPI:
    def __init__(self, script=None):
        self.script = list(script or [])
        self.sent = []
        self.stop = threading.Event()
        self.calls = 0

    def send(self, chat_id, text, buttons=None):
        self.sent.append((int(chat_id), str(text), buttons))
        return {"ok": True, "result": {"message_id": len(self.sent)}}

    def get_updates(self, offset, timeout=None):
        self.calls += 1
        if not self.script:
            self.stop.set()
            return []
        nxt = self.script.pop(0)
        if not nxt and not self.script:
            self.stop.set()
        return nxt

    def answer_callback(self, callback_id, text=""):
        return {"ok": True}


class FailingAPI:
    def __init__(self):
        self.calls = 0

    def get_updates(self, offset, timeout=None):
        self.calls += 1
        raise OSError("network down")

    def send(self, *a, **k):
        return {"ok": True}


class FakePool:
    """ThreadPoolExecutor ki jagah — max_workers/shutdown assert karne ke liye."""

    instances = []

    def __init__(self, max_workers=1, thread_name_prefix=""):
        self.max_workers = max_workers
        self.thread_name_prefix = thread_name_prefix
        self.submitted = 0
        self.shutdown_calls = []
        FakePool.instances.append(self)

    def submit(self, fn, *args, **kwargs):
        self.submitted += 1
        fn(*args, **kwargs)

    def shutdown(self, wait=False, cancel_futures=False):
        self.shutdown_calls.append({"wait": wait,
                                    "cancel_futures": cancel_futures})


class TestUpdateWorkerPool(unittest.TestCase):
    def tearDown(self):
        FakePool.instances = []

    def test_update_workers_default_and_env(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("JIN_AGENT_UPDATE_WORKERS", None)
            self.assertEqual(tb.update_workers(), 2)
        with mock.patch.dict(os.environ, {"JIN_AGENT_UPDATE_WORKERS": "5"}):
            self.assertEqual(tb.update_workers(), 5)
        with mock.patch.dict(os.environ, {"JIN_AGENT_UPDATE_WORKERS": "abc"}):
            self.assertEqual(tb.update_workers(), 2)
        with mock.patch.dict(os.environ, {"JIN_AGENT_UPDATE_WORKERS": "0"}):
            self.assertEqual(tb.update_workers(), 1)       # clamp min
        with mock.patch.dict(os.environ, {"JIN_AGENT_UPDATE_WORKERS": "99"}):
            self.assertEqual(tb.update_workers(), 16)      # clamp max

    def test_run_uses_bounded_pool_and_shuts_down(self):
        api = FakeAPI([[], [{"update_id": 5,
                             "message": {"chat": {"id": 1},
                                         "text": "/status"}}], []])
        with mock.patch.object(tb, "ThreadPoolExecutor", FakePool):
            tb.run("tok", cfg={"telegram_chat_id": "1"}, api=api, stop=api.stop)
        self.assertEqual(len(FakePool.instances), 1)
        pool = FakePool.instances[0]
        self.assertEqual(pool.max_workers, tb.update_workers())
        self.assertGreaterEqual(pool.submitted, 1)
        self.assertEqual(len(pool.shutdown_calls), 1)
        self.assertTrue(pool.shutdown_calls[0]["cancel_futures"])

    def test_run_pool_size_follows_env(self):
        api = FakeAPI([[], []])
        with mock.patch.dict(os.environ, {"JIN_AGENT_UPDATE_WORKERS": "3"}), \
                mock.patch.object(tb, "ThreadPoolExecutor", FakePool):
            tb.run("tok", cfg={"telegram_chat_id": "1"}, api=api, stop=api.stop)
        self.assertEqual(FakePool.instances[0].max_workers, 3)


class TestResearchStopRace(unittest.TestCase):
    cfg = {"telegram_chat_id": "42", "llm": {}}

    def test_stop_invalidates_running_research(self):
        release = threading.Event()
        seen = {}

        def slow_research(q, cfg):
            seen["started"] = True
            release.wait(10)
            seen["returned"] = True
            return "# Report"

        api = FakeAPI()
        box = {}

        def runner():
            box["res"] = tb._send_research(42, "q", self.cfg, api,
                                           research=slow_research)

        t = threading.Thread(target=runner, daemon=True)
        t.start()
        deadline = time.time() + 5
        while not seen.get("started") and time.time() < deadline:
            time.sleep(0.01)
        self.assertTrue(seen.get("started"))

        stop_res = tb.dispatch(42, "/stop", self.cfg, api=api)
        self.assertTrue(stop_res["ok"])
        t.join(5)
        self.assertFalse(t.is_alive())
        self.assertEqual((box.get("res") or {}).get("error"), "stopped by user")

        joined = "\n".join(text for _, text, _ in api.sent)
        self.assertNotIn("# Report", joined)  # rokne ke baad report nahi gayi

        release.set()
        end = time.time() + 5
        while tb._active_research_threads() and time.time() < end:
            time.sleep(0.02)
        self.assertEqual(tb._active_research_threads(), [])

    def test_concurrent_research_is_serialized(self):
        active = 0
        max_active = 0
        lock = threading.Lock()

        def research(q, cfg):
            nonlocal active, max_active
            with lock:
                active += 1
                max_active = max(max_active, active)
            time.sleep(0.15)
            with lock:
                active -= 1
            return "# " + q

        api = FakeAPI()
        results = {}

        def run_one(name, q):
            results[name] = tb._send_research(42, q, self.cfg, api,
                                              research=research)

        threads = [threading.Thread(target=run_one, args=(f"t{i}", f"q{i}"))
                   for i in range(2)]
        for th in threads:
            th.start()
        for th in threads:
            th.join(10)
        self.assertTrue(all(results[k]["ok"] for k in results))
        self.assertEqual(max_active, 1)  # lock ne serialize kiya
        self.assertEqual(tb._active_research_threads(), [])

    def test_new_research_after_stop_starts_fresh_session(self):
        api = FakeAPI()
        res = tb.dispatch(42, "/stop", self.cfg, api=api)
        self.assertTrue(res["ok"])
        self.assertTrue(tb._stop_research)
        res = tb._send_research(42, "dobara", self.cfg, api,
                                research=lambda q, cfg: "# Nayi report")
        self.assertTrue(res["ok"])
        self.assertIn("Nayi report", "\n".join(t for _, t, _ in api.sent))


class TestPollFailureCap(unittest.TestCase):
    def test_max_poll_failures_env(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("JIN_AGENT_MAX_POLL_FAILURES", None)
            self.assertEqual(tb.max_poll_failures(), 0)
        with mock.patch.dict(os.environ, {"JIN_AGENT_MAX_POLL_FAILURES": "5"}):
            self.assertEqual(tb.max_poll_failures(), 5)
        with mock.patch.dict(os.environ, {"JIN_AGENT_MAX_POLL_FAILURES": "abc"}):
            self.assertEqual(tb.max_poll_failures(), 0)
        with mock.patch.dict(os.environ, {"JIN_AGENT_MAX_POLL_FAILURES": "-3"}):
            self.assertEqual(tb.max_poll_failures(), 0)

    def test_run_exits_after_cap(self):
        api = FailingAPI()
        with mock.patch.dict(os.environ, {"JIN_AGENT_MAX_POLL_FAILURES": "2"}), \
                mock.patch.object(tb.time, "sleep", lambda s: None):
            with self.assertRaises(Exception):
                tb.run("tok", cfg={"telegram_chat_id": "1"}, api=api,
                       stop=threading.Event())
        # startup drain (1) + do lagataar fail = 3 calls
        self.assertEqual(api.calls, 3)


class FakeSocks:
    SOCKS5 = 2
    socksocket = object()  # sentinel

    def __init__(self):
        self.default_calls = []

    def set_default_proxy(self, *args):
        self.default_calls.append(args)


class TestSocksScoping(unittest.TestCase):
    """PySocks ke baghair bhi scoping logic test ho — fake socks module se."""

    cfg = {"proxy_type": "socks5", "proxy_host": "127.0.0.1",
           "proxy_port": 1080}

    def test_socks_patch_scoped_to_http_call(self):
        import urllib.request
        orig_socket = socket.socket
        fake = FakeSocks()
        with mock.patch.object(tb, "_SOCKS_AVAILABLE", True), \
                mock.patch.object(tb, "socks", fake, create=True):
            tb._make_opener(self.cfg)
            self.assertIs(socket.socket, orig_socket)  # build par global patch nahi

            seen = {}

            class Resp:
                def read(self):
                    return json.dumps({"ok": True, "result": []}).encode()

                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    return False

            class FakeOpener:
                def open(self, req, timeout=None):
                    seen["during"] = socket.socket
                    return Resp()

            with mock.patch.object(urllib.request, "build_opener",
                                   lambda *a, **k: FakeOpener()):
                api = tb._api("TOKEN", self.cfg)
                api.get_updates(0)

        self.assertIs(seen.get("during"), fake.socksocket)  # call ke dauran
        self.assertIs(socket.socket, orig_socket)            # baad me restore
        self.assertTrue(fake.default_calls)                  # proxy set hua

    def test_no_socks_config_leaves_socket_alone(self):
        orig_socket = socket.socket
        with tb._socks_scope({"proxy_type": "http", "proxy_host": "h",
                              "proxy_port": 8080}):
            self.assertIs(socket.socket, orig_socket)
        self.assertIs(socket.socket, orig_socket)

    @unittest.skipUnless(tb._SOCKS_AVAILABLE, "PySocks installed nahi")
    def test_real_pysocks_scoping(self):
        import socks
        import urllib.request
        orig_socket = socket.socket
        seen = {}

        class Resp:
            def read(self):
                return json.dumps({"ok": True, "result": []}).encode()

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        class FakeOpener:
            def open(self, req, timeout=None):
                seen["during"] = socket.socket
                return Resp()

        with mock.patch.object(urllib.request, "build_opener",
                               lambda *a, **k: FakeOpener()):
            api = tb._api("TOKEN", self.cfg)
            api.get_updates(0)
        self.assertIs(seen.get("during"), socks.socksocket)
        self.assertIs(socket.socket, orig_socket)


if __name__ == "__main__":
    unittest.main()
