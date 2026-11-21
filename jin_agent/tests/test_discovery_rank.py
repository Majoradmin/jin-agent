"""P45 - Discovery ranking + safety filters.

- relevance ordering (query terms -> title/handle/descr/preview)
- spam/scam filter (match + false-positive nahi; FRP/FMI/MDM waghera NAHI)
- ``policy`` blocked pattern -> ``status='blocked'``
- case-insensitive dedupe (Telegram handles)
- source diversity (handle -> engine) + ``rank`` field

Sab network calls mocked hain (project rule: tests kabhi live internet na
chhedein).
"""

import os
import tempfile
import unittest
from unittest import mock

from jin_agent import channels, config, discovery, discovery_rank, policy, store


def setUpModule():
    os.environ["JIN_AGENT_DATA"] = tempfile.mkdtemp(prefix="jin-rank-")
    store.init_db()
    channels.ensure_table()
    discovery.clear_cache()


def _html(title: str, descr: str = "Mobile infosec news about security",
          posts: int = 12, last: str = "2026-11-19T10:00:00+00:00") -> str:
    post_tags = "".join(f'<div data-post="c/{i}"></div>' for i in range(posts))
    return (
        f'<meta property="og:title" content="{title}">'
        f'<meta property="og:description" content="{descr}">'
        f'{post_tags}'
        f'<time datetime="{last}"></time>'
        f'<div class="tgme_widget_message_text">Firmware update news</div>')


class TestRelevance(unittest.TestCase):
    def test_ordering_title_match_beats_unrelated(self):
        good = discovery_rank.relevance("android security",
                                        "Android Security & Malware")
        bad = discovery_rank.relevance("android security", "GSM Lab Channel")
        self.assertGreater(good, bad)
        self.assertGreaterEqual(good, 6)
        self.assertEqual(bad, 0)

    def test_matched_terms_and_reason(self):
        detail = discovery_rank.relevance_detail(
            "android security", "Android Security & Malware")
        self.assertEqual(detail["matched"], ["android", "security"])
        reason = discovery_rank.relevance_reason(
            "android security", "Android Security & Malware")
        self.assertEqual(reason, "android, security")

    def test_handle_and_descr_also_count(self):
        self.assertEqual(discovery_rank.relevance("infosec", "News"), 0)
        self.assertGreater(discovery_rank.relevance(
            "infosec", "Mobile infosec news"), 0)

    def test_urdu_query_non_latin(self):
        self.assertGreater(discovery_rank.relevance("موبائل", "موبائل ٹاور"), 0)
        self.assertEqual(discovery_rank.relevance("موبائل", "GSM Lab"), 0)

    def test_score_query_beats_no_query(self):
        rec = {"title": "Zebra migrations study", "channel": "zebra_ch",
               "last_post_at": "2026-11-19 10:00:00", "post_count": 5,
               "subscribers": "1K", "avg_text_len": 100}
        cfg = config.load()
        self.assertGreater(channels.score(rec, cfg, query="zebra migrations"),
                           channels.score(rec, cfg))

    def test_channel_signs_topic_match_from_query(self):
        rec = {"title": "Android Security", "channel": "androidsec",
               "last_post_at": "2026-11-19 10:00:00", "post_count": 5,
               "subscribers": "1K", "avg_text_len": 100}
        cfg = config.load()
        self.assertTrue(
            channels.channel_signs(rec, cfg, query="android security")["topic_match"])
        self.assertFalse(
            channels.channel_signs(rec, cfg, query="cooking recipes")["topic_match"])
        # query ke baghair purana keyword block
        self.assertTrue(channels.channel_signs(rec, cfg)["topic_match"])


class TestSpamFilter(unittest.TestCase):
    def test_matches(self):
        self.assertEqual(discovery_rank.spam_reason("Free Money Earn Daily"),
                         "free money")
        self.assertEqual(discovery_rank.spam_reason("100% Free IPA"), "100% free")
        self.assertEqual(discovery_rank.spam_reason("Crypto giveaway now"),
                         "crypto giveaway")
        self.assertEqual(discovery_rank.spam_reason("Best Casino Tips"),
                         "casino/gambling")
        self.assertEqual(discovery_rank.spam_reason("Easy Loan approval"),
                         "ipo/loan")
        self.assertEqual(discovery_rank.spam_reason("paisa kamai daily"),
                         "paisa kamai")
        self.assertEqual(discovery_rank.spam_reason("كازينو"), "casino/lottery")

    def test_no_false_positive(self):
        for text in ("Android Security & Malware", "GSM Lab Channel",
                     "Tech and hacking channel", "موبائل ٹاور",
                     "Firmware update news"):
            self.assertEqual(discovery_rank.spam_reason(text), "", text)

    def test_frp_not_spam_policy_is_separate(self):
        # FRP/FMI/MDM/IMEI patterns spam filter me NAHI — aur P47 se policy block
        # bhi retire, is liye blocked_reason hamesha "" deta hai.
        self.assertEqual(discovery_rank.spam_reason("FRP bypass kar do"), "")
        self.assertEqual(discovery_rank.blocked_reason("FRP bypass kar do"), "")


class TestBlockedFilter(unittest.TestCase):
    def test_block_retired(self):
        # P47: ownership-control title block retire — hamesha "" (safety net).
        self.assertEqual(discovery_rank.blocked_reason("FRP bypass kar do"), "")
        self.assertEqual(discovery_rank.blocked_reason("iCloud activation lock bypass"), "")
        self.assertEqual(discovery_rank.blocked_reason("Android Security"), "")


class TestDedupe(unittest.TestCase):
    def test_case_insensitive(self):
        self.assertEqual(discovery_rank.dedupe_handles(
            ["Foo", "foo", "FOO", "bar", "Bar", ""]),
            ["Foo", "bar"])

    def test_run_discovery_dedupes_case(self):
        seen = {}

        def fake_web(query, cfg=None, info=None, merge=False, providers=None):
            seen["query"] = query
            info["sources"] = {}
            return ["Dup_Ch", "dup_ch", "other_ch"]

        rows = {
            "Dup_Ch": {"channel": "Dup_Ch", "status": "dead", "score": 0,
                       "note": "dead: 0 posts on preview"},
            "other_ch": {"channel": "other_ch", "status": "dead", "score": 0,
                         "note": "dead: 0 posts on preview"},
        }
        with mock.patch.object(channels, "web_search_candidates", fake_web), \
             mock.patch.object(channels, "harvest_archive",
                               lambda cfg=None, query="": []), \
             mock.patch.object(channels, "check_channel",
                               lambda ch, cfg=None, query="": dict(rows[ch])):
            out = channels.run_discovery(config.load(), offline=False,
                                         max_add=5, query="python")
        handles = [r["channel"] for r in out["probe_rows"]]
        self.assertEqual(len(handles), len(set(h.lower() for h in handles)))
        self.assertIn("Dup_Ch", handles)
        self.assertNotIn("dup_ch", handles)
        self.assertEqual(seen.get("query"), "python")


class TestSourceAndRank(unittest.TestCase):
    def test_probe_merge_sources(self):
        discovery.clear_cache()
        rightdao = ('<div class="summary"><div>Page <b>1</b> of total 8 items'
                    '</div></div><div class="results"><div class="item">'
                    '<div class="title"><a href="https://t.me/rightdao_ch">R</a>'
                    '</div></div></div>')
        lyzem = ('<ul class="search-results"><li class="search-result">'
                 '<div class="search-result-type-wrapper " title="channel"></div>'
                 '<div class="search-result-info">'
                 '<p class="search-result-title"><a href="https://t.me/androidmalware">'
                 'A</a></p><p class="search-result-descr"><a href="https://t.me/androidmalware">'
                 'Mobile infosec</a></p></div></li></ul>')

        def fake_fetch(url, cfg=None, extra_hosts=()):
            if "rightdao.com" in url:
                return rightdao
            if "lyzem.com" in url:
                return lyzem
            raise ValueError("blocked")

        with mock.patch.object(channels.adapters, "fetch", fake_fetch):
            info = discovery.probe("android security", config.load(),
                                   providers=("rightdao", "lyzem"), merge=True)
        self.assertEqual(info["sources"]["rightdao_ch"], "rightdao")
        self.assertEqual(info["sources"]["androidmalware"], "lyzem")
        self.assertIn("rightdao", info["engines"])
        self.assertIn("lyzem", info["engines"])

    def test_merge_web_probe_merges_sources(self):
        merged = channels.merge_web_probe([
            {"engine": "rightdao", "candidates": 1, "sources": {"a": "rightdao"},
             "tried": [], "error": "", "anomaly": False},
            {"engine": "lyzem", "candidates": 1, "sources": {"b": "lyzem"},
             "tried": [], "error": "", "anomaly": False},
        ])
        self.assertEqual(merged["sources"], {"a": "rightdao", "b": "lyzem"})

    def test_run_discovery_source_and_rank(self):
        def fake_web(query, cfg=None, info=None, merge=False, providers=None):
            info["sources"] = {"act_ch": "rightdao", "dead_ch": "lyzem"}
            return ["act_ch", "dead_ch"]

        rows = {
            "act_ch": {"channel": "act_ch", "status": "active", "score": 8,
                       "title": "Live", "subscribers": "10K",
                       "last_post_at": "2026-11-19 10:00:00", "post_count": 9,
                       "note": "auto-discovered liveness check"},
            "dead_ch": {"channel": "dead_ch", "status": "dead", "score": 1,
                        "title": "", "subscribers": "", "last_post_at": "",
                        "post_count": 0, "note": "dead: 0 posts on preview"},
        }
        with mock.patch.object(channels, "web_search_candidates", fake_web), \
             mock.patch.object(channels, "harvest_archive",
                               lambda cfg=None, query="": []), \
             mock.patch.object(channels, "check_channel",
                               lambda ch, cfg=None, query="": dict(rows[ch])):
            out = channels.run_discovery(config.load(), offline=False,
                                         max_add=5, query="python")
        by = {r["channel"]: r for r in out["probe_rows"]}
        self.assertEqual(by["act_ch"]["source"], "rightdao")
        self.assertEqual(by["dead_ch"]["source"], "lyzem")
        self.assertEqual(by["act_ch"]["rank"], 1)
        self.assertEqual(sorted(r["rank"] for r in out["probe_rows"]), [1, 2])
        self.assertEqual(out["summaries"][0]["source"], "rightdao")


class TestCheckChannelSafety(unittest.TestCase):
    def _check(self, title: str, query: str = ""):
        with mock.patch.object(channels.adapters, "fetch",
                               lambda url, cfg=None, extra_hosts=(): _html(title)):
            return channels.check_channel("safety_ch", config.load(), query=query)

    def test_spam_status(self):
        res = self._check("Free Money Earn Daily")
        self.assertEqual(res["status"], "spam")
        self.assertEqual(res["score"], 0)
        self.assertTrue(res["note"].startswith("spam:"))

    def test_block_retired_title_not_blocked(self):
        # P47: ownership-control title block retire — FRP title ab 'active'
        # (ya liveness ke mutabiq koi aur status), 'blocked' nahi.
        res = self._check("FRP Bypass Tool")
        self.assertNotEqual(res["status"], "blocked")
        self.assertFalse(res["note"].startswith("blocked:"))

    def test_normal_active_with_relevance(self):
        res = self._check("Android Security", query="android security")
        self.assertEqual(res["status"], "active")
        self.assertGreaterEqual(res["score"], 4)
        self.assertGreater(res["relevance"], 0)
        self.assertIn("android", res["reason"])

    def test_frp_title_not_blocked(self):
        # P47: FRP wala title ab blocked NAHI — liveness ke mutabiq status.
        res = self._check("FRP Bypass Tool")
        self.assertNotEqual(res["status"], "blocked")
        self.assertFalse(res["note"].startswith("spam:"))


if __name__ == "__main__":
    unittest.main()
