"""Tests for pagination extractor."""
from selectolax.parser import HTMLParser

from scraper_service.extractors.pagination import extract


class TestPaginationWithFullPage:
    """Tests using the full_page_html fixture."""

    def test_has_rel_next(self, full_page_tree):
        result = extract(full_page_tree, "https://example.com/seo-tools")
        assert result["has_rel_next"] is True

    def test_rel_next_url(self, full_page_tree):
        result = extract(full_page_tree, "https://example.com/seo-tools")
        assert result["rel_next_url"] == "https://example.com/seo-tools?page=2"

    def test_no_rel_prev(self, full_page_tree):
        result = extract(full_page_tree, "https://example.com/seo-tools")
        assert result["has_rel_prev"] is False
        assert result["rel_prev_url"] is None


class TestPageNumberInUrl:
    def test_page_number_detected(self, full_page_tree):
        result = extract(full_page_tree, "https://example.com/page/3")
        assert result["page_number_in_url"] is True

    def test_page_param_detected(self, full_page_tree):
        result = extract(full_page_tree, "https://example.com/articles?paged=5")
        assert result["page_number_in_url"] is True

    def test_no_page_number(self, full_page_tree):
        result = extract(full_page_tree, "https://example.com/seo-tools")
        assert result["page_number_in_url"] is False


class TestPaginationNoSignals:
    def test_minimal_html_no_pagination(self, minimal_tree):
        result = extract(minimal_tree, "https://example.com")
        assert result["has_rel_next"] is False
        assert result["has_rel_prev"] is False
        assert result["page_number_in_url"] is False
        assert result["has_pagination_nav"] is False
        assert result["has_infinite_scroll"] is False

    def test_returns_seven_fields(self, minimal_tree):
        result = extract(minimal_tree, "https://example.com")
        expected_keys = {
            "has_rel_next", "rel_next_url", "has_rel_prev", "rel_prev_url",
            "page_number_in_url", "has_pagination_nav", "has_infinite_scroll",
        }
        assert set(result.keys()) == expected_keys


class TestPaginationNav:
    def test_pagination_nav_detected_by_class(self):
        html = '<html><body><nav class="pagination"><a>1</a><a>2</a></nav></body></html>'
        tree = HTMLParser(html)
        result = extract(tree, "https://example.com")
        assert result["has_pagination_nav"] is True

    def test_pager_class_detected(self):
        html = '<html><body><div class="pager">1 2 3</div></body></html>'
        tree = HTMLParser(html)
        result = extract(tree, "https://example.com")
        assert result["has_pagination_nav"] is True


class TestInfiniteScroll:
    def test_infinite_scroll_detected(self):
        html = '<html><body><script>var infinite_scroll = true;</script></body></html>'
        tree = HTMLParser(html)
        result = extract(tree, "https://example.com")
        assert result["has_infinite_scroll"] is True


class TestPaginationNeverRaises:
    def test_malformed_html_does_not_raise(self):
        tree = HTMLParser("<html><body><nav><></div>")
        result = extract(tree, "https://example.com")
        assert isinstance(result, dict)
        assert "has_rel_next" in result

    def test_empty_url_does_not_raise(self, minimal_tree):
        result = extract(minimal_tree, "")
        assert isinstance(result, dict)

    def test_none_url_does_not_raise(self, minimal_tree):
        result = extract(minimal_tree, None)
        assert isinstance(result, dict)
