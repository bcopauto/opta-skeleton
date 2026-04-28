"""Tests for technical extractor."""
from selectolax.parser import HTMLParser

from scraper_service.extractors.technical import extract


class TestTechnicalWithFullPage:
    """Tests using the full_page_html fixture."""

    def test_is_https(self, full_page_tree):
        result = extract(full_page_tree, "https://example.com/seo-tools")
        assert result["is_https"] is True

    def test_has_viewport(self, full_page_tree):
        result = extract(full_page_tree, "https://example.com/seo-tools")
        assert result["has_viewport"] is True

    def test_total_scripts_at_least_two(self, full_page_tree):
        # Two JSON-LD scripts in the fixture
        result = extract(full_page_tree, "https://example.com/seo-tools")
        assert result["total_scripts"] >= 2

    def test_charset(self, full_page_tree):
        result = extract(full_page_tree, "https://example.com/seo-tools")
        assert result["charset"] == "UTF-8"

    def test_has_favicon(self, full_page_tree):
        result = extract(full_page_tree, "https://example.com/seo-tools")
        assert result["has_favicon"] is True

    def test_has_apple_touch_icon(self, full_page_tree):
        result = extract(full_page_tree, "https://example.com/seo-tools")
        assert result["has_apple_touch_icon"] is True

    def test_returns_thirty_plus_fields(self, full_page_tree):
        result = extract(full_page_tree, "https://example.com/seo-tools")
        assert len(result) >= 30

    def test_resource_hints_are_int(self, full_page_tree):
        result = extract(full_page_tree, "https://example.com/seo-tools")
        assert isinstance(result["dns_prefetch_count"], int)
        assert isinstance(result["preconnect_count"], int)
        assert isinstance(result["preload_count"], int)


class TestTechnicalWithTrackerScript:
    def test_google_analytics_detected(self):
        html = (
            '<html><head></head><body>'
            '<script src="https://www.google-analytics.com/analytics.js"></script>'
            '</body></html>'
        )
        tree = HTMLParser(html)
        result = extract(tree, "https://example.com")
        assert result["has_google_analytics"] is True

    def test_gtm_detected(self):
        html = (
            '<html><head></head><body>'
            '<script>googletagmanager.com/gtag/js?id=G-XXXXX</script>'
            '</body></html>'
        )
        tree = HTMLParser(html)
        result = extract(tree, "https://example.com")
        assert result["has_gtm"] is True


class TestTechnicalNoScripts:
    def test_no_scripts_returns_zero(self, minimal_tree):
        result = extract(minimal_tree, "https://example.com")
        assert result["total_scripts"] == 0
        assert result["inline_scripts"] == 0
        assert result["external_scripts"] == 0


class TestTechnicalNeverRaises:
    def test_malformed_html_does_not_raise(self):
        tree = HTMLParser("<html><head><script></div></body>")
        result = extract(tree, "https://example.com")
        assert isinstance(result, dict)
        assert "total_scripts" in result

    def test_empty_url_does_not_raise(self, minimal_tree):
        result = extract(minimal_tree, "")
        assert isinstance(result, dict)

    def test_none_url_does_not_raise(self, minimal_tree):
        result = extract(minimal_tree, None)
        assert isinstance(result, dict)
