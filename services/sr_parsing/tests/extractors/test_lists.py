"""Tests for lists extractor (EXTR-06)."""
from __future__ import annotations

from selectolax.parser import HTMLParser

from scraper_service.extractors.lists import extract


class TestListsExtract:
    """Tests for lists.extract()."""

    def test_full_page_lists(self, full_page_tree: HTMLParser) -> None:
        """Full page has TOC ul, Related Articles ul (in aside), and one ol (Steps)."""
        result = extract(full_page_tree, "https://example.com")
        assert result["ul_count"] >= 2  # TOC list + Related Articles list
        assert result["ol_count"] == 1
        # First ordered list should be the "Steps to Get Started"
        assert "Sign up for a free trial of your chosen tool" in result["ordered_lists"][0][0]

    def test_no_lists_returns_empty(self, minimal_tree: HTMLParser) -> None:
        """Page with no lists returns all zeros and empty lists."""
        result = extract(minimal_tree, "https://example.com")
        assert result["ul_count"] == 0
        assert result["ol_count"] == 0
        assert result["total_items"] == 0
        assert result["unordered_lists"] == []
        assert result["ordered_lists"] == []

    def test_nested_list_extracts_outer_items(self) -> None:
        """Nested list items may appear as concatenated text (acceptable for v1)."""
        html = """<html><body><ul>
            <li>Item one
                <ul><li>Sub-item A</li><li>Sub-item B</li></ul>
            </li>
            <li>Item two</li>
        </ul></body></html>"""
        tree = HTMLParser(html)
        result = extract(tree, "https://example.com")
        # Outer list has 2 items (selectolax text() concatenates nested text)
        assert result["ul_count"] >= 1
        # "Item one" should appear in the outer list text
        outer_texts = " ".join(result["unordered_lists"][0])
        assert "Item one" in outer_texts

    def test_empty_ul_excluded(self) -> None:
        """Empty <ul></ul> is excluded from count."""
        html = "<html><body><ul></ul><ul><li>only item</li></ul></body></html>"
        tree = HTMLParser(html)
        result = extract(tree, "https://example.com")
        assert result["ul_count"] == 1
        assert result["total_items"] == 1

    def test_never_raises_on_malformed_html(self) -> None:
        """Extractor never raises on garbage input."""
        html = "<html><body><ul><li>unclosed"
        tree = HTMLParser(html)
        result = extract(tree, "https://example.com")
        assert "ul_count" in result
        assert "ol_count" in result

    def test_returns_all_expected_keys(self, full_page_tree: HTMLParser) -> None:
        """Result dict contains all expected fields."""
        result = extract(full_page_tree, "https://example.com")
        expected_keys = {"unordered_lists", "ordered_lists", "ul_count", "ol_count", "total_items"}
        assert set(result.keys()) == expected_keys

    def test_total_items_matches(self) -> None:
        """total_items equals sum of all ul and ol items."""
        html = """<html><body>
            <ul><li>A</li><li>B</li></ul>
            <ol><li>1</li><li>2</li><li>3</li></ol>
        </body></html>"""
        tree = HTMLParser(html)
        result = extract(tree, "https://example.com")
        assert result["ul_count"] == 1
        assert result["ol_count"] == 1
        assert result["total_items"] == 5  # 2 ul items + 3 ol items
