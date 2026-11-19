"""P41 - extra engines: news RSS, academic, patents, archive/data, web, social.

Live classification 2026-11-19 (JIN-Agent UA):
- auto=True (18): 10 news RSS + datacite/openaire/hal + usgs/weather +
  wiby/rightdao + lemmy.
- auto=False (20): blocked (403/404/503/504/timeout/Cloudflare/JS) ya
  key/appname maangne wale — jhoota auto nahi likha gaya.

Network calls mocked hain (project rule).
"""

import os
import tempfile
import unittest

from jin_agent import adapters, policy, store


def setUpModule():
    os.environ["JIN_AGENT_DATA"] = tempfile.mkdtemp(prefix="jin-p41-")
    store.init_db()


AUTO_41 = ["bbc-news", "aljazeera", "arstechnica", "wired", "techcrunch",
           "theverge", "zdnet", "cnet", "nytimes", "npr", "datacite",
           "openaire", "hal", "usgs", "weather", "wiby", "rightdao", "lemmy"]
BLOCKED_41 = ["wapo", "reuters", "groundnews", "orcid", "scilit", "fatcat",
              "citeseerx", "repec", "econpapers", "philpapers", "pubpsych",
              "ipaustralia", "jplatpat", "kipris", "commoncrawl", "loc",
              "worldcat", "reliefweb", "4cdn", "8kun"]
NEW_HOSTS = [
    "https://feeds.bbci.co.uk/news/rss.xml",
    "https://www.aljazeera.com/xml/rss/all.xml",
    "https://feeds.arstechnica.com/arstechnica/index",
    "https://www.wired.com/feed",
    "https://techcrunch.com/feed/",
    "https://www.theverge.com/rss/index.xml",
    "https://www.zdnet.com/news/rss.xml",
    "https://www.cnet.com/rss/news/",
    "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
    "https://feeds.washingtonpost.com/rss/technology",
    "https://feeds.npr.org/1001/rss.xml",
    "https://www.reutersagency.com/feed/",
    "https://ground.news/rss",
    "https://api.datacite.org/dois?query=x",
    "https://pub.orcid.org/v3.0/search?q=x",
    "https://api.scilit.net/api/publications?q=x",
    "https://api.fatcat.wiki/v0/release/lookup?search=x",
    "https://api.openaire.eu/search/publications?title=x&format=json",
    "https://api.archives-ouvertes.fr/search/?q=x&wt=json",
    "https://citeseerx.ist.psu.edu/search?q=x",
    "https://ideas.repec.org/cgi-bin/htsearch?q=x",
    "https://econpapers.repec.org/scripts/search.pf?ft=x",
    "https://philpapers.org/advancedsearch?q=x",
    "https://pubpsych.zpid.de/api/v1/search?query=x",
    "https://search.ipaustralia.gov.au/patents/search?q=x",
    "https://j-platpat.inpit.go.jp/",
    "https://kris.kipris.or.kr/",
    "https://index.commoncrawl.org/CC-MAIN-2026-30-index?url=x&output=json",
    "https://www.loc.gov/search/?q=x&fo=json",
    "https://search.worldcat.org/title/x",
    "https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&limit=3",
    "https://api.weather.gov/alerts?limit=3",
    "https://api.reliefweb.int/v2/reports?appname=x&limit=3",
    "https://wiby.me/?q=x",
    "https://rightdao.com/search?q=x",
    "https://lemmy.ml/api/v3/search?q=x&type_=Communities&limit=3",
    "https://a.4cdn.org/",
    "https://8kun.top/",
]


class TestPolicy(unittest.TestCase):
    def test_new_hosts_allowlisted(self):
        for url in NEW_HOSTS:
            ok, reason = policy.check_url(url)
            self.assertTrue(ok, f"{url} -> {reason}")

    def test_counts(self):
        rows = policy.register()
        self.assertEqual(len(rows), 130)
        self.assertEqual(sum(1 for r in rows if r["auto"]), 57)

    def test_auto_and_blocked_flags(self):
        rows = {r["key"]: r for r in policy.register()}
        for key in AUTO_41:
            self.assertTrue(rows[key]["auto"], key)
        for key in BLOCKED_41:
            self.assertFalse(rows[key]["auto"], key)
            self.assertIn("auto=False", rows[key]["notes"], key)

    def test_adapter_presence(self):
        for key in AUTO_41:
            self.assertIn(key, adapters.BY_KEY, key)
        for key in BLOCKED_41:
            self.assertNotIn(key, adapters.BY_KEY, key)

    def test_adapter_count(self):
        self.assertEqual(len(adapters.ADAPTERS), 57)


class TestParsers(unittest.TestCase):
    def test_datacite(self):
        data = '{"data": [{"attributes": {"titles": [{"title": "T"}], ' \
               '"doi": "10.1/x", "url": "https://x", ' \
               '"descriptions": [{"description": "D"}]}}]}'
        items = adapters.parse_datacite_rows(data, "DC", "datacite", "q", {})
        self.assertEqual(items[0]["url"], "https://x")
        self.assertEqual(items[0]["excerpt"], "D")

    def test_openaire(self):
        data = '{"response": {"results": {"result": [{"metadata": ' \
               '{"oaf:entity": {"oaf:result": {"title": [{"$": "T"}], ' \
               '"pid": {"@classid": "doi", "$": "10.1/x"}, ' \
               '"dateofacceptance": {"$": "2026-01-01"}, ' \
               '"description": {"$": "D"}}}}}]}}}'
        items = adapters.parse_openaire_rows(data, "OA", "openaire", "q", {})
        self.assertEqual(items[0]["url"], "https://doi.org/10.1/x")
        self.assertTrue(items[0]["published"].startswith("2026-01-01"))

    def test_hal(self):
        data = '{"response": {"docs": [{"title_s": ["T"], ' \
               '"uri_s": "https://hal/x", "producedDate_tdate": "2026-01-01"}]}}'
        items = adapters.parse_hal_rows(data, "HAL", "hal", "q", {})
        self.assertEqual(items[0]["url"], "https://hal/x")

    def test_usgs(self):
        data = '{"features": [{"properties": {"title": "T", ' \
               '"url": "https://usgs/x", "place": "P"}}]}'
        items = adapters.parse_usgs_rows(data, "USGS", "usgs", "q", {})
        self.assertEqual(items[0]["url"], "https://usgs/x")
        self.assertEqual(items[0]["excerpt"], "P")

    def test_weather(self):
        data = '{"features": [{"properties": {"event": "Storm", ' \
               '"areaDesc": "Karachi", "@id": "https://weather/x"}}]}'
        items = adapters.parse_weather_rows(data, "NOAA", "weather", "q", {})
        self.assertEqual(items[0]["title"], "Storm — Karachi")
        self.assertEqual(items[0]["url"], "https://weather/x")

    def test_wiby_and_rightdao(self):
        html = ('<a href="https://example.com/a">A real result title</a>'
                '<a href="https://wiby.me/nav">Wiby nav</a>')
        items = adapters.parse_wiby_rows(html, "Wiby", "wiby", "q", {})
        self.assertEqual([i["url"] for i in items], ["https://example.com/a"])
        items2 = adapters.parse_rightdao_rows(html, "RD", "rightdao", "q", {})
        self.assertEqual([i["url"] for i in items2], ["https://example.com/a"])

    def test_lemmy(self):
        data = '{"communities": [{"community": {"name": "c1", "title": "T", ' \
               '"description": "D"}}]}'
        items = adapters.parse_lemmy_rows(data, "Lemmy", "lemmy", "q", {})
        self.assertEqual(items[0]["url"], "https://lemmy.ml/c/c1")


if __name__ == "__main__":
    unittest.main()
