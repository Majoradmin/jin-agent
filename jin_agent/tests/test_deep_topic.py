"""P42 - ``/deep <topic>`` ab research chalati hai (deep engines ke links ke saath).

Pehle ``/deep <topic>`` sirf engine list dikhati thi, research nahi chalti thi.
"""

import os
import tempfile
import unittest
from unittest import mock

from jin_agent import store, telegram_bot as tb


def setUpModule():
    os.environ.setdefault("JIN_AGENT_DATA", tempfile.mkdtemp(prefix="jin-deep-"))
    store.init_db()


class FakeAPI:
    def __init__(self):
        self.sent = []
        self.modes = []

    def send(self, chat_id, text, buttons=None, parse_mode=None):
        self.sent.append((int(chat_id), str(text)))
        self.modes.append(parse_mode)
        return {"ok": True, "result": {"message_id": len(self.sent)}}

    def edit(self, *a, **k):
        return {"ok": True}

    def send_document(self, chat_id, file_path, caption="", timeout=120):
        self.sent.append((int(chat_id), str(caption)))
        self.modes.append(None)
        return {"ok": True, "result": {"message_id": len(self.sent)}}


class TestDeepTopic(unittest.TestCase):
    def test_deep_bina_topic_engine_list(self):
        api = FakeAPI()
        res = tb.dispatch(42, "/deep", {"telegram_chat_id": "42"}, api=api)
        self.assertTrue(res["ok"])
        self.assertEqual(res["action"], "deep")
        self.assertEqual(res["count"], len(tb.DEEP_ENGINES))
        self.assertTrue(api.sent)
        self.assertIn("Dark", api.sent[0][1])
        # koi research nahi chalani
        self.assertNotIn("deep", res)

    def test_deep_topic_research_chalata_hai(self):
        api = FakeAPI()
        with mock.patch.object(tb, "_send_research",
                               return_value={"ok": True, "action": "research"}) as m:
            res = tb.dispatch(42, "/deep firmware security",
                              {"telegram_chat_id": "42"}, api=api)
        self.assertTrue(res.get("deep"))
        m.assert_called_once()
        topic = m.call_args[0][1]
        self.assertIn("firmware security", str(topic))

    def test_deep_topic_ke_baad_deep_links_bhi(self):
        api = FakeAPI()
        with mock.patch.object(tb, "_send_research",
                               return_value={"ok": True, "action": "research"}):
            tb.dispatch(42, "/deep firmware security",
                        {"telegram_chat_id": "42"}, api=api)
        # research ke baad deep-engine list bhi gayi (alag message)
        deep_msgs = [t for _, t in api.sent if "Dark" in t]
        self.assertTrue(deep_msgs, "deep links message nahi mila")

    def test_deep_onion_sirf_link_fetch_nahi(self):
        api = FakeAPI()
        with mock.patch.object(tb, "_send_research",
                               return_value={"ok": True, "action": "research"}):
            tb.dispatch(42, "/deep onion test",
                        {"telegram_chat_id": "42"}, api=api)
        text = " ".join(t for _, t in api.sent)
        self.assertIn(".onion", text)
        # fetch mana hai — policy rule bhi mojood
        self.assertTrue(tb.policy.DARK_WEB_RULE)

    def test_deep_darkweb_alias_bhi_chalta_hai(self):
        api = FakeAPI()
        res = tb.dispatch(42, "/darkweb", {"telegram_chat_id": "42"}, api=api)
        self.assertTrue(res["ok"])
        self.assertEqual(res["action"], "deep")


if __name__ == "__main__":
    unittest.main()
