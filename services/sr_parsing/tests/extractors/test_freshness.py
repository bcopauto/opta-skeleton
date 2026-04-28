"""Tests for the freshness extractor."""
from __future__ import annotations

import pytest
from selectolax.parser import HTMLParser

from scraper_service.extractors.freshness import extract


def _tree(html: str) -> HTMLParser:
    return HTMLParser(html)


URL = "https://example.com/article"


class TestJsonldDates:
    def test_date_published(self) -> None:
        html = '<html><head><script type="application/ld+json">{"@type":"Article","datePublished":"2025-03-15"}</script></head><body></body></html>'
        result = extract(_tree(html), URL)
        assert result["published_date"] == "2025-03-15"
        assert any(d["source"] == "jsonld_published" for d in result["date_sources"])

    def test_date_modified(self) -> None:
        html = '<html><head><script type="application/ld+json">{"@type":"Article","dateModified":"2025-04-01"}</script></head><body></body></html>'
        result = extract(_tree(html), URL)
        assert result["modified_date"] == "2025-04-01"
        assert any(d["source"] == "jsonld_modified" for d in result["date_sources"])

    def test_nested_graph(self) -> None:
        html = '<html><head><script type="application/ld+json">{"@graph":[{"@type":"Article","datePublished":"2025-01-10"}]}</script></head><body></body></html>'
        result = extract(_tree(html), URL)
        assert result["published_date"] == "2025-01-10"


class TestOgMetaDates:
    def test_published_time(self) -> None:
        html = '<html><head><meta property="article:published_time" content="2025-01-10"></head><body></body></html>'
        result = extract(_tree(html), URL)
        assert result["published_date"] == "2025-01-10"
        assert any(d["source"] == "og_published_time" for d in result["date_sources"])

    def test_modified_time(self) -> None:
        html = '<html><head><meta property="article:modified_time" content="2025-02-20"></head><body></body></html>'
        result = extract(_tree(html), URL)
        assert result["modified_date"] == "2025-02-20"
        assert any(d["source"] == "og_modified_time" for d in result["date_sources"])


class TestTimeElement:
    def test_time_datetime(self) -> None:
        html = '<html><body><time datetime="2025-06-01">June 1</time></body></html>'
        result = extract(_tree(html), URL)
        assert any(d["source"] == "time_element" and d["value"] == "2025-06-01" for d in result["date_sources"])


class TestUrlDatePattern:
    def test_year_month(self) -> None:
        result = extract(_tree("<html><body></body></html>"), "https://example.com/2024/06/my-article/")
        assert any(d["source"] == "url_pattern" for d in result["date_sources"])
        assert any("2024-06" in d["value"] for d in result["date_sources"])

    def test_year_month_day(self) -> None:
        result = extract(_tree("<html><body></body></html>"), "https://example.com/2024/01/15/slug/")
        assert any(d["source"] == "url_pattern" and d["value"] == "2024-01-15" for d in result["date_sources"])

    def test_no_date_in_url(self) -> None:
        result = extract(_tree("<html><body></body></html>"), "https://example.com/about/")
        assert not any(d["source"] == "url_pattern" for d in result["date_sources"])


class TestVisibleDate:
    def test_visible_date_in_article(self) -> None:
        html = '<html><body><article>Published January 15, 2025. This is an article.</article></body></html>'
        result = extract(_tree(html), URL)
        assert any(d["source"] == "visible_text" for d in result["date_sources"])


class TestHttpLastModified:
    def test_last_modified_header(self) -> None:
        html = "<html><body></body></html>"
        headers = {"last-modified": "Tue, 01 Apr 2025 12:00:00 GMT"}
        result = extract(_tree(html), URL, response_headers=headers)
        assert result["modified_date"] == "Tue, 01 Apr 2025 12:00:00 GMT"
        assert any(d["source"] == "http_last_modified" for d in result["date_sources"])

    def test_no_headers(self) -> None:
        result = extract(_tree("<html><body></body></html>"), URL, response_headers=None)
        assert not any(d["source"] == "http_last_modified" for d in result["date_sources"])


class TestPriority:
    def test_jsonld_wins_over_og(self) -> None:
        html = """<html><head>
            <meta property="article:published_time" content="2025-01-01">
            <script type="application/ld+json">{"datePublished":"2025-06-15"}</script>
        </head><body></body></html>"""
        result = extract(_tree(html), URL)
        assert result["published_date"] == "2025-06-15"


class TestEdgeCases:
    def test_empty_page(self) -> None:
        result = extract(_tree("<html><body></body></html>"), URL)
        assert result["published_date"] is None
        assert result["modified_date"] is None
        assert result["date_sources"] == []
        assert result["date_source_count"] == 0

    def test_multiple_sources_counted(self) -> None:
        html = """<html><head>
            <meta property="article:published_time" content="2025-01-01">
            <script type="application/ld+json">{"datePublished":"2025-06-15"}</script>
        </head><body><time datetime="2025-03-01">March</time></body></html>"""
        result = extract(_tree(html), URL)
        assert result["date_source_count"] >= 3

    def test_garbage_html_never_raises(self) -> None:
        result = extract(_tree("<<<not html at all>>>"), URL)
        assert isinstance(result, dict)
        assert "published_date" in result

    def test_malformed_jsonld(self) -> None:
        html = '<html><head><script type="application/ld+json">{invalid json}</script></head><body></body></html>'
        result = extract(_tree(html), URL)
        assert isinstance(result, dict)
