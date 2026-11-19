"""P38 - multi-turn chat context: migration, follow-up detect, attach, /new clear."""

import os
import tempfile
import unittest

from jin_agent import chat_context as cc, store, telegram_bot as tb  # noqa: E402


def setUpModule():
    os.environ["JIN_AGENT_DATA"] = tempfile.mkdtemp(prefix="jin-ctx-")
    store.init_db()


class TestMigration(unittest.TestCase):
    def test_chat_context_table_exists(self):
        with store.session() as con:
            self.assertTrue(store._table_exists(con, "chat_context"))
        # Purana DB par dobara init_db bhi bemtanag.
        store.init_db()
        with store.session() as con:
            self.assertTrue(store._table_exists(con, "chat_context"))

    def test_store_roundtrip(self):
        store.save_chat_query(42, "mediatek firmware unlock")
        self.assertEqual(store.last_chat_query(42), "mediatek firmware unlock")
        store.save_chat_query(42, "aur")
        self.assertEqual(store.last_chat_query(42), "aur")
        self.assertEqual(store.clear_chat_context(42), 1)
        self.assertEqual(store.last_chat_query(42), "")
        self.assertEqual(store.clear_chat_context(42), 0)


class TestDetect(unittest.TestCase):
    def test_short_text_is_followup(self):
        self.assertTrue(cc.is_followup("aur"))
        self.assertTrue(cc.is_followup("iske baare me"))
        self.assertTrue(cc.is_followup("more details"))
        self.assertTrue(cc.is_followup("  aur   phir "))
        self.assertFalse(cc.is_followup(""))

    def test_long_text_without_hint_is_not_followup(self):
        self.assertFalse(cc.is_followup(
            "mediatek preloader scatter DA file ka exact version kya hai"))
        # "suraj" ke andar "aur" lafz nahi — word-boundary check.
        self.assertFalse(cc.is_followup(
            "suraj daily news channel ke aaj ki khabar"))

    def test_long_text_with_hint_is_followup(self):
        self.assertTrue(cc.is_followup(
            "mediatek firmware unlock tool ke baare me aur iska version kya hai"))


class TestAttach(unittest.TestCase):
    def test_attach_previous_query(self):
        store.save_chat_query(7, "mediatek firmware unlock")
        self.assertEqual(cc.attach(7, "aur"), "mediatek firmware unlock | aur")
        # Non-followup as-is.
        self.assertEqual(cc.attach(7, "samsung knox mdm policy kya hai"),
                         "samsung knox mdm policy kya hai")
        # History na ho to as-is.
        self.assertEqual(cc.attach(99, "aur"), "aur")
        # Wahi query dobara na jure.
        store.save_chat_query(8, "aur")
        self.assertEqual(cc.attach(8, "aur"), "aur")


class FakeAPI:
    def __init__(self):
        self.sent = []

    def send(self, chat_id, text, buttons=None, parse_mode=None):
        self.sent.append(str(text))
        return {"ok": True}

    def send_document(self, chat_id, file_path, caption="", timeout=120):
        self.sent.append(str(caption))
        return {"ok": True}


class TestBotContext(unittest.TestCase):
    def test_research_attaches_context_and_new_clears(self):
        seen = []

        def fake_research(q, cfg, save=True, live=False):
            seen.append(q)
            return "# Brief"

        api = FakeAPI()
        first = tb.dispatch(55, "/research mediatek firmware unlock",
                            {"telegram_chat_id": "55"}, api=api,
                            research=fake_research)
        self.assertTrue(first["ok"])
        follow = tb.dispatch(55, "/research aur",
                             {"telegram_chat_id": "55"}, api=api,
                             research=fake_research)
        self.assertTrue(follow["ok"])
        self.assertEqual(seen[0], "mediatek firmware unlock")
        self.assertEqual(seen[1], "mediatek firmware unlock | aur")
        # /new context clear karta hai.
        new = tb.dispatch(55, "/new", {"telegram_chat_id": "55"}, api=api)
        self.assertTrue(new["ok"])
        self.assertEqual(store.last_chat_query(55), "")
        after = tb.dispatch(55, "/research aur",
                            {"telegram_chat_id": "55"}, api=api,
                            research=fake_research)
        self.assertTrue(after["ok"])
        self.assertEqual(seen[2], "aur")


if __name__ == "__main__":
    unittest.main()
