"""P1.5 - query-term highlighting aur entity-safe HTML chunking."""

import os
import re
import tempfile
import unittest
from html.parser import HTMLParser

from jin_agent import highlight  # noqa: E402


def setUpModule():
    os.environ["JIN_AGENT_DATA"] = tempfile.mkdtemp(prefix="jin-highlight-")


def _balanced(chunk: str) -> bool:
    """Har chunk khud me balance ho: koi adhura tag na rahe."""

    class _P(HTMLParser):
        VOID = highlight.VOID_TAGS

        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.stack = []
            self.ok = True

        def handle_starttag(self, tag, attrs):
            if tag not in self.VOID:
                self.stack.append(tag)

        def handle_endtag(self, tag):
            if tag in self.VOID:
                return
            if not self.stack or self.stack[-1] != tag:
                self.ok = False
            else:
                self.stack.pop()

        def handle_startendtag(self, tag, attrs):
            pass

    p = _P()
    try:
        p.feed(chunk)
        p.close()
    except Exception:
        return False
    return p.ok and not p.stack


class TestTerms(unittest.TestCase):
    def test_basic_meaningful_terms(self):
        self.assertEqual(
            highlight.terms("Android security bulletin"),
            ["bulletin", "security", "android"],
        )

    def test_case_insensitive_and_deduped(self):
        out = highlight.terms("Android AND android And")
        self.assertEqual(out.count("android"), 1)

    def test_stopwords_removed(self):
        out = highlight.terms("what is the new phone kya hai")
        for word in ("is", "the", "new", "kya", "hai"):
            self.assertNotIn(word, out)
        self.assertIn("phone", out)

    def test_single_letters_and_dedupe(self):
        self.assertNotIn("a", highlight.terms("a b c ab"))
        self.assertIn("ab", highlight.terms("a b c ab"))

    def test_longest_first_no_overlap(self):
        out = highlight.terms("android security")
        self.assertGreaterEqual(len(out), 2)
        for i in range(len(out) - 1):
            self.assertGreaterEqual(len(out[i]), len(out[i + 1]))

    def test_limit(self):
        out = highlight.terms("alpha beta gamma delta epsilon", limit=2)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0], "epsilon")

    def test_empty_and_none(self):
        self.assertEqual(highlight.terms(""), [])
        self.assertEqual(highlight.terms("the a of"), [])


class TestHighlightHtml(unittest.TestCase):
    def test_basic_bold(self):
        out = highlight.highlight_html("android security news", ["security"])
        self.assertEqual(out, "android <b>security</b> news")

    def test_case_insensitive(self):
        out = highlight.highlight_html("Android SECURITY news", ["security"])
        self.assertEqual(out, "Android <b>SECURITY</b> news")

    def test_no_match_returns_identical(self):
        html = "<p>koi match nahi</p>"
        self.assertEqual(highlight.highlight_html(html, ["zzz"]), html)

    def test_empty_terms_returns_identical(self):
        html = "<p>text</p>"
        self.assertEqual(highlight.highlight_html(html, []), html)

    def test_tags_and_urls_not_highlighted(self):
        html = '<a href="https://example.com/android">android</a>'
        out = highlight.highlight_html(html, ["android"])
        self.assertEqual(out, '<a href="https://example.com/android">'
                              '<b>android</b></a>')

    def test_attribute_value_not_highlighted(self):
        html = '<a href="android" title="android">link</a>'
        out = highlight.highlight_html(html, ["android"])
        self.assertEqual(out, html)

    def test_entities_preserved(self):
        html = "alpha &amp; beta"
        self.assertEqual(highlight.highlight_html(html, ["amp"]), html)
        self.assertEqual(highlight.highlight_html(html, ["alpha"]), "<b>alpha</b> &amp; beta")

    def test_term_once_only(self):
        out = highlight.highlight_html("alpha beta alpha", ["alpha"])
        self.assertEqual(out, "<b>alpha</b> beta alpha")

    def test_overlapping_terms_longest_first(self):
        out = highlight.highlight_html("android security bulletin", ["android", "security"])
        self.assertEqual(out.count("<b>"), 2)
        self.assertIn("<b>android</b>", out)
        self.assertIn("<b>security</b>", out)

    def test_escaped_html_not_unescaped(self):
        html = "x &lt;script&gt; y"
        out = highlight.highlight_html(html, ["script"])
        self.assertNotIn("<script>", out)
        self.assertIn("&lt;<b>script</b>&gt;", out)

    def test_multiple_terms_across_nodes(self):
        html = "<p>android</p><p>security</p>"
        out = highlight.highlight_html(html, ["android", "security"])
        self.assertEqual(out, "<p><b>android</b></p><p><b>security</b></p>")

    def test_term_matching_inside_bold_not_nested(self):
        html = "android security"
        out = highlight.highlight_html(html, ["android security", "android"])
        self.assertEqual(out, "<b>android security</b>")


class TestSplitHtml(unittest.TestCase):
    def test_short_html_single_chunk(self):
        html = "<b>hello</b> world"
        self.assertEqual(highlight.split_html(html), [html])

    def test_empty(self):
        self.assertEqual(highlight.split_html(""), [])

    def test_chunks_within_limit_utf16(self):
        html = "😀" * 5000
        chunks = highlight.split_html(html, 4096)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(highlight._ulen(chunk), 4096)
        self.assertEqual("".join(chunks), html)

    def test_tags_balanced_per_chunk(self):
        html = ('<b>' + 'alpha ' * 400 + '</b> '
                '<a href="https://example.com/x">' + 'beta ' * 400 + '</a>')
        chunks = highlight.split_html(html, 200)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertTrue(_balanced(chunk), chunk[:80])
            self.assertLessEqual(len(chunk), 200)

    def test_newline_preferred_break(self):
        chunks = highlight.split_html("aaaa\nbbbb", 5)
        self.assertEqual(chunks, ["aaaa\n", "bbbb"])

    def test_entity_not_cut(self):
        chunks = highlight.split_html("&amp;" * 100, 10)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertRegex(chunk, r"^(?:&amp;)+$")

    def test_reopened_attributes_survive(self):
        html = '<a href="https://example.com/">' + "text " * 100 + "</a>"
        chunks = highlight.split_html(html, 20)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            if chunk.startswith("<a"):
                self.assertIn('href="https://example.com/"', chunk)

    def test_unclosed_tag_is_closed(self):
        chunks = highlight.split_html("<b>" + "x" * 100, 20)
        self.assertTrue(all(_balanced(c) for c in chunks))
        text = re.sub(r"<[^>]*>", "", "".join(chunks))
        self.assertEqual(text, "x" * 100)

    def test_plain_text_reassembles(self):
        html = ("line one\nline two\n" * 200)
        chunks = highlight.split_html(html, 64)
        self.assertEqual("".join(chunks), html)


class TestHighlightMarkdown(unittest.TestCase):
    def test_basic_bold(self):
        self.assertEqual(highlight.highlight_markdown("free api key", ["api"]),
                         "free **api** key")

    def test_case_insensitive(self):
        self.assertEqual(highlight.highlight_markdown("Free API key", ["api"]),
                         "Free **API** key")

    def test_url_not_highlighted(self):
        text = "dekhein https://example.com/api docs"
        self.assertEqual(highlight.highlight_markdown(text, ["api"]), text)

    def test_inline_code_not_highlighted(self):
        text = "use `api` yahan"
        self.assertEqual(highlight.highlight_markdown(text, ["api"]), text)

    def test_markdown_meta_escaped_inside_bold(self):
        out = highlight.highlight_markdown("foo_bar baz", ["foo_bar"])
        self.assertEqual(out, "**foo\\_bar** baz")

    def test_multiple_terms_longest_first(self):
        out = highlight.highlight_markdown("android security bulletin",
                                           ["android", "security"])
        self.assertEqual(out.count("**"), 4)
        self.assertIn("**android**", out)
        self.assertIn("**security**", out)

    def test_no_match_returns_identical(self):
        text = "koi match nahi"
        self.assertEqual(highlight.highlight_markdown(text, ["zzz"]), text)

    def test_empty_terms(self):
        text = "plain text"
        self.assertEqual(highlight.highlight_markdown(text, []), text)


if __name__ == "__main__":
    unittest.main()
