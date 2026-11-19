"""P39 - /explore Telegram discovery: Bing engine + ck/a decode + anomaly fallback.

Live bug (2026-11-19): /explore hamesha Telegram group khaali rakhta tha.
Wajah: ``web_search_candidates`` sirf DuckDuckGo par hardcoded tha, aur DDG
abhi anti-bot "anomaly" page deta hai (``uddg=0``) — koi anomaly detection
nahi. ``www.bing.com`` allowlist me bhi nahi tha. Ab Bing pehle, DDG html/lite
fallback, aur anomaly par agla engine.

Sab network calls mocked hain (project rule: tests kabhi live internet na
chhedein).
"""

import os
import tempfile
import unittest
from unittest import mock

from jin_agent import channels, config, policy, store
from jin_agent import telegram_bot as tb


def setUpModule():
    os.environ["JIN_AGENT_DATA"] = tempfile.mkdtemp(prefix="jin-bing-disc-")
    store.init_db()
    channels.ensure_table()


# Bing result URL: https://www.bing.com/ck/a?...&u=a1<urlsafe-base64>
_BING_TOKEN = "aHR0cHM6Ly90Lm1lL3MvYW5kcm9pZE1hbHdhcmU="  # -> t.me/s/androidMalware
BING_HTML = (
    '<div id="b_results">'
    '<li class="b_algo"><h2><a href="https://www.bing.com/ck/a?x=1&amp;'
    'u=a1' + _BING_TOKEN + '&amp;y=2">Android Security &amp; Malware – Telegram</a>'
    '</h2></li>'
    '<li class="b_algo"><h2><a href="https://www.bing.com/ck/a?x=1&amp;'
    'u=a1aHR0cHM6Ly90Lm1lL3MvU2FmZUFuZHJvaWQ=">Safe Android</a></h2></li>'
    '</div>')
BING_ANOMALY = "<html><body>Our systems have detected unusual traffic "
BING_ANOMALY += "(anomaly). Please try again later.</body></html>"
DDG_HTML_GOOD = (
    '<a href="//duckduckgo.com/l/?uddg=https%3A%2F%2Ft.me%2Fs%2Fwebnew_ch"'
    '&amp;rut=x">r</a>')
DDG_HTML_ANOMALY = "<html><body>anomaly</body></html>"
DDG_LITE_GOOD = (
    '<a rel="nofollow" href="https://t.me/s/lite_ch" class="result-link">'
    'Lite Channel</a>')
DDG_LITE_ANOMALY = "<html><body>anomaly</body></html>"
# b_algo mojood (asli results) magar koi t.me handle nahi — "results magar
# handle nahi" ka live halat.
BING_RESULTS_NO_HANDLE = (
    '<div id="b_results">'
    '<li class="b_algo"><h2><a href="https://example.com/x">Android News</a>'
    '</h2></li></div>')


class _FakeFetch:
    """URL fragment -> HTML body; na mila to ValueError (blocked)."""

    def __init__(self, routes):
        self.routes = dict(routes)
        self.calls = []

    def __call__(self, url, cfg=None, extra_hosts=()):
        self.calls.append(url)
        for frag, body in self.routes.items():
            if frag in url:
                return body
        raise ValueError("blocked")

    def has(self, frag):
        return any(frag in u for u in self.calls)


class TestBingParse(unittest.TestCase):
    def test_decode_bing_url(self):
        self.assertEqual(channels.decode_bing_url(_BING_TOKEN),
                         "https://t.me/s/androidMalware")

    def test_decode_bing_url_padding_and_garbage(self):
        # padding ghair-mukammal bhi chalna chahiye
        self.assertEqual(channels.decode_bing_url(_BING_TOKEN.rstrip("=")),
                         "https://t.me/s/androidMalware")
        self.assertEqual(channels.decode_bing_url(""), "")
        self.assertEqual(channels.decode_bing_url("!!!not-base64!!!"), "")

    def test_parse_bing_html_extracts_handles(self):
        handles = channels.parse_bing_html(BING_HTML)
        self.assertIn("androidMalware", handles)
        self.assertIn("SafeAndroid", handles)

    def test_bing_has_results(self):
        self.assertTrue(channels.bing_has_results(BING_HTML))
        self.assertFalse(channels.bing_has_results(BING_ANOMALY))


class TestPolicy(unittest.TestCase):
    def test_bing_host_allowed_for_search(self):
        ok, reason = policy.check_url("https://www.bing.com/search?q=t.me%2Fs")
        self.assertTrue(ok, reason)

    def test_onion_still_blocked(self):
        ok, reason = policy.check_url("http://example.onion/search")
        self.assertFalse(ok)
        self.assertIn("onion", reason.lower())

    def test_bing_web_registered_auto(self):
        row = [r for r in policy.register() if r["key"] == "bing-web"]
        self.assertEqual(len(row), 1)
        self.assertTrue(row[0]["auto"])
        self.assertIn("www.bing.com", row[0]["url"])


class TestEngineFallback(unittest.TestCase):
    def setUp(self):
        self._patch = mock.patch.object(channels.adapters, "fetch")
        self.mock_fetch = self._patch.start()
        self.addCleanup(self._patch.stop)

    def test_bing_success_skips_ddg(self):
        self.mock_fetch.side_effect = _FakeFetch({"bing.com": BING_HTML})
        info = {}
        handles = channels.web_search_candidates("android security",
                                                 config.load(), info)
        self.assertIn("androidMalware", handles)
        self.assertEqual(info["engine"], "bing")
        self.assertFalse(info["anomaly"])
        self.assertFalse(self.mock_fetch.side_effect.has("duckduckgo"))

    def test_ddg_anomaly_falls_back_to_lite(self):
        self.mock_fetch.side_effect = _FakeFetch({
            "bing.com": BING_ANOMALY,
            "html.duckduckgo.com": DDG_HTML_ANOMALY,
            "lite.duckduckgo.com": DDG_LITE_GOOD,
        })
        info = {}
        handles = channels.web_search_candidates("android security",
                                                 config.load(), info)
        self.assertEqual(handles, ["lite_ch"])
        self.assertEqual(info["engine"], "ddg-lite")
        self.assertFalse(info["anomaly"])

    def test_ddg_html_result_used_when_bing_anomaly(self):
        self.mock_fetch.side_effect = _FakeFetch({
            "bing.com": BING_ANOMALY,
            "html.duckduckgo.com": DDG_HTML_GOOD,
        })
        info = {}
        handles = channels.web_search_candidates("android security",
                                                 config.load(), info)
        self.assertEqual(handles, ["webnew_ch"])
        self.assertEqual(info["engine"], "ddg-html")

    def test_all_anomaly_reports_anti_bot(self):
        self.mock_fetch.side_effect = _FakeFetch({
            "bing.com": BING_ANOMALY,
            "html.duckduckgo.com": DDG_HTML_ANOMALY,
            "lite.duckduckgo.com": DDG_LITE_ANOMALY,
        })
        info = {}
        handles = channels.web_search_candidates("android security",
                                                 config.load(), info)
        self.assertEqual(handles, [])
        self.assertTrue(info["anomaly"])
        self.assertIn("anti-bot", info["error"])

    def test_fetch_error_falls_through(self):
        self.mock_fetch.side_effect = _FakeFetch({
            "html.duckduckgo.com": DDG_HTML_GOOD,
        })
        info = {}
        handles = channels.web_search_candidates("android security",
                                                 config.load(), info)
        self.assertEqual(handles, ["webnew_ch"])
        self.assertEqual(info["engine"], "ddg-html")


class TestStatusDiscoveryBlock(unittest.TestCase):
    def test_status_shows_last_discovery_engine_and_counts(self):
        channels.save_discovery_state({
            "ts": 1_800_000_000, "query": "android security", "engine": "bing",
            "candidates": 9, "probed": 8, "added": 2, "dead": 6,
            "anomaly": False, "error": "", "tried": [],
        })
        text = tb.format_status_text()
        self.assertIn("Telegram discovery:", text)
        self.assertIn("engine bing", text)
        self.assertIn("candidates 9", text)
        self.assertIn("probed 8", text)
        self.assertIn("added 2", text)

    def test_status_shows_fail_reason(self):
        channels.save_discovery_state({
            "ts": 1_800_000_000, "query": "android security", "engine": "",
            "candidates": 0, "probed": 0, "added": 0, "dead": 0,
            "anomaly": True,
            "error": "search engine ne results nahi diye (anti-bot)",
            "tried": [],
        })
        text = tb.format_status_text()
        self.assertIn("✗ wajah: search engine ne results nahi diye (anti-bot)",
                      text)


class TestResultsWithoutHandles(unittest.TestCase):
    """Results mile magar t.me handle nahi — engine ka naam bhi darj ho.

    Live bug (2026-11-19): ``web_search_probe`` is haalat par ``engine=""``
    return karta tha, is liye ``/status`` hamesha ``engine n/a`` dikhata tha.
    """

    def setUp(self):
        self._patch = mock.patch.object(channels.adapters, "fetch")
        self.mock_fetch = self._patch.start()
        self.addCleanup(self._patch.stop)

    def test_engine_kept_when_no_handle_found(self):
        self.mock_fetch.side_effect = _FakeFetch({
            "bing.com": BING_RESULTS_NO_HANDLE,
            "html.duckduckgo.com": DDG_HTML_ANOMALY,
            "lite.duckduckgo.com": DDG_LITE_ANOMALY,
        })
        info = {}
        handles = channels.web_search_candidates("android security",
                                                 config.load(), info)
        self.assertEqual(handles, [])
        self.assertEqual(info["engine"], "bing")
        self.assertFalse(info["anomaly"])
        self.assertIn("t.me channel nahi mila", info["error"])
        # RightDAO pehle chalta hai (blocked) — bing bhi tried me darj hona chahiye.
        self.assertIn("bing", [t["engine"] for t in info["tried"]])

    def test_only_anomaly_keeps_engine_empty(self):
        self.mock_fetch.side_effect = _FakeFetch({
            "bing.com": BING_ANOMALY,
            "html.duckduckgo.com": DDG_HTML_ANOMALY,
            "lite.duckduckgo.com": DDG_LITE_ANOMALY,
        })
        info = {}
        self.assertEqual(channels.web_search_candidates("android security",
                                                        config.load(), info), [])
        self.assertEqual(info["engine"], "")
        self.assertIn("anti-bot", info["error"])

    def test_merge_falls_back_to_tried(self):
        merged = channels.merge_web_probe(
            [{"engine": "", "candidates": 0, "anomaly": False, "error": "",
              "tried": [{"engine": "bing", "ok": True, "handles": 0,
                         "anomaly": False}]}])
        self.assertEqual(merged["engine"], "bing")

    def test_status_shows_engine_with_reason(self):
        channels.save_discovery_state({
            "ts": 1_800_000_000, "query": "android security", "engine": "bing",
            "candidates": 0, "probed": 0, "added": 0, "dead": 0,
            "anomaly": False, "error": "results me t.me channel nahi mila",
            "tried": [{"engine": "bing", "ok": True, "handles": 0,
                       "anomaly": False}],
        })
        text = tb.format_status_text()
        self.assertIn("engine bing", text)
        self.assertIn("wajah: results me t.me channel nahi mila", text)


class _FakeAPI:
    def __init__(self):
        self.sent = []

    def send(self, chat_id, text, buttons=None):
        self.sent.append((int(chat_id), str(text), buttons))
        return {"ok": True}

    def edit(self, chat_id, message_id, text, parse_mode=None):
        return {"ok": True}

    def get_updates(self, offset, timeout=None):
        return []

    def answer_callback(self, callback_id, text=""):
        return {"ok": True}

    def set_my_commands(self, commands, timeout=30):
        return {"ok": True}


class TestHonestEmptyMessage(unittest.TestCase):
    def setUp(self):
        tb._EXPLORE_PENDING.pop(42, None)
        tb._EXPLORE_SHOWN.pop(42, None)
        tb._EXPLORE_TOPICS.clear()

    def tearDown(self):
        tb._EXPLORE_PENDING.pop(42, None)
        tb._EXPLORE_SHOWN.pop(42, None)

    def test_empty_reason_anti_bot(self):
        res = {"discovery": {"candidates": 0, "probed": 0, "added": [],
                             "web_search": {"anomaly": True, "engine": "",
                                            "error": "search engine ne results "
                                                     "nahi diye (anti-bot)"}}}
        reason = tb._explore_empty_reason(res, "all")
        self.assertIn("koi naya channel nahi mila", reason)
        self.assertIn("anti-bot", reason)
        self.assertIn("/status", reason)

    def test_render_empty_sends_honest_reason(self):
        res = {"topic": "android security", "query": "android security",
               "items": 0,
               "discovery": {"candidates": 0, "probed": 0, "added": [],
                             "dead": [], "counts": {"active": 0},
                             "web_search": {"anomaly": True, "engine": "",
                                            "error": "search engine ne results "
                                                     "nahi diye (anti-bot)"}},
               "scored": []}
        api = _FakeAPI()
        out = tb._render_explore(42, "android security", "tg", res,
                                 config.load(), api)
        self.assertTrue(out["empty"])
        text = api.sent[-1][1]
        self.assertIn("search engine ne results nahi diye (anti-bot)", text)


if __name__ == "__main__":
    unittest.main()
