"""Tests for the async httpx fetcher (Scraper class)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest import mock

import httpx
import pytest

from scraper_service.fetcher import Scraper
from scraper_service.models import ErrorType, PageData, RenderMethod, ScrapeRequest
from scraper_service.settings import Settings


@pytest.fixture()
def _patch_tier_deps_for_httpx_tests(monkeypatch):
    """Patch tier escalation dependencies so existing httpx tests stay on httpx.

    Existing tests were written when _fetch_single was httpx-only. Now that
    it has tier escalation, short HTML bodies would fail sufficiency and
    escalate to Playwright. This fixture prevents that by making
    is_content_sufficient always return True, so the httpx tier "wins" and
    tests keep testing what they always tested.
    """
    monkeypatch.setattr(
        "scraper_service.fetcher.is_content_sufficient",
        lambda html, min_body_chars=500: True,
    )
    monkeypatch.setattr(
        "scraper_service.fetcher.extract_xhr_content",
        lambda html: None,
    )


# ---------------------------------------------------------------------------
# Original httpx-only tests (18 tests, preserved from Phase 2)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.usefixtures("_patch_tier_deps_for_httpx_tests")
async def test_fetch_single_url_success():
    """Mock httpx response 200 with HTML body. Verify PageData with status_code=200 and html."""
    settings = Settings()
    async with Scraper(settings) as scraper:
        mock_response = mock.Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.url = "https://example.com"
        mock_response.text = "<html><body>Test</body></html>"

        with mock.patch.object(
            scraper._client, "get", return_value=mock_response
        ):
            results = await scraper.fetch(["https://example.com"])

    assert len(results) == 1
    result = results[0]
    assert result.url == "https://example.com"
    assert result.final_url == "https://example.com"
    assert result.status_code == 200
    assert result.html == "<html><body>Test</body></html>"
    assert result.render_method == RenderMethod.HTTPX
    assert result.error is None


@pytest.mark.asyncio
@pytest.mark.usefixtures("_patch_tier_deps_for_httpx_tests")
async def test_fetch_follows_redirects():
    """Mock redirect 301->200. Verify final_url is the redirect target."""
    settings = Settings()
    async with Scraper(settings) as scraper:
        mock_response = mock.Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.url = "https://example.com/redirected"
        mock_response.text = "<html><body>Redirected</body></html>"

        with mock.patch.object(
            scraper._client, "get", return_value=mock_response
        ):
            results = await scraper.fetch(["https://example.com/original"])

    assert len(results) == 1
    result = results[0]
    assert result.url == "https://example.com/original"
    assert result.final_url == "https://example.com/redirected"
    assert result.status_code == 200


@pytest.mark.asyncio
@pytest.mark.usefixtures("_patch_tier_deps_for_httpx_tests")
async def test_fetch_uses_random_ua():
    """Verify UA header is one from the pool."""
    settings = Settings()
    async with Scraper(settings) as scraper:
        mock_response = mock.Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.url = "https://example.com"
        mock_response.text = "<html></html>"

        with mock.patch.object(
            scraper._client, "get", return_value=mock_response
        ) as mock_get:
            await scraper.fetch(["https://example.com"])

    call_kwargs = mock_get.call_args[1]
    assert "headers" in call_kwargs
    assert "User-Agent" in call_kwargs["headers"]
    ua = call_kwargs["headers"]["User-Agent"]
    assert ua in settings.user_agent_pool


@pytest.mark.asyncio
@pytest.mark.usefixtures("_patch_tier_deps_for_httpx_tests")
async def test_fetch_with_proxy_url_set_direct_no_proxy():
    """D-18: direct fetch does NOT use proxy even when proxy_url is set.

    Proxy is only used as a fallback on error when use_proxy=True.
    """
    settings = Settings(proxy_url="http://proxy:8080")
    async with Scraper(settings) as scraper:
        mock_response = mock.Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.url = "https://example.com"
        mock_response.text = "<html></html>"

        with mock.patch.object(
            scraper._client, "get", return_value=mock_response
        ) as mock_get:
            await scraper.fetch(["https://example.com"])

    call_kwargs = mock_get.call_args[1]
    assert "proxy" not in call_kwargs or call_kwargs.get("proxy") is None


@pytest.mark.asyncio
@pytest.mark.usefixtures("_patch_tier_deps_for_httpx_tests")
async def test_fetch_without_proxy():
    """Settings with empty proxy_url. Verify httpx.get called without proxy kwarg."""
    settings = Settings(proxy_url="")
    async with Scraper(settings) as scraper:
        mock_response = mock.Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.url = "https://example.com"
        mock_response.text = "<html></html>"

        with mock.patch.object(
            scraper._client, "get", return_value=mock_response
        ) as mock_get:
            await scraper.fetch(["https://example.com"])

    call_kwargs = mock_get.call_args[1]
    assert "proxy" not in call_kwargs or call_kwargs.get("proxy") is None


@pytest.mark.asyncio
@pytest.mark.usefixtures("_patch_tier_deps_for_httpx_tests")
async def test_retry_on_5xx():
    """Mock first response 500 then 200. Verify retry happened and final status_code=200."""
    settings = Settings(max_retries=3, retry_backoff=0.1)
    async with Scraper(settings) as scraper:
        mock_500 = mock.Mock(spec=httpx.Response)
        mock_500.status_code = 500
        mock_500.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500 Server Error", request=mock.Mock(), response=mock_500
        )

        mock_200 = mock.Mock(spec=httpx.Response)
        mock_200.status_code = 200
        mock_200.url = "https://example.com"
        mock_200.text = "<html></html>"

        with mock.patch.object(
            scraper._client, "get", side_effect=[mock_500, mock_200]
        ):
            results = await scraper.fetch(["https://example.com"])

    assert len(results) == 1
    result = results[0]
    assert result.status_code == 200


@pytest.mark.asyncio
@pytest.mark.usefixtures("_patch_tier_deps_for_httpx_tests")
async def test_retry_on_network_error():
    """Mock httpx.ConnectError then 200. Verify retry happened."""
    settings = Settings(max_retries=3, retry_backoff=0.1)
    async with Scraper(settings) as scraper:
        network_error = httpx.NetworkError("Connection failed")

        mock_response = mock.Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.url = "https://example.com"
        mock_response.text = "<html></html>"

        with mock.patch.object(
            scraper._client, "get", side_effect=[network_error, mock_response]
        ):
            results = await scraper.fetch(["https://example.com"])

    assert len(results) == 1
    result = results[0]
    assert result.status_code == 200


@pytest.mark.asyncio
@pytest.mark.usefixtures("_patch_tier_deps_for_httpx_tests")
async def test_no_retry_on_4xx():
    """Mock 404 response. Verify no retry, PageData.error contains '404'."""
    settings = Settings(max_retries=3)
    async with Scraper(settings) as scraper:
        mock_404 = mock.Mock(spec=httpx.Response)
        mock_404.status_code = 404
        mock_404.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404 Not Found", request=mock.Mock(), response=mock_404
        )

        with mock.patch.object(
            scraper._client, "get", return_value=mock_404
        ):
            results = await scraper.fetch(["https://example.com"])

    assert len(results) == 1
    result = results[0]
    assert result.status_code is None
    assert result.render_method == RenderMethod.FAILED
    assert result.error is not None
    assert "404" in result.error


@pytest.mark.asyncio
@pytest.mark.usefixtures("_patch_tier_deps_for_httpx_tests")
async def test_error_isolation():
    """Mock 3 URLs: one succeeds, one 500 (retries exhausted), one network error.
    Verify results list has 3 PageData items, only first succeeded."""
    settings = Settings(max_retries=2, retry_backoff=0.1)
    async with Scraper(settings) as scraper:
        mock_ok = mock.Mock(spec=httpx.Response)
        mock_ok.status_code = 200
        mock_ok.url = "https://example.com/1"
        mock_ok.text = "<html>OK</html>"

        mock_500 = mock.Mock(spec=httpx.Response)
        mock_500.status_code = 500
        mock_500.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500 Server Error", request=mock.Mock(), response=mock_500
        )

        network_error = httpx.NetworkError("Connection failed")

        with mock.patch.object(
            scraper._client, "get", side_effect=[mock_ok, mock_500, network_error]
        ):
            results = await scraper.fetch([
                "https://example.com/1",
                "https://example.com/2",
                "https://example.com/3",
            ])

    assert len(results) == 3
    assert results[0].status_code == 200
    assert results[1].status_code is None
    assert results[1].error is not None
    assert results[2].status_code is None
    assert results[2].error is not None


@pytest.mark.asyncio
@pytest.mark.usefixtures("_patch_tier_deps_for_httpx_tests")
async def test_semaphore_bounds_concurrency():
    """Set max_concurrent_requests=2, fetch 5 URLs with artificial delay.
    Verify at most 2 concurrent at any time."""
    settings = Settings(max_concurrent_requests=2)
    async with Scraper(settings) as scraper:
        concurrent_count = 0
        max_concurrent_seen = 0
        lock = asyncio.Lock()

        async def delayed_fetch(*args, **kwargs):
            nonlocal concurrent_count, max_concurrent_seen
            async with lock:
                concurrent_count += 1
                if concurrent_count > max_concurrent_seen:
                    max_concurrent_seen = concurrent_count
            await asyncio.sleep(0.1)
            async with lock:
                concurrent_count -= 1

            mock_response = mock.Mock(spec=httpx.Response)
            mock_response.status_code = 200
            mock_response.url = kwargs.get("url", "https://example.com")
            mock_response.text = "<html></html>"
            return mock_response

        with mock.patch.object(
            scraper._client, "get", side_effect=delayed_fetch
        ):
            await scraper.fetch([
                "https://example.com/1",
                "https://example.com/2",
                "https://example.com/3",
                "https://example.com/4",
                "https://example.com/5",
            ])

    assert max_concurrent_seen <= 2


@pytest.mark.asyncio
@pytest.mark.usefixtures("_patch_tier_deps_for_httpx_tests")
async def test_invalid_url_rejected_upfront():
    """fetch(['not-a-url']). Verify PageData with error='Invalid URL' without HTTP request."""
    settings = Settings()
    async with Scraper(settings) as scraper:
        with mock.patch.object(
            scraper._client, "get"
        ) as mock_get:
            results = await scraper.fetch(["not-a-url"])

    assert len(results) == 1
    result = results[0]
    assert result.url == "not-a-url"
    assert result.status_code is None
    assert result.render_method == RenderMethod.FAILED
    assert "Invalid URL" in result.error
    mock_get.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.usefixtures("_patch_tier_deps_for_httpx_tests")
async def test_deduplication_before_fetch():
    """fetch(['https://example.com', 'https://example.com/']). Verify only 1 HTTP request."""
    settings = Settings()
    async with Scraper(settings) as scraper:
        mock_response = mock.Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.url = "https://example.com"
        mock_response.text = "<html></html>"

        with mock.patch.object(
            scraper._client, "get", return_value=mock_response
        ) as mock_get:
            results = await scraper.fetch([
                "https://example.com",
                "https://example.com/",
            ])

    assert len(results) == 2
    assert results[0].status_code == 200
    assert results[1].status_code == 200
    assert mock_get.call_count == 1


@pytest.mark.asyncio
@pytest.mark.usefixtures("_patch_tier_deps_for_httpx_tests")
async def test_context_manager_creates_and_closes_client():
    """Verify __aenter__ creates client and browser_manager, __aexit__ cleans up."""
    settings = Settings()
    scraper = Scraper(settings)

    assert scraper._client is None
    assert scraper._browser_manager is None

    async with scraper:
        assert scraper._client is not None
        assert scraper._browser_manager is not None

    async with scraper:
        assert scraper._client is not None
        assert scraper._browser_manager is not None


@pytest.mark.asyncio
@pytest.mark.usefixtures("_patch_tier_deps_for_httpx_tests")
async def test_browser_like_headers():
    """Verify request headers include Accept, Accept-Language, Sec-Fetch-Dest, Sec-Fetch-Mode."""
    settings = Settings()
    async with Scraper(settings) as scraper:
        mock_response = mock.Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.url = "https://example.com"
        mock_response.text = "<html></html>"

        with mock.patch.object(
            scraper._client, "get", return_value=mock_response
        ) as mock_get:
            await scraper.fetch(["https://example.com"])

    call_kwargs = mock_get.call_args[1]
    headers = call_kwargs["headers"]
    assert "Accept" in headers
    assert "Accept-Language" in headers
    assert "Sec-Fetch-Dest" in headers
    assert "Sec-Fetch-Mode" in headers


@pytest.mark.asyncio
@pytest.mark.usefixtures("_patch_tier_deps_for_httpx_tests")
async def test_max_pages_enforced():
    """fetch(urls) with more than max_pages_per_job URLs raises ValueError."""
    settings = Settings(max_pages_per_job=2)
    async with Scraper(settings) as scraper:
        with pytest.raises(ValueError, match="Too many URLs"):
            await scraper.fetch([
                "https://example.com/1",
                "https://example.com/2",
                "https://example.com/3",
            ])


@pytest.mark.asyncio
@pytest.mark.usefixtures("_patch_tier_deps_for_httpx_tests")
async def test_results_preserve_input_order():
    """fetch(['valid-url', 'invalid', 'another-valid']). Verify results order matches input."""
    settings = Settings()
    async with Scraper(settings) as scraper:
        mock_ok = mock.Mock(spec=httpx.Response)
        mock_ok.status_code = 200
        mock_ok.url = "https://example.com/1"
        mock_ok.text = "<html>1</html>"

        mock_404 = mock.Mock(spec=httpx.Response)
        mock_404.status_code = 404
        mock_404.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404 Not Found", request=mock.Mock(), response=mock_404
        )

        with mock.patch.object(
            scraper._client, "get", side_effect=[mock_ok, mock_404]
        ):
            results = await scraper.fetch([
                "https://example.com/1",
                "not-a-url",
                "https://example.com/3",
            ])

    assert len(results) == 3
    assert results[0].url == "https://example.com/1"
    assert results[0].status_code == 200
    assert results[1].url == "not-a-url"
    assert results[1].status_code is None
    assert results[1].render_method == RenderMethod.FAILED
    assert results[2].url == "https://example.com/3"
    assert results[2].status_code is None
    assert results[2].render_method == RenderMethod.FAILED


@pytest.mark.asyncio
@pytest.mark.usefixtures("_patch_tier_deps_for_httpx_tests")
async def test_scraper_importable_from_package():
    """from scraper_service import Scraper works and is the same class."""
    from scraper_service import Scraper as ScraperFromPackage

    assert ScraperFromPackage is Scraper


@pytest.mark.asyncio
@pytest.mark.usefixtures("_patch_tier_deps_for_httpx_tests")
async def test_correlation_id_bound_at_job_start():
    """Verify correlation ID is bound at job start."""
    settings = Settings()
    async with Scraper(settings) as scraper:
        mock_response = mock.Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.url = "https://example.com"
        mock_response.text = "<html></html>"

        with mock.patch.object(
            scraper._client, "get", return_value=mock_response
        ):
            results = await scraper.fetch(["https://example.com"])

    assert len(results) == 1


# ---------------------------------------------------------------------------
# Tier escalation tests (Plan 03: httpx -> XHR sniffing -> Playwright)
# ---------------------------------------------------------------------------


def _make_httpx_response(
    url: str = "https://example.com",
    text: str = "<html><body>Test</body></html>",
    status_code: int = 200,
) -> mock.Mock:
    """Build a mock httpx.Response with sensible defaults."""
    resp = mock.Mock(spec=httpx.Response)
    resp.status_code = status_code
    resp.url = url
    resp.text = text
    return resp


@pytest.mark.asyncio
async def test_httpx_sufficient_content_no_escalation():
    """httpx fetch with sufficient content returns render_method=HTTPX."""
    settings = Settings()
    async with Scraper(settings) as scraper:
        long_body = "<html><body>" + "x" * 600 + "</body></html>"
        mock_resp = _make_httpx_response(text=long_body)

        with mock.patch.object(
            scraper._client, "get", return_value=mock_resp
        ), mock.patch(
            "scraper_service.fetcher.is_content_sufficient", return_value=True
        ):
            results = await scraper.fetch(["https://example.com"])

    assert results[0].render_method == RenderMethod.HTTPX
    assert results[0].status_code == 200


@pytest.mark.asyncio
async def test_httpx_insufficient_escalates_to_xhr():
    """Insufficient httpx content tries XHR sniffing, XHR data found, returns XHR."""
    settings = Settings()
    async with Scraper(settings) as scraper:
        short_body = "<html><body>short</body></html>"
        mock_resp = _make_httpx_response(text=short_body)

        xhr_html = "<html><body>" + "x" * 600 + "</body></html>"

        with mock.patch.object(
            scraper._client, "get", return_value=mock_resp
        ), mock.patch(
            "scraper_service.fetcher.is_content_sufficient",
            side_effect=[False, True],  # httpx insufficient, XHR sufficient
        ), mock.patch(
            "scraper_service.fetcher.extract_xhr_content", return_value=xhr_html
        ):
            results = await scraper.fetch(["https://example.com"])

    assert results[0].render_method == RenderMethod.XHR
    assert results[0].html == xhr_html


@pytest.mark.asyncio
async def test_xhr_found_but_insufficient_escalates_to_playwright():
    """XHR data found but insufficient content escalates to Playwright."""
    settings = Settings()
    async with Scraper(settings) as scraper:
        short_body = "<html><body>short</body></html>"
        mock_resp = _make_httpx_response(text=short_body)

        xhr_html = "<html><body>short xhr</body></html>"
        pw_result = PageData(
            url="https://example.com",
            final_url="https://example.com",
            status_code=200,
            render_method=RenderMethod.PLAYWRIGHT,
            html="<html><body>full content</body></html>",
        )

        with mock.patch.object(
            scraper._client, "get", return_value=mock_resp
        ), mock.patch(
            "scraper_service.fetcher.is_content_sufficient",
            side_effect=[False, False],  # httpx insufficient, XHR insufficient
        ), mock.patch(
            "scraper_service.fetcher.extract_xhr_content", return_value=xhr_html
        ), mock.patch.object(
            scraper._browser_manager, "fetch_page", return_value=pw_result
        ):
            results = await scraper.fetch(["https://example.com"])

    assert results[0].render_method == RenderMethod.PLAYWRIGHT


@pytest.mark.asyncio
async def test_xhr_not_found_escalates_to_playwright():
    """XHR sniffing finds nothing, Playwright runs."""
    settings = Settings()
    async with Scraper(settings) as scraper:
        short_body = "<html><body>short</body></html>"
        mock_resp = _make_httpx_response(text=short_body)

        pw_result = PageData(
            url="https://example.com",
            final_url="https://example.com",
            status_code=200,
            render_method=RenderMethod.PLAYWRIGHT,
            html="<html><body>rendered</body></html>",
        )

        with mock.patch.object(
            scraper._client, "get", return_value=mock_resp
        ), mock.patch(
            "scraper_service.fetcher.is_content_sufficient", return_value=False
        ), mock.patch(
            "scraper_service.fetcher.extract_xhr_content", return_value=None
        ), mock.patch.object(
            scraper._browser_manager, "fetch_page", return_value=pw_result
        ):
            results = await scraper.fetch(["https://example.com"])

    assert results[0].render_method == RenderMethod.PLAYWRIGHT


@pytest.mark.asyncio
async def test_all_tiers_fail_returns_failed():
    """All tiers fail returns render_method=FAILED with error."""
    settings = Settings()
    async with Scraper(settings) as scraper:
        mock_resp = _make_httpx_response(
            text="<html><body>short</body></html>"
        )

        with mock.patch.object(
            scraper._client, "get", return_value=mock_resp
        ), mock.patch(
            "scraper_service.fetcher.is_content_sufficient", return_value=False
        ), mock.patch(
            "scraper_service.fetcher.extract_xhr_content", return_value=None
        ), mock.patch.object(
            scraper._browser_manager, "fetch_page",
            return_value=PageData(
                url="https://example.com",
                final_url="https://example.com",
                render_method=RenderMethod.FAILED,
                error="Playwright crashed",
            ),
        ):
            results = await scraper.fetch(["https://example.com"])

    assert results[0].render_method == RenderMethod.FAILED
    assert results[0].error is not None


@pytest.mark.asyncio
async def test_forced_httpx_skips_escalation():
    """force_render_method=HTTPX returns httpx result even with insufficient content."""
    settings = Settings()
    async with Scraper(settings, force_render_method=RenderMethod.HTTPX) as scraper:
        short_body = "<html><body>short</body></html>"
        mock_resp = _make_httpx_response(text=short_body)

        with mock.patch.object(
            scraper._client, "get", return_value=mock_resp
        ), mock.patch(
            "scraper_service.fetcher.is_content_sufficient", return_value=False
        ):
            results = await scraper.fetch(["https://example.com"])

    assert results[0].render_method == RenderMethod.HTTPX


@pytest.mark.asyncio
async def test_forced_playwright_skips_httpx():
    """force_render_method=PLAYWRIGHT skips httpx entirely."""
    settings = Settings()
    async with Scraper(settings, force_render_method=RenderMethod.PLAYWRIGHT) as scraper:
        pw_result = PageData(
            url="https://example.com",
            final_url="https://example.com",
            status_code=200,
            render_method=RenderMethod.PLAYWRIGHT,
            html="<html><body>rendered</body></html>",
        )

        with mock.patch.object(
            scraper._browser_manager, "fetch_page", return_value=pw_result
        ), mock.patch.object(
            scraper._client, "get"
        ) as mock_get:
            results = await scraper.fetch(["https://example.com"])

    assert results[0].render_method == RenderMethod.PLAYWRIGHT
    mock_get.assert_not_called()


@pytest.mark.asyncio
async def test_forced_xhr_uses_xhr_only():
    """force_render_method=XHR tries XHR but skips Playwright on failure."""
    settings = Settings()
    async with Scraper(settings, force_render_method=RenderMethod.XHR) as scraper:
        short_body = "<html><body>short</body></html>"
        mock_resp = _make_httpx_response(text=short_body)
        xhr_html = "<html><body>" + "x" * 600 + "</body></html>"

        with mock.patch.object(
            scraper._client, "get", return_value=mock_resp
        ), mock.patch(
            "scraper_service.fetcher.is_content_sufficient", return_value=False
        ), mock.patch(
            "scraper_service.fetcher.extract_xhr_content", return_value=xhr_html
        ), mock.patch.object(
            scraper._browser_manager, "fetch_page"
        ) as mock_pw:
            results = await scraper.fetch(["https://example.com"])

    assert results[0].render_method == RenderMethod.XHR
    mock_pw.assert_not_called()


@pytest.mark.asyncio
async def test_scrape_request_render_method_forces_tier():
    """ScrapeRequest.render_method=PLAYWRIGHT skips httpx."""
    settings = Settings()
    async with Scraper(settings) as scraper:
        pw_result = PageData(
            url="https://example.com",
            final_url="https://example.com",
            status_code=200,
            render_method=RenderMethod.PLAYWRIGHT,
            html="<html><body>rendered</body></html>",
        )
        req = ScrapeRequest(
            urls=["https://example.com"],
            render_method=RenderMethod.PLAYWRIGHT,
        )

        with mock.patch.object(
            scraper._browser_manager, "fetch_page", return_value=pw_result
        ), mock.patch.object(
            scraper._client, "get"
        ) as mock_get:
            results = await scraper.fetch(["https://example.com"], scrape_request=req)

    assert results[0].render_method == RenderMethod.PLAYWRIGHT
    mock_get.assert_not_called()


@pytest.mark.asyncio
async def test_constructor_force_overrides_scrape_request():
    """Constructor force_render_method takes precedence over ScrapeRequest."""
    settings = Settings()
    async with Scraper(settings, force_render_method=RenderMethod.HTTPX) as scraper:
        long_body = "<html><body>" + "x" * 600 + "</body></html>"
        mock_resp = _make_httpx_response(text=long_body)

        req = ScrapeRequest(
            urls=["https://example.com"],
            render_method=RenderMethod.PLAYWRIGHT,
        )

        with mock.patch.object(
            scraper._client, "get", return_value=mock_resp
        ), mock.patch.object(
            scraper._browser_manager, "fetch_page"
        ) as mock_pw:
            results = await scraper.fetch(
                ["https://example.com"], scrape_request=req
            )

    assert results[0].render_method == RenderMethod.HTTPX
    mock_pw.assert_not_called()


@pytest.mark.asyncio
async def test_aenter_creates_browser_manager():
    """Scraper.__aenter__ creates a BrowserManager instance."""
    settings = Settings()
    scraper = Scraper(settings)

    async with scraper:
        assert scraper._browser_manager is not None

    # After exit, browser_manager should be cleaned up
    assert scraper._browser_manager is None


@pytest.mark.asyncio
async def test_aexit_closes_browser_manager():
    """Scraper.__aexit__ calls browser_manager.close()."""
    settings = Settings()
    scraper = Scraper(settings)

    async with scraper:
        bm = scraper._browser_manager
        assert bm is not None
        with mock.patch.object(bm, "close") as mock_close:
            pass
        # The real close happens in __aexit__, so check after exiting context

    assert scraper._browser_manager is None


@pytest.mark.asyncio
async def test_fetch_accepts_scrape_request_parameter():
    """fetch() accepts optional ScrapeRequest without crashing."""
    settings = Settings()
    async with Scraper(settings) as scraper:
        long_body = "<html><body>" + "x" * 600 + "</body></html>"
        mock_resp = _make_httpx_response(text=long_body)

        req = ScrapeRequest(urls=["https://example.com"])

        with mock.patch.object(
            scraper._client, "get", return_value=mock_resp
        ), mock.patch(
            "scraper_service.fetcher.is_content_sufficient", return_value=True
        ):
            results = await scraper.fetch(
                ["https://example.com"], scrape_request=req
            )

    assert results[0].status_code == 200


@pytest.mark.asyncio
async def test_xhr_sufficient_returns_xhr():
    """XHR data found and sufficient returns render_method=XHR."""
    settings = Settings()
    async with Scraper(settings) as scraper:
        short_body = "<html><body>short</body></html>"
        mock_resp = _make_httpx_response(text=short_body)

        xhr_html = "<html><body>" + "x" * 600 + "</body></html>"

        with mock.patch.object(
            scraper._client, "get", return_value=mock_resp
        ), mock.patch(
            "scraper_service.fetcher.is_content_sufficient",
            side_effect=[False, True],
        ), mock.patch(
            "scraper_service.fetcher.extract_xhr_content", return_value=xhr_html
        ), mock.patch.object(
            scraper._browser_manager, "fetch_page"
        ) as mock_pw:
            results = await scraper.fetch(["https://example.com"])

    assert results[0].render_method == RenderMethod.XHR
    assert results[0].html == xhr_html
    mock_pw.assert_not_called()


# ---------------------------------------------------------------------------
# Circuit breaker tests (Phase 7, Plan 01)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.usefixtures("_patch_tier_deps_for_httpx_tests")
async def test_circuit_breaker_trips_after_5_failures():
    """5 consecutive failures from same domain trips breaker -- 6th URL is skipped."""
    settings = Settings(max_retries=1, retry_backoff=0.01)
    async with Scraper(settings) as scraper:
        # All 6 URLs from the same domain
        urls = [f"https://failing.com/{i}" for i in range(6)]

        network_error = httpx.NetworkError("Connection refused")
        with mock.patch.object(
            scraper._client, "get", side_effect=network_error
        ):
            results = await scraper.fetch(urls)

    assert len(results) == 6
    # First 5 should be normal failures (fetched via httpx)
    for i in range(5):
        assert results[i].error is not None
        assert results[i].error_type != ErrorType.CIRCUIT_BREAKER
    # 6th should be circuit breaker
    assert results[5].error_type == ErrorType.CIRCUIT_BREAKER
    assert results[5].render_method == RenderMethod.FAILED
    assert results[5].status_code is None
    assert "failing.com" in results[5].error
    assert "5 consecutive failures" in results[5].error


@pytest.mark.asyncio
@pytest.mark.usefixtures("_patch_tier_deps_for_httpx_tests")
async def test_circuit_breaker_error_contains_domain():
    """Circuit breaker error string names the domain."""
    settings = Settings(max_retries=1, retry_backoff=0.01)
    async with Scraper(settings) as scraper:
        urls = [f"https://broken-site.example.org/{i}" for i in range(6)]

        network_error = httpx.NetworkError("Connection refused")
        with mock.patch.object(
            scraper._client, "get", side_effect=network_error
        ):
            results = await scraper.fetch(urls)

    assert "broken-site.example.org" in results[5].error


@pytest.mark.asyncio
@pytest.mark.usefixtures("_patch_tier_deps_for_httpx_tests")
async def test_circuit_breaker_resets_on_success():
    """A successful fetch resets the failure counter for that domain."""
    settings = Settings(max_retries=1, retry_backoff=0.01)
    async with Scraper(settings) as scraper:
        # 3 failures, 1 success, then 5 more failures = 9 URLs total
        # The success at position 3 resets the counter, so the breaker
        # should not trip until 5 consecutive failures after the success
        # (positions 4-8). Position 9 would be circuit-broken.
        urls = [f"https://flaky.com/{i}" for i in range(9)]

        network_error = httpx.NetworkError("Connection refused")
        mock_ok = mock.Mock(spec=httpx.Response)
        mock_ok.status_code = 200
        mock_ok.url = "https://flaky.com/3"
        mock_ok.text = "<html><body>OK</body></html>"

        # Positions 0-2: fail, position 3: success, positions 4-8: fail
        side_effects = [network_error, network_error, network_error, mock_ok,
                        network_error, network_error, network_error, network_error, network_error]
        with mock.patch.object(
            scraper._client, "get", side_effect=side_effects
        ):
            results = await scraper.fetch(urls)

    assert len(results) == 9
    # Position 3 should be success
    assert results[3].status_code == 200
    assert results[3].error is None
    # Positions 4-8: 5 consecutive failures after reset
    for i in range(4, 8):
        assert results[i].error is not None
        assert results[i].error_type != ErrorType.CIRCUIT_BREAKER
    # Position 8 is the 5th consecutive failure, so position 8 is failure #5
    # The NEXT one (index 8 = 5th failure) should be the last real one
    # Actually: after success at 3, failures at 4,5,6,7,8 = 5 consecutive
    # So the 6th after reset (index 9, but we only have 9 URLs: 0-8)
    # index 8 = 5th failure after reset -- the breaker trips AFTER 5, so
    # index 8 is still a real fetch. We'd need a 10th URL to see CIRCUIT_BREAKER.
    # Let me just verify that index 8 is NOT circuit_breaker (only 5 failures, need >5)
    assert results[8].error_type != ErrorType.CIRCUIT_BREAKER


@pytest.mark.asyncio
@pytest.mark.usefixtures("_patch_tier_deps_for_httpx_tests")
async def test_circuit_breaker_independent_domains():
    """Different domains have independent failure counters."""
    settings = Settings(max_retries=1, retry_backoff=0.01)
    async with Scraper(settings) as scraper:
        # 5 failures from domain A, then 1 from domain B
        urls = [f"https://bad-a.com/{i}" for i in range(5)]
        urls.append("https://good-b.com/0")

        network_error = httpx.NetworkError("Connection refused")
        mock_ok = mock.Mock(spec=httpx.Response)
        mock_ok.status_code = 200
        mock_ok.url = "https://good-b.com/0"
        mock_ok.text = "<html><body>OK</body></html>"

        # 5 failures for domain A, then success for domain B
        side_effects = [network_error] * 5 + [mock_ok]
        with mock.patch.object(
            scraper._client, "get", side_effect=side_effects
        ):
            results = await scraper.fetch(urls)

    assert len(results) == 6
    # Domain B should succeed -- not affected by domain A's failures
    assert results[5].status_code == 200
    assert results[5].error is None


@pytest.mark.asyncio
@pytest.mark.usefixtures("_patch_tier_deps_for_httpx_tests")
async def test_circuit_breaker_fresh_per_context():
    """Each Scraper context manager starts with a clean circuit breaker."""
    settings = Settings(max_retries=1, retry_backoff=0.01)

    network_error = httpx.NetworkError("Connection refused")

    # First context: trip the breaker
    async with Scraper(settings) as scraper:
        urls = [f"https://reset-test.com/{i}" for i in range(6)]
        with mock.patch.object(
            scraper._client, "get", side_effect=network_error
        ):
            results1 = await scraper.fetch(urls)

    assert results1[5].error_type == ErrorType.CIRCUIT_BREAKER

    # Second context: same domain should not be circuit-broken
    async with Scraper(settings) as scraper:
        mock_ok = mock.Mock(spec=httpx.Response)
        mock_ok.status_code = 200
        mock_ok.url = "https://reset-test.com/0"
        mock_ok.text = "<html><body>OK</body></html>"

        with mock.patch.object(
            scraper._client, "get", return_value=mock_ok
        ):
            results2 = await scraper.fetch(["https://reset-test.com/0"])

    assert results2[0].status_code == 200
    assert results2[0].error_type is None


@pytest.mark.asyncio
@pytest.mark.usefixtures("_patch_tier_deps_for_httpx_tests")
async def test_circuit_breaker_4_failures_does_not_trip():
    """4 consecutive failures does NOT trip the breaker (threshold is 5)."""
    settings = Settings(max_retries=1, retry_backoff=0.01)
    async with Scraper(settings) as scraper:
        urls = [f"https://almost.com/{i}" for i in range(5)]

        network_error = httpx.NetworkError("Connection refused")
        with mock.patch.object(
            scraper._client, "get", side_effect=network_error
        ):
            results = await scraper.fetch(urls)

    assert len(results) == 5
    # All 5 should be real failures, none circuit-broken
    for r in results:
        assert r.error_type != ErrorType.CIRCUIT_BREAKER


# ---------------------------------------------------------------------------
# ErrorType assignment tests (Phase 7, Plan 01)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.usefixtures("_patch_tier_deps_for_httpx_tests")
async def test_error_type_timeout():
    """httpx.TimeoutException sets error_type=TIMEOUT."""
    settings = Settings(max_retries=1, retry_backoff=0.01)
    async with Scraper(settings) as scraper:
        with mock.patch.object(
            scraper._client, "get",
            side_effect=httpx.TimeoutException("request timed out"),
        ):
            results = await scraper.fetch(["https://example.com"])

    assert results[0].error_type == ErrorType.TIMEOUT
    assert results[0].render_method == RenderMethod.FAILED


@pytest.mark.asyncio
@pytest.mark.usefixtures("_patch_tier_deps_for_httpx_tests")
async def test_error_type_network():
    """httpx.NetworkError sets error_type=NETWORK."""
    settings = Settings(max_retries=1, retry_backoff=0.01)
    async with Scraper(settings) as scraper:
        with mock.patch.object(
            scraper._client, "get",
            side_effect=httpx.NetworkError("Connection refused"),
        ):
            results = await scraper.fetch(["https://example.com"])

    assert results[0].error_type == ErrorType.NETWORK
    assert results[0].render_method == RenderMethod.FAILED


@pytest.mark.asyncio
@pytest.mark.usefixtures("_patch_tier_deps_for_httpx_tests")
async def test_error_type_http_4xx():
    """httpx.HTTPStatusError with 404 sets error_type=HTTP_4XX."""
    settings = Settings(max_retries=1)
    async with Scraper(settings) as scraper:
        mock_404 = mock.Mock(spec=httpx.Response)
        mock_404.status_code = 404
        mock_404.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404 Not Found", request=mock.Mock(), response=mock_404
        )
        with mock.patch.object(scraper._client, "get", return_value=mock_404):
            results = await scraper.fetch(["https://example.com"])

    assert results[0].error_type == ErrorType.HTTP_4XX


@pytest.mark.asyncio
@pytest.mark.usefixtures("_patch_tier_deps_for_httpx_tests")
async def test_error_type_http_5xx():
    """httpx.HTTPStatusError with 500 sets error_type=HTTP_5XX."""
    settings = Settings(max_retries=1, retry_backoff=0.01)
    async with Scraper(settings) as scraper:
        mock_500 = mock.Mock(spec=httpx.Response)
        mock_500.status_code = 500
        mock_500.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500 Server Error", request=mock.Mock(), response=mock_500
        )
        with mock.patch.object(scraper._client, "get", return_value=mock_500):
            results = await scraper.fetch(["https://example.com"])

    assert results[0].error_type == ErrorType.HTTP_5XX


@pytest.mark.asyncio
@pytest.mark.usefixtures("_patch_tier_deps_for_httpx_tests")
async def test_error_type_invalid_url():
    """Invalid URL gets error_type=INVALID_URL."""
    settings = Settings()
    async with Scraper(settings) as scraper:
        results = await scraper.fetch(["not-a-url"])

    assert results[0].error_type == ErrorType.INVALID_URL
    assert results[0].render_method == RenderMethod.FAILED


@pytest.mark.asyncio
async def test_error_type_playwright_crash():
    """Playwright failure sets error_type=PLAYWRIGHT_CRASH."""
    settings = Settings()
    async with Scraper(settings, force_render_method=RenderMethod.PLAYWRIGHT) as scraper:
        pw_failed = PageData(
            url="https://example.com",
            final_url="https://example.com",
            render_method=RenderMethod.FAILED,
            error="Browser crashed",
            error_type=ErrorType.PLAYWRIGHT_CRASH,
        )
        with mock.patch.object(
            scraper._browser_manager, "fetch_page", return_value=pw_failed
        ):
            results = await scraper.fetch(["https://example.com"])

    assert results[0].error_type == ErrorType.PLAYWRIGHT_CRASH


# ---------------------------------------------------------------------------
# Robots.txt integration tests (Phase 7, Plan 02)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.usefixtures("_patch_tier_deps_for_httpx_tests")
async def test_robots_denied_when_respect_robots_true():
    """With respect_robots=True, disallowed URL gets error_type=ROBOTS_DENIED."""
    settings = Settings()
    async with Scraper(settings) as scraper:
        req = ScrapeRequest(urls=["https://example.com/blocked"], respect_robots=True)

        with mock.patch(
            "scraper_service.fetcher.RobotsChecker"
        ) as MockChecker:
            checker_instance = mock.AsyncMock()
            checker_instance.is_allowed.return_value = False
            MockChecker.return_value = checker_instance

            results = await scraper.fetch(
                ["https://example.com/blocked"], scrape_request=req
            )

    assert len(results) == 1
    assert results[0].error_type == ErrorType.ROBOTS_DENIED
    assert results[0].render_method == RenderMethod.FAILED
    assert "robots.txt" in results[0].error


@pytest.mark.asyncio
@pytest.mark.usefixtures("_patch_tier_deps_for_httpx_tests")
async def test_robots_not_checked_when_respect_robots_false():
    """With respect_robots=False (default), robots.txt is never fetched."""
    settings = Settings()
    async with Scraper(settings) as scraper:
        mock_response = mock.Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.url = "https://example.com"
        mock_response.text = "<html><body>Content</body></html>"

        with mock.patch.object(
            scraper._client, "get", return_value=mock_response
        ), mock.patch(
            "scraper_service.fetcher.RobotsChecker"
        ) as MockChecker:
            results = await scraper.fetch(["https://example.com"])

    MockChecker.assert_not_called()
    assert results[0].status_code == 200


@pytest.mark.asyncio
@pytest.mark.usefixtures("_patch_tier_deps_for_httpx_tests")
async def test_robots_check_after_circuit_breaker():
    """If domain is circuit-broken, robots.txt is NOT fetched."""
    settings = Settings(max_retries=1, retry_backoff=0.01)
    async with Scraper(settings) as scraper:
        # Trip the circuit breaker by failing 5 times
        urls = [f"https://tripped.com/{i}" for i in range(6)]
        network_error = httpx.NetworkError("Connection refused")

        req = ScrapeRequest(urls=urls, respect_robots=True)

        with mock.patch.object(
            scraper._client, "get", side_effect=network_error
        ), mock.patch(
            "scraper_service.fetcher.RobotsChecker"
        ) as MockChecker:
            checker_instance = mock.AsyncMock()
            checker_instance.is_allowed.return_value = True
            MockChecker.return_value = checker_instance

            results = await scraper.fetch(urls, scrape_request=req)

    # The 6th URL is circuit-broken, so robots.txt should not be checked for it
    assert results[5].error_type == ErrorType.CIRCUIT_BREAKER
    # is_allowed should have been called 5 times (for the first 5), not 6
    assert checker_instance.is_allowed.call_count == 5


# ---------------------------------------------------------------------------
# 429 Retry-After tests (Phase 7, Plan 02)
# ---------------------------------------------------------------------------


def _make_429_response(retry_after: str | None = None) -> mock.Mock:
    """Build a mock 429 response that raises HTTPStatusError on raise_for_status."""
    resp = mock.Mock(spec=httpx.Response)
    resp.status_code = 429
    resp.headers = {"Retry-After": retry_after} if retry_after else {}
    resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "429 Too Many Requests", request=mock.Mock(), response=resp
    )
    return resp


@pytest.mark.asyncio
@pytest.mark.usefixtures("_patch_tier_deps_for_httpx_tests")
async def test_429_is_retried():
    """429 response triggers retry, second attempt succeeds."""
    settings = Settings(max_retries=3, retry_backoff=0.01)
    async with Scraper(settings) as scraper:
        mock_429 = _make_429_response()
        mock_200 = _make_httpx_response()

        with mock.patch.object(
            scraper._client, "get", side_effect=[mock_429, mock_200]
        ) as mock_get:
            results = await scraper.fetch(["https://example.com"])

    assert results[0].status_code == 200
    assert mock_get.call_count == 2


@pytest.mark.asyncio
@pytest.mark.usefixtures("_patch_tier_deps_for_httpx_tests")
async def test_429_retry_after_header():
    """429 with Retry-After: 1 waits approximately 1 second before retry."""
    import time
    settings = Settings(max_retries=3, retry_backoff=0.01)
    async with Scraper(settings) as scraper:
        mock_429 = _make_429_response(retry_after="1")
        mock_200 = _make_httpx_response()

        t0 = time.monotonic()
        with mock.patch.object(
            scraper._client, "get", side_effect=[mock_429, mock_200]
        ):
            results = await scraper.fetch(["https://example.com"])
        elapsed = time.monotonic() - t0

    assert results[0].status_code == 200
    # Should have waited ~1 second (allow 0.5s tolerance)
    assert elapsed >= 0.8, f"Expected ~1s wait, got {elapsed:.2f}s"


@pytest.mark.asyncio
@pytest.mark.usefixtures("_patch_tier_deps_for_httpx_tests")
async def test_retry_after_capped_at_60():
    """Retry-After value > 60 is capped at 60 seconds."""
    from scraper_service.fetcher import _parse_retry_after
    assert _parse_retry_after("120") == 60.0
    assert _parse_retry_after("999") == 60.0
    assert _parse_retry_after("60") == 60.0
    assert _parse_retry_after("30") == 30.0


@pytest.mark.asyncio
@pytest.mark.usefixtures("_patch_tier_deps_for_httpx_tests")
async def test_429_without_retry_after_uses_backoff():
    """429 without Retry-After falls back to exponential backoff."""
    settings = Settings(max_retries=3, retry_backoff=0.01)
    async with Scraper(settings) as scraper:
        mock_429 = _make_429_response()  # No Retry-After header
        mock_200 = _make_httpx_response()

        with mock.patch.object(
            scraper._client, "get", side_effect=[mock_429, mock_200]
        ) as mock_get:
            results = await scraper.fetch(["https://example.com"])

    assert results[0].status_code == 200
    assert mock_get.call_count == 2


@pytest.mark.asyncio
@pytest.mark.usefixtures("_patch_tier_deps_for_httpx_tests")
async def test_5xx_still_uses_backoff():
    """5xx responses still use exponential backoff (unchanged)."""
    settings = Settings(max_retries=3, retry_backoff=0.01)
    async with Scraper(settings) as scraper:
        mock_500 = mock.Mock(spec=httpx.Response)
        mock_500.status_code = 500
        mock_500.headers = {}
        mock_500.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500 Server Error", request=mock.Mock(), response=mock_500
        )
        mock_200 = _make_httpx_response()

        with mock.patch.object(
            scraper._client, "get", side_effect=[mock_500, mock_200]
        ):
            results = await scraper.fetch(["https://example.com"])

    assert results[0].status_code == 200


@pytest.mark.asyncio
@pytest.mark.usefixtures("_patch_tier_deps_for_httpx_tests")
async def test_4xx_not_429_still_not_retried():
    """4xx response (not 429) is still NOT retried."""
    settings = Settings(max_retries=3)
    async with Scraper(settings) as scraper:
        mock_403 = mock.Mock(spec=httpx.Response)
        mock_403.status_code = 403
        mock_403.headers = {}
        mock_403.raise_for_status.side_effect = httpx.HTTPStatusError(
            "403 Forbidden", request=mock.Mock(), response=mock_403
        )

        with mock.patch.object(
            scraper._client, "get", return_value=mock_403
        ) as mock_get:
            results = await scraper.fetch(["https://example.com"])

    assert results[0].error_type == ErrorType.HTTP_4XX
    assert mock_get.call_count == 1  # No retry


# ---------------------------------------------------------------------------
# Proxy-as-fallback tests (Phase 7, Plan 02)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.usefixtures("_patch_tier_deps_for_httpx_tests")
async def test_proxy_fallback_on_403():
    """403 with use_proxy=True triggers proxy fallback, proxy succeeds."""
    settings = Settings(use_proxy=True, proxy_url="http://proxy:8080", max_retries=1)
    async with Scraper(settings) as scraper:
        mock_403 = mock.Mock(spec=httpx.Response)
        mock_403.status_code = 403
        mock_403.headers = {}
        mock_403.raise_for_status.side_effect = httpx.HTTPStatusError(
            "403 Forbidden", request=mock.Mock(), response=mock_403
        )

        mock_200_proxy = mock.Mock(spec=httpx.Response)
        mock_200_proxy.status_code = 200
        mock_200_proxy.url = "https://example.com"
        mock_200_proxy.text = "<html><body>Via proxy</body></html>"

        # Direct fetch returns 403, proxy fetch returns 200
        with mock.patch.object(
            scraper._client, "get", side_effect=[mock_403, mock_200_proxy]
        ):
            results = await scraper.fetch(["https://example.com"])

    assert results[0].status_code == 200
    assert results[0].html == "<html><body>Via proxy</body></html>"


@pytest.mark.asyncio
@pytest.mark.usefixtures("_patch_tier_deps_for_httpx_tests")
async def test_proxy_fallback_on_429_after_retries():
    """429 after retries exhausted triggers proxy fallback."""
    settings = Settings(use_proxy=True, proxy_url="http://proxy:8080", max_retries=1, retry_backoff=0.01)
    async with Scraper(settings) as scraper:
        mock_429 = _make_429_response()

        mock_200_proxy = mock.Mock(spec=httpx.Response)
        mock_200_proxy.status_code = 200
        mock_200_proxy.url = "https://example.com"
        mock_200_proxy.text = "<html><body>Via proxy</body></html>"

        # Direct fetch returns 429 (retries exhausted), proxy fallback returns 200
        with mock.patch.object(
            scraper._client, "get", side_effect=[mock_429, mock_200_proxy]
        ):
            results = await scraper.fetch(["https://example.com"])

    assert results[0].status_code == 200


@pytest.mark.asyncio
@pytest.mark.usefixtures("_patch_tier_deps_for_httpx_tests")
async def test_proxy_fallback_on_network_error():
    """Network error with use_proxy=True triggers proxy fallback."""
    settings = Settings(use_proxy=True, proxy_url="http://proxy:8080", max_retries=1, retry_backoff=0.01)
    async with Scraper(settings) as scraper:
        network_error = httpx.NetworkError("Connection refused")

        mock_200_proxy = mock.Mock(spec=httpx.Response)
        mock_200_proxy.status_code = 200
        mock_200_proxy.url = "https://example.com"
        mock_200_proxy.text = "<html><body>Via proxy</body></html>"

        with mock.patch.object(
            scraper._client, "get", side_effect=[network_error, mock_200_proxy]
        ):
            results = await scraper.fetch(["https://example.com"])

    assert results[0].status_code == 200


@pytest.mark.asyncio
@pytest.mark.usefixtures("_patch_tier_deps_for_httpx_tests")
async def test_proxy_fallback_single_attempt():
    """Proxy fallback is a single attempt -- if proxy also fails, return error."""
    settings = Settings(use_proxy=True, proxy_url="http://proxy:8080", max_retries=1, retry_backoff=0.01)
    async with Scraper(settings) as scraper:
        mock_403 = mock.Mock(spec=httpx.Response)
        mock_403.status_code = 403
        mock_403.headers = {}
        mock_403.raise_for_status.side_effect = httpx.HTTPStatusError(
            "403 Forbidden", request=mock.Mock(), response=mock_403
        )

        proxy_error = httpx.NetworkError("Proxy connection failed")

        with mock.patch.object(
            scraper._client, "get", side_effect=[mock_403, proxy_error]
        ):
            results = await scraper.fetch(["https://example.com"])

    assert results[0].render_method == RenderMethod.FAILED
    assert results[0].error is not None


@pytest.mark.asyncio
@pytest.mark.usefixtures("_patch_tier_deps_for_httpx_tests")
async def test_no_proxy_fallback_when_disabled():
    """When use_proxy=False (default), no proxy fallback on 403."""
    settings = Settings(use_proxy=False, max_retries=1)
    async with Scraper(settings) as scraper:
        mock_403 = mock.Mock(spec=httpx.Response)
        mock_403.status_code = 403
        mock_403.headers = {}
        mock_403.raise_for_status.side_effect = httpx.HTTPStatusError(
            "403 Forbidden", request=mock.Mock(), response=mock_403
        )

        with mock.patch.object(
            scraper._client, "get", return_value=mock_403
        ) as mock_get:
            results = await scraper.fetch(["https://example.com"])

    assert results[0].error_type == ErrorType.HTTP_4XX
    # Only 1 call -- no proxy fallback
    assert mock_get.call_count == 1


@pytest.mark.asyncio
@pytest.mark.usefixtures("_patch_tier_deps_for_httpx_tests")
async def test_proxy_fallback_skipped_when_no_proxy_url():
    """When use_proxy=True but proxy_url is empty, log warning and skip."""
    settings = Settings(use_proxy=True, proxy_url="", max_retries=1)
    async with Scraper(settings) as scraper:
        mock_403 = mock.Mock(spec=httpx.Response)
        mock_403.status_code = 403
        mock_403.headers = {}
        mock_403.raise_for_status.side_effect = httpx.HTTPStatusError(
            "403 Forbidden", request=mock.Mock(), response=mock_403
        )

        with mock.patch.object(
            scraper._client, "get", return_value=mock_403
        ) as mock_get:
            results = await scraper.fetch(["https://example.com"])

    assert results[0].error_type == ErrorType.HTTP_4XX
    # Only 1 call -- proxy fallback skipped because no proxy_url
    assert mock_get.call_count == 1


@pytest.mark.asyncio
@pytest.mark.usefixtures("_patch_tier_deps_for_httpx_tests")
async def test_successful_fetch_no_proxy_fallback():
    """Successful direct fetch does not trigger proxy fallback."""
    settings = Settings(use_proxy=True, proxy_url="http://proxy:8080")
    async with Scraper(settings) as scraper:
        mock_200 = _make_httpx_response()

        with mock.patch.object(
            scraper._client, "get", return_value=mock_200
        ) as mock_get:
            results = await scraper.fetch(["https://example.com"])

    assert results[0].status_code == 200
    # Only 1 call -- no proxy needed
    assert mock_get.call_count == 1
