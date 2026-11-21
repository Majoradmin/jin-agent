"""P0-2 - Telegram authorization: require mode safe startup + throttled
unauthorized reply. is_owner ka allow-all default barqarar rehta hai."""

import argparse
import os
import tempfile
import threading
import unittest
from unittest import mock

from jin_agent import __main__ as cli  # noqa: E402
from jin_agent import store, telegram_bot as tb  # noqa: E402


def setUpModule():
    os.environ["JIN_AGENT_DATA"] = tempfile.mkdtemp(prefix="jin-authz-")
    store.init_db()


class FakeAPI:
    def __init__(self):
        self.sent = []
        self.answered = []

    def send(self, chat_id, text, buttons=None):
        self.sent.append((int(chat_id), str(text)))
        return {"ok": True}

    def answer_callback(self, callback_id, text=""):
        self.answered.append((str(callback_id), str(text)))
        return {"ok": True}


class OneShotAPI(FakeAPI):
    """Startup drain (timeout=0) khaali; script timeout>0 par chalti hai."""

    def __init__(self, script):
        super().__init__()
        self.script = list(script)
        self.stop = threading.Event()

    def get_updates(self, offset, timeout=None):
        if not timeout:
            return []
        if self.script:
            return [self.script.pop(0)]
        self.stop.set()
        return []


class TestCmdBotGuard(unittest.TestCase):
    def setUp(self):
        tb._UNAUTH_LAST.clear()

    def test_require_unset_blocks_startup(self):
        cfg = {"telegram_bot_token": "tok", "telegram_chat_id": ""}
        with mock.patch.dict(os.environ, {"JIN_AGENT_REQUIRE_CHAT_ID": "1"}), \
                mock.patch.object(tb.config, "load", return_value=cfg), \
                mock.patch.object(tb, "run") as run:
            self.assertEqual(cli.cmd_bot(argparse.Namespace()), 1)
        run.assert_not_called()

    def test_require_invalid_blocks_startup(self):
        cfg = {"telegram_bot_token": "tok", "telegram_chat_id": "abc"}
        with mock.patch.dict(os.environ, {"JIN_AGENT_REQUIRE_CHAT_ID": "1"}), \
                mock.patch.object(tb.config, "load", return_value=cfg), \
                mock.patch.object(tb, "run") as run:
            self.assertEqual(cli.cmd_bot(argparse.Namespace()), 1)
        run.assert_not_called()

    def test_require_valid_chat_starts(self):
        cfg = {"telegram_bot_token": "tok", "telegram_chat_id": "123"}
        stop = threading.Event()
        with mock.patch.dict(os.environ, {"JIN_AGENT_REQUIRE_CHAT_ID": "1"}), \
                mock.patch.object(tb.config, "load", return_value=cfg), \
                mock.patch.object(tb, "run", side_effect=lambda *a, **k: stop.set()) as run:
            self.assertEqual(cli.cmd_bot(argparse.Namespace()), 0)
        run.assert_called_once()

    def test_require_off_still_allow_all(self):
        cfg = {"telegram_bot_token": "tok", "telegram_chat_id": ""}
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("JIN_AGENT_REQUIRE_CHAT_ID", None)
            self.assertTrue(tb.is_owner(999, cfg))


class TestUnauthorizedReply(unittest.TestCase):
    def setUp(self):
        tb._UNAUTH_LAST.clear()

    def test_first_reply_then_throttled(self):
        api = FakeAPI()
        with mock.patch.dict(os.environ, {"JIN_AGENT_REQUIRE_CHAT_ID": "1"}):
            self.assertTrue(tb._unauthorized_reply(999, api))
            self.assertFalse(tb._unauthorized_reply(999, api))
        self.assertEqual(len(api.sent), 1)
        self.assertEqual(api.sent[0][1], tb.UNAUTHORIZED_TEXT)

    def test_per_chat_independent(self):
        api = FakeAPI()
        with mock.patch.dict(os.environ, {"JIN_AGENT_REQUIRE_CHAT_ID": "1"}):
            self.assertTrue(tb._unauthorized_reply(999, api))
            self.assertTrue(tb._unauthorized_reply(1000, api))
        self.assertEqual(len(api.sent), 2)

    def test_callback_toast_and_message(self):
        api = FakeAPI()
        with mock.patch.dict(os.environ, {"JIN_AGENT_REQUIRE_CHAT_ID": "1"}):
            self.assertTrue(tb._unauthorized_reply(999, api, callback_id="cb-1"))
            self.assertFalse(tb._unauthorized_reply(999, api, callback_id="cb-2"))
        self.assertEqual(api.answered, [("cb-1", tb.UNAUTHORIZED_TEXT)])
        self.assertEqual(len(api.sent), 1)

    def test_allow_all_sends_nothing(self):
        api = FakeAPI()
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("JIN_AGENT_REQUIRE_CHAT_ID", None)
            self.assertFalse(tb._unauthorized_reply(999, api))
            self.assertTrue(tb.is_owner(999, {"telegram_chat_id": ""}))
        self.assertEqual(api.sent, [])
        self.assertEqual(api.answered, [])


class TestRunGateIntegration(unittest.TestCase):
    def setUp(self):
        tb._UNAUTH_LAST.clear()

    def test_unauthorized_message_replies_in_loop(self):
        api = OneShotAPI([{
            "update_id": 1,
            "message": {"chat": {"id": 999}, "text": "/status"},
        }])
        with mock.patch.dict(os.environ, {"JIN_AGENT_REQUIRE_CHAT_ID": "1"}):
            tb.run("tok", cfg={"telegram_chat_id": "111"}, api=api, stop=api.stop)
        self.assertEqual(len(api.sent), 1)
        self.assertEqual(api.sent[0], (999, tb.UNAUTHORIZED_TEXT))

    def test_authorized_message_not_rejected(self):
        api = OneShotAPI([{
            "update_id": 2,
            "message": {"chat": {"id": 111}, "text": "/status"},
        }])
        with mock.patch.dict(os.environ, {"JIN_AGENT_REQUIRE_CHAT_ID": "1"}):
            tb.run("tok", cfg={"telegram_chat_id": "111"}, api=api, stop=api.stop)
        self.assertNotIn(tb.UNAUTHORIZED_TEXT,
                         [t for _, t in api.sent])


if __name__ == "__main__":
    unittest.main()
