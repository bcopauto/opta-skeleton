"""Tests for callout_boxes extractor (EXTR-11)."""
from selectolax.parser import HTMLParser

from scraper_service.extractors.callout_boxes import extract


class TestCalloutBoxesFromFixture:
    """Tests using the full_page_html fixture from conftest."""

    def test_detects_callouts(self, full_page_tree):
        result = extract(full_page_tree, "https://example.com")
        assert result["has_callouts"] is True
        # Fixture has <div class="callout notice"> and <div class="alert alert-warning">
        assert result["callout_count"] >= 2

    def test_callout_notice_content(self, full_page_tree):
        result = extract(full_page_tree, "https://example.com")
        notice = [c for c in result["callouts"] if "callout" in c["classes"]]
        assert len(notice) >= 1
        assert "Important: Always track your results over time." in notice[0]["text"]

    def test_alert_warning_content(self, full_page_tree):
        result = extract(full_page_tree, "https://example.com")
        alerts = [c for c in result["callouts"] if "alert" in c["classes"]]
        assert len(alerts) >= 1
        assert alerts[0]["text"].startswith("Warning:")


class TestCalloutBoxesEdgeCases:
    def test_no_callout_elements(self):
        html = "<html><body><p>Just a paragraph</p></body></html>"
        tree = HTMLParser(html)
        result = extract(tree, "https://example.com")
        assert result["has_callouts"] is False
        assert result["callout_count"] == 0
        assert result["callouts"] == []

    def test_role_alert_detected(self):
        html = '<html><body><div role="alert">System alert</div></body></html>'
        tree = HTMLParser(html)
        result = extract(tree, "https://example.com")
        assert result["has_callouts"] is True
        alert = [c for c in result["callouts"] if c["role"] == "alert"]
        assert len(alert) == 1
        assert alert[0]["text"] == "System alert"

    def test_never_raises_on_malformed_html(self):
        tree = HTMLParser("<div class='callout><p>broken")
        result = extract(tree, "https://example.com")
        assert "has_callouts" in result
        assert "callout_count" in result
        assert "callouts" in result

    def test_no_double_counting(self):
        # Element matching multiple selectors counted once
        html = '<div class="callout alert warning" role="alert">Multi-match</div>'
        tree = HTMLParser(html)
        result = extract(tree, "https://example.com")
        # Count how many times "Multi-match" appears
        matches = [c for c in result["callouts"] if c["text"] == "Multi-match"]
        assert len(matches) == 1

    def test_text_truncated_at_500_chars(self):
        long_text = "x" * 600
        html = f'<div class="callout">{long_text}</div>'
        tree = HTMLParser(html)
        result = extract(tree, "https://example.com")
        assert len(result["callouts"][0]["text"]) == 500
