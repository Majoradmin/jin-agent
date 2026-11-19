"""Phase 4 (top-class): markdown HTML, BLUF, honest absence, confirm-gated
addchannel, progress edit, /new, rate limit + budget, commands, health,
parser selftest, memory audit."""

import json
import os
import tempfile
import time
import unittest
from unittest import mock

from jin_agent import (channels, config, orchestrator, store,
                       telegram_bot as tb)  # noqa: E402


def setUpModule():
    os.environ["JIN_AGENT_DATA"] = tempfile.mkdtemp(prefix="jin-p4-")
    store.init_db()
    channels.ensure_table()
    tb.memory_mod.ensure_table()


class DocAPI:
    def __init__(self):
        self.sent = []
        self.docs = []

    def send(self, chat_id, text, buttons=None):
        self.sent.append((int(chat_id), str(text), buttons))
        return {"ok": True}

    def send_document(self, chat_id, file_path, caption="", timeout=120):
        self.docs.append((int(chat_id), str(file_path), str(caption)))
        return {"ok": True}

    def get_updates(self, offset, timeout=None):
        return []

    def answer_callback(self, callback_id, text=""):
        return {"ok": True}


class EditAPI(DocAPI):
    def __init__(self):
        super().__init__()
        self.edits = []

    def send(self, chat_id, text, buttons=None):
        self.sent.append((int(chat_id), str(text), buttons))
        return {"ok": True, "result": {"message_id": len(self.sent)}}

    def edit(self, chat_id, message_id, text, parse_mode=None):
        self.edits.append((int(chat_id), int(message_id), str(text)))
        return {"ok": True}


class TestMarkdownHtml(unittest.TestCase):
    def test_convert_and_escape(self):
        out = tb.markdown_to_html(
            "**bold** [x](https://e.com/?a=1&b=2) `<b>`\n- item")
        self.assertIn("<b>bold</b>", out)
        self.assertIn('<a href="https://e.com/?a=1&amp;b=2">x</a>', out)
        self.assertIn("<code>&lt;b&gt;</code>", out)
        self.assertIn("• item", out)

    def test_send_parse_mode_payload(self):
        seen = {}

        class Resp:
            def read(self):
                return b'{"ok": true, "result": {"message_id": 1}}'

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        class FakeOpener:
            def open(self, req, timeout=None):
                seen["data"] = json.loads(req.data.decode())
                return Resp()

        cfg = {"proxy_type": "", "proxy_host": "", "proxy_port": 0}
        with mock.patch.object(tb.urllib.request, "build_opener",
                               lambda *a, **k: FakeOpener()):
            api = tb._api("TOK", cfg)
            api.send(1, "x", parse_mode="HTML")
        self.assertEqual(seen["data"]["parse_mode"], "HTML")

    def test_send_chunks_forwards_parse_mode(self):
        api = DocAPI()
        tb.send_chunks(api, 1, "hello", delay=0, parse_mode="HTML")
        self.assertEqual(len(api.sent), 1)


class TestBlufAndAbsence(unittest.TestCase):
    def _file(self, name):
        path = os.path.join(config.reports_dir(), name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("# Report")
        return path

    def test_bluf_under_1000_with_findings(self):
        out = {"items": [{"title": f"Story {i}"} for i in range(8)]}
        text = tb._bluf_text("q", out, 0.9, "high", ["s"], ["c"], "ok")
        self.assertLessEqual(len(text), 1000)
        self.assertIn("Story 0", text)
        self.assertIn("Report tayyar hai", text)

    def _patch_full(self, kind, confidence=0.9, path=None):
        def fake_full(query, cfg, save=True, live=True, skip_sources=None,
                      skip_channels=None):
            return {"ok": True, "markdown": "# Report", "sources": [], "channels": [],
                    "failed_channels": [], "report_path": path or "",
                    "confidence": confidence, "confidence_label": "high",
                    "absence_kind": kind, "items": []}
        return mock.patch.object(tb, "research_full", fake_full)

    def test_no_results_message_no_document(self):
        path = self._file("absent-none.md")
        api = DocAPI()
        with self._patch_full("no_results", path=path):
            tb._send_research(42, "q", {"telegram_chat_id": "42", "llm": {}}, api)
        self.assertEqual(api.docs, [])
        self.assertTrue(any("Koi result nahi mila" in t for _, t, _ in api.sent))

    def test_fetch_failed_message_no_document(self):
        path = self._file("absent-fail.md")
        api = DocAPI()
        with self._patch_full("fetch_failed", path=path):
            tb._send_research(42, "q", {"telegram_chat_id": "42", "llm": {}}, api)
        self.assertEqual(api.docs, [])
        self.assertTrue(any("Fetch fail hua" in t for _, t, _ in api.sent))

    def test_high_confidence_bluf_plus_document(self):
        path = self._file("bluf.md")
        api = EditAPI()

        def fake_full(query, cfg, save=True, live=True, skip_sources=None,
                      skip_channels=None):
            return {"ok": True, "markdown": "# Report",
                    "sources": ["s"], "channels": ["c"], "failed_channels": [],
                    "report_path": path, "confidence": 0.9,
                    "confidence_label": "high", "absence_kind": "ok",
                    "items": [{"title": "Key finding"}]}

        with mock.patch.object(tb, "research_full", fake_full):
            tb._send_research(42, "q", {"telegram_chat_id": "42", "llm": {}}, api)
        self.assertEqual(len(api.docs), 1)
        self.assertTrue(any("Key finding" in t for _, t, _ in api.sent))
        self.assertTrue(api.edits)   # progress edit-in-place


class TestConfirmAddChannel(unittest.TestCase):
    def test_pending_then_confirm(self):
        api = DocAPI()
        res = tb.dispatch(42, "/addchannel https://t.me/confch",
                          {"telegram_chat_id": "42"}, api=api)
        self.assertEqual(res["action"], "addchannel_pending")
        self.assertFalse(any(r["channel"] == "confch"
                             for r in channels.list_channels()))
        with mock.patch.object(tb.channels_mod, "check_channel",
                               lambda h, cfg=None: {"alive": True, "title": "T",
                                                    "subscribers": "1", "post_count": 1}):
            res2 = tb.handle_callback(42, "add:ok:confch",
                                      {"telegram_chat_id": "42"}, api=api)
        self.assertTrue(res2["ok"])
        self.assertTrue(any(r["channel"] == "confch" for r in channels.list_channels()))

    def test_cancel_does_not_add(self):
        api = DocAPI()
        tb.dispatch(42, "/addchannel https://t.me/cancelch",
                    {"telegram_chat_id": "42"}, api=api)
        res = tb.handle_callback(42, "add:no", {"telegram_chat_id": "42"}, api=api)
        self.assertTrue(res["ok"])
        self.assertFalse(any(r["channel"] == "cancelch"
                             for r in channels.list_channels()))


class TestNewAndCommands(unittest.TestCase):
    def test_new_resets_context(self):
        row = tb.memory_mod.begin(42, "context reset")
        api = DocAPI()
        res = tb.dispatch(42, "/new", {"telegram_chat_id": "42"}, api=api)
        self.assertTrue(res["ok"])
        self.assertEqual(tb.memory_mod.get(row["id"])["status"], "done")

    def test_commands_ok(self):
        api = DocAPI()
        cfg = {"telegram_chat_id": "42"}
        for text in ("/schedule", "/channelhealth", "/reports", "/alerts",
                     "/memoryaudit", "/selftest"):
            res = tb.dispatch(42, text, cfg, api=api)
            self.assertTrue(res["ok"], text)

    def test_digest_command(self):
        api = DocAPI()
        res = tb.dispatch(42, "/digest", {"telegram_chat_id": "42"}, api=api)
        self.assertTrue(res["ok"])
        self.assertEqual(res["action"], "digest")

    def test_channel_health_flags_quiet(self):
        now = int(time.time())
        with store.session() as con:
            con.execute("INSERT INTO tg_channels(channel,status,last_checked,"
                        "last_post_at) VALUES('quiet_ch','active',?,'2020-01-01 00:00')",
                        (now,))
        text = tb.format_channel_health()
        self.assertIn("khamosh", text)
        self.assertIn("quiet_ch", text)

    def test_parser_selftest_passes(self):
        res = channels.parser_selftest()
        self.assertTrue(res["ok"], res)


class TestRateLimitAndBudget(unittest.TestCase):
    def tearDown(self):
        tb._GROUP_HITS.clear()

    def test_group_rate_limit(self):
        self.assertEqual(tb.GROUP_RATE_LIMIT, 20)
        for _ in range(20):
            self.assertTrue(tb._group_allowed(1))
        self.assertFalse(tb._group_allowed(1))
        self.assertTrue(tb._group_allowed(2))   # doosri chat alag

    def test_budget_meter(self):
        with mock.patch.dict(os.environ, {"JIN_AGENT_TOKEN_BUDGET": "10"}):
            out = orchestrator.run("MediaTek", live=False, save=False)
        self.assertEqual(out["metrics"]["token_budget"], 10)
        self.assertIn("budget_exceeded", out["metrics"])


class TestMemoryAudit(unittest.TestCase):
    def test_audit_duplicates_and_stale(self):
        row = tb.memory_mod.begin(7, "audit dup")
        # doosra active row banao bilkul waisi hi query key se
        tb.memory_mod.begin(7, "audit dup")   # wahi row (active) — naya nahi
        with store.session() as con:
            con.execute("INSERT INTO search_memory(chat_id,query_key,query,round_no,"
                        "status,created_at,updated_at) VALUES(7,'audit dup','dup2',1,"
                        "'active',1,1)")
            con.execute("INSERT INTO search_memory(chat_id,query_key,query,round_no,"
                        "status,created_at,updated_at) VALUES(7,'stale q','stale',1,"
                        "'active',1,1)")
        out = tb.memory_mod.audit()
        self.assertGreaterEqual(len(out["duplicates"]), 1)
        self.assertGreaterEqual(len(out["stale"]), 1)


if __name__ == "__main__":
    unittest.main()
