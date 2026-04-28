"""Tests for comparison_tables extractor (EXTR-10)."""
from selectolax.parser import HTMLParser

from scraper_service.extractors.comparison_tables import extract


class TestComparisonTablesFromFixture:
    """Tests using the full_page_html fixture from conftest."""

    def test_detects_comparison_table(self, full_page_tree):
        result = extract(full_page_tree, "https://example.com")
        assert result["has_comparison_table"] is True
        assert result["comparison_table_count"] == 1
        # The fixture table has 3 data rows
        assert result["comparison_tables"][0]["row_count"] == 3

    def test_headers_match_fixture(self, full_page_tree):
        result = extract(full_page_tree, "https://example.com")
        table = result["comparison_tables"][0]
        assert table["headers"] == ["Feature", "Ahrefs", "SEMrush", "Moz"]

    def test_rows_have_correct_keys(self, full_page_tree):
        result = extract(full_page_tree, "https://example.com")
        rows = result["comparison_tables"][0]["rows"]
        assert len(rows) == 3
        assert rows[0]["Feature"] == "Keyword Research"
        assert rows[2]["Feature"] == "Site Audit"
        assert rows[2]["Moz"] == "No"


class TestComparisonTablesEdgeCases:
    def test_two_column_table_not_detected(self):
        html = """<table><thead><tr><th>Name</th><th>Value</th></tr></thead>
        <tbody><tr><td>A</td><td>1</td></tr></tbody></table>"""
        tree = HTMLParser(html)
        result = extract(tree, "https://example.com")
        assert result["has_comparison_table"] is False
        assert result["comparison_table_count"] == 0

    def test_three_column_table_no_keywords(self):
        html = """<table><thead><tr><th>City</th><th>Population</th><th>Area</th></tr></thead>
        <tbody><tr><td>Tokyo</td><td>14M</td><td>2194</td></tr></tbody></table>"""
        tree = HTMLParser(html)
        result = extract(tree, "https://example.com")
        assert result["has_comparison_table"] is False

    def test_vs_in_header_detected(self):
        html = """<table><thead><tr><th>Option A vs B</th><th>Score</th><th>Rating</th></tr></thead>
        <tbody><tr><td>A</td><td>90</td><td>5</td></tr></tbody></table>"""
        tree = HTMLParser(html)
        result = extract(tree, "https://example.com")
        assert result["has_comparison_table"] is True

    def test_no_tables(self):
        html = "<html><body><p>No tables here</p></body></html>"
        tree = HTMLParser(html)
        result = extract(tree, "https://example.com")
        assert result["has_comparison_table"] is False
        assert result["comparison_tables"] == []

    def test_never_raises_on_malformed_html(self):
        tree = HTMLParser("<table><tr><th>Feature<th><th>Plan<th>")
        result = extract(tree, "https://example.com")
        # Should return valid structure even with bad HTML
        assert "has_comparison_table" in result
        assert "comparison_table_count" in result
        assert "comparison_tables" in result

    def test_pricing_keyword_detected(self):
        html = """<table><thead><tr><th>Pricing</th><th>Basic</th><th>Pro</th></tr></thead>
        <tbody><tr><td>Monthly</td><td>$9</td><td>$29</td></tr></tbody></table>"""
        tree = HTMLParser(html)
        result = extract(tree, "https://example.com")
        assert result["has_comparison_table"] is True
