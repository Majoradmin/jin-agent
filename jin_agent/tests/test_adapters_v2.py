"""P27 - new adapters, all offline with injected fetch fixtures.

Every network call goes through ``adapters.fetch``; tests replace it with a
router. No test touches the internet, and optional keyed adapters must make
zero calls when no key is configured.
"""

import json
import os
import tempfile
import time
import unittest
from unittest import mock

os.environ.setdefault("JIN_AGENT_DATA", tempfile.mkdtemp(prefix="jin-adapters2-"))

from jin_agent import adapters, config, policy, ratelimit  # noqa: E402

REDDIT_JSON = json.dumps({"data": {"children": [{"data": {
    "title": "MTK preloader scatter fails after update",
    "permalink": "/r/android/comments/abc/thread/",
    "created_utc": 1763000000,
    "selftext": "DA version mismatch on Dimensity device",
    "subreddit": "android",
}}]}})

WIKI_JSON = json.dumps({"query": {"search": [{
    "title": "MediaTek", "pageid": 12345,
    "snippet": "<span class=\"searchmatch\">MediaTek</span> chip maker",
    "timestamp": "2026-11-01T00:00:00Z",
}]}})

WIKIDATA_JSON = json.dumps({"search": [{
    "id": "Q12345", "label": "MediaTek",
    "description": "fabless semiconductor company",
    "concepturi": "https://www.wikidata.org/entity/Q12345",
}]})

GNEWS_RSS = """<?xml version="1.0"?><rss><channel><item>
<title>Android firmware update</title>
<link>https://news.google.com/rss/articles/abc</link>
<pubDate>Sat, 01 Nov 2026 10:00:00 GMT</pubDate>
<description>Firmware rollout news</description>
</item></channel></rss>"""

WAYBACK_JSON = json.dumps({"archived_snapshots": {"closest": {
    "url": "https://web.archive.org/web/20260101120000/https://example.com/x",
    "timestamp": "20260101120000", "original": "https://example.com/x"}}})

CDX_JSON = json.dumps([
    ["urlkey", "timestamp", "original", "mimetype", "statuscode"],
    ["com,example)/x", "20260101120000", "https://example.com/x", "text/html", "200"],
])

GITHUB_JSON = json.dumps({"items": [{
    "full_name": "bkerler/mtkclient", "html_url": "https://github.com/bkerler/mtkclient",
    "description": "MediaTek reverse engineering tool",
    "updated_at": "2026-11-01T00:00:00Z", "stargazers_count": 4200,
}]})

GITHUB_RATE = json.dumps({"message": "API rate limit exceeded for 1.2.3.4",
                          "documentation_url": "https://docs.github.com/rest"})

NVD_JSON = json.dumps({"vulnerabilities": [{"cve": {
    "id": "CVE-2026-1234",
    "descriptions": [{"lang": "en", "value": "bootloader verification bypass issue"}],
    "published": "2026-11-01T00:00:00Z",
}}]})

ROBOTS = "User-agent: *\nDisallow: /private\nSitemap: https://source.android.com/sitemap.xml\n"

SITEMAP_URLSET = """<?xml version="1.0"?><urlset>
<url><loc>https://source.android.com/docs/security/bulletin</loc>
<lastmod>2026-11-01</lastmod></url>
<url><loc>https://source.android.com/docs/setup/build</loc></url>
</urlset>"""

SITEMAP_INDEX = """<?xml version="1.0"?><sitemapindex>
<sitemap><loc>https://source.android.com/sitemap-docs.xml</loc></sitemap>
</sitemapindex>"""

BRAVE_JSON = json.dumps({"web": {"results": [{
    "title": "Brave result", "url": "https://example.com/brave",
    "description": "brave snippet", "age": "2026-11-01",
}]}})

BING_JSON = json.dumps({"webPages": {"value": [{
    "name": "Bing result", "url": "https://example.com/bing",
    "snippet": "bing snippet", "dateLastCrawled": "2026-11-01T00:00:00Z",
}]}})


class FakeNet:
    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def __call__(self, url, cfg=None, extra_hosts=(), headers=None):
        self.calls.append({"url": url, "headers": dict(headers or {})})
        for fragment, payload in self.routes.items():
            if fragment in url:
                if isinstance(payload, Exception):
                    raise payload
                return payload
        raise ValueError("unexpected fetch: " + url)


def offline():
    return {"offline": True}


class TestParsers(unittest.TestCase):
    def test_parse_reddit(self):
        rows = adapters.parse_reddit(REDDIT_JSON)
        self.assertEqual(len(rows), 1)
        self.assertIn("preloader", rows[0]["title"])
        self.assertEqual(rows[0]["source_key"], "reddit")
        self.assertTrue(rows[0]["url"].startswith("https://www.reddit.com/r/"))
        self.assertTrue(rows[0]["published"].startswith("2025-"))

    def test_parse_wikipedia(self):
        rows = adapters.parse_wikipedia(WIKI_JSON)
        self.assertEqual(rows[0]["title"], "MediaTek")
        self.assertEqual(rows[0]["url"], "https://en.wikipedia.org/?curid=12345")
        self.assertNotIn("<span", rows[0]["excerpt"])

    def test_parse_wikidata(self):
        rows = adapters.parse_wikidata(WIKIDATA_JSON)
        self.assertEqual(rows[0]["title"], "MediaTek (Q12345)")
        self.assertIn("semiconductor", rows[0]["excerpt"])
        self.assertEqual(rows[0]["source_key"], "wikidata")

    def test_parse_github_search(self):
        rows = adapters.parse_github_search(GITHUB_JSON)
        self.assertEqual(rows[0]["source_key"], "github-search")
        self.assertIn("bkerler/mtkclient", rows[0]["title"])
        self.assertIn("stars: 4200", rows[0]["excerpt"])

    def test_parse_nvd(self):
        rows = adapters.parse_nvd(NVD_JSON)
        self.assertEqual(rows[0]["source_key"], "nvd")
        self.assertTrue(rows[0]["title"].startswith("CVE-2026-1234"))
        self.assertEqual(rows[0]["category"], "Security")
        self.assertIn("/vuln/detail/", rows[0]["url"])

    def test_parse_wayback_availability_and_cdx(self):
        availability = adapters.parse_wayback(WAYBACK_JSON, "https://example.com/x")
        self.assertEqual(len(availability), 1)
        self.assertTrue(availability[0]["link_only"])
        self.assertIn("web.archive.org", availability[0]["url"])
        self.assertTrue(availability[0]["published"].startswith("2026-01-01"))
        cdx = adapters.parse_wayback(CDX_JSON, "https://example.com/x")
        self.assertEqual(cdx[0]["url"], "https://example.com/x")

    def test_parse_robots_and_sitemaps(self):
        self.assertEqual(adapters.parse_robots(ROBOTS),
                         ["https://source.android.com/sitemap.xml"])
        urlset = adapters.parse_sitemap(SITEMAP_URLSET)
        self.assertEqual(len(urlset["urls"]), 2)
        self.assertEqual(urlset["sitemaps"], [])
        index = adapters.parse_sitemap(SITEMAP_INDEX)
        self.assertEqual(index["sitemaps"], ["https://source.android.com/sitemap-docs.xml"])

    def test_sitemap_items_prefers_query_match(self):
        rows = adapters.sitemap_items(
            adapters.parse_sitemap(SITEMAP_URLSET)["urls"], "security bulletin")
        self.assertEqual(len(rows), 1)
        self.assertIn("Bulletin", rows[0]["title"])

    def test_parse_brave_and_bing(self):
        brave = adapters.parse_brave(BRAVE_JSON)
        self.assertEqual(brave[0]["source_key"], "brave-search")
        self.assertEqual(brave[0]["url"], "https://example.com/brave")
        bing = adapters.parse_bing(BING_JSON)
        self.assertEqual(bing[0]["source_key"], "bing-search")
        self.assertEqual(bing[0]["title"], "Bing result")

    def test_garbage_is_empty_not_crash(self):
        for func in (adapters.parse_reddit, adapters.parse_wikipedia,
                     adapters.parse_wikidata, adapters.parse_github_search,
                     adapters.parse_nvd, adapters.parse_brave, adapters.parse_bing):
            self.assertEqual(func("not json"), [], func.__name__)
        self.assertEqual(adapters.parse_sitemap("<not xml"), {"urls": [], "sitemaps": []})


class TestAdaptersMocked(unittest.TestCase):
    def setUp(self):
        ratelimit.reset()
        adapters.BY_KEY["github-search"]._blocked_until = 0.0

    def tearDown(self):
        adapters.BY_KEY["github-search"]._blocked_until = 0.0

    def _search(self, key, query="android firmware", routes=None, cfg=None):
        net = FakeNet(routes or {})
        with mock.patch.object(adapters, "fetch", net):
            items = adapters.BY_KEY[key].search(query, cfg=cfg or config.load())
        return items, net

    def test_reddit_adapter(self):
        items, net = self._search("reddit", routes={"search.json": REDDIT_JSON})
        self.assertEqual(items[0]["source_key"], "reddit")
        self.assertIn("/r/android+AndroidQuestions+firmware/search.json", net.calls[0]["url"])

    def test_wikipedia_adapter(self):
        items, net = self._search("wikipedia", routes={"w/api.php": WIKI_JSON})
        self.assertEqual(items[0]["source"], "Wikipedia Search")
        self.assertIn("srsearch=", net.calls[0]["url"])

    def test_wikidata_adapter(self):
        items, net = self._search("wikidata", routes={"w/api.php": WIKIDATA_JSON})
        self.assertEqual(items[0]["source_key"], "wikidata")
        self.assertIn("wbsearchentities", net.calls[0]["url"])

    def test_google_news_topic_adapter(self):
        items, net = self._search("gnews-topic", query="android security",
                                  routes={"news.google.com/rss": GNEWS_RSS})
        self.assertEqual(items[0]["source_key"], "gnews-topic")
        self.assertIn("/topic/TECHNOLOGY", net.calls[0]["url"])

    def test_wayback_adapter(self):
        items, net = self._search(
            "wayback", query="https://example.com/x old page",
            routes={"archive.org/wayback/available": WAYBACK_JSON})
        self.assertEqual(len(items), 1)
        self.assertTrue(items[0]["link_only"])
        self.assertIn("example.com%2Fx", net.calls[0]["url"])

    def test_github_search_uses_token_header_not_url(self):
        token = "gh" + "p_" + "x" * 20
        cfg = config.load()
        cfg["github_token"] = token
        items, net = self._search("github-search", routes={"api.github.com/search": GITHUB_JSON},
                                  cfg=cfg)
        self.assertEqual(items[0]["source_key"], "github-search")
        self.assertIn("Authorization", net.calls[0]["headers"])
        self.assertNotIn(token, net.calls[0]["url"])

    def test_github_search_rate_limit_sets_cooldown(self):
        adapter = adapters.BY_KEY["github-search"]
        net = FakeNet({"api.github.com/search": GITHUB_RATE})
        with mock.patch.object(adapters, "fetch", net):
            self.assertEqual(adapter.search("x", cfg=config.load()), [])
            self.assertGreater(adapter._blocked_until, time.monotonic())
            self.assertEqual(adapter.search("x", cfg=config.load()), [])
        self.assertEqual(len(net.calls), 1)

    def test_nvd_adapter(self):
        items, net = self._search("nvd", query="bootloader cve",
                                  routes={"services.nvd.nist.gov": NVD_JSON})
        self.assertEqual(items[0]["source_key"], "nvd")
        self.assertIn("keywordSearch=", net.calls[0]["url"])

    def test_sitemap_adapter_follows_robots_and_bounded_depth(self):
        routes = {"robots.txt": ROBOTS, "sitemap.xml": SITEMAP_URLSET,
                  "sitemap-docs.xml": SITEMAP_URLSET}
        items, net = self._search("sitemap", query="security bulletin", routes=routes)
        self.assertTrue(items)
        self.assertIn("bulletin", items[0]["url"])
        self.assertLessEqual(len(net.calls), 5)

    def test_keyed_adapters_disabled_without_key(self):
        for key in ("brave-search", "bing-search"):
            items, net = self._search(key)
            self.assertEqual(items, [])
            self.assertEqual(net.calls, [])

    def test_brave_adapter_with_key(self):
        cfg = config.load()
        cfg["brave_key"] = "brave-test-key"
        items, net = self._search("brave-search", routes={"api.search.brave.com": BRAVE_JSON},
                                  cfg=cfg)
        self.assertEqual(items[0]["source"], "Brave Search API")
        self.assertIn("X-Subscription-Token", net.calls[0]["headers"])
        self.assertNotIn("brave-test-key", net.calls[0]["url"])

    def test_bing_adapter_with_key(self):
        cfg = config.load()
        cfg["bing_key"] = "bing-test-key"
        items, net = self._search("bing-search", routes={"api.bing.microsoft.com": BING_JSON},
                                  cfg=cfg)
        self.assertEqual(items[0]["source"], "Bing Web Search API")
        self.assertIn("Ocp-Apim-Subscription-Key", net.calls[0]["headers"])

    def test_wayback_network_error_returns_empty(self):
        net = FakeNet({"archive.org": ValueError("timeout")})
        with mock.patch.object(adapters, "fetch", net):
            items = adapters.BY_KEY["wayback"].search(
                "https://example.com/x", cfg=config.load())
        self.assertEqual(items, [])


class TestRegistryAndSafety(unittest.TestCase):
    def test_adapter_and_register_counts(self):
        self.assertEqual(len(adapters.ADAPTERS), 27)
        self.assertEqual(len(policy.register()), 33)

    def test_new_hosts_allowlisted(self):
        for url in ("https://www.reddit.com/r/android/search.json",
                    "https://en.wikipedia.org/w/api.php",
                    "https://www.wikidata.org/w/api.php",
                    "https://archive.org/wayback/available?url=x",
                    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                    "https://web.archive.org/cdx/search/cdx?url=x",
                    "https://services.nvd.nist.gov/rest/json/cves/2.0",
                    "https://api.search.brave.com/res/v1/web/search?q=x",
                    "https://api.bing.microsoft.com/v7.0/search?q=x"):
            self.assertTrue(policy.check_url(url)[0], url)

    def test_free_adapters_have_offline_fixture(self):
        for key in ("reddit", "wikipedia", "wikidata", "gnews-topic", "wayback",
                    "github-search", "nvd", "sitemap"):
            items = adapters.BY_KEY[key].search("MediaTek firmware", offline=True)
            self.assertTrue(items, key)
        self.assertTrue(adapters.BY_KEY["wayback"].search("x", offline=True)[0]["link_only"])

    def test_keyed_adapters_offline_without_key_is_empty(self):
        for key in ("brave-search", "bing-search"):
            self.assertEqual(adapters.BY_KEY[key].search("x", offline=True), [])

    def test_run_skips_keyed_adapter_without_key(self):
        items, diag = adapters.run("x", keys=["brave-search"],
                                   cfg=config.load(), offline=False)
        self.assertEqual(items, [])
        self.assertEqual(diag, [])

    def test_run_offline_with_keyed_adapter_uses_fixture(self):
        cfg = config.load()
        cfg["brave_key"] = "k"
        items, diag = adapters.run("MediaTek", keys=["brave-search"], cfg=cfg,
                                   offline=True)
        self.assertTrue(items)
        self.assertEqual(diag[0]["key"], "brave-search")

    def test_config_public_masks_new_keys(self):
        cfg = config.load()
        cfg["brave_key"] = "b-key"
        cfg["bing_key"] = "g-key"
        cfg["github_token"] = "gh-token"
        public = config.public(cfg)
        self.assertEqual(public["brave_key"], "***")
        self.assertEqual(public["bing_key"], "***")
        self.assertEqual(public["github_token"], "***")

    def test_rate_limit_interval_and_backoff(self):
        cfg = {"host_min_interval": 2.0, "host_backoff_base": 10.0,
               "host_backoff_max": 20.0}
        ratelimit.reset()
        self.assertAlmostEqual(ratelimit.delay_for("example.com", cfg, now=100.0), 0.0)
        with ratelimit._LOCK:
            ratelimit._LAST["example.com"] = 100.0
        self.assertAlmostEqual(ratelimit.delay_for("example.com", cfg, now=100.5), 1.5)
        self.assertEqual(ratelimit.note_failure("example.com", cfg), 10.0)
        self.assertEqual(ratelimit.note_failure("example.com", cfg), 20.0)
        self.assertEqual(ratelimit.note_failure("example.com", cfg), 20.0)
        self.assertGreater(ratelimit.blocked_for("example.com"), 0)
        with self.assertRaises(ratelimit.RateLimited):
            ratelimit.wait("example.com", cfg)
        ratelimit.note_success("example.com")
        self.assertEqual(ratelimit.blocked_for("example.com"), 0)
        ratelimit.reset()


class TestPubMedAndAhmia(unittest.TestCase):
    """P29: deep-web database (PubMed) + onion link-only index (Ahmia)."""

    ESEARCH = json.dumps({"esearchresult": {"count": "2", "idlist": ["111", "222"]}})
    ESUMMARY = json.dumps({"result": {
        "111": {"title": "Firmware repair in mobile SoCs",
                "pubdate": "2026/10/01", "fulljournalname": "J. Repair Eng."},
        "222": {"title": "Chipset security bulletin",
                "pubdate": "2026/09/15", "fulljournalname": "Security Rev."},
    }})

    def test_parse_pubmed(self):
        items = adapters.parse_pubmed(self.ESEARCH, self.ESUMMARY)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["url"], "https://pubmed.ncbi.nlm.nih.gov/111/")
        self.assertEqual(items[0]["source_key"], "pubmed")
        self.assertTrue(all(i["trust"] >= 0.8 for i in items))

    def test_parse_pubmed_no_ids(self):
        self.assertEqual(adapters.parse_pubmed('{"esearchresult":{"idlist":[]}}', "{}"), [])
        self.assertEqual(adapters.parse_pubmed("not json", "not json"), [])

    def test_pubmed_adapter_uses_fetch(self):
        def fake_fetch(url, cfg=None, extra_hosts=()):
            if "esearch" in url:
                return self.ESEARCH
            if "esummary" in url:
                return self.ESUMMARY
            raise ValueError("unexpected url " + str(url))

        a = adapters.BY_KEY["pubmed"]
        with mock.patch.object(adapters, "fetch", fake_fetch):
            items = a.search("firmware repair", cfg=config.load())
        self.assertEqual(len(items), 2)
        self.assertIn("eutils.ncbi.nlm.nih.gov", a.last_fetch["url"])

    def test_pubmed_adapter_empty_result_makes_one_call_only(self):
        calls = []

        def fake_fetch(url, cfg=None, extra_hosts=()):
            calls.append(url)
            return '{"esearchresult":{"idlist":[]}}'

        a = adapters.BY_KEY["pubmed"]
        with mock.patch.object(adapters, "fetch", fake_fetch):
            self.assertEqual(a.search("qqq zzz", cfg=config.load()), [])
        self.assertEqual(len(calls), 1)

    def test_ahmia_link_only_dark_query(self):
        a = adapters.BY_KEY["ahmia"]
        items = a.search("dark web onion markets", cfg=config.load())
        self.assertEqual(len(items), 1)
        self.assertTrue(items[0]["link_only"])
        self.assertIn("ahmia.fi/search/?q=", items[0]["url"])
        self.assertIn(".onion", items[0]["excerpt"])
        self.assertIsNone(a.last_fetch)  # koi fetch nahi hua

    def test_ahmia_quiet_for_normal_query(self):
        self.assertEqual(adapters.BY_KEY["ahmia"].search("firmware update",
                                                         cfg=config.load()), [])

    def test_ahmia_off_when_tor_disabled(self):
        cfg = config.load()
        cfg["tor_mode"] = "off"
        self.assertEqual(adapters.BY_KEY["ahmia"].search("dark web", cfg=cfg), [])

    def test_run_skip_sources(self):
        cfg = config.load()
        with mock.patch.object(adapters, "ADAPTERS", [
                adapters.BY_KEY["pubmed"], adapters.BY_KEY["arxiv"]]):
            items, diag = adapters.run("x", keys=["pubmed", "arxiv"], cfg=cfg,
                                       offline=True, skip=["pubmed"])
        self.assertEqual([d["key"] for d in diag], ["arxiv"])


if __name__ == "__main__":
    unittest.main()
