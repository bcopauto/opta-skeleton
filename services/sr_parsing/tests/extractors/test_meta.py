"""Tests for meta extractor."""
from selectolax.parser import HTMLParser

from scraper_service.extractors.meta import extract


class TestMetaWithFullPage:
    """Tests using the full_page_html fixture."""

    def test_title(self, full_page_tree):
        result = extract(full_page_tree, "https://example.com/seo-tools")
        assert result["title"] == "Best SEO Tools 2025 - Complete Guide"

    def test_title_length(self, full_page_tree):
        result = extract(full_page_tree, "https://example.com/seo-tools")
        assert result["title_length"] == len("Best SEO Tools 2025 - Complete Guide")

    def test_meta_description(self, full_page_tree):
        result = extract(full_page_tree, "https://example.com/seo-tools")
        assert result["meta_description"] == "Comprehensive guide to SEO tools for 2025"

    def test_canonical_url(self, full_page_tree):
        result = extract(full_page_tree, "https://example.com/seo-tools")
        assert result["canonical_url"] == "https://example.com/seo-tools"

    def test_canonical_is_self(self, full_page_tree):
        result = extract(full_page_tree, "https://example.com/seo-tools")
        assert result["canonical_is_self"] is True

    def test_og_title(self, full_page_tree):
        result = extract(full_page_tree, "https://example.com/seo-tools")
        assert result["og_title"] == "Best SEO Tools 2025"

    def test_og_type(self, full_page_tree):
        result = extract(full_page_tree, "https://example.com/seo-tools")
        assert result["og_type"] == "article"

    def test_og_present(self, full_page_tree):
        result = extract(full_page_tree, "https://example.com/seo-tools")
        assert result["og_present"] is True

    def test_twitter_card(self, full_page_tree):
        result = extract(full_page_tree, "https://example.com/seo-tools")
        assert result["twitter_card"] == "summary_large_image"

    def test_twitter_present(self, full_page_tree):
        result = extract(full_page_tree, "https://example.com/seo-tools")
        assert result["twitter_present"] is True

    def test_hreflang_count(self, full_page_tree):
        result = extract(full_page_tree, "https://example.com/seo-tools")
        assert result["hreflang_count"] >= 2

    def test_hreflang_x_default(self, full_page_tree):
        result = extract(full_page_tree, "https://example.com/seo-tools")
        assert result["hreflang_x_default"] is True

    def test_hreflang_langs(self, full_page_tree):
        result = extract(full_page_tree, "https://example.com/seo-tools")
        assert "en" in result["hreflang_langs"]
        assert "de" in result["hreflang_langs"]

    def test_robots_noindex_false(self, full_page_tree):
        result = extract(full_page_tree, "https://example.com/seo-tools")
        assert result["robots_noindex"] is False

    def test_robots_nofollow_false(self, full_page_tree):
        result = extract(full_page_tree, "https://example.com/seo-tools")
        assert result["robots_nofollow"] is False

    def test_robots_max_snippet(self, full_page_tree):
        result = extract(full_page_tree, "https://example.com/seo-tools")
        assert result["robots_max_snippet"] == 200

    def test_robots_max_image_preview(self, full_page_tree):
        result = extract(full_page_tree, "https://example.com/seo-tools")
        assert result["robots_max_image_preview"] == "large"

    def test_meta_charset(self, full_page_tree):
        result = extract(full_page_tree, "https://example.com/seo-tools")
        assert result["meta_charset"] == "UTF-8"

    def test_meta_keywords(self, full_page_tree):
        result = extract(full_page_tree, "https://example.com/seo-tools")
        assert result["meta_keywords"] == "seo, tools, 2025"

    def test_meta_author(self, full_page_tree):
        result = extract(full_page_tree, "https://example.com/seo-tools")
        assert result["meta_author"] == "Jane Doe"

    def test_meta_viewport(self, full_page_tree):
        result = extract(full_page_tree, "https://example.com/seo-tools")
        assert result["meta_viewport"] is not None
        assert "width=device-width" in result["meta_viewport"]

    def test_meta_theme_color(self, full_page_tree):
        result = extract(full_page_tree, "https://example.com/seo-tools")
        assert result["meta_theme_color"] == "#ffffff"

    def test_googlebot_directives(self, full_page_tree):
        result = extract(full_page_tree, "https://example.com/seo-tools")
        assert result["googlebot_noindex"] is False
        assert result["googlebot_nofollow"] is False

    def test_returns_forty_plus_fields(self, full_page_tree):
        result = extract(full_page_tree, "https://example.com/seo-tools")
        assert len(result) >= 40


class TestMetaNoTags:
    def test_minimal_html_no_meta(self, minimal_tree):
        result = extract(minimal_tree, "https://example.com")
        assert result["title"] is None
        assert result["og_present"] is False
        assert result["twitter_present"] is False

    def test_meta_description_none_when_absent(self, minimal_tree):
        result = extract(minimal_tree, "https://example.com")
        assert result["meta_description"] is None

    def test_canonical_none_when_absent(self, minimal_tree):
        result = extract(minimal_tree, "https://example.com")
        assert result["canonical_url"] is None
        assert result["canonical_is_self"] is None


class TestMetaNeverRaises:
    def test_malformed_html_does_not_raise(self):
        tree = HTMLParser("<html><head><meta</div></body>")
        result = extract(tree, "https://example.com")
        assert isinstance(result, dict)
        assert "title" in result

    def test_empty_url_does_not_raise(self, minimal_tree):
        result = extract(minimal_tree, "")
        assert isinstance(result, dict)

    def test_none_url_does_not_raise(self, minimal_tree):
        result = extract(minimal_tree, None)
        assert isinstance(result, dict)
