"""Tests for toc extractor (EXTR-09)."""
from selectolax.parser import HTMLParser

from scraper_service.extractors import toc


class TestTocWithFullPage:
    """Tests using the full_page_html fixture which has TOC anchor links to headings."""

    def test_toc_detected(self, full_page_tree: HTMLParser) -> None:
        result = toc.extract(full_page_tree, "https://example.com")
        assert result["has_toc"] is True

    def test_toc_link_count(self, full_page_tree: HTMLParser) -> None:
        result = toc.extract(full_page_tree, "https://example.com")
        assert result["toc_link_count"] == 3

    def test_toc_links_targets(self, full_page_tree: HTMLParser) -> None:
        result = toc.extract(full_page_tree, "https://example.com")
        target_ids = [link["target_id"] for link in result["toc_links"]]
        assert "keyword-tools" in target_ids
        assert "technical-seo" in target_ids
        assert "comparison" in target_ids

    def test_toc_links_have_text(self, full_page_tree: HTMLParser) -> None:
        result = toc.extract(full_page_tree, "https://example.com")
        texts = [link["text"] for link in result["toc_links"]]
        assert "Keyword Research Tools" in texts


class TestTocNoAnchors:
    """Tests with minimal HTML that has no TOC."""

    def test_no_toc(self, minimal_tree: HTMLParser) -> None:
        result = toc.extract(minimal_tree, "https://example.com")
        assert result["has_toc"] is False
        assert result["toc_link_count"] == 0
        assert result["toc_links"] == []


class TestTocSingleAnchor:
    """A single anchor to a heading is not enough for TOC detection."""

    def test_single_anchor_no_toc(self) -> None:
        html = '<html><body><h2 id="section">Section</h2><a href="#section">Go to section</a></body></html>'
        tree = HTMLParser(html)
        result = toc.extract(tree, "https://example.com")
        assert result["has_toc"] is False
        assert result["toc_link_count"] == 1


class TestTocNonHeadingAnchors:
    """Anchors to non-heading IDs should not appear in toc_links."""

    def test_non_heading_anchors_excluded(self) -> None:
        html = '<html><body><div id="footer">Footer</div><a href="#footer">Footer</a></body></html>'
        tree = HTMLParser(html)
        result = toc.extract(tree, "https://example.com")
        assert result["toc_link_count"] == 0
        assert result["has_toc"] is False


class TestTocNeverRaises:
    """Extractor must never raise, even on malformed input."""

    def test_malformed_html(self) -> None:
        tree = HTMLParser("<html><<<<>>>></html>")
        result = toc.extract(tree, "https://example.com")
        assert isinstance(result, dict)
        assert "has_toc" in result
        assert result["has_toc"] is False
