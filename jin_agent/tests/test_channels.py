"""P23 - Telegram channel auto-discovery: registry, liveness, scoring, cap.

Sab network calls mocked hain (project rule: tests kabhi live internet na
chhedein). Offline discovery cycle bhi deterministic hai.
"""

import os
import tempfile
import unittest
from unittest import mock

from jin_agent import channels, config, policy, store


def setUpModule():
    os.environ["JIN_AGENT_DATA"] = tempfile.mkdtemp(prefix="jin-channels-")
    store.init_db()


ALIVE_HTML = """
<meta property="og:title" content="GSM Lab Channel">
<meta property="og:description" content="25.4K subscribers">
<div data-post="gsmlab/120"></div><div data-post="gsmlab/121"></div>
<div data-post="gsmlab/122"></div><div data-post="gsmlab/123"></div>
<div data-post="gsmlab/124"></div><div data-post="gsmlab/125"></div>
<div data-post="gsmlab/126"></div><div data-post="gsmlab/127"></div>
<div data-post="gsmlab/128"></div><div data-post="gsmlab/129"></div>
<div data-post="gsmlab/130"></div><div data-post="gsmlab/131"></div>
<time datetime="2026-11-15T10:00:00+00:00"></time>
<div class="tgme_widget_message_text">Firmware update news. Visit t.me/s/gsm_archive for older posts</div>
"""

DEAD_HTML = "<html><body>If you have Telegram, you can view and join</body></html>"


def _fake_fetch(url, cfg=None, extra_hosts=()):
    if "webnew_ch" in url or "t.me/s/gsmlab" in url or "t.me/s/gsm_archive" in url:
        return ALIVE_HTML
    if "t.me/s/dead_channel" in url:
        return DEAD_HTML
    if "t.me/s/pool_alive" in url:
        return ALIVE_HTML
    if "t.me/s/pool_dead" in url:
        return DEAD_HTML
    if "duckduckgo" in url:
        return ('<a href="//duckduckgo.com/l/?uddg=https%3A%2F%2Ft.me%2Fs%2Fwebnew_ch"'
                '&amp;rut=x">r</a><a href="//d.com/l/?uddg=https%3A%2F%2Ft.me%2Fs%2F'
                'dead_channel">d</a>')
    raise ValueError("blocked")


@mock.patch.object(channels.adapters, "fetch", _fake_fetch)
class TestHandles(unittest.TestCase):
    def test_extract_handles_skips_service_paths(self):
        text = "join https://t.me/s/gsmlab and t.me/joinchat/AbCd t.me/@osint_x"
        self.assertEqual(channels.extract_handles(text), ["gsmlab", "osint_x"])

    def test_clean_handle_accepts_url_and_at(self):
        self.assertEqual(channels.clean_handle("@GSM_Lab"), "GSM_Lab")
        self.assertEqual(channels.clean_handle("https://t.me/s/gsmlab"), "gsmlab")
        self.assertEqual(channels.clean_handle("bad!name"), "")

    def test_web_search_url_allowed(self):
        ok, _ = policy.check_url(
            "https://html.duckduckgo.com/html/?q=site%3At.me%2Fs")
        self.assertTrue(ok)


@mock.patch.object(channels.adapters, "fetch", _fake_fetch)
class TestProbeAndScore(unittest.TestCase):
    def test_probe_alive_parses_stats_and_harvest(self):
        rec = channels.probe("gsmlab", config.load())
        self.assertTrue(rec["alive"])
        self.assertEqual(rec["post_count"], 12)
        self.assertEqual(rec["title"], "GSM Lab Channel")
        self.assertIn("25.4", rec["subscribers"])
        self.assertTrue(rec["last_post_at"].startswith("2026-11-15"))
        self.assertIn("gsm_archive", rec["harvested"])

    def test_probe_dead(self):
        rec = channels.probe("dead_channel", config.load())
        self.assertFalse(rec["alive"])
        self.assertEqual(rec["post_count"], 0)

    def test_score_recency_volume_subs(self):
        cfg = config.load()
        rec = channels.probe("gsmlab", cfg)
        sc = channels.score(rec, cfg)
        self.assertGreaterEqual(sc, 8)  # 4 recency + 2 volume + 2 subs
        dead = channels.score(channels.probe("dead_channel", cfg), cfg)
        self.assertLessEqual(dead, 1)


@mock.patch.object(channels.adapters, "fetch", _fake_fetch)
class TestRegistry(unittest.TestCase):
    def test_check_channel_adds_active_and_dead(self):
        a = channels.check_channel("gsmlab", config.load())
        self.assertEqual(a["status"], "active")
        d = channels.check_channel("dead_channel", config.load())
        self.assertEqual(d["status"], "dead")
        rows = {r["channel"]: r for r in channels.list_channels()}
        self.assertEqual(rows["gsmlab"]["status"], "active")
        self.assertEqual(rows["dead_channel"]["status"], "dead")  # archive-not-delete

    def test_remove_channel_archives_not_deletes(self):
        channels.add_channel("temp_ch", origin="manual")
        channels.remove_channel("temp_ch")
        rows = {r["channel"]: r for r in channels.list_channels()}
        self.assertEqual(rows["temp_ch"]["status"], "archived")

    def test_probe_error_keeps_existing_active_row(self):
        channels.add_channel("alive_ch", origin="manual")
        with mock.patch.object(channels.adapters, "fetch",
                               side_effect=ValueError("blocked")):
            res = channels.check_channel("brand_new", config.load())
            self.assertEqual(res["status"], "dead")
            res2 = channels.check_channel("alive_ch", config.load())
            self.assertEqual(res2["status"], "dead")  # error view returns dead
        rows = {r["channel"]: r for r in channels.list_channels()}
        # existing manual row: status change NAHI hua (network-blip safety)
        self.assertEqual(rows["alive_ch"]["status"], "active")
        self.assertIn("probe error", rows["alive_ch"]["note"])
        # naya row dead mark hua
        self.assertEqual(rows["brand_new"]["status"], "dead")


@mock.patch.object(channels.adapters, "fetch", _fake_fetch)
class TestDiscovery(unittest.TestCase):
    def test_offline_discovery_adds_from_pool(self):
        channels.add_candidates(["t.me/s/pool_alive", "t.me/s/pool_dead"])
        html_map = {"t.me/s/pool_alive": ALIVE_HTML, "t.me/s/pool_dead": DEAD_HTML}

        def fake(url, cfg=None, extra_hosts=()):
            for k, v in html_map.items():
                if k in url:
                    return v
            raise ValueError("blocked")

        with mock.patch.object(channels.adapters, "fetch", fake):
            out = channels.run_discovery(config.load(), offline=True, max_add=5)
        self.assertIn("pool_alive", out["added"])
        self.assertIn("pool_dead", out["dead"])

    def test_web_discovery_via_mock(self):
        out = channels.run_discovery(config.load(), offline=False, max_add=5)
        self.assertIn("webnew_ch", out["added"])

    def test_cap_limits_auto_adds(self):
        cfg = config.load()
        before = channels.counts()["active"]
        cfg["channel_discovery_max_auto"] = before + 1
        channels.add_candidates(["cap_new_ch"])

        def fake(url, cfg=None, extra_hosts=()):
            if "t.me/s/cap_new_ch" in url:
                return ALIVE_HTML
            raise ValueError("blocked")

        with mock.patch.object(channels.adapters, "fetch", fake):
            out = channels.run_discovery(cfg, offline=True, max_add=5)
        self.assertLessEqual(out["counts"]["active"], before + 1)

    def test_adapter_channels_merges_config_and_registry(self):
        channels.check_channel("gsmlab", config.load())
        cfg = config.load()
        cfg["telegram_channels"] = ["@manual_ch"]
        merged = channels.adapter_channels(cfg)
        self.assertIn("manual_ch", merged)
        self.assertIn("gsmlab", merged)


class TestSchedulerJob(unittest.TestCase):
    def test_discovery_job_registered(self):
        import jin_agent.scheduler as sched
        self.assertIn("discovery", sched.JOB_MINUTES)

    def test_run_job_discovery_offline_no_network(self):
        import jin_agent.scheduler as sched

        def no_network(*a, **k):  # koi bhi network call test fail kar de
            raise AssertionError("offline discovery ne network call kiya")
        with mock.patch.object(channels.adapters, "fetch", no_network):
            res = sched.run_job("discovery", {}, config.load(), offline=True)
        self.assertIn("counts", res)


class TestSavedChannelSearch(unittest.TestCase):
    """P28: saved channels ke andar public preview ?q= search (mock only)."""

    def test_search_url_encodes_query(self):
        url = channels.search_url("https://t.me/gsmlab", "firmware update")
        self.assertEqual(url, "https://t.me/s/gsmlab?q=firmware%20update")

    def test_search_url_rejects_bad_handle(self):
        with self.assertRaises(ValueError):
            channels.search_url("", "x")

    def test_search_posts_tags_channel_and_dedupes(self):
        urls = []

        def fake_fetch(url, cfg=None, extra_hosts=()):
            urls.append(url)
            return ALIVE_HTML

        res = channels.search_posts("firmware", ["gsmlab", "gsmlab", "bad handle!"],
                                    config.load(), fetch=fake_fetch)
        self.assertEqual(res["query"], "firmware")
        self.assertEqual(res["channels"], ["gsmlab"])  # bad + duplicate hataye
        self.assertTrue(res["items"])
        self.assertTrue(all(it["channel"] == "gsmlab" for it in res["items"]))
        self.assertTrue(all("?q=firmware" in u for u in urls))
        # same post dobara na aaye
        self.assertEqual(len({it["url"] for it in res["items"]}), len(res["items"]))

    def test_search_posts_one_channel_failure_does_not_break_others(self):
        def fake_fetch(url, cfg=None, extra_hosts=()):
            if "t.me/s/broken" in url:
                raise ValueError("network down")
            return ALIVE_HTML

        res = channels.search_posts("x", ["broken", "gsmlab"], config.load(),
                                    fetch=fake_fetch)
        self.assertEqual(res["ok"], 1)
        self.assertEqual(res["failed"][0]["channel"], "broken")
        self.assertTrue(res["items"])

    def test_search_posts_without_channels(self):
        res = channels.search_posts("x", [], config.load())
        self.assertEqual(res["items"], [])
        self.assertEqual(res["channels"], [])

    def test_search_posts_empty_query_no_network(self):
        def no_network(*a, **k):
            raise AssertionError("empty query par network call hui")
        res = channels.search_posts("   ", ["gsmlab"], config.load(),
                                    fetch=no_network)
        self.assertEqual(res["items"], [])


if __name__ == "__main__":
    unittest.main()
