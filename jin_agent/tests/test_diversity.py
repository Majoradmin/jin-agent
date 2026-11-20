"""Report diversification — ek hi source ki items ki had.

User shikayat: "free api key" par 14 Stack Exchange sawaal aisi lagti thi
ke report "repeated" hai. Hal: ``orchestrator._diversify`` har source ki
items ``max_items_per_source`` (default 6) par rok deta hai.
"""

import os
import tempfile
import unittest

from jin_agent import orchestrator, ranker, store


def setUpModule():
    os.environ.setdefault("JIN_AGENT_DATA", tempfile.mkdtemp(prefix="jin-div-"))
    store.init_db()


def item(source_key, title, score=5.0):
    return {"source_key": source_key, "source": source_key.upper(),
            "title": title, "score": score, "guid": source_key + ":" + title}


class TestDiversify(unittest.TestCase):
    def test_har_source_ki_items_cap_ho_jati_hain(self):
        rows = ([item("stackexchange", f"so-{i}", score=9.0) for i in range(14)] +
                [item("gitlab", f"gl-{i}", score=8.0) for i in range(7)] +
                [item("hn", f"hn-{i}", score=9.5) for i in range(2)])
        out = orchestrator._diversify(rows, 6)
        counts = {}
        for r in out:
            counts[r["source_key"]] = counts.get(r["source_key"], 0) + 1
        self.assertEqual(counts["stackexchange"], 6)
        self.assertEqual(counts["gitlab"], 6)
        self.assertEqual(counts["hn"], 2)
        self.assertLessEqual(len(out), 14)

    def test_tarteeb_seebar_kee_jati_hai(self):
        rows = [item("a", "a1", score=9.0), item("b", "b1", score=8.0),
                item("a", "a2", score=7.0)]
        out = orchestrator._diversify(rows, 1)
        self.assertEqual([r["title"] for r in out], ["a1", "b1"])

    def test_khaali_list(self):
        self.assertEqual(orchestrator._diversify([], 6), [])

    def test_source_key_nahio_to_source_use_hota_hai(self):
        rows = [item("", "x", 5.0), {"source": "Named", "title": "y", "score": 4.0}]
        out = orchestrator._diversify(rows, 6)
        self.assertEqual(len(out), 2)

    def test_ranker_ke_sath_cap_lagta_hai(self):
        rows = [item("stackexchange", f"q-{i}", score=8.0 + i / 100.0)
                for i in range(20)]
        ranked = ranker.rank(rows, "free api key", 25)
        out = orchestrator._diversify(ranked, 6)
        self.assertEqual(len(out), 6)

    def test_config_default_hai(self):
        from jin_agent import config
        cfg = config.load()
        self.assertEqual(cfg.get("max_items_per_source"), 6)


if __name__ == "__main__":
    unittest.main()
