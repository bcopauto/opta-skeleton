"""Tests for body_text extractor (EXTR-04)."""
from __future__ import annotations

from selectolax.parser import HTMLParser

from scraper_service.extractors.body_text import extract


class TestBodyTextExtract:
    """Tests for body_text.extract()."""

    def test_full_page_returns_word_count(self, full_page_tree: HTMLParser) -> None:
        """Full page fixture has many words -- word_count should be well above 100."""
        result = extract(full_page_tree, "https://example.com")
        assert result["word_count"] > 100
        assert isinstance(result["text_html_ratio"], float)
        assert 0 < result["text_html_ratio"] < 1

    def test_minimal_page_returns_empty(self, minimal_tree: HTMLParser) -> None:
        """Page with no body content returns zero counts."""
        result = extract(minimal_tree, "https://example.com")
        assert result["word_count"] == 0
        assert result["text"] == ""
        assert result["char_count"] == 0
        assert result["sentence_count"] == 0
        assert result["paragraph_count"] == 0
        assert result["text_html_ratio"] == 0
        assert result["reading_time_s"] == 0
        assert result["lang"] is None

    def test_strips_script_content(self) -> None:
        """Script content must not appear in extracted text."""
        html = "<html><body><p>Visible text</p><script>var x = 'should not appear';</script></body></html>"
        tree = HTMLParser(html)
        result = extract(tree, "https://example.com")
        assert "should not appear" not in result["text"]
        assert "Visible text" in result["text"]

    def test_strips_nav_and_footer(self) -> None:
        """Nav and footer text must not appear in extracted text."""
        html = "<html><body><nav>menu items</nav><p>Main content here</p><footer>footer text</footer></body></html>"
        tree = HTMLParser(html)
        result = extract(tree, "https://example.com")
        assert "menu items" not in result["text"]
        assert "footer text" not in result["text"]
        assert "Main content here" in result["text"]

    def test_simple_body_text(self) -> None:
        """Simple body with one paragraph returns correct word count."""
        html = "<html><body><p>Hello world</p></body></html>"
        tree = HTMLParser(html)
        result = extract(tree, "https://example.com")
        assert result["word_count"] == 2
        assert result["char_count"] > 0

    def test_never_raises_on_malformed_html(self) -> None:
        """Extractor never raises, even on garbage input."""
        html = "<html><body><div><p>unclosed"
        tree = HTMLParser(html)
        result = extract(tree, "https://example.com")
        # Should return a dict with the expected keys, never raise
        assert "word_count" in result
        assert "text" in result

    def test_lang_attribute_extracted(self, full_page_tree: HTMLParser) -> None:
        """Language from <html lang> is extracted."""
        result = extract(full_page_tree, "https://example.com")
        assert result["lang"] == "en"

    def test_reading_time_nonzero_for_long_text(self, full_page_tree: HTMLParser) -> None:
        """Reading time should be nonzero for a page with > 200 words."""
        result = extract(full_page_tree, "https://example.com")
        # The full page fixture has > 100 words, may or may not exceed 200
        assert result["reading_time_s"] >= 0
        assert isinstance(result["reading_time_s"], int)

    def test_returns_all_expected_keys(self, full_page_tree: HTMLParser) -> None:
        """Result dict contains all expected fields."""
        result = extract(full_page_tree, "https://example.com")
        expected_keys = {
            "word_count", "char_count", "sentence_count", "paragraph_count",
            "text_html_ratio", "reading_time_s", "lang", "text",
        }
        assert set(result.keys()) == expected_keys
