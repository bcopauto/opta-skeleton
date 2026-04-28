"""Tests for title extractor (EXTR-01)."""
from selectolax.parser import HTMLParser

from scraper_service.extractors.title import extract


def test_extracts_title_from_full_page(full_page_tree: HTMLParser) -> None:
    result = extract(full_page_tree, "https://example.com")
    assert result["title"] == "Best SEO Tools 2025 - Complete Guide"
    assert result["title_length"] == 36


def test_missing_title_returns_none(minimal_tree: HTMLParser) -> None:
    result = extract(minimal_tree, "https://example.com")
    assert result["title"] is None
    assert result["title_length"] == 0


def test_empty_title_tag_returns_empty_string() -> None:
    tree = HTMLParser("<html><head><title></title></head><body></body></html>")
    result = extract(tree, "https://example.com")
    assert result["title"] == ""
    assert result["title_length"] == 0


def test_never_raises_on_malformed_html() -> None:
    result = extract(HTMLParser("<html><title>hello"), "https://example.com")
    assert isinstance(result, dict)
    assert "title" in result
    assert "title_length" in result
