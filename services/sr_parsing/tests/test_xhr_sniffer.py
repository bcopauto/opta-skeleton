"""Tests for XHR data sniffer (FETCH-06, FETCH-07)."""
from __future__ import annotations

import json

import pytest


class TestExtractXhrContent:
    """Tests for extract_xhr_content() function."""

    def _next_data_html(self, page_props: dict) -> str:
        """Build HTML with __NEXT_DATA__ script tag."""
        data = {"props": {"pageProps": page_props}}
        return (
            '<html><head>'
            f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script>'
            '</head><body><div id="__next"></div></body></html>'
        )

    def _nuxt_assignment_html(self, nuxt_data: dict) -> str:
        """Build HTML with __NUXT__ assignment in script tag."""
        return (
            '<html><head>'
            f'<script>window.__NUXT__ = {json.dumps(nuxt_data)};</script>'
            '</head><body><div id="__nuxt"></div></body></html>'
        )

    def _apollo_assignment_html(self, apollo_data: dict) -> str:
        """Build HTML with __APOLLO_STATE__ assignment in script tag."""
        return (
            '<html><head>'
            f'<script>window.__APOLLO_STATE__ = {json.dumps(apollo_data)};</script>'
            '</head><body></body></html>'
        )

    def test_next_data_with_content_key(self) -> None:
        """__NEXT_DATA__ with props.pageProps.content returns the content string."""
        from scraper_service.xhr_sniffer import extract_xhr_content

        content = "This is a long article body. " * 10  # > 100 chars
        html = self._next_data_html({"content": content})
        result = extract_xhr_content(html)
        assert result is not None
        assert content in result

    def test_next_data_with_body_key(self) -> None:
        """__NEXT_DATA__ with props.pageProps.body returns the body string."""
        from scraper_service.xhr_sniffer import extract_xhr_content

        body = "Article body text that is long enough. " * 10
        html = self._next_data_html({"body": body})
        result = extract_xhr_content(html)
        assert result is not None
        assert body in result

    def test_next_data_empty_page_props(self) -> None:
        """__NEXT_DATA__ with empty pageProps returns None."""
        from scraper_service.xhr_sniffer import extract_xhr_content

        html = self._next_data_html({})
        result = extract_xhr_content(html)
        assert result is None

    def test_next_data_malformed_json(self) -> None:
        """__NEXT_DATA__ with malformed JSON returns None."""
        from scraper_service.xhr_sniffer import extract_xhr_content

        html = (
            '<html><head>'
            '<script id="__NEXT_DATA__" type="application/json">{invalid json}</script>'
            '</head><body></body></html>'
        )
        result = extract_xhr_content(html)
        assert result is None

    def test_nuxt_data_reconstruction(self) -> None:
        """__NUXT__ assignment returns reconstructed HTML."""
        from scraper_service.xhr_sniffer import extract_xhr_content

        nuxt_data = {"data": [{"content": "x" * 150}]}
        html = self._nuxt_assignment_html(nuxt_data)
        result = extract_xhr_content(html)
        assert result is not None

    def test_apollo_state_reconstruction(self) -> None:
        """__APOLLO_STATE__ assignment returns reconstructed HTML."""
        from scraper_service.xhr_sniffer import extract_xhr_content

        apollo_data = {
            "Article:1": {"__typename": "Article", "body": "x" * 60},
            "Article:2": {"__typename": "Article", "body": "y" * 60},
        }
        html = self._apollo_assignment_html(apollo_data)
        result = extract_xhr_content(html)
        assert result is not None

    def test_no_framework_data_returns_none(self) -> None:
        """No framework data present returns None."""
        from scraper_service.xhr_sniffer import extract_xhr_content

        html = "<html><body><p>Hello world</p></body></html>"
        result = extract_xhr_content(html)
        assert result is None

    def test_multiple_frameworks_returns_first(self) -> None:
        """When multiple frameworks present, returns first successful extraction."""
        from scraper_service.xhr_sniffer import extract_xhr_content

        data = {"props": {"pageProps": {"content": "x" * 150}}}
        next_tag = f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script>'
        nuxt_tag = f'<script>window.__NUXT__ = {json.dumps({"data": {"content": "y" * 150}})};</script>'
        html = f"<html><head>{next_tag}{nuxt_tag}</head><body></body></html>"
        result = extract_xhr_content(html)
        assert result is not None
        assert "x" * 150 in result

    def test_next_data_with_html_key(self) -> None:
        """__NEXT_DATA__ with props.pageProps.html returns the html string."""
        from scraper_service.xhr_sniffer import extract_xhr_content

        html_content = "<p>Rich content here that is quite long. </p>" * 10
        html = self._next_data_html({"html": html_content})
        result = extract_xhr_content(html)
        assert result is not None
        assert html_content in result

    def test_next_data_fallback_json_dump(self) -> None:
        """__NEXT_DATA__ with unknown keys returns JSON-wrapped HTML."""
        from scraper_service.xhr_sniffer import extract_xhr_content

        props = {"customField": "x" * 200, "otherField": "y" * 200}
        html = self._next_data_html(props)
        result = extract_xhr_content(html)
        assert result is not None
        assert "<html>" in result.lower() or "customField" in result


class TestExtractScriptJson:
    """Tests for _extract_script_json() helper."""

    def test_extracts_valid_json(self) -> None:
        """Extracts JSON from a script tag with matching id."""
        from scraper_service.xhr_sniffer import _extract_script_json

        html = '<script id="test-id" type="application/json">{"key": "value"}</script>'
        result = _extract_script_json(html, "test-id")
        assert result == {"key": "value"}

    def test_returns_none_on_missing_id(self) -> None:
        """Returns None when script tag id doesn't match."""
        from scraper_service.xhr_sniffer import _extract_script_json

        html = '<script id="other-id" type="application/json">{"key": "value"}</script>'
        result = _extract_script_json(html, "test-id")
        assert result is None

    def test_returns_none_on_invalid_json(self) -> None:
        """Returns None when script tag content is not valid JSON."""
        from scraper_service.xhr_sniffer import _extract_script_json

        html = '<script id="test-id" type="application/json">not json</script>'
        result = _extract_script_json(html, "test-id")
        assert result is None


class TestExtractAssignmentJson:
    """Tests for _extract_assignment_json() helper."""

    def test_extracts_valid_assignment(self) -> None:
        """Extracts JSON from window.__VAR__ = {...} pattern."""
        from scraper_service.xhr_sniffer import _extract_assignment_json

        html = '<script>window.__TEST__ = {"key": "value"};</script>'
        result = _extract_assignment_json(html, "__TEST__")
        assert result == {"key": "value"}

    def test_returns_none_on_missing_var(self) -> None:
        """Returns None when variable name is not in the HTML."""
        from scraper_service.xhr_sniffer import _extract_assignment_json

        html = '<script>window.__OTHER__ = {"key": "value"};</script>'
        result = _extract_assignment_json(html, "__TEST__")
        assert result is None

    def test_returns_none_on_invalid_json(self) -> None:
        """Returns None when the assignment value is not valid JSON."""
        from scraper_service.xhr_sniffer import _extract_assignment_json

        html = '<script>window.__TEST__ = {broken};</script>'
        result = _extract_assignment_json(html, "__TEST__")
        assert result is None
