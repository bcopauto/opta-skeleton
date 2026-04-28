"""Tests for BrowserManager -- Playwright browser lifecycle."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scraper_service.browser import BrowserManager
from scraper_service.models import PageData, RenderMethod
from scraper_service.settings import Settings


# ---------------------------------------------------------------------------
# Helpers for mocking the Playwright API
# ---------------------------------------------------------------------------


def _make_mock_browser() -> AsyncMock:
    """Create a mock Browser that pretends to be connected.

    is_connected() is a sync method in Playwright, so we use MagicMock for it.
    """
    browser = AsyncMock()
    # is_connected is a sync method in Playwright's API
    browser.is_connected = MagicMock(return_value=True)
    browser.close = AsyncMock()
    return browser


def _make_mock_playwright(mock_browser: AsyncMock) -> AsyncMock:
    """Create a mock Playwright instance whose chromium.launch returns mock_browser."""
    pw = AsyncMock()
    pw.chromium.launch = AsyncMock(return_value=mock_browser)
    pw.stop = AsyncMock()
    return pw


def _make_mock_context(page: AsyncMock) -> AsyncMock:
    """Create a mock BrowserContext that returns the given page."""
    ctx = AsyncMock()
    ctx.new_page = AsyncMock(return_value=page)
    ctx.close = AsyncMock()
    return ctx


def _make_mock_page(
    html: str = "<html><body>Hello</body></html>",
    final_url: str = "https://example.com",
) -> AsyncMock:
    """Create a mock Page with configurable content and url."""
    page = AsyncMock()
    page.url = final_url
    page.content = AsyncMock(return_value=html)
    page.goto = AsyncMock()
    page.on = MagicMock()
    return page


# ---------------------------------------------------------------------------
# Browser lifecycle (FETCH-13, D-05)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_starts_with_no_browser_or_playwright():
    """BrowserManager starts lazy -- _browser and _playwright are None."""
    mgr = BrowserManager(Settings())
    assert mgr._browser is None
    assert mgr._playwright is None


@pytest.mark.asyncio
async def test_ensure_browser_creates_playwright_and_launches_chromium():
    """First call to _ensure_browser creates a Playwright instance and launches Chromium."""
    mock_browser = _make_mock_browser()
    mock_pw = _make_mock_playwright(mock_browser)

    with patch("scraper_service.browser.async_playwright", return_value=MagicMock(start=AsyncMock(return_value=mock_pw))):
        mgr = BrowserManager(Settings())
        browser = await mgr._ensure_browser()

    assert browser is mock_browser
    mock_pw.chromium.launch.assert_called_once()


@pytest.mark.asyncio
async def test_ensure_browser_returns_existing_on_subsequent_calls():
    """Second call returns the same browser instance without relaunching."""
    mock_browser = _make_mock_browser()
    mock_pw = _make_mock_playwright(mock_browser)

    with patch("scraper_service.browser.async_playwright", return_value=MagicMock(start=AsyncMock(return_value=mock_pw))):
        mgr = BrowserManager(Settings())
        first = await mgr._ensure_browser()
        second = await mgr._ensure_browser()

    assert first is second
    assert mock_pw.chromium.launch.call_count == 1


@pytest.mark.asyncio
async def test_ensure_browser_uses_lock_to_prevent_concurrent_creation():
    """Two concurrent _ensure_browser calls result in only one launch (asyncio.Lock)."""
    mock_browser = _make_mock_browser()
    mock_pw = _make_mock_playwright(mock_browser)

    call_count = 0

    original_launch = mock_pw.chromium.launch

    async def slow_launch(**kwargs):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.05)
        return await original_launch(**kwargs)

    mock_pw.chromium.launch = slow_launch

    with patch("scraper_service.browser.async_playwright", return_value=MagicMock(start=AsyncMock(return_value=mock_pw))):
        mgr = BrowserManager(Settings())
        await asyncio.gather(mgr._ensure_browser(), mgr._ensure_browser())

    assert call_count == 1


# ---------------------------------------------------------------------------
# Per-URL context (FETCH-13)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_page_creates_new_context_per_url():
    """Each fetch_page call creates a fresh BrowserContext."""
    mock_browser = _make_mock_browser()
    mock_pw = _make_mock_playwright(mock_browser)
    page = _make_mock_page()
    ctx = _make_mock_context(page)
    mock_browser.new_context = AsyncMock(return_value=ctx)

    with patch("scraper_service.browser.async_playwright", return_value=MagicMock(start=AsyncMock(return_value=mock_pw))):
        mgr = BrowserManager(Settings())
        await mgr.fetch_page("https://a.com")
        await mgr.fetch_page("https://b.com")

    assert mock_browser.new_context.call_count == 2


@pytest.mark.asyncio
async def test_fetch_page_closes_context_in_finally_on_error():
    """Context is closed even when page.goto raises."""
    mock_browser = _make_mock_browser()
    mock_pw = _make_mock_playwright(mock_browser)
    page = _make_mock_page()
    page.goto = AsyncMock(side_effect=RuntimeError("navigation failed"))
    ctx = _make_mock_context(page)
    mock_browser.new_context = AsyncMock(return_value=ctx)

    with patch("scraper_service.browser.async_playwright", return_value=MagicMock(start=AsyncMock(return_value=mock_pw))):
        mgr = BrowserManager(Settings())
        result = await mgr.fetch_page("https://example.com")

    # Context should be closed regardless of the error
    ctx.close.assert_called_once()
    assert result.render_method == RenderMethod.PLAYWRIGHT


@pytest.mark.asyncio
async def test_fetch_page_returns_playwright_on_success():
    """Successful fetch returns PageData with render_method=PLAYWRIGHT."""
    mock_browser = _make_mock_browser()
    mock_pw = _make_mock_playwright(mock_browser)
    page = _make_mock_page(html="<html><body>Rendered</body></html>")
    ctx = _make_mock_context(page)
    mock_browser.new_context = AsyncMock(return_value=ctx)

    with patch("scraper_service.browser.async_playwright", return_value=MagicMock(start=AsyncMock(return_value=mock_pw))):
        mgr = BrowserManager(Settings())
        result = await mgr.fetch_page("https://example.com")

    assert result.render_method == RenderMethod.PLAYWRIGHT
    assert result.html == "<html><body>Rendered</body></html>"
    assert result.status_code == 200
    assert result.url == "https://example.com"


# ---------------------------------------------------------------------------
# Crash recovery (D-06)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_browser_crash_sets_browser_to_none():
    """When browser.is_connected() returns False after exception, _browser is set to None."""
    mock_browser = _make_mock_browser()
    mock_pw = _make_mock_playwright(mock_browser)
    page = _make_mock_page()
    page.content = AsyncMock(side_effect=RuntimeError("browser crashed"))
    # _browser is None before _ensure_browser, so is_connected is never called
    # there. The crash handler at the except block calls it once -> returns False.
    mock_browser.is_connected.side_effect = [False]
    ctx = _make_mock_context(page)
    mock_browser.new_context = AsyncMock(return_value=ctx)

    with patch("scraper_service.browser.async_playwright", return_value=MagicMock(start=AsyncMock(return_value=mock_pw))):
        mgr = BrowserManager(Settings())
        result = await mgr.fetch_page("https://example.com")

    assert mgr._browser is None
    assert result.render_method == RenderMethod.FAILED


@pytest.mark.asyncio
async def test_after_crash_next_call_launches_fresh_browser():
    """After crash detection, next fetch_page call launches a new browser."""
    mock_browser1 = _make_mock_browser()
    mock_browser2 = _make_mock_browser()
    mock_pw = AsyncMock()

    call_num = 0

    async def mock_launch(**kwargs):
        nonlocal call_num
        call_num += 1
        if call_num == 1:
            return mock_browser1
        return mock_browser2

    mock_pw.chromium.launch = mock_launch
    mock_pw.stop = AsyncMock()

    # First browser crashes immediately
    page1 = _make_mock_page()
    page1.content = AsyncMock(side_effect=RuntimeError("crash"))
    # _browser is None before _ensure_browser, so is_connected never called there.
    # Crash handler calls it once -> returns False.
    mock_browser1.is_connected.side_effect = [False]
    ctx1 = _make_mock_context(page1)
    mock_browser1.new_context = AsyncMock(return_value=ctx1)

    # Second browser works fine
    page2 = _make_mock_page(html="<html><body>OK</body></html>")
    ctx2 = _make_mock_context(page2)
    mock_browser2.new_context = AsyncMock(return_value=ctx2)

    with patch("scraper_service.browser.async_playwright", return_value=MagicMock(start=AsyncMock(return_value=mock_pw))):
        mgr = BrowserManager(Settings())
        result1 = await mgr.fetch_page("https://example.com")
        result2 = await mgr.fetch_page("https://example.com")

    assert result1.render_method == RenderMethod.FAILED
    assert result2.render_method == RenderMethod.PLAYWRIGHT
    assert call_num == 2


@pytest.mark.asyncio
async def test_fetch_page_returns_failed_on_crash():
    """Crash during fetch returns PageData with render_method=FAILED."""
    mock_browser = _make_mock_browser()
    mock_pw = _make_mock_playwright(mock_browser)
    page = _make_mock_page()
    page.content = AsyncMock(side_effect=RuntimeError("crashed"))
    # _browser is None before _ensure_browser, so is_connected never called there.
    # Crash handler calls it once -> returns False.
    mock_browser.is_connected.side_effect = [False]
    ctx = _make_mock_context(page)
    mock_browser.new_context = AsyncMock(return_value=ctx)

    with patch("scraper_service.browser.async_playwright", return_value=MagicMock(start=AsyncMock(return_value=mock_pw))):
        mgr = BrowserManager(Settings())
        result = await mgr.fetch_page("https://example.com")

    assert result.render_method == RenderMethod.FAILED
    assert result.error is not None
    assert "crashed" in result.error


# ---------------------------------------------------------------------------
# Networkidle and timeout (FETCH-09, D-07)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_goto_uses_networkidle():
    """page.goto is called with wait_until='networkidle'."""
    mock_browser = _make_mock_browser()
    mock_pw = _make_mock_playwright(mock_browser)
    page = _make_mock_page()
    ctx = _make_mock_context(page)
    mock_browser.new_context = AsyncMock(return_value=ctx)

    with patch("scraper_service.browser.async_playwright", return_value=MagicMock(start=AsyncMock(return_value=mock_pw))):
        mgr = BrowserManager(Settings())
        await mgr.fetch_page("https://example.com")

    page.goto.assert_called_once()
    call_kwargs = page.goto.call_args
    assert call_kwargs[1].get("wait_until") == "networkidle" or (
        len(call_kwargs[0]) > 1 and call_kwargs[0][1] == "networkidle"
    ) or call_kwargs.kwargs.get("wait_until") == "networkidle"


@pytest.mark.asyncio
async def test_goto_timeout_from_settings():
    """Timeout is converted from seconds (settings) to milliseconds for Playwright."""
    mock_browser = _make_mock_browser()
    mock_pw = _make_mock_playwright(mock_browser)
    page = _make_mock_page()
    ctx = _make_mock_context(page)
    mock_browser.new_context = AsyncMock(return_value=ctx)

    with patch("scraper_service.browser.async_playwright", return_value=MagicMock(start=AsyncMock(return_value=mock_pw))):
        mgr = BrowserManager(Settings(timeout=15))
        await mgr.fetch_page("https://example.com")

    call_kwargs = page.goto.call_args.kwargs
    assert call_kwargs.get("timeout") == 15000


@pytest.mark.asyncio
async def test_on_timeout_partial_html_captured():
    """When page.goto times out, whatever HTML was loaded so far is captured."""
    mock_browser = _make_mock_browser()
    mock_pw = _make_mock_playwright(mock_browser)
    page = _make_mock_page(html="<html><body>Partial</body></html>")
    page.goto = AsyncMock(side_effect=TimeoutError("networkidle timeout"))
    ctx = _make_mock_context(page)
    mock_browser.new_context = AsyncMock(return_value=ctx)

    with patch("scraper_service.browser.async_playwright", return_value=MagicMock(start=AsyncMock(return_value=mock_pw))):
        mgr = BrowserManager(Settings())
        result = await mgr.fetch_page("https://example.com")

    # Partial HTML should still be captured
    assert result.html == "<html><body>Partial</body></html>"


@pytest.mark.asyncio
async def test_on_timeout_render_method_still_playwright():
    """Timeout is not a hard failure -- render_method stays PLAYWRIGHT for partial content."""
    mock_browser = _make_mock_browser()
    mock_pw = _make_mock_playwright(mock_browser)
    page = _make_mock_page(html="<html><body>Partial</body></html>")
    page.goto = AsyncMock(side_effect=TimeoutError("timeout"))
    ctx = _make_mock_context(page)
    mock_browser.new_context = AsyncMock(return_value=ctx)

    with patch("scraper_service.browser.async_playwright", return_value=MagicMock(start=AsyncMock(return_value=mock_pw))):
        mgr = BrowserManager(Settings())
        result = await mgr.fetch_page("https://example.com")

    assert result.render_method == RenderMethod.PLAYWRIGHT


# ---------------------------------------------------------------------------
# XHR response capture (FETCH-09)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_response_handler_registered_on_page():
    """page.on('response', handler) is called during fetch."""
    mock_browser = _make_mock_browser()
    mock_pw = _make_mock_playwright(mock_browser)
    page = _make_mock_page()
    ctx = _make_mock_context(page)
    mock_browser.new_context = AsyncMock(return_value=ctx)

    with patch("scraper_service.browser.async_playwright", return_value=MagicMock(start=AsyncMock(return_value=mock_pw))):
        mgr = BrowserManager(Settings())
        await mgr.fetch_page("https://example.com")

    page.on.assert_called_once()
    args = page.on.call_args[0]
    assert args[0] == "response"


@pytest.mark.asyncio
async def test_json_responses_captured():
    """The response handler captures JSON responses into the list."""
    captured: list[dict] = []
    handler = BrowserManager._make_response_handler(captured)

    mock_response = AsyncMock()
    mock_response.headers = {"content-type": "application/json"}
    mock_response.url = "https://api.example.com/data"
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"key": "value"})

    await handler(mock_response)

    assert len(captured) == 1
    assert captured[0]["url"] == "https://api.example.com/data"
    assert captured[0]["status"] == 200
    assert captured[0]["body"] == {"key": "value"}


@pytest.mark.asyncio
async def test_only_json_content_type_captured():
    """Non-JSON responses are ignored by the handler."""
    captured: list[dict] = []
    handler = BrowserManager._make_response_handler(captured)

    mock_response = AsyncMock()
    mock_response.headers = {"content-type": "text/html"}
    mock_response.url = "https://example.com/page"
    mock_response.status = 200

    await handler(mock_response)

    assert len(captured) == 0


@pytest.mark.asyncio
async def test_bad_json_body_ignored():
    """Failed JSON body reads are silently ignored -- no crash."""
    captured: list[dict] = []
    handler = BrowserManager._make_response_handler(captured)

    mock_response = AsyncMock()
    mock_response.headers = {"content-type": "application/json"}
    mock_response.url = "https://api.example.com/bad"
    mock_response.status = 200
    mock_response.json = AsyncMock(side_effect=RuntimeError("not valid json"))

    await handler(mock_response)

    assert len(captured) == 0


@pytest.mark.asyncio
async def test_xhr_responses_in_page_data():
    """Captured XHR responses appear in the returned PageData.xhr_responses."""
    mock_browser = _make_mock_browser()
    mock_pw = _make_mock_playwright(mock_browser)
    page = _make_mock_page()
    ctx = _make_mock_context(page)
    mock_browser.new_context = AsyncMock(return_value=ctx)

    async def simulate_xhr_capture(url, **kwargs):
        # Find the response handler registered via page.on
        on_call_args = page.on.call_args
        if on_call_args:
            handler = on_call_args[0][1]
            mock_resp = AsyncMock()
            mock_resp.headers = {"content-type": "application/json"}
            mock_resp.url = "https://api.example.com/data"
            mock_resp.status = 200
            mock_resp.json = AsyncMock(return_value={"items": [1, 2, 3]})
            await handler(mock_resp)

    page.goto = AsyncMock(side_effect=simulate_xhr_capture)

    with patch("scraper_service.browser.async_playwright", return_value=MagicMock(start=AsyncMock(return_value=mock_pw))):
        mgr = BrowserManager(Settings())
        result = await mgr.fetch_page("https://example.com")

    assert result.xhr_responses is not None
    assert len(result.xhr_responses) == 1
    assert result.xhr_responses[0]["body"] == {"items": [1, 2, 3]}


# ---------------------------------------------------------------------------
# Proxy support
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_proxy_configured_at_browser_launch():
    """If settings.proxy_url is set, browser is launched with proxy."""
    mock_browser = _make_mock_browser()
    mock_pw = _make_mock_playwright(mock_browser)

    with patch("scraper_service.browser.async_playwright", return_value=MagicMock(start=AsyncMock(return_value=mock_pw))):
        mgr = BrowserManager(Settings(proxy_url="http://user:pass@proxy:8080"))
        await mgr._ensure_browser()

    launch_kwargs = mock_pw.chromium.launch.call_args.kwargs
    assert "proxy" in launch_kwargs
    assert launch_kwargs["proxy"]["server"] == "http://user:pass@proxy:8080"


@pytest.mark.asyncio
async def test_no_proxy_when_not_set():
    """When proxy_url is empty, no proxy kwarg passed to launch."""
    mock_browser = _make_mock_browser()
    mock_pw = _make_mock_playwright(mock_browser)

    with patch("scraper_service.browser.async_playwright", return_value=MagicMock(start=AsyncMock(return_value=mock_pw))):
        mgr = BrowserManager(Settings(proxy_url=""))
        await mgr._ensure_browser()

    launch_kwargs = mock_pw.chromium.launch.call_args.kwargs
    assert "proxy" not in launch_kwargs


# ---------------------------------------------------------------------------
# close() cleanup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_close_closes_browser_and_stops_playwright():
    """close() calls browser.close() and playwright.stop()."""
    mock_browser = _make_mock_browser()
    mock_pw = _make_mock_playwright(mock_browser)

    with patch("scraper_service.browser.async_playwright", return_value=MagicMock(start=AsyncMock(return_value=mock_pw))):
        mgr = BrowserManager(Settings())
        await mgr._ensure_browser()
        await mgr.close()

    mock_browser.close.assert_called_once()
    mock_pw.stop.assert_called_once()


@pytest.mark.asyncio
async def test_close_is_idempotent():
    """Calling close() multiple times does not raise."""
    mock_browser = _make_mock_browser()
    mock_pw = _make_mock_playwright(mock_browser)

    with patch("scraper_service.browser.async_playwright", return_value=MagicMock(start=AsyncMock(return_value=mock_pw))):
        mgr = BrowserManager(Settings())
        await mgr._ensure_browser()
        await mgr.close()
        await mgr.close()  # Second call should not raise

    # browser.close should be called once (not on the second close)
    assert mock_browser.close.call_count == 1


@pytest.mark.asyncio
async def test_after_close_browser_and_playwright_are_none():
    """After close(), _browser and _playwright are reset to None."""
    mock_browser = _make_mock_browser()
    mock_pw = _make_mock_playwright(mock_browser)

    with patch("scraper_service.browser.async_playwright", return_value=MagicMock(start=AsyncMock(return_value=mock_pw))):
        mgr = BrowserManager(Settings())
        await mgr._ensure_browser()
        await mgr.close()

    assert mgr._browser is None
    assert mgr._playwright is None


# ---------------------------------------------------------------------------
# Headless mode (D-08)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_headless_true_by_default():
    """Browser launched with headless=True by default."""
    mock_browser = _make_mock_browser()
    mock_pw = _make_mock_playwright(mock_browser)

    with patch("scraper_service.browser.async_playwright", return_value=MagicMock(start=AsyncMock(return_value=mock_pw))):
        mgr = BrowserManager(Settings())
        await mgr._ensure_browser()

    launch_kwargs = mock_pw.chromium.launch.call_args.kwargs
    assert launch_kwargs["headless"] is True


@pytest.mark.asyncio
async def test_headless_false_when_configured():
    """Browser launched with headless=False when settings.headless=False."""
    mock_browser = _make_mock_browser()
    mock_pw = _make_mock_playwright(mock_browser)

    with patch("scraper_service.browser.async_playwright", return_value=MagicMock(start=AsyncMock(return_value=mock_pw))):
        mgr = BrowserManager(Settings(headless=False))
        await mgr._ensure_browser()

    launch_kwargs = mock_pw.chromium.launch.call_args.kwargs
    assert launch_kwargs["headless"] is False


# ---------------------------------------------------------------------------
# Launch failure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_browser_launch_failure_returns_failed_page_data():
    """If _ensure_browser fails, fetch_page returns FAILED PageData instead of crashing."""
    mock_pw = AsyncMock()
    mock_pw.chromium.launch = AsyncMock(side_effect=RuntimeError("no chromium installed"))
    mock_pw.stop = AsyncMock()

    with patch("scraper_service.browser.async_playwright", return_value=MagicMock(start=AsyncMock(return_value=mock_pw))):
        mgr = BrowserManager(Settings())
        result = await mgr.fetch_page("https://example.com")

    assert result.render_method == RenderMethod.FAILED
    assert "Browser launch failed" in result.error


# ---------------------------------------------------------------------------
# Context cleanup on success
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_context_closed_on_success():
    """After a successful fetch, the context is closed."""
    mock_browser = _make_mock_browser()
    mock_pw = _make_mock_playwright(mock_browser)
    page = _make_mock_page()
    ctx = _make_mock_context(page)
    mock_browser.new_context = AsyncMock(return_value=ctx)

    with patch("scraper_service.browser.async_playwright", return_value=MagicMock(start=AsyncMock(return_value=mock_pw))):
        mgr = BrowserManager(Settings())
        await mgr.fetch_page("https://example.com")

    ctx.close.assert_called_once()
