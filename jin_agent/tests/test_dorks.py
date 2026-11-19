"""P41 - Google-dork helper + /dork command + /status dork block.

Backend live classification 2026-11-19 (JIN-Agent UA):
- Bing: dork qabool, asli results (auto=True).
- Mojeek/DuckDuckGo Lite/Startpage/Ecosia/Google(gbv=1): block/JS — auto=False.

Network calls mocked hain (project rule).
"""

import os
import tempfile
import unittest
from unittest import mock

from jin_agent import config, dorks, policy, store
from jin_agent import telegram_bot as tb


def setUpModule():
    os.environ["JIN_AGENT_DATA"] = tempfile.mkdtemp(prefix="jin-dorks-")
    store.init_db()


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


class TestOperators(unittest.TestCase):
    def test_site_intitle_inurl_filetype(self):
        self.assertEqual(dorks.site("android", "t.me/s"), 'site:t.me/s "android"')
        self.assertEqual(dorks.intitle("android"), 'intitle:"android"')
        self.assertEqual(dorks.inurl("android"), 'inurl:"android"')
        self.assertEqual(dorks.filetype("android", "pdf"), 'filetype:pdf "android"')

    def test_exclude(self):
        self.assertEqual(dorks.exclude("q", ("twitter", "-instagram")),
                         "q -twitter -instagram")

    def test_build(self):
        self.assertEqual(dorks.build("android", [dorks.intitle("android")]),
                         'android intitle:"android"')

    def test_tg_preset(self):
        self.assertEqual(dorks.tg("android"),
                         "site:t.me/s android -twitter -instagram")

    def test_tg_existing_site_not_duplicated(self):
        # query me pehle se site:t.me/s ho to dobara na jodo
        self.assertEqual(dorks.tg("site:t.me/s android"),
                         "site:t.me/s android -twitter -instagram")
        # case-insensitive talaash; site: ke baad ka hissa barqarar
        self.assertEqual(dorks.tg("SITE:T.ME/S Android"),
                         "SITE:T.ME/S Android -twitter -instagram")

    def test_tg_normal_case_unchanged(self):
        self.assertEqual(dorks.tg("android"),
                         "site:t.me/s android -twitter -instagram")
        self.assertEqual(dorks.tg("firmware update"),
                         "site:t.me/s firmware update -twitter -instagram")

    def test_other_presets(self):
        self.assertEqual(dorks.pdf("x"), 'filetype:pdf "x"')
        self.assertEqual(dorks.gov("x"), 'site:gov "x"')
        self.assertEqual(dorks.edu("x"), 'site:edu "x"')
        self.assertEqual(dorks.pastebin("x"), 'site:pastebin.com "x"')


class TestBackends(unittest.TestCase):
    def test_only_bing_auto(self):
        auto = [b["key"] for b in dorks.DORK_BACKENDS if b["auto"]]
        self.assertEqual(auto, ["dork-bing"])

    def test_blocked_have_reason(self):
        for b in dorks.DORK_BACKENDS:
            if not b["auto"]:
                self.assertIn("auto=False", b["note"], b["key"])

    def test_backend_url_quotes(self):
        b = [x for x in dorks.DORK_BACKENDS if x["key"] == "dork-bing"][0]
        self.assertIn("q=site%3At.me/s%20android", dorks.backend_url(b, "site:t.me/s android"))

    def test_working_backends(self):
        self.assertEqual(len(dorks.working_backends()), 1)


class TestParser(unittest.TestCase):
    def test_parse_bing_results_decodes_ck_a(self):
        html = ('<li class="b_algo"><h2><a href="https://www.bing.com/ck/a?x=1&'
                'u=a1aHR0cHM6Ly9leGFtcGxlLmNvbS94">Example Title</a></h2></li>')
        items = dorks.parse_bing_results(html)
        self.assertEqual(items[0]["url"], "https://example.com/x")
        self.assertEqual(items[0]["title"], "Example Title")

    def test_parse_bing_results_empty(self):
        self.assertEqual(dorks.parse_bing_results("<html>anomaly</html>"), [])

    def test_selftest(self):
        self.assertTrue(dorks.selftest()["ok"])


class TestRender(unittest.TestCase):
    def test_render_has_presets_links_and_status(self):
        text = dorks.render("android security", [])
        self.assertIn("Dork: android security", text)
        self.assertIn("site:t.me/s android security -twitter -instagram", text)
        self.assertIn("filetype:pdf", text)
        self.assertIn("https://www.bing.com/search?q=", text)
        self.assertIn("Dork backend:", text)
        self.assertIn("✓ Bing", text)
        self.assertIn("✗ Google (gbv=1)", text)

    def test_onion_is_link_only(self):
        link = dorks.onion_link("android")
        self.assertTrue(link["url"].startswith("https://ahmia.fi/"))
        self.assertIn("onion", link["note"].lower())


class TestCommand(unittest.TestCase):
    def setUp(self):
        tb._EXPLORE_PENDING.pop(42, None)
        tb._EXPLORE_SHOWN.pop(42, None)
        tb._EXPLORE_TOPICS.clear()

    def tearDown(self):
        tb._EXPLORE_PENDING.pop(42, None)
        tb._EXPLORE_SHOWN.pop(42, None)

    def test_dork_command(self):
        api = _FakeAPI()
        with mock.patch.object(dorks, "search", return_value=[]):
            res = tb.dispatch(42, "/dork android security",
                              {"telegram_chat_id": "42"}, api=api)
        self.assertTrue(res["ok"])
        self.assertEqual(res["action"], "dork")
        self.assertIn("site:t.me/s android security", api.sent[-1][1])

    def test_dork_requires_query(self):
        api = _FakeAPI()
        res = tb.dispatch(42, "/dork", {"telegram_chat_id": "42"}, api=api)
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"], "query required")

    def test_explore_dork_flag(self):
        api = _FakeAPI()
        res_obj = {
            "topic": "android security", "query": "android security", "items": 1,
            "discovery": {"added": [], "dead": [], "candidates": 0, "probed": 0,
                          "counts": {"active": 0, "dead": 0, "archived": 0,
                                     "stale": 0, "total": 0}},
            "scored": [],
        }
        with mock.patch.object(tb.scheduler, "run_job", lambda *a, **k: res_obj), \
             mock.patch.object(dorks, "search", return_value=[]):
            res = tb.dispatch(42, "/explore android security --dork",
                              {"telegram_chat_id": "42"}, api=api)
        self.assertTrue(res["ok"])
        self.assertIn("dork", res)
        self.assertTrue(any("site:t.me/s android security" in t
                            for _, t, _ in api.sent))

    def test_status_has_dork_block(self):
        text = tb.format_status_text()
        self.assertIn("Dork:", text)
        self.assertIn("Bing ✓", text)


if __name__ == "__main__":
    unittest.main()
