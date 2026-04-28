"""Tests for headings extractor (EXTR-03)."""
from selectolax.parser import HTMLParser

from scraper_service.extractors.headings import extract


def test_full_page_heading_counts(full_page_tree: HTMLParser) -> None:
    result = extract(full_page_tree, "https://example.com")
    # h1: "Best SEO Tools 2025" (1)
    # h2: Table of Contents, Keyword Research Tools, Technical SEO Tools, Tool Comparison, Steps to Get Started (5)
    # h3: Ahrefs Keywords Explorer, SEMrush Keyword Magic, Related Articles (3)
    assert result["h1_count"] == 1
    assert result["h2_count"] == 5
    assert result["h3_count"] == 3
    assert result["h4_count"] == 0
    assert result["h5_count"] == 0
    assert result["h6_count"] == 0
    assert result["h1_texts"] == ["Best SEO Tools 2025"]
    assert result["duplicate_h1"] is False


def test_no_headings_returns_empty(minimal_tree: HTMLParser) -> None:
    result = extract(minimal_tree, "https://example.com")
    assert result["h1_count"] == 0
    assert result["h2_count"] == 0
    assert result["h3_count"] == 0
    assert result["total_headings"] == 0
    assert result["h1_texts"] == []
    assert result["h2_texts"] == []
    assert result["hierarchy_issues"] == []
    assert result["duplicate_h1"] is False
    assert result["empty_headings"] == 0


def test_hierarchy_issue_detected() -> None:
    html = "<html><body><h3>before h2</h3><h2>after</h2></body></html>"
    tree = HTMLParser(html)
    result = extract(tree, "https://example.com")
    assert "h3 before h2" in result["hierarchy_issues"]


def test_duplicate_h1_detected() -> None:
    html = "<html><body><h1>First</h1><h2>Section</h2><h1>Second</h1></body></html>"
    tree = HTMLParser(html)
    result = extract(tree, "https://example.com")
    assert result["duplicate_h1"] is True
    assert result["h1_count"] == 2


def test_empty_heading_counted() -> None:
    html = "<html><body><h1></h1><h2>Not empty</h2></body></html>"
    tree = HTMLParser(html)
    result = extract(tree, "https://example.com")
    assert result["empty_headings"] == 1


def test_never_raises_on_malformed_html() -> None:
    result = extract(HTMLParser("<html><body><h1>hello"), "https://example.com")
    assert isinstance(result, dict)
    assert "h1_count" in result
    assert "hierarchy_issues" in result


def test_heading_word_count() -> None:
    html = "<html><body><h1>Hello World</h1><h2>Three Word Title</h2></body></html>"
    tree = HTMLParser(html)
    result = extract(tree, "https://example.com")
    # "Hello World" = 2 words, "Three Word Title" = 3 words = 5 total
    assert result["heading_word_count"] == 5
