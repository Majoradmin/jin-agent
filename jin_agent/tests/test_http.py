"""P20 - loopback Agent Console HTTP smoke tests (offline only)."""

import json
import os
import tempfile
import threading
import urllib.error
import urllib.request
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]

from jin_agent import server, store  # noqa: E402

HTTPD = None
THREAD = None
PORT = 0


def setUpModule():
    global HTTPD, THREAD, PORT
    os.environ["JIN_AGENT_DATA"] = tempfile.mkdtemp(prefix="jin-http-")
    HTTPD = server.make_server(0)
    PORT = HTTPD.server_address[1]
    THREAD = threading.Thread(target=HTTPD.serve_forever,
                              kwargs={"poll_interval": 0.2}, daemon=True)
    THREAD.start()


def tearDownModule():
    HTTPD.shutdown()
    HTTPD.server_close()
    THREAD.join(5)


def req(path, method="GET", body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    r = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", data=data,
                               method=method, headers=headers)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return resp.status, resp.read(), dict(resp.headers)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), dict(exc.headers)


def get_json(path, method="GET", body=None):
    code, raw, headers = req(path, method, body)
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except ValueError:
        parsed = {}
    return code, parsed, headers


class TestConsole(unittest.TestCase):
    def test_01_static_shell(self):
        code, raw, headers = req("/")
        self.assertEqual(code, 200)
        self.assertIn(b"JIN Agent", raw)
        self.assertIn("Content-Security-Policy", headers)

    def test_02_static_assets(self):
        for path in ("/app.js", "/style.css", "/favicon.svg"):
            self.assertEqual(req(path)[0], 200, path)

    def test_03_status(self):
        code, body, _ = get_json("/api/status")
        self.assertEqual(code, 200)
        self.assertEqual(body["version"], "2.9.0")
        self.assertTrue(body["fts5"])
        self.assertIn("changes", body)

    def test_04_settings_masked(self):
        code, body, _ = get_json("/api/settings")
        self.assertEqual(code, 200)
        self.assertNotIn("sk-", json.dumps(body))
        self.assertIn("assumptions", body["settings"])

    def test_05_sources(self):
        code, body, _ = get_json("/api/sources")
        self.assertEqual(code, 200)
        self.assertGreaterEqual(len(body["sources"]), 20)

    def test_06_run_offline(self):
        code, body, _ = get_json("/api/run", "POST",
                                 {"query": "MediaTek preloader scatter DA", "live": False})
        self.assertEqual(code, 200)
        self.assertTrue(body["items"])
        self.assertEqual(body["audit"]["fabricated"], 0)
        self.assertIn("## Facts by Category", body["report"]["markdown"])
        self.assertTrue(body["saved"]["md"])

    def test_07_report_view(self):
        _, run, _ = get_json("/api/run", "POST", {"query": "Qualcomm EDL 9008", "live": False})
        rid = run["saved"]["id"]
        code, raw, _ = req("/api/report?id=" + str(rid))
        self.assertEqual(code, 200)
        self.assertIn(b"Research Brief", raw)

    def test_08_report_not_found(self):
        self.assertEqual(get_json("/api/report?id=999999")[0], 404)

    def test_09_archive(self):
        code, body, _ = get_json("/api/archive?q=MediaTek")
        self.assertEqual(code, 200)
        self.assertIsInstance(body["items"], list)

    def test_10_watchlist(self):
        code, body, _ = get_json("/api/watchlist", "POST", {"term": "SM-G991B"})
        self.assertEqual(code, 200)
        self.assertEqual(body["item"]["term"], "SM-G991B")

    def test_11_scheduler_tick(self):
        code, body, _ = get_json("/api/scheduler", "POST", {"action": "tick", "offline": True})
        self.assertEqual(code, 200)
        self.assertEqual(body["result"]["errors"], [])

    def test_12_classify_blocked(self):
        code, body, _ = get_json("/api/classify", "POST", {"text": "FRP bypass kar do"})
        self.assertEqual(code, 200)
        self.assertEqual(body["gate"]["verdict"], "blocked")

    def test_13_tools_listed(self):
        code, body, _ = get_json("/api/tools")
        self.assertEqual(code, 200)
        self.assertIn("search_public", body["tools"])
        self.assertNotIn("run_shell", body["tools"])

    def test_14_bad_provider_rejected(self):
        code, body, _ = get_json("/api/settings", "POST", {"llm": {"provider": "evil"}})
        self.assertEqual(code, 400)

    def test_15_bad_tor_mode_rejected(self):
        code, _, _ = get_json("/api/settings", "POST", {"tor_mode": "auto-fetch"})
        self.assertEqual(code, 400)

    def test_16_llm_probe_graceful(self):
        code, body, _ = get_json("/api/llm/test", "POST", {})
        self.assertEqual(code, 200)
        self.assertIn("ok", body["result"])

    def test_17_unknown_route(self):
        self.assertEqual(get_json("/api/nope")[0], 404)

    def test_18_csp_on_json(self):
        _, _, headers = get_json("/api/status")
        self.assertIn("Content-Security-Policy", headers)
        self.assertIn("X-Content-Type-Options", headers)

    def test_19_loopback_only(self):
        src = (BASE / "jin_agent" / "server.py").read_text(encoding="utf-8")
        self.assertIn('("127.0.0.1", int(port))', src)
        self.assertNotIn('("0.0.0.0"', src)

    def test_20_health(self):
        code, body, headers = get_json("/api/health")
        self.assertEqual(code, 200)
        self.assertTrue(body["ok"])
        self.assertEqual(body["version"], "2.9.0")
        self.assertTrue(body["db"]["ok"])
        self.assertTrue(body["data_writable"])
        self.assertIsInstance(body["llm_enabled"], bool)
        self.assertGreaterEqual(body["uptime_seconds"], 0)
        self.assertNotIn("sk-", json.dumps(body))
        self.assertIn("Content-Security-Policy", headers)

    def test_21_metrics(self):
        code, body, _ = get_json("/api/metrics")
        self.assertEqual(code, 200)
        snap = body["metrics"]
        for key in ("counters", "gauges", "latency"):
            self.assertIn(key, snap)
        self.assertIn("queries_total", snap["counters"])
        self.assertGreaterEqual(snap["counters"]["queries_total"], 1)
        self.assertIn("run", snap["latency"])
        self.assertNotIn("sk-", json.dumps(body))
        self.assertNotIn("telegram_bot_token", json.dumps(body))


if __name__ == "__main__":
    unittest.main()
