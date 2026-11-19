"""429 rate-limit handling: chunks ke darmiyan intezar + retry_after.

FadeHost console par asli traceback: `HTTP Error 429: Too Many Requests` ne
dispatch threads (Thread-278/280/287) ko mar diya tha. Ye tests us hal ka
regression cover karte hain.
"""

import io
import json
import os
import tempfile
import unittest
import urllib.error
from unittest import mock

from jin_agent import store, telegram_bot as tb


def setUpModule():
    os.environ["JIN_AGENT_DATA"] = tempfile.mkdtemp(prefix="jin-rate-")
    store.init_db()


class FakeAPI:
    def __init__(self):
        self.sent = []

    def send(self, chat_id, text, buttons=None):
        self.sent.append((int(chat_id), str(text)))
        return {"ok": True}

    def get_updates(self, offset, timeout=None):
        return []

    def answer_callback(self, callback_id, text=""):
        return {"ok": True}


def _429(retry_after=None, body=None):
    payload = body if body is not None else json.dumps(
        {"ok": False, "error_code": 429,
         "parameters": {"retry_after": retry_after or 1}}).encode()
    hdrs = {"Retry-After": str(retry_after)} if retry_after else {}
    return urllib.error.HTTPError("https://api.telegram.org/x", 429,
                                  "Too Many Requests", hdrs, io.BytesIO(payload))


class TestSendChunks(unittest.TestCase):
    def test_send_chunks_sends_every_chunk(self):
        api = FakeAPI()
        n = tb.send_chunks(api, 7, "x" * 9000, delay=0)
        self.assertEqual(n, 3)
        self.assertEqual(len(api.sent), 3)

    def test_send_chunks_waits_between_chunks(self):
        api = FakeAPI()
        with mock.patch.object(tb.time, "sleep") as sl:
            tb.send_chunks(api, 7, "x" * 9000, delay=0.5)
        self.assertEqual(sl.call_count, 2)  # pehle chunk ke baad nahi

    def test_send_chunks_delay_zero_no_sleep(self):
        api = FakeAPI()
        with mock.patch.object(tb.time, "sleep") as sl:
            tb.send_chunks(api, 7, "x" * 9000, delay=0)
        sl.assert_not_called()

    def test_send_chunks_empty_text_sends_nothing(self):
        api = FakeAPI()
        self.assertEqual(tb.send_chunks(api, 7, "", delay=0), 0)
        self.assertEqual(api.sent, [])


class TestRetryAfter(unittest.TestCase):
    def test_parses_parameters_retry_after(self):
        self.assertEqual(tb._telegram_retry_after(_429(7)), 7)

    def test_parses_header_when_body_missing(self):
        exc = urllib.error.HTTPError("https://x", 429, "x",
                                     {"Retry-After": "4"}, io.BytesIO(b""))
        self.assertEqual(tb._telegram_retry_after(exc), 4)

    def test_zero_when_absent(self):
        exc = urllib.error.HTTPError("https://x", 429, "x", {},
                                     io.BytesIO(b""))
        self.assertEqual(tb._telegram_retry_after(exc), 0)


class TestPost429Retry(unittest.TestCase):
    def _api(self, opener):
        with mock.patch.object(tb, "_make_opener", lambda cfg=None: opener):
            return tb._api("TOKEN", {})

    def test_retries_on_429_then_succeeds(self):
        calls = []

        class Opener:
            def open(self, req, timeout=None):
                calls.append(1)
                if len(calls) < 3:
                    raise _429(1)
                return io.BytesIO(b'{"ok": true, "result": {"message_id": 1}}')

        api = self._api(Opener())
        with mock.patch.object(tb.time, "sleep") as sl:
            res = api.send(1, "salam")
        self.assertTrue(res["ok"])
        self.assertEqual(len(calls), 3)
        self.assertEqual(sl.call_count, 2)

    def test_gives_up_after_three_attempts(self):
        class Opener:
            def open(self, req, timeout=None):
                raise _429(1)

        api = self._api(Opener())
        with mock.patch.object(tb.time, "sleep"):
            with self.assertRaises(urllib.error.HTTPError):
                api.send(1, "salam")

    def test_non_429_raises_immediately(self):
        class Opener:
            def open(self, req, timeout=None):
                raise urllib.error.HTTPError("https://x", 400, "Bad", {},
                                             io.BytesIO(b'{"ok":false}'))

        api = self._api(Opener())
        with self.assertRaises(urllib.error.HTTPError):
            api.send(1, "salam")


if __name__ == "__main__":
    unittest.main()
