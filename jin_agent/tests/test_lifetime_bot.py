"""Lifetime fixes (bot): send delay, /stop thread, poll observability,
opt-in chat id, rounds cap (G6-G10)."""

import os
import tempfile
import threading
import time
import unittest
from unittest import mock

from jin_agent import store, telegram_bot as tb  # noqa: E402


def setUpModule():
    os.environ["JIN_AGENT_DATA"] = tempfile.mkdtemp(prefix="jin-life-bot-")
    store.init_db()


class FakeAPI:
    def __init__(self):
        self.sent = []

    def send(self, chat_id, text, buttons=None):
        self.sent.append((int(chat_id), str(text), buttons))
        return {"ok": True}

    def get_updates(self, offset, timeout=None):
        return []

    def answer_callback(self, callback_id, text=""):
        return {"ok": True}


class ScriptAPI:
    """Startup drain (timeout=0) khaali; asli script timeout>0 par chalti hai."""

    def __init__(self, script):
        self.script = list(script)
        self.sent = []
        self.stop = threading.Event()

    def send(self, chat_id, text, buttons=None):
        self.sent.append((int(chat_id), str(text), buttons))
        return {"ok": True}

    def get_updates(self, offset, timeout=None):
        if not timeout:
            return []
        if not self.script:
            self.stop.set()
            return []
        return self.script.pop(0)

    def answer_callback(self, callback_id, text=""):
        return {"ok": True}


class FailingAPI:
    def __init__(self):
        self.calls = 0
        self.stop = threading.Event()

    def get_updates(self, offset, timeout=None):
        if not timeout:
            return []
        self.calls += 1
        raise OSError("network down")

    def send(self, *a, **k):
        return {"ok": True}


class TestSendDelay(unittest.TestCase):
    def test_default_is_one_second(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("JIN_AGENT_SEND_DELAY", None)
            self.assertEqual(tb.send_delay(), 1.0)
        self.assertEqual(tb.SEND_DELAY, 1.0)

    def test_env_override(self):
        with mock.patch.dict(os.environ, {"JIN_AGENT_SEND_DELAY": "0.25"}):
            self.assertEqual(tb.send_delay(), 0.25)
        with mock.patch.dict(os.environ, {"JIN_AGENT_SEND_DELAY": "abc"}):
            self.assertEqual(tb.send_delay(), 1.0)


class TestRequireChatId(unittest.TestCase):
    def test_default_allow_all_unchanged(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("JIN_AGENT_REQUIRE_CHAT_ID", None)
            self.assertTrue(tb.is_owner(None, {}))
            self.assertTrue(tb.is_owner(999, {"telegram_chat_id": ""}))
            self.assertTrue(tb.is_owner(7, {"telegram_chat_id": "7"}))

    def test_opt_in_rejects_unset(self):
        with mock.patch.dict(os.environ, {"JIN_AGENT_REQUIRE_CHAT_ID": "1"}):
            self.assertFalse(tb.is_owner(None, {}))
            self.assertFalse(tb.is_owner(999, {"telegram_chat_id": ""}))
            self.assertTrue(tb.is_owner(7, {"telegram_chat_id": "7"}))
            self.assertFalse(tb.is_owner(8, {"telegram_chat_id": "7"}))


class TestRoundsCap(unittest.TestCase):
    def test_default_five(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("JIN_AGENT_MAX_ROUNDS", None)
            self.assertEqual(tb.max_rounds(), 5)
        with mock.patch.dict(os.environ, {"JIN_AGENT_MAX_ROUNDS": "2"}):
            self.assertEqual(tb.max_rounds(), 2)

    def test_searchmemory_rounds_capped(self):
        row = tb.memory_mod.begin(42, "lifetime rounds")
        with mock.patch.dict(os.environ, {"JIN_AGENT_MAX_ROUNDS": "3"}):
            for _ in range(10):
                row = tb.memory_mod.remember(row["id"], ["s"], ["c"], advance=True)
        self.assertLessEqual(row["round_no"], 3)

    def test_send_research_stops_at_cap(self):
        row = tb.memory_mod.begin(42, "lifetime cap")
        tb.memory_mod.remember(row["id"], ["a"], ["c"], advance=True)
        with store.session() as con:
            con.execute("UPDATE search_memory SET round_no=5 WHERE id=?",
                        (row["id"],))
        api = FakeAPI()
        called = []

        def research(q, cfg):
            called.append(q)
            return "# report"

        with mock.patch.dict(os.environ, {"JIN_AGENT_MAX_ROUNDS": "5"}):
            res = tb.handle_callback(42, f"mem:{row['id']}:more",
                                     {"telegram_chat_id": "42"}, api=api,
                                     research=research)
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"], "max rounds")
        self.assertEqual(called, [])
        self.assertIn("Aur sources nahi mile",
                      "\n".join(t for _, t, _ in api.sent))


class TestPollFailureObservability(unittest.TestCase):
    def test_fail_count_exposed_in_status(self):
        api = FailingAPI()

        def stopper():
            time.sleep(0.3)
            api.stop.set()

        threading.Thread(target=stopper, daemon=True).start()
        with mock.patch.object(tb.time, "sleep", lambda s: None), \
                mock.patch("builtins.print") as pr:
            tb.run("tok", cfg={"telegram_chat_id": "1"}, api=api, stop=api.stop)
        self.assertGreaterEqual(tb.status()["poll_failures"], 1)
        printed = " ".join(str(c.args[0]) for c in pr.call_args_list if c.args)
        self.assertIn("get_updates fail", printed)

    def test_fail_count_resets_after_success(self):
        class OnceFailing(FailingAPI):
            def get_updates(self, offset, timeout=None):
                if not timeout:
                    return []
                if self.calls == 0:
                    self.calls += 1
                    raise OSError("blip")
                self.stop.set()
                return []

        api = OnceFailing()
        with mock.patch.object(tb.time, "sleep", lambda s: None):
            tb.run("tok", cfg={"telegram_chat_id": "1"}, api=api, stop=api.stop)
        self.assertEqual(tb.status()["poll_failures"], 0)


class TestStopNotQueued(unittest.TestCase):
    def test_stop_fast_with_two_busy_workers(self):
        release = threading.Event()

        def slow_research(q, cfg, save=True, live=False,
                          skip_sources=None, skip_channels=None):
            release.wait(8)
            return {"ok": True, "markdown": "# slow", "sources": [],
                    "channels": []}

        api = ScriptAPI([
            [{"update_id": 1,
              "message": {"chat": {"id": 1}, "text": "/research one"}},
             {"update_id": 2,
              "message": {"chat": {"id": 1}, "text": "/research two"}}],
            [{"update_id": 3,
              "message": {"chat": {"id": 1}, "text": "/stop"}}],
        ])
        with mock.patch.object(tb, "research_full", slow_research):
            t0 = time.monotonic()
            tb.run("tok", cfg={"telegram_chat_id": "1"}, api=api, stop=api.stop)
            elapsed = time.monotonic() - t0
        release.set()
        # /stop dedicated thread par hai: busy workers ke peeche nahi atka.
        self.assertLess(elapsed, 5.0)
        deadline = time.monotonic() + 3
        joined = "\n".join(t for _, t, _ in api.sent)
        while "rok di gayi" not in joined and time.monotonic() < deadline:
            time.sleep(0.05)
            joined = "\n".join(t for _, t, _ in api.sent)
        self.assertIn("rok di gayi", joined)


if __name__ == "__main__":
    unittest.main()
