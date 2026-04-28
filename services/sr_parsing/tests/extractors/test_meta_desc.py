"""Tests for meta_desc extractor (EXTR-02)."""
from selectolax.parser import HTMLParser

from scraper_service.extractors.meta_desc import extract


def test_extracts_description_from_full_page(full_page_tree: HTMLParser) -> None:
    result = extract(full_page_tree, "https://example.com")
    assert result["meta_description"] == "Comprehensive guide to SEO tools for 2025"
    assert result["meta_description_length"] == 41


def test_missing_description_returns_none(minimal_tree: HTMLParser) -> None:
    result = extract(minimal_tree, "https://example.com")
    assert result["meta_description"] is None
    assert result["meta_description_length"] == 0


def test_empty_content_returns_none() -> None:
    html = '<html><head><meta name="description" content=""></head><body></body></html>'
    tree = HTMLParser(html)
    result = extract(tree, "https://example.com")
    assert result["meta_description"] is None
    assert result["meta_description_length"] == 0


def test_whitespace_only_content_returns_none() -> None:
    html = '<html><head><meta name="description" content="   "></head><body></body></html>'
    tree = HTMLParser(html)
    result = extract(tree, "https://example.com")
    assert result["meta_description"] is None
    assert result["meta_description_length"] == 0


def test_never_raises_on_malformed_html() -> None:
    result = extract(HTMLParser("<html><meta name=description content=oops"), "https://example.com")
    assert isinstance(result, dict)
    assert "meta_description" in result
    assert "meta_description_length" in result
