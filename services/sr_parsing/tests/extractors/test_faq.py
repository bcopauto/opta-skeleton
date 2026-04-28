"""Tests for faq extractor (EXTR-07)."""
from selectolax.parser import HTMLParser

from scraper_service.extractors import faq


class TestFaqWithFullPage:
    """Tests using the full_page_html fixture which has FAQPage schema and details/summary."""

    def test_detects_faq(self, full_page_tree: HTMLParser) -> None:
        result = faq.extract(full_page_tree, "https://example.com")
        assert result["has_faq"] is True

    def test_faq_schema_count(self, full_page_tree: HTMLParser) -> None:
        result = faq.extract(full_page_tree, "https://example.com")
        assert result["faq_schema_count"] == 1

    def test_faq_schema_questions(self, full_page_tree: HTMLParser) -> None:
        result = faq.extract(full_page_tree, "https://example.com")
        assert "What is SEO?" in result["faq_schema_questions"]
        assert "How to start?" in result["faq_schema_questions"]

    def test_details_count(self, full_page_tree: HTMLParser) -> None:
        result = faq.extract(full_page_tree, "https://example.com")
        assert result["details_count"] == 2

    def test_details_questions(self, full_page_tree: HTMLParser) -> None:
        result = faq.extract(full_page_tree, "https://example.com")
        assert "What is the best free SEO tool?" in result["details_questions"]
        assert "How long does SEO take?" in result["details_questions"]

    def test_total_faq_items(self, full_page_tree: HTMLParser) -> None:
        result = faq.extract(full_page_tree, "https://example.com")
        # 2 schema questions + 2 details questions
        assert result["total_faq_items"] >= 4


class TestFaqWithNoPatterns:
    """Tests with minimal HTML that has no FAQ patterns."""

    def test_no_faq_detected(self, minimal_tree: HTMLParser) -> None:
        result = faq.extract(minimal_tree, "https://example.com")
        assert result["has_faq"] is False
        assert result["faq_schema_count"] == 0
        assert result["details_count"] == 0
        assert result["total_faq_items"] == 0
        assert result["faq_schema_questions"] == []
        assert result["details_questions"] == []
        assert result["class_based_questions"] == []
        assert result["question_headings"] == []


class TestFaqQuestionHeadings:
    """Tests detection of headings ending in '?'."""

    def test_question_heading_detected(self) -> None:
        html = "<html><body><h2>Why use SEO tools?</h2></body></html>"
        tree = HTMLParser(html)
        result = faq.extract(tree, "https://example.com")
        assert result["has_faq"] is True
        assert "Why use SEO tools?" in result["question_headings"]

    def test_non_question_heading_ignored(self) -> None:
        html = "<html><body><h2>SEO Tools Overview</h2></body></html>"
        tree = HTMLParser(html)
        result = faq.extract(tree, "https://example.com")
        assert "SEO Tools Overview" not in result["question_headings"]


class TestFaqClassBased:
    """Tests detection of FAQ content via class names."""

    def test_faq_class_detected(self) -> None:
        html = '<html><body><div class="faq-item">What is SEO?</div></body></html>'
        tree = HTMLParser(html)
        result = faq.extract(tree, "https://example.com")
        assert result["has_faq"] is True
        assert "What is SEO?" in result["class_based_questions"]


class TestFaqNeverRaises:
    """Extractor must never raise, even on malformed input."""

    def test_malformed_html(self) -> None:
        tree = HTMLParser("<html><<<<>>>></html>")
        result = faq.extract(tree, "https://example.com")
        assert isinstance(result, dict)
        assert "has_faq" in result

    def test_invalid_jsonld(self) -> None:
        html = '<html><head><script type="application/ld+json">{bad json}</script></head><body></body></html>'
        tree = HTMLParser(html)
        result = faq.extract(tree, "https://example.com")
        assert result["has_faq"] is False
        assert result["faq_schema_count"] == 0
