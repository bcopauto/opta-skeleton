"""Tests for links extractor."""
from selectolax.parser import HTMLParser

from scraper_service.extractors.links import extract


class TestLinksWithFullPage:
    """Tests using the full_page_html fixture."""

    def test_total_links_greater_than_five(self, full_page_tree):
        result = extract(full_page_tree, "https://example.com/seo-tools")
        assert result["total_links"] > 5

    def test_external_links_at_least_one(self, full_page_tree):
        # ahrefs.com is the only truly external domain in the fixture
        result = extract(full_page_tree, "https://example.com/seo-tools")
        assert result["external_links"] >= 1

    def test_nofollow_links_at_least_one(self, full_page_tree):
        # The Ahrefs link has rel="nofollow"
        result = extract(full_page_tree, "https://example.com/seo-tools")
        assert result["nofollow_links"] >= 1

    def test_internal_links_include_relative(self, full_page_tree):
        result = extract(full_page_tree, "https://example.com/seo-tools")
        assert result["internal_links"] >= 3  # Home, About, Internal Page, etc.

    def test_top_external_domains_contains_ahrefs(self, full_page_tree):
        result = extract(full_page_tree, "https://example.com/seo-tools")
        assert "ahrefs.com" in result["top_external_domains"]

    def test_returns_seventeen_fields(self, full_page_tree):
        result = extract(full_page_tree, "https://example.com/seo-tools")
        expected_keys = {
            "total_links", "internal_links", "external_links",
            "nofollow_links", "sponsored_links", "ugc_links",
            "noreferrer_links", "noopener_links", "blank_target_links",
            "http_external_links", "empty_anchor_links",
            "image_only_anchor_links", "generic_anchor_links",
            "unique_external_domains", "top_external_domains",
            "top_anchor_texts",
        }
        assert set(result.keys()) == expected_keys


class TestLinksWithNoLinks:
    def test_no_links_returns_zero(self, minimal_tree):
        result = extract(minimal_tree, "https://example.com")
        assert result["total_links"] == 0
        assert result["internal_links"] == 0
        assert result["external_links"] == 0


class TestLinksMailtoExclusion:
    def test_mailto_not_counted(self):
        html = '<html><body><a href="mailto:test@example.com">Email</a></body></html>'
        tree = HTMLParser(html)
        result = extract(tree, "https://example.com")
        assert result["total_links"] == 0


class TestLinksNeverRaises:
    def test_malformed_html_does_not_raise(self):
        tree = HTMLParser("<html><body><a href=>broken</a><></div>")
        result = extract(tree, "https://example.com")
        assert isinstance(result, dict)
        assert "total_links" in result

    def test_empty_url_does_not_raise(self, full_page_tree):
        result = extract(full_page_tree, "")
        assert isinstance(result, dict)

    def test_none_url_does_not_raise(self, full_page_tree):
        result = extract(full_page_tree, None)
        assert isinstance(result, dict)
