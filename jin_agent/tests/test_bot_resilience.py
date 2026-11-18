"""Bot resilience fixes: empty-poll offset, proxy creds, ok:false, secret masking.

Context: getUpdates ke khali jawab par bhi offset aage badh raha tha — quiet
period ke baad aane wala message kabhi deliver nahi hota tha. Isi tarah proxy
credentials ignore hote the, Telegram ok:false ignore hota tha, aur
config.public() proxy_pass leak karta tha.
"""

import os
import tempfile
import threading
import unittest

os.environ.setdefault("JIN_AGENT_DATA", tempfile.mkdtemp(prefix="jin-res-"))

from jin_agent import config, telegram_bot as tb


class FakeAPI:
    """get_updates script chalata hai; har call par offset record hota hai."""

    def __init__(self, script):
        self.script = list(script)
        self.offsets = []
        self.stop = threading.Event()

    def get_updates(self, offset, timeout=None):
        self.offsets.append(int(offset))
        if not self.script:
            self.stop.set()
            return []
        nxt = self.script.pop(0)
        if not nxt:
            # khali poll bhi stop kare taake test deterministic rahe
            if not self.script:
                self.stop.set()
        return nxt

    def send(self, *a, **k):
        return {"ok": True}

    def answer_callback(self, *a, **k):
        return {"ok": True}


class TestPollOffset(unittest.TestCase):
    def test_empty_poll_does_not_advance_offset(self):
        api = FakeAPI([[]])  # startup drain + ek khali poll
        tb.run("tok", cfg={"telegram_chat_id": "1"}, api=api, stop=api.stop)
        # startup drain offset=0, khali poll bhi offset=0 (purana code 1 karta tha)
        self.assertEqual(api.offsets[0], 0)
        self.assertEqual(api.offsets[-1], 0)

    def test_update_advances_offset(self):
        api = FakeAPI([[{"update_id": 5, "message": {"chat": {"id": 1},
                                                     "text": "/status"}}]])
        tb.run("tok", cfg={"telegram_chat_id": "1"}, api=api, stop=api.stop)
        # aakhri poll offset 6 par tha (5 + 1)
        self.assertIn(6, api.offsets)

    def test_startup_drain_loops_until_empty(self):
        api = FakeAPI([[{"update_id": 1}, {"update_id": 2}], [{"update_id": 3}], []])
        tb.run("tok", cfg={"telegram_chat_id": "1"}, api=api, stop=api.stop)
        # drain: offset 0 -> 3 -> 4 (do kalam), phir poll offset 4
        self.assertEqual(api.offsets[0], 0)
        self.assertEqual(api.offsets[1], 3)
        self.assertEqual(api.offsets[2], 4)
        self.assertEqual(api.offsets[-1], 4)


class TestProxyConfig(unittest.TestCase):
    def _http_proxy(self, op):
        for h in op.handlers:
            p = getattr(h, "proxies", None)
            if p and (p.get("http") or p.get("https")):
                return p
        return None

    def test_http_proxy_includes_credentials(self):
        op = tb._make_opener({"proxy_type": "http", "proxy_host": "127.0.0.1",
                              "proxy_port": 8080, "proxy_user": "us er",
                              "proxy_pass": "p@ss"})
        p = self._http_proxy(op)
        self.assertIsNotNone(p)
        self.assertIn("us%20er:p%40ss@127.0.0.1:8080", p["http"])

    def test_unsupported_proxy_type_falls_back_to_direct(self):
        op = tb._make_opener({"proxy_type": "socks4", "proxy_host": "h",
                              "proxy_port": 1080})
        self.assertIsNone(self._http_proxy(op))

    def test_bad_proxy_port_falls_back_to_direct(self):
        op = tb._make_opener({"proxy_type": "http", "proxy_host": "h",
                              "proxy_port": "abc"})
        self.assertIsNone(self._http_proxy(op))


class TestAPIErrorHandling(unittest.TestCase):
    def test_ok_false_raises_bot_api_error(self):
        import json as _json
        import urllib.request

        class FakeResp:
            def __init__(self, payload):
                self.payload = payload

            def read(self):
                return _json.dumps(self.payload).encode()

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        seen = {}

        class FakeOpener:
            def open(self, req, timeout=None):
                seen["path"] = req.full_url
                return FakeResp({"ok": False, "error_code": 409,
                                 "description": "Conflict: terminated by other"})

        import urllib.request as _ur
        orig = _ur.build_opener
        _ur.build_opener = lambda *a, **k: FakeOpener()
        try:
            api = tb._api("TOKEN", {})
            with self.assertRaises(tb.BotAPIError) as ctx:
                api.get_updates(0)
            self.assertIn("409", str(ctx.exception))
        finally:
            _ur.build_opener = orig


class TestPublicMasking(unittest.TestCase):
    def test_proxy_pass_masked(self):
        pub = config.public({"llm": {}, "proxy_pass": "secret",
                             "proxy_user": "u"})
        self.assertEqual(pub["proxy_pass"], "***")
        self.assertEqual(pub["proxy_user"], "u")


if __name__ == "__main__":
    unittest.main()
