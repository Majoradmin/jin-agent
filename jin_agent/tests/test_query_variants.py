"""Phase 2 — multilingual query pipeline tests (network-free, deterministic).

``query_variants`` stdlib-only hai aur LLM ke baghair bhi kaam karta hai;
ye tests usi deterministic fallback par hain. Koi network call nahi.
"""

import os
import tempfile
import unittest

from jin_agent import query_variants as qv


class TestDetectLanguage(unittest.TestCase):
    def test_urdu_arabic_script(self):
        r = qv.detect_language("موبائل سیکیورٹی")
        self.assertEqual(r["script"], "arabic")
        self.assertEqual(r["lang"], "ur")

    def test_arabic_without_urdu_markers(self):
        r = qv.detect_language("تكنولوجيا")
        self.assertEqual(r["script"], "arabic")
        self.assertEqual(r["lang"], "ar")

    def test_roman_urdu_latin(self):
        r = qv.detect_language("mobail security")
        self.assertEqual(r["script"], "latin")
        self.assertEqual(r["lang"], "roman-urdu")

    def test_english(self):
        r = qv.detect_language("android firmware unlock")
        self.assertEqual(r["lang"], "en")

    def test_cyrrillic(self):
        self.assertEqual(qv.detect_language("привет мир")["lang"], "ru")

    def test_khaali(self):
        r = qv.detect_language("")
        self.assertEqual(r["lang"], "unknown")
        self.assertEqual(r["confidence"], 0.0)

    def test_confidence_range(self):
        for t in ("موبائل", "mobail security", "android", ""):
            c = qv.detect_language(t)["confidence"]
            self.assertGreaterEqual(c, 0.0)
            self.assertLessEqual(c, 1.0)


class TestTransliteration(unittest.TestCase):
    def test_arabic_to_latin(self):
        out = qv.transliterate("موبائل", "arabic-to-latin")
        self.assertEqual(out, "mobail")

    def test_latin_to_arabic(self):
        out = qv.transliterate("mobail", "latin-to-arabic")
        self.assertEqual(out, "موبائل")

    def test_securiti(self):
        self.assertEqual(qv.transliterate("securiti", "latin-to-arabic"),
                         "سیکیورٹی")

    def test_khaali_auur_ghalat_direction(self):
        self.assertEqual(qv.transliterate("", "latin-to-arabic"), "")
        # ghalat direction = default (arabic-to-latin) treat hota hai
        self.assertIsInstance(qv.transliterate("abc", "nope"), str)

    def test_round_trip_stable(self):
        once = qv.transliterate("موبائل سیکیورٹی", "arabic-to-latin")
        twice = qv.transliterate(once, "arabic-to-latin")
        self.assertEqual(once, twice)


class TestTranslate(unittest.TestCase):
    def test_en_to_ur(self):
        out = qv.translate_query("mobile", ["ur"], {})
        self.assertEqual(out.get("ur"), "موبائل")

    def test_ur_to_en(self):
        out = qv.translate_query("موبائل", ["en"], {})
        self.assertEqual(out.get("en"), "mobile")

    def test_anu_urdu_se_english(self):
        out = qv.translate_query("نیوز", ["en"], {})
        self.assertEqual(out.get("en"), "news")

    def test_unknown_kuch_nahi(self):
        # Jhoot nahi — anu lafz par khali
        self.assertEqual(qv.translate_query("xyzzyunknown", ["ur"], {}), {})

    def test_khaali_targets(self):
        self.assertEqual(qv.translate_query("mobile", [], {}), {})
        self.assertEqual(qv.translate_query("", ["ur"], {}), {})

    def test_roman_urdu_source_bhi_en_ke_hav_jata_hai(self):
        out = qv.translate_query("mobile", ["ur"], {})
        self.assertEqual(out.get("ur"), "موبائل")


class TestSynonyms(unittest.TestCase):
    def test_en_firmware(self):
        got = qv.synonyms("firmware", "en", {})
        self.assertIn("rom", got)

    def test_urdu_mobile(self):
        got = qv.synonyms("موبائل", "ur", {})
        self.assertTrue(any("موبائل" in g or "فون" in g for g in got))

    def test_roman_urdu_mobail(self):
        got = qv.synonyms("mobail", "roman-urdu", {})
        self.assertTrue(got)

    def test_limit(self):
        self.assertLessEqual(len(qv.synonyms("firmware", "en", {})), 8)


class TestVariants(unittest.TestCase):
    def test_khaali_query(self):
        self.assertEqual(qv.variants("", {}), [])

    def test_urdu_variants_me_transliteration_hai(self):
        vs = qv.variants("موبائل سیکیورٹی", {})
        kinds = {v["kind"] for v in vs}
        self.assertIn("transliteration", kinds)
        texts = {v["text"] for v in vs}
        self.assertIn("mobail", qv.transliterate("موبائل", "arabic-to-latin"))

    def test_roman_urdu_variants_me_arabic_hai(self):
        vs = qv.variants("mobail security", {})
        kinds = {v["kind"] for v in vs}
        self.assertIn("transliteration", kinds)
        self.assertIn("synonym", kinds)

    def test_original_hamesha_pehle(self):
        vs = qv.variants("android security", {})
        self.assertEqual(vs[0]["text"], "android security")
        self.assertEqual(vs[0]["kind"], "original")

    def test_dedupe(self):
        vs = qv.variants("mobile mobile mobile", {})
        texts = [v["text"] for v in vs]
        self.assertEqual(len(texts), len(set(t.lower() for t in texts)))

    def test_cap(self):
        vs = qv.variants("موبائل سیکیورٹی", {}, max_variants=3)
        self.assertLessEqual(len(vs), 3)

    def test_llm_off_deterministic(self):
        # cfg khaali = LLM off; do dafa bilkul barabar (koi network nahi)
        a = qv.variants("free api key", {})
        b = qv.variants("free api key", {})
        self.assertEqual(a, b)

    def test_variant_texts(self):
        self.assertEqual(qv.variant_texts("", {}), [])
        self.assertTrue(qv.variant_texts("firmware", {}))


class TestDiscoveryWiring(unittest.TestCase):
    """``channels.run_discovery`` variants qabool karta hai (offline)."""

    def test_run_discovery_offline_with_variants(self):
        from jin_agent import channels, store
        os.environ["JIN_AGENT_DATA"] = tempfile.mkdtemp(prefix="qv-")
        store.init_db()
        out = channels.run_discovery({"channel_discovery_web": False},
                                     offline=True, max_add=2,
                                     query="موبائل سیکیورٹی",
                                     variants=qv.variants("موبائل سیکیورٹی", {}))
        self.assertEqual(out["query"], "موبائل سیکیورٹی")
        self.assertTrue(out["variants"])
        self.assertIn("mobail", " ".join(out["variants"]).lower())


if __name__ == "__main__":
    unittest.main()
