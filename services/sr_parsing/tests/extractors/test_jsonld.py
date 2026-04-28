"""Tests for jsonld extractor (EXTR-13)."""
from __future__ import annotations

import json

from selectolax.parser import HTMLParser

from scraper_service.extractors.jsonld import extract


class TestJsonldFromFullPage:
    """Tests using the full_page_html fixture from conftest.py."""

    def test_jsonld_present_and_count(self, full_page_tree: HTMLParser) -> None:
        result = extract(full_page_tree, "https://example.com/seo-tools")
        assert result["jsonld_present"] is True
        assert result["jsonld_count"] == 2

    def test_jsonld_types(self, full_page_tree: HTMLParser) -> None:
        result = extract(full_page_tree, "https://example.com/seo-tools")
        assert "article" in result["jsonld_types"]
        assert "faqpage" in result["jsonld_types"]
        assert "person" in result["jsonld_types"]  # nested in Article author

    def test_has_article_flag(self, full_page_tree: HTMLParser) -> None:
        result = extract(full_page_tree, "https://example.com/seo-tools")
        assert result["has_article"] is True

    def test_has_faq_flag_and_count(self, full_page_tree: HTMLParser) -> None:
        result = extract(full_page_tree, "https://example.com/seo-tools")
        assert result["has_faq"] is True
        assert result["faq_count"] == 2

    def test_article_block_in_jsonld_blocks(self, full_page_tree: HTMLParser) -> None:
        result = extract(full_page_tree, "https://example.com/seo-tools")
        blocks = result["jsonld_blocks"]
        article_block = None
        for block in blocks:
            if isinstance(block, dict) and (block.get("@type") or "").lower() == "article":
                article_block = block
        assert article_block is not None
        assert article_block["headline"] == "Best SEO Tools 2025"

    def test_all_schema_types_includes_all_sources(
        self, full_page_tree: HTMLParser,
    ) -> None:
        result = extract(full_page_tree, "https://example.com/seo-tools")
        # Full page only has JSON-LD, no Microdata/RDFa
        assert "article" in result["all_schema_types"]
        assert "faqpage" in result["all_schema_types"]

    def test_microdata_rdfa_absent(self, full_page_tree: HTMLParser) -> None:
        result = extract(full_page_tree, "https://example.com/seo-tools")
        assert result["microdata_present"] is False
        assert result["rdfa_present"] is False
        assert result["microdata_types"] == []
        assert result["rdfa_types"] == []


class TestJsonldNoSchema:
    """Tests with minimal HTML that has no JSON-LD."""

    def test_no_jsonld(self, minimal_tree: HTMLParser) -> None:
        result = extract(minimal_tree, "https://example.com")
        assert result["jsonld_present"] is False
        assert result["jsonld_count"] == 0
        assert result["jsonld_types"] == []
        assert result["jsonld_blocks"] == []
        assert result["microdata_present"] is False
        assert result["rdfa_present"] is False

    def test_all_has_flags_false(self, minimal_tree: HTMLParser) -> None:
        result = extract(minimal_tree, "https://example.com")
        for key, val in result.items():
            if key.startswith("has_"):
                assert val is False, f"{key} should be False"


class TestJsonldMicrodata:
    """Tests for Microdata detection via BS4 fallback."""

    def test_microdata_product(self) -> None:
        html = '''<html><body>
            <div itemscope itemtype="https://schema.org/Product">
                <span itemprop="name">Widget</span>
            </div>
        </body></html>'''
        tree = HTMLParser(html)
        result = extract(tree, "https://example.com")
        assert result["microdata_present"] is True
        assert "product" in result["microdata_types"]
        assert result["has_product"] is True

    def test_microdata_multiple_types(self) -> None:
        html = '''<html><body>
            <div itemscope itemtype="https://schema.org/Product">
                <span itemprop="name">Widget</span>
            </div>
            <div itemscope itemtype="https://schema.org/Offer">
                <span itemprop="price">$9.99</span>
            </div>
        </body></html>'''
        tree = HTMLParser(html)
        result = extract(tree, "https://example.com")
        assert "product" in result["microdata_types"]
        assert "offer" in result["microdata_types"]


class TestJsonldRdfa:
    """Tests for RDFa detection via BS4 fallback."""

    def test_rdfa_person(self) -> None:
        html = '''<html><body>
            <div typeof="Person">
                <span property="name">Jane Doe</span>
            </div>
        </body></html>'''
        tree = HTMLParser(html)
        result = extract(tree, "https://example.com")
        assert result["rdfa_present"] is True
        assert "person" in result["rdfa_types"]
        assert result["has_person"] is True

    def test_rdfa_and_jsonld_combined(self) -> None:
        html = '''<html><head>
            <script type="application/ld+json">
            {"@context": "https://schema.org", "@type": "Article", "headline": "Test"}
            </script>
        </head><body>
            <div typeof="Person">
                <span property="name">Jane</span>
            </div>
        </body></html>'''
        tree = HTMLParser(html)
        result = extract(tree, "https://example.com")
        assert result["jsonld_present"] is True
        assert result["rdfa_present"] is True
        assert "article" in result["all_schema_types"]
        assert "person" in result["all_schema_types"]


class TestJsonldMalformed:
    """Tests for error handling with malformed content."""

    def test_invalid_json_ld_skipped(self) -> None:
        html = '''<html><head>
            <script type="application/ld+json">{invalid json!!!}</script>
            <script type="application/ld+json">
            {"@context": "https://schema.org", "@type": "Article", "headline": "OK"}
            </script>
        </head><body></body></html>'''
        tree = HTMLParser(html)
        result = extract(tree, "https://example.com")
        # Invalid block silently skipped, only valid one in blocks
        assert result["jsonld_count"] == 1
        assert "article" in result["jsonld_types"]
        assert result["has_article"] is True

    def test_never_raises_on_malformed_html(self) -> None:
        # Totally broken markup should not raise
        tree = HTMLParser("<html><<>>><<<")
        result = extract(tree, "https://example.com")
        assert isinstance(result, dict)
        assert result["jsonld_present"] is False


class TestJsonldHowto:
    """Tests for HowTo schema extraction."""

    def test_howto_steps(self) -> None:
        html = '''<html><head>
            <script type="application/ld+json">
            {
                "@context": "https://schema.org",
                "@type": "HowTo",
                "name": "How to Build a PC",
                "step": [
                    {"@type": "HowToStep", "text": "Buy parts"},
                    {"@type": "HowToStep", "text": "Assemble"},
                    {"@type": "HowToStep", "text": "Install OS"}
                ]
            }
            </script>
        </head><body></body></html>'''
        tree = HTMLParser(html)
        result = extract(tree, "https://example.com")
        assert result["has_howto"] is True
        assert result["howto_steps"] == 3


class TestJsonldRecipe:
    """Tests for Recipe schema extraction."""

    def test_recipe_info(self) -> None:
        html = '''<html><head>
            <script type="application/ld+json">
            {
                "@context": "https://schema.org",
                "@type": "Recipe",
                "name": "Pancakes",
                "cookTime": "PT20M",
                "recipeYield": "4 servings"
            }
            </script>
        </head><body></body></html>'''
        tree = HTMLParser(html)
        result = extract(tree, "https://example.com")
        assert result["has_recipe"] is True
        assert result["recipe_info"] is not None
        assert result["recipe_info"]["name"] == "Pancakes"
        assert result["recipe_info"]["cook_time"] == "PT20M"
        assert result["recipe_info"]["recipe_yield"] == "4 servings"


class TestJsonldBreadcrumb:
    """Tests for BreadcrumbList schema extraction."""

    def test_breadcrumb_items(self) -> None:
        html = '''<html><head>
            <script type="application/ld+json">
            {
                "@context": "https://schema.org",
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "Home"},
                    {"@type": "ListItem", "position": 2, "name": "Tools"},
                    {"@type": "ListItem", "position": 3, "name": "SEO"}
                ]
            }
            </script>
        </head><body></body></html>'''
        tree = HTMLParser(html)
        result = extract(tree, "https://example.com")
        assert result["has_breadcrumb"] is True
        assert result["breadcrumb_items"] == 3
