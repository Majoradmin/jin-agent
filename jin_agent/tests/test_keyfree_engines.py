"""P40 - key-free engine list: policy allowlist, register auto flags, parsers.

Live classification 2026-11-19 (JIN-Agent UA):
- auto=True (12): yahoojp, seznam, bing-news, doaj, europepmc, gitlab,
  huggingface, stackexchange, npm, crates, archive-search, openlibrary.
- auto=False (34): blocked (captcha/429/Cloudflare/JS shell) ya key/email
  maangne wale — jhoota auto nahi likha gaya.

Sab network calls mocked hain (project rule).
"""

import os
import tempfile
import unittest
from unittest import mock

from jin_agent import adapters, config, policy, store


def setUpModule():
    os.environ["JIN_AGENT_DATA"] = tempfile.mkdtemp(prefix="jin-keyfree-")
    store.init_db()


AUTO_ENGINES = ["yahoojp", "seznam", "bing-news", "doaj", "europepmc",
                "gitlab", "huggingface", "stackexchange", "npm", "crates",
                "archive-search", "openlibrary"]
BLOCKED_ENGINES = [
    "mojeek", "marginalia", "searx-be", "gibiru", "ecosia", "qwant",
    "startpage", "swisscows", "presearch", "yandex", "baidu", "sogou",
    "naver", "daum", "yahoo", "rambler", "semanticscholar", "biorxiv",
    "unpaywall", "core", "base-search", "espacenet", "patentscope", "uspto",
    "codeberg", "sourceforge", "pypi", "gutendex", "googlebooks",
    "yahoo-news", "bsky", "mastodon", "tgstat", "telemetr",
]
NEW_HOSTS = [
    "https://www.mojeek.com/search?q=x",
    "https://search.marginalia.nu/search?query=x",
    "https://searx.be/search?q=x",
    "https://gibiru.com/results.html?q=x",
    "https://www.ecosia.org/search?q=x",
    "https://www.qwant.com/?q=x",
    "https://www.startpage.com/sp/search?query=x",
    "https://swisscows.com/en/web?query=x",
    "https://presearch.com/search?q=x",
    "https://yandex.ru/yandsearch?text=x",
    "https://www.baidu.com/s?wd=x",
    "https://www.sogou.com/web?query=x",
    "https://search.naver.com/search.naver?query=x",
    "https://search.daum.net/search?q=x",
    "https://search.yahoo.com/search?p=x",
    "https://search.yahoo.co.jp/search?p=x",
    "https://search.seznam.cz/?q=x",
    "https://nova.rambler.ru/search?query=x",
    "https://api.semanticscholar.org/graph/v1/paper/search?query=x",
    "https://doaj.org/api/search/articles/x",
    "https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=x",
    "https://api.biorxiv.org/details/biorxiv/2026-01-01/2026-01-02",
    "https://api.unpaywall.org/v2/10.1/x?email=a@b.c",
    "https://api.core.ac.uk/v3/search/works?q=x",
    "https://api.base-search.net/cgi-bin/BaseHttpSearchInterface.fcgi",
    "https://worldwide.espacenet.com/searchResults?query=x",
    "https://patentscope.wipo.int/search/en/result.jsf?query=x",
    "https://api.uspto.gov/api/v1/patent/applications/search?q=x",
    "https://gitlab.com/api/v4/projects?search=x",
    "https://codeberg.org/api/v1/repos/search?q=x",
    "https://sourceforge.net/directory/?q=x",
    "https://huggingface.co/api/models?search=x",
    "https://api.stackexchange.com/2.3/search/advanced?q=x",
    "https://pypi.org/pypi",
    "https://registry.npmjs.org/-/v1/search?text=x",
    "https://crates.io/api/v1/crates?q=x",
    "https://archive.org/advancedsearch.php?q=x",
    "https://openlibrary.org/search.json?q=x",
    "https://gutendex.com/books/?search=x",
    "https://www.googleapis.com/books/v1/volumes?q=x",
    "https://www.bing.com/news/search?q=x",
    "https://news.yahoo.com/search?p=x",
    "https://public.api.bsky.app/xrpc/app.bsky.unspecced.searchPostsTrending",
    "https://mastodon.social/api/v2/search?q=x",
    "https://tgstat.com/search?q=x",
    "https://telemetr.io/search?q=x",
]


class TestPolicyAllowlist(unittest.TestCase):
    def test_new_hosts_allowlisted(self):
        for url in NEW_HOSTS:
            ok, reason = policy.check_url(url)
            self.assertTrue(ok, f"{url} -> {reason}")

    def test_onion_still_blocked(self):
        ok, reason = policy.check_url("http://example.onion/x")
        self.assertFalse(ok)
        self.assertIn("onion", reason.lower())


class TestRegisterFlags(unittest.TestCase):
    def test_counts(self):
        rows = policy.register()
        self.assertEqual(len(rows), 130)
        self.assertEqual(sum(1 for r in rows if r["auto"]), 57)

    def test_auto_engines_are_auto(self):
        rows = {r["key"]: r for r in policy.register()}
        for key in AUTO_ENGINES:
            self.assertTrue(rows[key]["auto"], key)

    def test_blocked_engines_not_auto_and_have_reason(self):
        rows = {r["key"]: r for r in policy.register()}
        for key in BLOCKED_ENGINES:
            self.assertFalse(rows[key]["auto"], key)
            self.assertIn("auto=False", rows[key]["notes"], key)

    def test_auto_engines_have_adapters_blocked_do_not(self):
        for key in AUTO_ENGINES:
            self.assertIn(key, adapters.BY_KEY, key)
        for key in BLOCKED_ENGINES:
            self.assertNotIn(key, adapters.BY_KEY, key)

    def test_adapter_count(self):
        self.assertEqual(len(adapters.ADAPTERS), 57)


class TestParsers(unittest.TestCase):
    def test_parse_html_links_excludes_own_site(self):
        html = ('<a href="https://example.com/a">A real result title</a>'
                '<a href="https://search.example.com/nav">Navigation</a>'
                '<a href="https://other.com/b">Another real result</a>')
        items = adapters.parse_html_links(
            html, "Src", "src", "q", {}, exclude_hosts=("search.example.com",),
            min_text=10)
        self.assertEqual([i["url"] for i in items],
                         ["https://example.com/a", "https://other.com/b"])

    def test_parse_json_rows(self):
        data = '{"items": [{"title": "T", "link": "https://x/1", "body": "b"},' \
               ' {"title": "", "link": "https://x/2"}]}'
        items = adapters.parse_json_rows(
            data, "Src", "src", "q", {}, rows_path=("items",),
            title_key="title", url_key="link", excerpt_key="body")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["url"], "https://x/1")
        self.assertEqual(items[0]["excerpt"], "b")

    def test_parse_doaj(self):
        data = '{"results": [{"bibjson": {"title": "T", ' \
               '"link": [{"url": "https://doaj.org/x"}], "abstract": "A"}}]}'
        items = adapters.parse_doaj_rows(data, "DOAJ", "doaj", "q", {})
        self.assertEqual(items[0]["title"], "T")
        self.assertEqual(items[0]["url"], "https://doaj.org/x")

    def test_parse_europepmc(self):
        data = '{"resultList": {"result": [{"title": "T", ' \
               '"doi": "10.1/x", "firstPublicationDate": "2026-01-01"}]}}'
        items = adapters.parse_europepmc_rows(data, "EPMC", "europepmc", "q", {})
        self.assertEqual(items[0]["url"], "https://doi.org/10.1/x")

    def test_parse_gitlab(self):
        data = '[{"path_with_namespace": "g/p", ' \
               '"web_url": "https://gitlab.com/g/p", "description": "d"}]'
        items = adapters.parse_gitlab_rows(data, "GitLab", "gitlab", "q", {})
        self.assertEqual(items[0]["url"], "https://gitlab.com/g/p")

    def test_parse_huggingface(self):
        data = '[{"id": "org/model", "tags": ["a", "b"]}]'
        items = adapters.parse_huggingface_rows(data, "HF", "huggingface",
                                                "q", {})
        self.assertEqual(items[0]["url"], "https://huggingface.co/org/model")

    def test_parse_npm(self):
        data = '{"objects": [{"package": {"name": "pkg", "description": "d", ' \
               '"links": {"repository": "https://github.com/x/y"}}}]}'
        items = adapters.parse_npm_rows(data, "npm", "npm", "q", {})
        self.assertEqual(items[0]["url"], "https://github.com/x/y")

    def test_parse_crates(self):
        data = '{"crates": [{"id": "c1", "name": "c1", "description": "d"}]}'
        items = adapters.parse_crates_rows(data, "crates", "crates", "q", {})
        self.assertEqual(items[0]["url"], "https://crates.io/crates/c1")

    def test_parse_archive(self):
        data = '{"response": {"docs": [{"identifier": "id1", "title": "T"}]}}'
        items = adapters.parse_archive_rows(data, "IA", "archive-search",
                                            "q", {})
        self.assertEqual(items[0]["url"], "https://archive.org/details/id1")

    def test_parse_openlibrary(self):
        data = '{"docs": [{"title": "T", "key": "/works/OL1W", ' \
               '"author_name": ["A"]}]}'
        items = adapters.parse_openlibrary_rows(data, "OL", "openlibrary",
                                                "q", {})
        self.assertEqual(items[0]["url"], "https://openlibrary.org/works/OL1W")


class TestSimpleAdapter(unittest.TestCase):
    def test_build_replaces_query_and_limit(self):
        a = adapters.SimpleEngineAdapter(
            "x", "X", "https://example.com/search?q={q}&n={n}", "json",
            {"rows_path": ("items",), "title_key": "title", "url_key": "url"})
        url = a.build("android security", 7, 25, {})
        self.assertIn("q=android%20security", url)
        self.assertIn("n=25", url)

    def test_search_uses_parser(self):
        a = adapters.SimpleEngineAdapter(
            "x", "X", "https://example.com/search?q={q}", "json",
            {"rows_path": ("items",), "title_key": "title", "url_key": "url"})
        body = '{"items": [{"title": "T", "url": "https://example.com/t"}]}'
        with mock.patch.object(adapters, "fetch", lambda *args, **kw: body):
            items = a.search("q", cfg=config.load(), offline=False)
        self.assertEqual(items[0]["url"], "https://example.com/t")
        self.assertEqual(items[0]["source_key"], "x")


if __name__ == "__main__":
    unittest.main()
