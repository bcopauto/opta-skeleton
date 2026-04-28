"""Tests for content sufficiency checker and model/settings extensions (FETCH-05)."""
from __future__ import annotations

import pytest

from scraper_service.models import PageData, RenderMethod, ScrapeRequest


# ---------------------------------------------------------------------------
# Content sufficiency (sufficiency.py)
# ---------------------------------------------------------------------------


class TestContentSufficient:
    """Tests for is_content_sufficient()."""

    def _make_html(self, body_text: str, extra: str = "") -> str:
        """Helper to build an HTML page with given body text."""
        return f"<html><body><p>{body_text}</p>{extra}</body></html>"

    def test_full_page_returns_true(self) -> None:
        """Body text > 500 chars should be sufficient."""
        from scraper_service.sufficiency import is_content_sufficient

        text = "x" * 501
        assert is_content_sufficient(self._make_html(text)) is True

    def test_short_body_text_returns_false(self) -> None:
        """Body text < 500 chars should be insufficient."""
        from scraper_service.sufficiency import is_content_sufficient

        text = "x" * 200
        assert is_content_sufficient(self._make_html(text)) is False

    def test_noscript_enable_javascript_returns_false(self) -> None:
        """'enable JavaScript' in noscript tag -> insufficient."""
        from scraper_service.sufficiency import is_content_sufficient

        text = "x" * 600
        html = f'<html><body><noscript>Please enable JavaScript to continue.</noscript><p>{text}</p></body></html>'
        assert is_content_sufficient(html) is False

    def test_javascript_is_required_returns_false(self) -> None:
        """'Javascript is required' in body text -> insufficient."""
        from scraper_service.sufficiency import is_content_sufficient

        text = "x" * 600
        html = f"<html><body><p>{text}</p><p>Javascript is required to view this page.</p></body></html>"
        assert is_content_sufficient(html) is False

    def test_javascript_is_disabled_returns_false(self) -> None:
        """'JavaScript is disabled' in body text -> insufficient."""
        from scraper_service.sufficiency import is_content_sufficient

        text = "x" * 600
        html = f"<html><body><p>{text}</p><p>JavaScript is disabled in your browser.</p></body></html>"
        assert is_content_sufficient(html) is False

    def test_requires_javascript_returns_false(self) -> None:
        """'requires JavaScript' in body text -> insufficient."""
        from scraper_service.sufficiency import is_content_sufficient

        text = "x" * 600
        html = f"<html><body><p>{text}</p><p>This site requires JavaScript.</p></body></html>"
        assert is_content_sufficient(html) is False

    def test_js_patterns_case_insensitive(self) -> None:
        """JS-required patterns are checked case-insensitively."""
        from scraper_service.sufficiency import is_content_sufficient

        text = "x" * 600
        html = f"<html><body><p>{text}</p><p>PLEASE ENABLE JAVASCRIPT NOW</p></body></html>"
        assert is_content_sufficient(html) is False

    def test_empty_div_root_returns_false(self) -> None:
        """Empty div#root (SPA root) with only scripts -> insufficient."""
        from scraper_service.sufficiency import is_content_sufficient

        html = '<html><body><div id="root"><script src="app.js"></script></div></body></html>'
        assert is_content_sufficient(html) is False

    def test_empty_div_next_returns_false(self) -> None:
        """Empty div#__next -> insufficient."""
        from scraper_service.sufficiency import is_content_sufficient

        html = '<html><body><div id="__next"></div></body></html>'
        assert is_content_sufficient(html) is False

    def test_empty_div_nuxt_returns_false(self) -> None:
        """Empty div#__nuxt -> insufficient."""
        from scraper_service.sufficiency import is_content_sufficient

        html = '<html><body><div id="__nuxt"></div></body></html>'
        assert is_content_sufficient(html) is False

    def test_empty_div_app_returns_false(self) -> None:
        """Empty div#app -> insufficient."""
        from scraper_service.sufficiency import is_content_sufficient

        html = '<html><body><div id="app"></div></body></html>'
        assert is_content_sufficient(html) is False

    def test_populated_div_root_returns_true(self) -> None:
        """div#root with sufficient content -> sufficient."""
        from scraper_service.sufficiency import is_content_sufficient

        text = "x" * 501
        html = f'<html><body><div id="root"><p>{text}</p></div></body></html>'
        assert is_content_sufficient(html) is True

    def test_custom_min_body_chars(self) -> None:
        """Custom min_body_chars=100 with 200 chars body text -> sufficient."""
        from scraper_service.sufficiency import is_content_sufficient

        text = "x" * 200
        assert is_content_sufficient(self._make_html(text), min_body_chars=100) is True

    def test_empty_string_returns_false(self) -> None:
        """Empty string -> insufficient."""
        from scraper_service.sufficiency import is_content_sufficient

        assert is_content_sufficient("") is False

    def test_strips_script_style_tags(self) -> None:
        """Script and style tags are stripped before counting body chars."""
        from scraper_service.sufficiency import is_content_sufficient

        # 50 chars visible text + lots of script/style junk
        script_junk = '<script>var x = "' + ("a" * 1000) + '";</script>'
        style_junk = "<style>body { color: red; " + ("b" * 1000) + " }</style>"
        html = f"<html><body>{script_junk}{style_junk}<p>{'x' * 50}</p></body></html>"
        # Only 50 visible chars, below default threshold
        assert is_content_sufficient(html) is False


# ---------------------------------------------------------------------------
# Model extensions (RenderMethod.XHR, ScrapeRequest.render_method, PageData.xhr_responses)
# ---------------------------------------------------------------------------


class TestRenderMethodXHR:
    """Tests for XHR in RenderMethod enum."""

    def test_xhr_value(self) -> None:
        assert RenderMethod.XHR == "xhr"

    def test_xhr_is_member(self) -> None:
        assert RenderMethod("xhr") is RenderMethod.XHR


class TestScrapeRequestRenderMethod:
    """Tests for optional render_method field on ScrapeRequest."""

    def test_default_none(self) -> None:
        req = ScrapeRequest(urls=["https://example.com"])
        assert req.render_method is None

    def test_force_httpx(self) -> None:
        req = ScrapeRequest(urls=["https://example.com"], render_method=RenderMethod.HTTPX)
        assert req.render_method is RenderMethod.HTTPX

    def test_force_xhr(self) -> None:
        req = ScrapeRequest(urls=["https://example.com"], render_method=RenderMethod.XHR)
        assert req.render_method is RenderMethod.XHR


class TestPageDataXhrResponses:
    """Tests for xhr_responses field on PageData."""

    def test_default_none(self) -> None:
        pd = PageData(url="https://example.com", final_url="https://example.com")
        assert pd.xhr_responses is None

    def test_with_responses(self) -> None:
        responses = [{"url": "https://api.example.com/data", "status": 200, "body": {"key": "value"}}]
        pd = PageData(
            url="https://example.com",
            final_url="https://example.com",
            xhr_responses=responses,
        )
        assert pd.xhr_responses is not None
        assert len(pd.xhr_responses) == 1
        assert pd.xhr_responses[0]["url"] == "https://api.example.com/data"

    def test_empty_list(self) -> None:
        pd = PageData(
            url="https://example.com",
            final_url="https://example.com",
            xhr_responses=[],
        )
        assert pd.xhr_responses == []


# ---------------------------------------------------------------------------
# Settings extensions (min_body_chars, headless)
# ---------------------------------------------------------------------------


class TestSettingsExtensions:
    """Tests for new Settings fields."""

    def test_min_body_chars_default(self) -> None:
        from scraper_service.settings import Settings

        s = Settings()
        assert s.min_body_chars == 500

    def test_headless_default(self) -> None:
        from scraper_service.settings import Settings

        s = Settings()
        assert s.headless is True
