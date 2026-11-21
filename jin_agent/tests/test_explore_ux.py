"""P46 - /explore Telegram UX: cards, 4 actions, loading/empty/error, HTML.

- har Telegram card: title, @handle, t.me link, badge, score, subs, date,
  zaban, relevance reason, source link
- post/article/message card: 140-char preview + post link
- har card par 4 inline actions (🔗 Channel / 🗂 Posts / 🌐 Translate /
  🔄 Refine) + bulk ✅/❌ + 🔄 Aur explore karo
- loading message (wahi message edit), saaf empty wajah, error wajah
- HTML parse_mode + ``highlight.split_html`` se balanced chunks (4096)

Sab network calls mocked hain (project rule: tests kabhi live internet na
chhedein).
"""

import os
import tempfile
import unittest
from unittest import mock

from jin_agent import channels, config, highlight, store
from jin_agent import telegram_bot as tb


def setUpModule():
    os.environ["JIN_AGENT_DATA"] = tempfile.mkdtemp(prefix="jin-explore-ux-")
    store.init_db()
    channels.ensure_table()


class FakeAPI:
    def __init__(self):
        self.sent = []
        self.edits = []

    def send(self, chat_id, text, buttons=None):
        self.sent.append((int(chat_id), str(text), buttons))
        return {"ok": True, "result": {"message_id": len(self.sent)}}

    def edit(self, chat_id, message_id, text, parse_mode=None):
        self.edits.append((int(chat_id), int(message_id), str(text)))
        return {"ok": True}

    def get_updates(self, offset, timeout=None):
        return []

    def answer_callback(self, callback_id, text=""):
        return {"ok": True}

    def set_my_commands(self, commands, timeout=30):
        return {"ok": True}


def _probe_row(handle="androidsec", status="active", score=8, title="Android Security",
               subs="25.4K", last="2026-11-19 10:00:00", reason="android, security",
               source="rightdao"):
    return {"channel": handle, "status": status, "score": score, "title": title,
            "subscribers": subs, "last_post_at": last, "post_count": 9,
            "note": "auto-discovered liveness check", "relevance": 8,
            "reason": reason, "source": source, "rank": 1}


def _res(probe_rows=None, added=None, scored=None, lyzem=None):
    rows = list(probe_rows if probe_rows is not None else [_probe_row()])
    return {
        "topic": "android security", "query": "android security", "items": 1,
        "discovery": {"added": list(added if added is not None
                               else [r["channel"] for r in rows]),
                      "dead": [], "candidates": len(rows), "probed": len(rows),
                      "probe_rows": rows,
                      "counts": {"active": len(rows), "dead": 0, "archived": 0,
                                 "stale": 0, "total": len(rows)},
                      "web_search": {"engine": "rightdao, lyzem", "error": "",
                                     "anomaly": False}},
        "scored": list(scored or []),
        "lyzem_records": list(lyzem or []),
    }


class TestCardFields(unittest.TestCase):
    def test_card_has_all_fields(self):
        groups = tb._explore_groups(_res(), "android security", "all")
        text = tb.format_explore_cards_v2("android security", "all", groups)
        for needle in ("Android Security", "@androidsec", "✅ active",
                       "score 8", "25.4K subs", "📅 2026-11-19",
                       "English (en)", "🎯 android, security",
                       "📡 rightdao", "https://t.me/androidsec",
                       "https://t.me/s/androidsec"):
            self.assertIn(needle, text, needle)

    def test_urdu_language_label(self):
        row = _probe_row(title="موبائل سیکیورٹی", handle="mobail_sec")
        groups = tb._explore_groups(_res(probe_rows=[row]),
                                    "موبائل سیکیورٹی", "all")
        text = tb.format_explore_cards_v2("موبائل سیکیورٹی", "all", groups)
        self.assertIn("اردو (ur)", text)

    def test_html_escaped_title(self):
        row = _probe_row(title="A & B <news>")
        groups = tb._explore_groups(_res(probe_rows=[row]), "android", "all")
        text = tb.format_explore_cards_v2("android", "all", groups)
        self.assertIn("A &amp; B &lt;news&gt;", text)
        self.assertNotIn("<news>", text)

    def test_post_preview_card(self):
        lyzem = [{"handle": "zrumbesh", "url": "https://t.me/zrumbesh/2942",
                  "kind": "post", "title": "",
                  "descr": "موبائل سیکیورٹی کیا ہے — مکمل رہنمائی",
                  "msg_id": "2942"}]
        groups = tb._explore_groups(_res(probe_rows=[_probe_row()], lyzem=lyzem),
                                    "موبائل", "all")
        post = [it for it in groups["tg"] if it.get("kind") == "post"]
        self.assertEqual(len(post), 1)
        self.assertEqual(post[0]["preview"],
                         "موبائل سیکیورٹی کیا ہے — مکمل رہنمائی")
        text = tb.format_explore_cards_v2("موبائل", "all", groups)
        self.assertIn("📝 post", text)
        self.assertIn("https://t.me/zrumbesh/2942", text)
        self.assertIn("اردو (ur)", text)

    def test_post_preview_truncated_140(self):
        lyzem = [{"handle": "long_ch", "url": "https://t.me/long_ch/1",
                  "kind": "article", "title": "L",
                  "descr": "x" * 400, "msg_id": "1"}]
        groups = tb._explore_groups(_res(probe_rows=[_probe_row()], lyzem=lyzem),
                                    "android", "all")
        post = [it for it in groups["tg"] if it.get("kind") == "post"][0]
        self.assertLessEqual(len(post["preview"]), 140)


class TestButtons(unittest.TestCase):
    def setUp(self):
        tb._EXPLORE_PENDING.pop(42, None)
        tb._EXPLORE_SHOWN.pop(42, None)
        tb._EXPLORE_TOPICS.clear()

    def tearDown(self):
        tb._EXPLORE_PENDING.pop(42, None)
        tb._EXPLORE_SHOWN.pop(42, None)

    def test_four_actions_plus_bulk(self):
        api = FakeAPI()
        with mock.patch.object(tb.scheduler, "run_job",
                               lambda *a, **k: _res()):
            tb.dispatch(42, "/explore android security",
                        {"telegram_chat_id": "42"}, api=api)
        rows = api.sent[-1][2]
        # pehla row gate (purana behavior barqarar)
        self.assertEqual(rows[0][0]["callback_data"], "exp:keep:ch:androidsec")
        action = rows[1]
        self.assertEqual(len(action), 4)
        self.assertEqual(action[0]["text"], "🔗 Channel")
        self.assertEqual(action[0]["url"], "https://t.me/androidsec")
        self.assertEqual(action[1]["text"], "🗂 Posts")
        self.assertEqual(action[1]["url"], "https://t.me/s/androidsec")
        self.assertTrue(action[2]["callback_data"].startswith("tr:"))
        self.assertTrue(action[3]["callback_data"].startswith("refine:"))
        flat = [b for row in rows for b in row]
        cbs = [b.get("callback_data") for b in flat if b.get("callback_data")]
        self.assertIn("exp:keep:all", cbs)
        self.assertIn("exp:skip:all", cbs)
        self.assertTrue(any(c.startswith("exp:more:") for c in cbs))

    def test_action_hash_roundtrip(self):
        api = FakeAPI()
        with mock.patch.object(tb.scheduler, "run_job",
                               lambda *a, **k: _res()):
            tb.dispatch(42, "/explore android security",
                        {"telegram_chat_id": "42"}, api=api)
        rows = api.sent[-1][2]
        tr_cb = rows[1][2]["callback_data"]
        topic_hash, act_hash = tb.parse_explore_translate_callback(tr_cb)
        self.assertTrue(topic_hash)
        item = tb._EXPLORE_PENDING[42]["items"]["ch:androidsec"]
        self.assertEqual(tb._explore_action_hash(item), act_hash)


class TestLoadingEmptyError(unittest.TestCase):
    def setUp(self):
        tb._EXPLORE_PENDING.pop(42, None)
        tb._EXPLORE_SHOWN.pop(42, None)
        tb._EXPLORE_TOPICS.clear()

    def tearDown(self):
        tb._EXPLORE_PENDING.pop(42, None)
        tb._EXPLORE_SHOWN.pop(42, None)

    def test_loading_message_and_edit(self):
        api = FakeAPI()
        with mock.patch.object(tb.scheduler, "run_job",
                               lambda *a, **k: _res()):
            tb.dispatch(42, "/explore android security",
                        {"telegram_chat_id": "42"}, api=api)
        self.assertIn("⏳ Explore chal raha hai — android security",
                      api.sent[0][1])
        self.assertIn("✅ Explore ho gaya", api.edits[-1][2])
        self.assertIn("@androidsec", api.sent[-1][1])

    def test_empty_reason(self):
        api = FakeAPI()
        empty = {"topic": "kuch nahi", "query": "kuch nahi", "items": 0,
                 "discovery": {"added": [], "dead": [], "candidates": 0,
                               "probed": 0, "probe_rows": [],
                               "counts": {"active": 0, "dead": 0, "archived": 0,
                                          "stale": 0, "total": 0},
                               "web_search": {"engine": "", "error": "",
                                              "anomaly": False}},
                 "scored": [], "lyzem_records": []}
        with mock.patch.object(tb.scheduler, "run_job", lambda *a, **k: empty):
            res = tb._render_explore(42, "kuch nahi", "tg", empty,
                                     config.load(), api)
        self.assertTrue(res.get("empty"))
        self.assertIn("Koi naya item nahi mila", api.sent[-1][1])

    def test_error_message(self):
        api = FakeAPI()

        def boom(*a, **k):
            raise RuntimeError("probe down")

        with mock.patch.object(tb.scheduler, "run_job", boom):
            res = tb.dispatch(42, "/explore android security",
                              {"telegram_chat_id": "42"}, api=api)
        self.assertFalse(res["ok"])
        self.assertIn("⚠️ Explore me masla hua", api.edits[-1][2])
        self.assertIn("detail local console par hai", api.edits[-1][2])


class TestHtmlChunks(unittest.TestCase):
    def test_split_html_balanced_and_limit(self):
        groups = tb._explore_groups(_res(), "android security", "all")
        html = tb.format_explore_cards_v2("android security", "all", groups)
        chunks = highlight.split_html(html, 4096)
        self.assertTrue(chunks)
        for chunk in chunks:
            self.assertLessEqual(len(chunk), 4096)
            self.assertEqual(chunk.count("<b>"), chunk.count("</b>"))
            self.assertEqual(chunk.count("<a "), chunk.count("</a>"))

    def test_long_card_chunks_under_limit(self):
        rows = [_probe_row(handle=f"ch{i:02d}", title="T" * 80)
                for i in range(30)]
        groups = tb._explore_groups(_res(probe_rows=rows), "android", "all")
        html = tb.format_explore_cards_v2("android", "all", groups)
        for chunk in highlight.split_html(html, 4096):
            self.assertLessEqual(len(chunk), 4096)
            self.assertEqual(chunk.count("<b>"), chunk.count("</b>"))


class TestTranslateRefine(unittest.TestCase):
    def setUp(self):
        tb._EXPLORE_PENDING.pop(42, None)
        tb._EXPLORE_SHOWN.pop(42, None)
        tb._EXPLORE_TOPICS.clear()

    def tearDown(self):
        tb._EXPLORE_PENDING.pop(42, None)
        tb._EXPLORE_SHOWN.pop(42, None)

    def _dispatch(self, api):
        with mock.patch.object(tb.scheduler, "run_job",
                               lambda *a, **k: _res()):
            tb.dispatch(42, "/explore android security",
                        {"telegram_chat_id": "42"}, api=api)
        return api.sent[-1][2]

    def test_translate_callback(self):
        api = FakeAPI()
        rows = self._dispatch(api)
        tr_cb = rows[1][2]["callback_data"]
        with mock.patch.object(tb.llm, "translate_text",
                               lambda cfg, text, timeout=30: "ترجمہ شدہ متن"):
            res = tb.handle_callback(42, tr_cb, {"telegram_chat_id": "42"},
                                     api=api)
        self.assertTrue(res["ok"])
        self.assertIn("ترجمہ شدہ متن", api.sent[-1][1])

    def test_translate_expired(self):
        api = FakeAPI()
        res = tb.handle_callback(42, "tr:deadbeef0000:deadbeef",
                                 {"telegram_chat_id": "42"}, api=api)
        self.assertFalse(res["ok"])
        self.assertEqual(res["action"], "explore_translate")

    def test_refine_callback_uses_variants(self):
        api = FakeAPI()
        rows = self._dispatch(api)
        refine_cb = rows[1][3]["callback_data"]
        seen = {}

        def job(kind, payload=None, cfg=None, offline=True):
            seen.update(payload or {})
            return _res()

        with mock.patch.object(tb.query_variants, "variants",
                               lambda topic, cfg, n: [{"text": "موبيل حماية"}]), \
             mock.patch.object(tb.scheduler, "run_job", job):
            res = tb.handle_callback(42, refine_cb,
                                     {"telegram_chat_id": "42"}, api=api)
        self.assertTrue(res["ok"])
        self.assertEqual(seen.get("variants"), [{"text": "موبيل حماية"}])


if __name__ == "__main__":
    unittest.main()
