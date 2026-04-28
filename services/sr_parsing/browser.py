"""Playwright browser lifecycle manager for JS-heavy page rendering."""
from __future__ import annotations

import asyncio
import random
from typing import Any, Callable

import structlog
from playwright.async_api import Browser, BrowserContext, Playwright, async_playwright

from scraper_service.models import ErrorType, PageData, RenderMethod
from scraper_service.settings import Settings


class BrowserManager:
    """Manages a single Playwright Chromium browser instance with lazy launch,
    per-URL context isolation, crash recovery, and XHR response capture.

    Not an async context manager itself -- callers use close() to shut down.
    This keeps the Scraper as the single lifecycle owner.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._lock = asyncio.Lock()
        self._log = structlog.get_logger()

    async def _ensure_browser(self) -> Browser:
        """Lazy launch browser on first use (D-05).

        Uses asyncio.Lock to prevent concurrent browser creation when
        multiple coroutines hit this at the same time (Pitfall 6).
        """
        async with self._lock:
            if self._browser is not None and self._browser.is_connected():
                return self._browser
            # Clean up old playwright instance if browser disconnected
            if self._playwright is not None:
                try:
                    await self._playwright.stop()
                except Exception:
                    pass
            self._playwright = await async_playwright().start()
            launch_args = [
                "--disable-gpu",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ]
            kwargs: dict[str, Any] = {
                "headless": self._settings.headless,
                "args": launch_args,
            }
            if self._settings.proxy_url:
                kwargs["proxy"] = {"server": self._settings.proxy_url}
            self._browser = await self._playwright.chromium.launch(**kwargs)
            self._log.info("browser_launched", headless=self._settings.headless)
            return self._browser

    async def fetch_page(self, url: str) -> PageData:
        """Fetch URL using Playwright with per-URL context (FETCH-13).

        Creates a fresh BrowserContext for each URL, waits for networkidle,
        captures XHR JSON responses, and always closes the context in finally.
        """
        try:
            browser = await self._ensure_browser()
        except Exception as exc:
            self._log.error("browser_launch_failed", error=str(exc))
            return PageData(
                url=url,
                final_url=url,
                render_method=RenderMethod.FAILED,
                error=f"Browser launch failed: {exc}",
                error_type=ErrorType.PLAYWRIGHT_CRASH,
            )

        context: BrowserContext | None = None
        try:
            context = await browser.new_context(
                user_agent=random.choice(self._settings.user_agent_pool),
            )
            page = await context.new_page()
            captured_responses: list[dict[str, Any]] = []

            # Capture XHR responses (FETCH-09)
            page.on("response", self._make_response_handler(captured_responses))

            timeout_ms = self._settings.timeout * 1000
            main_response = None
            try:
                main_response = await page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            except Exception as exc:
                # Timeout or navigation error -- capture partial content
                self._log.warning(
                    "playwright_navigation_issue", url=url, error=str(exc)
                )

            html = await page.content()

            # Filter to only entries with a body
            xhr_data: list[dict[str, Any]] = [
                r for r in captured_responses if r.get("body") is not None
            ]

            # Capture whitelisted headers from main navigation response
            captured_headers: dict[str, str] | None = None
            status_code = 200
            if main_response is not None:
                try:
                    s = main_response.status
                    if isinstance(s, int):
                        status_code = s
                except Exception:
                    pass
                try:
                    _CAPTURE = {
                        "last-modified", "etag", "cache-control", "date",
                        "content-type", "x-robots-tag", "content-language",
                    }
                    raw_headers = main_response.headers
                    if isinstance(raw_headers, dict):
                        hdrs = {
                            k.lower(): v
                            for k, v in raw_headers.items()
                            if k.lower() in _CAPTURE
                        }
                        captured_headers = hdrs or None
                except Exception:
                    pass

            return PageData(
                url=url,
                final_url=page.url,
                status_code=status_code,
                render_method=RenderMethod.PLAYWRIGHT,
                html=html,
                xhr_responses=xhr_data if xhr_data else None,
                response_headers=captured_headers,
            )
        except Exception as exc:
            # D-06: Auto-restart on browser crash
            if browser and not browser.is_connected():
                self._log.error("browser_crash_detected", url=url)
                self._browser = None
            self._log.warning("playwright_fetch_failed", url=url, error=str(exc))
            return PageData(
                url=url,
                final_url=url,
                render_method=RenderMethod.FAILED,
                error=str(exc),
                error_type=ErrorType.PLAYWRIGHT_CRASH,
            )
        finally:
            if context:
                await context.close()

    @staticmethod
    def _make_response_handler(
        captured: list[dict[str, Any]],
    ) -> Callable[..., Any]:
        """Create response handler that captures JSON API responses (FETCH-09).

        Only captures responses with "json" in the content-type header.
        Failed JSON body reads are silently ignored.
        """

        async def handle_response(response: Any) -> None:
            content_type = response.headers.get("content-type", "")
            if "json" not in content_type:
                return
            try:
                body = await response.json()
                captured.append(
                    {
                        "url": response.url,
                        "status": response.status,
                        "body": body,
                    }
                )
            except Exception:
                pass  # Silently ignore failed JSON reads

        return handle_response

    async def close(self) -> None:
        """Close browser and stop Playwright instance. Idempotent."""
        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
            self._browser = None
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None
