"""Tests for tables extractor (EXTR-05)."""
from __future__ import annotations

from selectolax.parser import HTMLParser

from scraper_service.extractors.tables import extract


class TestTablesExtract:
    """Tests for tables.extract()."""

    def test_full_page_returns_one_table(self, full_page_tree: HTMLParser) -> None:
        """Full page fixture has one table with thead + tbody."""
        result = extract(full_page_tree, "https://example.com")
        assert result["table_count"] == 1
        assert len(result["tables"]) == 1

        table = result["tables"][0]
        assert len(table) == 3  # 3 data rows
        assert table[0] == {"Feature": "Keyword Research", "Ahrefs": "Yes", "SEMrush": "Yes", "Moz": "Yes"}
        assert table[1] == {"Feature": "Backlink Analysis", "Ahrefs": "Yes", "SEMrush": "Yes", "Moz": "Yes"}
        assert table[2] == {"Feature": "Site Audit", "Ahrefs": "Yes", "SEMrush": "Yes", "Moz": "No"}

    def test_no_tables_returns_empty(self, minimal_tree: HTMLParser) -> None:
        """Page with no tables returns zero count and empty list."""
        result = extract(minimal_tree, "https://example.com")
        assert result["table_count"] == 0
        assert result["tables"] == []

    def test_table_with_th_in_first_tr(self) -> None:
        """Table with no <thead> but <th> in first <tr> extracts headers correctly."""
        html = """<html><body><table>
            <tr><th>Name</th><th>Age</th></tr>
            <tr><td>Alice</td><td>30</td></tr>
            <tr><td>Bob</td><td>25</td></tr>
        </table></body></html>"""
        tree = HTMLParser(html)
        result = extract(tree, "https://example.com")
        assert result["table_count"] == 1
        table = result["tables"][0]
        assert len(table) == 2
        assert table[0] == {"Name": "Alice", "Age": "30"}
        assert table[1] == {"Name": "Bob", "Age": "25"}

    def test_table_no_headers_uses_col_keys(self) -> None:
        """Table with no <th> at all uses col_0, col_1 keys."""
        html = """<html><body><table>
            <tr><td>Alpha</td><td>100</td></tr>
            <tr><td>Beta</td><td>200</td></tr>
        </table></body></html>"""
        tree = HTMLParser(html)
        result = extract(tree, "https://example.com")
        assert result["table_count"] == 1
        table = result["tables"][0]
        assert table[0] == {"col_0": "Alpha", "col_1": "100"}
        assert table[1] == {"col_0": "Beta", "col_1": "200"}

    def test_never_raises_on_malformed_html(self) -> None:
        """Extractor never raises on broken table markup."""
        html = "<html><body><table><tr><td>broken</table></body></html>"
        tree = HTMLParser(html)
        result = extract(tree, "https://example.com")
        assert "table_count" in result
        assert "tables" in result

    def test_returns_all_expected_keys(self, full_page_tree: HTMLParser) -> None:
        """Result dict contains table_count and tables."""
        result = extract(full_page_tree, "https://example.com")
        assert set(result.keys()) == {"table_count", "tables"}

    def test_more_columns_than_headers(self) -> None:
        """Rows with more columns than headers get col_N keys for extras."""
        html = """<html><body><table>
            <thead><tr><th>A</th><th>B</th></tr></thead>
            <tbody><tr><td>1</td><td>2</td><td>3</td></tr></tbody>
        </table></body></html>"""
        tree = HTMLParser(html)
        result = extract(tree, "https://example.com")
        table = result["tables"][0]
        assert table[0] == {"A": "1", "B": "2", "col_2": "3"}
