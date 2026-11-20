"""Topic-based source routing (P2).

Masla: search_public hamesha 12 fixed keys use karta tha — "free api key"
par bhi GSMArena (mobile) query hota tha magar koi relevant item nahi.
Ab query ke topic ke mutabiq keys choose hote hain.
"""

import os
import tempfile
import unittest
from unittest import mock

from jin_agent import config, planner  # noqa: E402


def setUpModule():
    os.environ["JIN_AGENT_DATA"] = tempfile.mkdtemp(prefix="jin-topic-")


class TestTopicKeys(unittest.TestCase):
    def test_mobile_query_gets_mobile_sources(self):
        keys = planner.topic_keys("Samsung Galaxy firmware update")
        for key in ("gsmarena", "xda", "sammobile"):
            self.assertIn(key, keys)

    def test_security_query_gets_nvd(self):
        self.assertIn("nvd", planner.topic_keys("CVE vulnerability patch"))

    def test_code_query_gets_github(self):
        keys = planner.topic_keys("github repo source code")
        self.assertIn("github-search", keys)
        self.assertIn("github", keys)

    def test_free_api_key_is_code_topic_not_mobile(self):
        keys = planner.topic_keys("free api key")
        self.assertNotIn("gsmarena", keys)
        self.assertIn("github-search", keys)

    def test_generic_query_keeps_default_keys(self):
        self.assertEqual(planner.topic_keys("kal ka mausam"),
                         planner.DEFAULT_PUBLIC_KEYS)

    def test_multi_topic_merges_keys(self):
        keys = planner.topic_keys("iOS security patch")
        self.assertIn("gsmarena", keys)  # mobile topic
        self.assertIn("nvd", keys)       # security topic


class TestTopicToolHook(unittest.TestCase):
    def test_security_query_adds_search_security(self):
        calls = planner._deterministic_calls("CVE vulnerability", config.load())
        self.assertIn("search_security", [c["tool"] for c in calls])

    def test_code_query_adds_search_code(self):
        calls = planner._deterministic_calls("github repo", config.load())
        self.assertIn("search_code", [c["tool"] for c in calls])


class TestDispatchUsesTopicKeys(unittest.TestCase):
    def test_search_public_dispatch_uses_topic_keys(self):
        cfg = config.load()
        with mock.patch.object(planner.adapters, "run",
                               return_value=([], [])) as run:
            planner.dispatch(
                {"tool": "search_public",
                 "args": {"query": "Samsung Galaxy firmware", "days": 7,
                          "limit": 25}},
                {"cfg": cfg, "offline": True})
        keys = run.call_args.kwargs.get("keys") or run.call_args[1].get("keys")
        for key in ("gsmarena", "xda", "sammobile"):
            self.assertIn(key, keys)
        self.assertNotIn("gdelt", keys)


if __name__ == "__main__":
    unittest.main()
