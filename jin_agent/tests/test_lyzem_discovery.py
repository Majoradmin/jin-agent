"""P43 - Lyzem discovery engine + provider-agnostic ``discovery`` layer.

Live (2026-11-21): ``https://lyzem.com/search?q=<keyword>`` bina login / bina
API key kaam karta hai aur Telegram-wide channel/group/bot/post/article
results deta hai — ``android security`` par 10 results (channel/group/bot),
Urdu ``موبائل`` par post results. RightDAO ke rate-limit ke baat ye doosra
provider hai.

Sab network calls mocked hain (project rule: tests kabhi live internet na
chhedein).
"""

import os
import tempfile
import unittest
from unittest import mock

from jin_agent import channels, config, discovery, policy, store


def setUpModule():
    os.environ["JIN_AGENT_DATA"] = tempfile.mkdtemp(prefix="jin-lyzem-")
    store.init_db()
    channels.ensure_table()
    discovery.clear_cache()


LYZEM_HTML = (
    '<ul class="search-results">'
    '<li class="search-result">'
    '<div class="search-result-type-wrapper " title="channel"></div>'
    '<div class="search-result-info">'
    '<p class="search-result-title"><a href="https://t.me/androidmalware">'
    ' Android Security &amp; Malware </a></p>'
    '<p class="search-result-descr"><a href="https://t.me/androidmalware"'
    ' target="_blank"> Mobile infosec news about - security, privacy, malware'
    ' </a></p>'
    '</div></li>'
    '<li class="search-result">'
    '<div class="search-result-type-wrapper " title="group"></div>'
    '<div class="search-result-info">'
    '<p class="search-result-title"><a href="https://t.me/prasadsinghrandhawa">'
    ' Android malware-security </a></p>'
    '<p class="search-result-descr"><a href="https://t.me/prasadsinghrandhawa"'
    ' target="_blank"> Tech and hacking channel </a></p>'
    '</div></li>'
    '<li class="search-result">'
    '<div class="search-result-type-wrapper " title="post"></div>'
    '<div class="search-result-info">'
    '<p class="search-result-title"><a href="https://t.me/zrumbesh/2942">'
    ' </a></p>'
    '<p class="search-result-descr"><a href="https://t.me/zrumbesh/2942"'
    ' target="_blank"> دشت بل نگور ءَ زونگ <em>موبائل</em> ٹاور </a></p>'
    '</div></li>'
    '</ul>')
LYZEM_BLOCKED = "<html><body>rate limited</body></html>"
RIGHTDAO_HTML = (
    '<div class="summary"><div>Page <b>1</b> of total 8 items</div></div>'
    '<div class="results"><div class="item"><div class="title">'
    '<a href="https://t.me/rightdao_ch">Telegram: Contact @rightdao_ch</a>'
    '</div></div></div>')


class _FakeFetch:
    def __init__(self, routes):
        self.routes = dict(routes)
        self.calls = []

    def __call__(self, url, cfg=None, extra_hosts=()):
        self.calls.append(url)
        for frag, body in self.routes.items():
            if frag in url:
                return body
        raise ValueError("blocked")


class TestLyzemParse(unittest.TestCase):
    def test_parse_records(self):
        recs = channels.parse_lyzem_html(LYZEM_HTML)
        self.assertEqual([r["handle"] for r in recs],
                         ["androidmalware", "prasadsinghrandhawa", "zrumbesh"])
        self.assertEqual([r["kind"] for r in recs],
                         ["channel", "group", "post"])

    def test_parse_title_descr_and_msg_id(self):
        recs = channels.parse_lyzem_html(LYZEM_HTML)
        first = recs[0]
        self.assertEqual(first["title"], "Android Security & Malware")
        self.assertIn("malware", first["descr"])
        self.assertEqual(first["msg_id"], "")
        post = recs[2]
        self.assertEqual(post["msg_id"], "2942")
        # post ka title khaali tha -> descr se fallback
        self.assertTrue(post["title"])

    def test_duplicate_handles_deduped(self):
        html = LYZEM_HTML + LYZEM_HTML
        recs = channels.parse_lyzem_html(html)
        self.assertEqual(len(recs), 3)

    def test_has_results_marker(self):
        self.assertTrue(channels.lyzem_has_results(LYZEM_HTML))
        self.assertFalse(channels.lyzem_has_results(LYZEM_BLOCKED))
        self.assertFalse(channels.lyzem_has_results(""))

    def test_host_allowed_and_registered(self):
        ok, reason = policy.check_url("https://lyzem.com/search?q=android")
        self.assertTrue(ok, reason)
        keys = {r["key"] for r in policy.register()}
        self.assertIn("lyzem", keys)


class TestDiscoveryProbe(unittest.TestCase):
    def setUp(self):
        discovery.clear_cache()
        self._patch = mock.patch.object(channels.adapters, "fetch")
        self.mock_fetch = self._patch.start()
        self.addCleanup(self._patch.stop)

    def test_rightdao_first_then_lyzem(self):
        self.mock_fetch.side_effect = _FakeFetch({"rightdao.com": RIGHTDAO_HTML})
        info = channels.web_search_probe("android security", config.load())
        self.assertEqual(info["engine"], "rightdao")
        self.assertEqual(info["handles"], ["rightdao_ch"])
        self.assertEqual([t["engine"] for t in info["tried"]][0], "rightdao")

    def test_lyzem_used_when_rightdao_anomaly(self):
        self.mock_fetch.side_effect = _FakeFetch({
            "rightdao.com": "<html>blocked</html>",
            "lyzem.com": LYZEM_HTML,
        })
        info = channels.web_search_probe("android security", config.load())
        self.assertEqual(info["engine"], "lyzem")
        self.assertIn("androidmalware", info["handles"])
        self.assertFalse(info["anomaly"])

    def test_cache_hit_second_call(self):
        self.mock_fetch.side_effect = _FakeFetch({"lyzem.com": LYZEM_HTML})
        first = channels.web_search_probe("android security", config.load())
        self.assertFalse(first.get("cached"))
        calls = list(self.mock_fetch.side_effect.calls)
        second = channels.web_search_probe("android security", config.load())
        self.assertTrue(second.get("cached"))
        self.assertEqual(self.mock_fetch.side_effect.calls, calls)   # doosri fetch nahi

    def test_cache_can_be_disabled(self):
        cfg = dict(config.load(), discovery_cache_seconds=0)
        self.mock_fetch.side_effect = _FakeFetch({"lyzem.com": LYZEM_HTML})
        channels.web_search_probe("android security", cfg)
        channels.web_search_probe("android security", cfg)
        # cache band → har probe dobara chalta hai (rightdao fail + lyzem ok)
        self.assertEqual(len(self.mock_fetch.side_effect.calls), 4)

    def test_providers_subset(self):
        self.mock_fetch.side_effect = _FakeFetch({"lyzem.com": LYZEM_HTML})
        info = discovery.probe("android security", config.load(),
                               providers=("lyzem",))
        self.assertEqual(info["engine"], "lyzem")
        self.assertEqual([t["engine"] for t in info["tried"]], ["lyzem"])

    def test_lyzem_records_fail_returns_empty(self):
        self.mock_fetch.side_effect = ValueError("blocked")
        self.assertEqual(discovery.lyzem_records("android", config.load()), [])

    def test_merge_collects_from_both_providers(self):
        self.mock_fetch.side_effect = _FakeFetch({
            "rightdao.com": RIGHTDAO_HTML,
            "lyzem.com": LYZEM_HTML,
        })
        info = channels.web_search_probe("android security", config.load(),
                                         merge=True,
                                         providers=("rightdao", "lyzem"))
        self.assertIn("rightdao", info["engine"])
        self.assertIn("lyzem", info["engine"])
        self.assertIn("rightdao_ch", info["handles"])
        self.assertIn("androidmalware", info["handles"])
        self.assertFalse(info["anomaly"])

    def test_merge_skips_blocked_provider(self):
        self.mock_fetch.side_effect = _FakeFetch({"lyzem.com": LYZEM_HTML})
        info = channels.web_search_probe("android security", config.load(),
                                         merge=True,
                                         providers=("rightdao", "lyzem"))
        self.assertEqual(info["engine"], "lyzem")
        self.assertIn("androidmalware", info["handles"])


class TestHelpers(unittest.TestCase):
    def test_handle_from_url(self):
        self.assertEqual(discovery.handle_from_url("https://t.me/durov"), "durov")
        self.assertEqual(discovery.handle_from_url("https://t.me/s/durov/12"),
                         "durov")
        self.assertEqual(discovery.handle_from_url("https://example.org/x"), "")

    def test_clean_text(self):
        self.assertEqual(discovery.clean_text("<em>موبائل</em> &amp; ٹاور"),
                         "موبائل & ٹاور")


if __name__ == "__main__":
    unittest.main()
