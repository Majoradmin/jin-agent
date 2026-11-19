"""Phase 1: negative channel memory, channel-health status, dead cleanup.

Competitor patterns (web research):
  * dead/silent channel ka record TTL ke baad clean karo (14/30/90 din thresholds)
  * failed channel ko negative memory me yaad rakho taake agla round dobara
    try na kare (silent-failure detection)
"""

import json
import os
import tempfile
import time
import unittest
from unittest import mock

from jin_agent import channels, searchmemory as memory, store, telegram_bot as tb  # noqa: E402


def setUpModule():
    os.environ["JIN_AGENT_DATA"] = tempfile.mkdtemp(prefix="jin-p1-")
    store.init_db()
    memory.ensure_table()
    channels.ensure_table()


class FakeAPI:
    def __init__(self):
        self.sent = []

    def send(self, chat_id, text, buttons=None):
        self.sent.append((int(chat_id), str(text), buttons))
        return {"ok": True}

    def get_updates(self, offset, timeout=None):
        return []

    def answer_callback(self, callback_id, text=""):
        return {"ok": True}


class TestNegativeChannelMemory(unittest.TestCase):
    def test_remember_failed_and_read(self):
        row = memory.begin(1, "negative memory")
        memory.remember_failed(row["id"], ["deadA", "deadB"])
        self.assertEqual(memory.failed_channels(row["id"]), ["deadA", "deadB"])

    def test_ttl_expiry(self):
        row = memory.begin(1, "ttl")
        memory.remember_failed(row["id"], ["oldch"])
        old = time.time() - 10 * 86400
        with store.session() as con:
            con.execute("UPDATE search_memory SET failed_channels=? WHERE id=?",
                        (json.dumps([{"channel": "oldch", "at": old}]), row["id"]))
        with mock.patch.dict(os.environ, {"JIN_AGENT_CHANNEL_NEGATIVE_TTL_DAYS": "7"}):
            self.assertEqual(memory.failed_channels(row["id"]), [])
            memory.remember_failed(row["id"], ["newch"])
        self.assertEqual(memory.failed_channels(row["id"]), ["newch"])

    def test_ttl_env_default(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("JIN_AGENT_CHANNEL_NEGATIVE_TTL_DAYS", None)
            self.assertEqual(memory.channel_negative_ttl_days(), 7)
        with mock.patch.dict(os.environ, {"JIN_AGENT_CHANNEL_NEGATIVE_TTL_DAYS": "2"}):
            self.assertEqual(memory.channel_negative_ttl_days(), 2)

    def test_old_db_migration_adds_column(self):
        #ensure_table dobara chalane par column mojood ho (purana DB bhi).
        memory.ensure_table()
        with store.session() as con:
            cols = {r[1] for r in con.execute("PRAGMA table_info(search_memory)")}
        self.assertIn("failed_channels", cols)

    def test_send_research_skips_failed_channels(self):
        row = memory.begin(42, "skip failed")
        memory.remember(row["id"], ["src1"], ["usedch"])
        memory.remember_failed(row["id"], ["badch"])
        seen = {}

        def fake_research(q, cfg):
            return {"ok": True, "markdown": "# r", "sources": [], "channels": [],
                    "failed_channels": []}

        # research_full ko patch kar ke skip_channels capture karo.
        def fake_full(query, cfg, save=True, live=True, skip_sources=None,
                      skip_channels=None):
            seen["skip"] = list(skip_channels or [])
            return {"ok": True, "markdown": "# r", "sources": [], "channels": [],
                    "failed_channels": []}

        api = FakeAPI()
        with mock.patch.object(tb, "research_full", fake_full):
            tb._send_research(42, "q", {"telegram_chat_id": "42", "llm": {}},
                              api, row_id=row["id"])
        self.assertIn("badch", seen["skip"])
        self.assertIn("usedch", seen["skip"])

    def test_failed_channels_recorded_after_research(self):
        row = memory.begin(42, "record failed")
        api = FakeAPI()

        def fake_full(query, cfg, save=True, live=True, skip_sources=None,
                      skip_channels=None):
            return {"ok": True, "markdown": "# r", "sources": [], "channels": [],
                    "failed_channels": ["badch"], "report_path": "",
                    "confidence": 0.0, "confidence_label": "n/a"}

        with mock.patch.object(tb, "research_full", fake_full):
            tb._send_research(42, "q", {"telegram_chat_id": "42", "llm": {}},
                              api, row_id=row["id"])
        self.assertIn("badch", memory.failed_channels(row["id"]))


class TestChannelHealthAndCleanup(unittest.TestCase):
    def test_format_channels_empty_state_dead(self):
        msg = tb.format_channels([], counts={"active": 0, "dead": 2,
                                             "archived": 1, "total": 3})
        self.assertIn("dead", msg)
        self.assertIn("--all", msg)
        # counts na ho to purana payam barqarar
        self.assertIn("Koi channel save nahi", tb.format_channels([]))

    def test_status_reports_channel_health(self):
        channels.add_channel("health_active", origin="manual")
        tb.status()  # smoke
        with store.session() as con:
            con.execute("INSERT INTO tg_channels(channel,status,last_checked) "
                        "VALUES('health_dead','dead',?)", (int(time.time()),))
        st = tb.status()
        self.assertIn("channels_active", st)
        self.assertIn("channels_dead", st)
        self.assertGreaterEqual(st["channels_dead"], 1)

    def test_cleanup_dead_respects_ttl_and_keeps_active(self):
        now = int(time.time())
        with store.session() as con:
            con.execute("INSERT INTO tg_channels(channel,status,last_checked) "
                        "VALUES('olddead','dead',1)")
            con.execute("INSERT INTO tg_channels(channel,status,last_checked) "
                        "VALUES('newdead','dead',?)", (now,))
        channels.add_channel("keep_active", origin="manual")
        removed = channels.cleanup_dead()
        self.assertGreaterEqual(removed, 1)
        names = {r["channel"] for r in channels.list_channels()}
        self.assertNotIn("olddead", names)
        self.assertIn("newdead", names)
        self.assertIn("keep_active", names)

    def test_cleanup_dead_env_ttl(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("JIN_AGENT_CHANNEL_DEAD_TTL_DAYS", None)
            self.assertEqual(channels.dead_ttl_days(), 30)
        with mock.patch.dict(os.environ, {"JIN_AGENT_CHANNEL_DEAD_TTL_DAYS": "14"}):
            self.assertEqual(channels.dead_ttl_days(), 14)

    def test_dispatch_channels_all(self):
        channels.add_channel("all_active", origin="manual")
        with store.session() as con:
            con.execute("INSERT INTO tg_channels(channel,status,last_checked) "
                        "VALUES('all_dead','dead',?)", (int(time.time()),))
        api = FakeAPI()
        res = tb.dispatch(42, "/channels --all", {"telegram_chat_id": "42"}, api=api)
        self.assertTrue(res["ok"])
        self.assertEqual(res["action"], "channels_all")
        joined = "\n".join(t for _, t, _ in api.sent)
        self.assertIn("all_active", joined)
        self.assertIn("all_dead", joined)


if __name__ == "__main__":
    unittest.main()
