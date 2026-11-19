"""P42 - RightDAO discovery engine: parse, kram (pehla engine), anomaly fallback.

Live bug (2026-11-19): ``web_search_candidates`` sab queries par ``[]`` deta
tha — Bing ``site:`` ignore karta hai, DDG anomaly, Mojeek captcha, Startpage
Anubis, Ecosia 403, Brave 429. RightDAO (``rightdao.com/search?q=``) kaam
karta hai aur ``site:t.me <topic>`` par asli t.me handles deta hai. Ab wo
pehla engine hai.

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
    os.environ["JIN_AGENT_DATA"] = tempfile.mkdtemp(prefix="jin-rightdao-")
    store.init_db()
    channels.ensure_table()


# RightDAO result page ka hissa: ``class="item"`` marker + t.me links.
RIGHTDAO_HTML = (
    '<div class="summary"><div>Page <b>1</b> of total 8 items</div></div>'
    '<div class="results">'
    '<div class="item"><div class="title"><a href="https://t.me/it_security_news_info">'
    'Telegram: Contact @it_security_news_info</a></div></div>'
    '<div class="item"><div class="title"><a href="https://t.me/tgx_android">'
    'Telegram: Contact @tgx_android</a></div></div>'
    '<div class="item"><div class="title"><a href="https://t.me/android_broadcast_bot">'
    'Android Broadcast</a></div></div>'
    '</div>')
RIGHTDAO_ANOMALY = "<html><body>unusual traffic — blocked</body></html>"
BING_HTML = (
    '<div id="b_results"><li class="b_algo"><h2><a href="https://t.me/bing_ch">'
    'Bing Channel</a></h2></li></div>')


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


class TestRightDaoParse(unittest.TestCase):
    def test_parse_rightdao_html_extracts_handles(self):
        handles = channels.parse_rightdao_html(RIGHTDAO_HTML)
        self.assertEqual(handles, ["it_security_news_info", "tgx_android",
                                   "android_broadcast_bot"])

    def test_rightdao_has_results_marker(self):
        self.assertTrue(channels.rightdao_has_results(RIGHTDAO_HTML))
        self.assertFalse(channels.rightdao_has_results(RIGHTDAO_ANOMALY))

    def test_rightdao_has_results_fallback_on_handles(self):
        # marker nahi magar handle mojood → fallback True
        self.assertTrue(channels.rightdao_has_results(
            '<a href="https://t.me/fallback_ch">x</a>'))

    def test_rightdao_host_allowed(self):
        ok, reason = policy.check_url("https://rightdao.com/search?q=x")
        self.assertTrue(ok, reason)

    def test_noise_handles_excluded(self):
        text = "join https://t.me/login and https://t.me/socks and t.me/real_ch"
        self.assertEqual(channels.extract_handles(text), ["real_ch"])


class TestRightDaoEngineOrder(unittest.TestCase):
    def setUp(self):
        self._patch = mock.patch.object(channels.adapters, "fetch")
        self.mock_fetch = self._patch.start()
        self.addCleanup(self._patch.stop)

    def test_rightdao_is_first_engine(self):
        self.mock_fetch.side_effect = _FakeFetch({"rightdao.com": RIGHTDAO_HTML})
        info = {}
        handles = channels.web_search_candidates("android security",
                                                 config.load(), info)
        self.assertIn("it_security_news_info", handles)
        self.assertEqual(info["engine"], "rightdao")
        self.assertFalse(info["anomaly"])
        self.assertFalse(self.mock_fetch.side_effect.has("bing.com"))
        self.assertFalse(self.mock_fetch.side_effect.has("duckduckgo"))

    def test_rightdao_anomaly_falls_back_to_bing(self):
        self.mock_fetch.side_effect = _FakeFetch({
            "rightdao.com": RIGHTDAO_ANOMALY,
            "bing.com": BING_HTML,
        })
        info = {}
        handles = channels.web_search_candidates("android security",
                                                 config.load(), info)
        self.assertEqual(handles, ["bing_ch"])
        self.assertEqual(info["engine"], "bing")
        self.assertFalse(info["anomaly"])

    def test_rightdao_result_used_without_bing(self):
        self.mock_fetch.side_effect = _FakeFetch({"rightdao.com": RIGHTDAO_HTML})
        info = {}
        handles = channels.web_search_candidates("free api key", config.load(),
                                                 info)
        self.assertEqual(len(handles), 3)
        self.assertEqual(info["candidates"], 3)
        self.assertEqual([t["engine"] for t in info["tried"]][0], "rightdao")


class TestStatusLine(unittest.TestCase):
    def test_status_shows_rightdao_engine(self):
        channels.save_discovery_state({
            "ts": 1_800_000_000, "query": "android security",
            "engine": "rightdao", "candidates": 8, "probed": 8, "added": 5,
            "dead": 3, "anomaly": False, "error": "", "tried": [],
        })
        text = tb.format_status_text()
        self.assertIn("Telegram discovery:", text)
        self.assertIn("engine rightdao", text)
        self.assertIn("added 5", text)


if __name__ == "__main__":
    unittest.main()
