"""Tests for step_by_step extractor (EXTR-12)."""
import json

from selectolax.parser import HTMLParser

from scraper_service.extractors.step_by_step import extract


class TestStepByStepFromFixture:
    """Tests using the full_page_html fixture from conftest."""

    def test_detects_html_steps(self, full_page_tree):
        result = extract(full_page_tree, "https://example.com")
        assert result["has_steps"] is True
        assert result["html_step_groups"] == 1

    def test_html_steps_content(self, full_page_tree):
        result = extract(full_page_tree, "https://example.com")
        group = result["html_steps"][0]
        assert group["heading"] == "Steps to Get Started"
        assert group["steps"][0].startswith("Sign up for a free trial")
        assert len(group["steps"]) == 3

    def test_total_step_count(self, full_page_tree):
        result = extract(full_page_tree, "https://example.com")
        # 3 HTML steps, 0 schema steps
        assert result["total_step_count"] == 3


class TestStepByStepHowToSchema:
    def test_howto_schema_detected(self):
        schema = json.dumps({
            "@context": "https://schema.org",
            "@type": "HowTo",
            "step": [
                {"text": "Step one: do this"},
                {"text": "Step two: do that"},
                {"name": "Step three"},
            ],
        })
        html = f'<html><head><script type="application/ld+json">{schema}</script></head><body></body></html>'
        tree = HTMLParser(html)
        result = extract(tree, "https://example.com")
        assert result["has_steps"] is True
        assert result["schema_step_count"] == 3
        assert "Step one: do this" in result["schema_steps"]
        assert "Step three" in result["schema_steps"]

    def test_howto_schema_uses_name_fallback(self):
        schema = json.dumps({
            "@context": "https://schema.org",
            "@type": "HowTo",
            "step": [
                {"name": "Named step only"},
            ],
        })
        html = f'<html><head><script type="application/ld+json">{schema}</script></head><body></body></html>'
        tree = HTMLParser(html)
        result = extract(tree, "https://example.com")
        assert result["schema_steps"] == ["Named step only"]


class TestStepByStepEdgeCases:
    def test_ol_without_step_heading(self):
        html = """<html><body><h2>Ingredients</h2><ol><li>Flour</li><li>Sugar</li></ol></body></html>"""
        tree = HTMLParser(html)
        result = extract(tree, "https://example.com")
        assert result["has_steps"] is False

    def test_no_step_patterns(self):
        html = "<html><body><p>Just text</p></body></html>"
        tree = HTMLParser(html)
        result = extract(tree, "https://example.com")
        assert result["has_steps"] is False
        assert result["schema_step_count"] == 0
        assert result["html_step_groups"] == 0
        assert result["total_step_count"] == 0

    def test_never_raises_on_malformed_html(self):
        tree = HTMLParser("<h2>Steps<h2><ol><li>Step 1<li>")
        result = extract(tree, "https://example.com")
        assert "has_steps" in result
        assert "schema_steps" in result
        assert "html_steps" in result

    def test_never_raises_on_invalid_jsonld(self):
        html = """<html><head><script type="application/ld+json">{invalid json}</script></head>
        <body></body></html>"""
        tree = HTMLParser(html)
        result = extract(tree, "https://example.com")
        assert result["has_steps"] is False
        assert result["schema_step_count"] == 0

    def test_heading_with_how_to_keyword(self):
        html = """<html><body><h2>How to Optimize Your Site</h2>
        <ol><li>Fix meta tags</li><li>Improve speed</li></ol></body></html>"""
        tree = HTMLParser(html)
        result = extract(tree, "https://example.com")
        assert result["has_steps"] is True
        assert result["html_steps"][0]["heading"] == "How to Optimize Your Site"

    def test_non_howto_schema_ignored(self):
        schema = json.dumps({
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": "Not a how-to",
        })
        html = f'<html><head><script type="application/ld+json">{schema}</script></head><body></body></html>'
        tree = HTMLParser(html)
        result = extract(tree, "https://example.com")
        assert result["schema_step_count"] == 0
