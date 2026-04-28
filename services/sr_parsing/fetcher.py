"""Async httpx fetcher with tier escalation: httpx -> XHR sniffing -> Playwright."""
from __future__ import annotations

import random
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import asyncio
import httpx
import structlog
from email.utils import parsedate_to_datetime

from tenacity import (
    AsyncRetrying,
    RetryCallState,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)
from tenacity.wait import wait_base

from scraper_service.browser import BrowserManager
from scraper_service.logging import bind_correlation_id, configure_logging
from scraper_service.robots import RobotsChecker
from scraper_service.extractors.runner import extract_page
from scraper_service.models import (
    ErrorType,
    ExtractionResult,
    PageData,
    RenderMethod,
    ScrapedPage,
    ScrapeRequest,
    SinkConfig,
)
from scraper_service.sinks import run_sinks
from scraper_service.sinks.factory import build_sinks
from scraper_service.settings import Settings
from scraper_service.sufficiency import is_content_sufficient
from scraper_service.urls import deduplicate_urls, is_valid_url
from scraper_service.xhr_sniffer import extract_xhr_content

_CAPTURE_HEADERS: frozenset[str] = frozenset({
    "last-modified", "etag", "cache-control", "date",
    "content-type", "x-robots-tag", "content-language",
})


def _extract_headers(response: httpx.Response) -> dict[str, str] | None:
    """Extract whitelisted headers from an httpx response."""
    try:
        captured = {
            k.lower(): v for k, v in response.headers.items()
            if k.lower() in _CAPTURE_HEADERS
        }
        return captured or None
    except Exception:
        return None


_BROWSER_HEADERS: dict[str, str] = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "DNT": "1",
}


def _is_retryable(exc: BaseException) -> bool:
    """Check if an exception should trigger a retry.

    Returns True for:
    - httpx.TimeoutException (request timeout)
    - httpx.NetworkError (connection errors)
    - httpx.HTTPStatusError with status_code >= 500 (server errors)

    Returns False for:
    - httpx.HTTPStatusError with status_code < 500 (client errors like 404)
    - All other exceptions
    """
    if isinstance(exc, httpx.TimeoutException):
        return True
    if isinstance(exc, httpx.NetworkError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status >= 500 or status == 429
    return False


_MAX_RETRY_AFTER_SECONDS: float = 60.0


def _parse_retry_after(value: str) -> float:
    """Parse Retry-After header value as seconds or HTTP-date.

    Returns seconds to wait, capped at _MAX_RETRY_AFTER_SECONDS.
    """
    try:
        seconds = float(value)
        return min(seconds, _MAX_RETRY_AFTER_SECONDS)
    except ValueError:
        pass
    try:
        dt = parsedate_to_datetime(value)
        delta = (dt - datetime.now(timezone.utc)).total_seconds()
        return min(max(0.0, delta), _MAX_RETRY_AFTER_SECONDS)
    except Exception:
        return 0.0


class WaitRetryAfter(wait_base):
    """Custom tenacity wait that respects Retry-After header on 429 responses."""

    def __init__(self, fallback: wait_base) -> None:
        self.fallback = fallback

    def __call__(self, retry_state: RetryCallState) -> float:
        exc = retry_state.outcome.exception() if retry_state.outcome else None
        if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429:
            retry_after = exc.response.headers.get("Retry-After")
            if retry_after:
                return _parse_retry_after(retry_after)
        return self.fallback(retry_state)


class Scraper:
    """Async fetcher with tier escalation: httpx -> XHR sniffing -> Playwright.

    Lifecycle:
        async with Scraper(settings) as scraper:
            results = await scraper.fetch(urls)

    The async context manager creates an httpx.AsyncClient and BrowserManager
    on enter and closes both on exit.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        force_render_method: RenderMethod | None = None,
    ) -> None:
        """Initialize the scraper with optional settings and forced render method.

        Args:
            settings: Application settings. If None, uses default Settings().
            force_render_method: Force all fetches to use this tier. Takes
                precedence over ScrapeRequest.render_method. None = auto-detect.
        """
        self._settings = settings or Settings()
        self._client: httpx.AsyncClient | None = None
        self._semaphore: asyncio.Semaphore | None = None
        self._browser_manager: BrowserManager | None = None
        self._force_render_method = force_render_method
        self._respect_robots: bool = False
        self._robots_checker: RobotsChecker | None = None
        self._log = structlog.get_logger()

    async def __aenter__(self) -> Scraper:
        """Create httpx.AsyncClient, BrowserManager, and semaphore on context entry.

        Returns:
            Self for use in async with statement.
        """
        configure_logging(level=self._settings.log_level)
        bind_correlation_id()
        self._client = httpx.AsyncClient(
            timeout=self._settings.timeout,
            follow_redirects=True,
        )
        self._semaphore = asyncio.Semaphore(
            self._settings.max_concurrent_requests
        )
        self._browser_manager = BrowserManager(self._settings)
        self._circuit_breaker: dict[str, int] = {}
        return self

    async def __aexit__(self, *args: object) -> None:
        """Close BrowserManager and httpx.AsyncClient on context exit."""
        if self._browser_manager:
            await self._browser_manager.close()
            self._browser_manager = None
        if self._client:
            await self._client.aclose()

    async def fetch(
        self,
        urls: list[str],
        scrape_request: ScrapeRequest | None = None,
    ) -> list[PageData]:
        """Fetch multiple URLs concurrently with tier escalation.

        Args:
            urls: List of URLs to fetch. Invalid URLs are rejected upfront.
            scrape_request: Optional request with per-request render_method
                override. Ignored if constructor force_render_method is set.

        Returns:
            List of PageData in the same order as input URLs. Invalid URLs
            appear at their original index with error state.

        Raises:
            ValueError: If URL count exceeds max_pages_per_job.
        """
        if len(urls) > self._settings.max_pages_per_job:
            raise ValueError(
                f"Too many URLs: {len(urls)} exceeds max_pages_per_job={self._settings.max_pages_per_job}"
            )
        self._log.info("fetch_started", url_count=len(urls))

        # Resolve effective render method: constructor param wins over per-request
        self._force_render_method = (
            self._force_render_method
            or (scrape_request.render_method if scrape_request else None)
        )

        # Set up robots.txt checking if requested
        self._respect_robots = (
            scrape_request.respect_robots if scrape_request else False
        )
        if self._respect_robots and self._client:
            self._robots_checker = RobotsChecker(
                self._client, timeout=self._settings.robots_timeout
            )
        else:
            self._robots_checker = None

        # Classify URLs as valid or invalid, preserving original positions
        validity: list[tuple[str, bool]] = [
            (url, is_valid_url(url)) for url in urls
        ]

        # Collect valid URLs, deduplicate, track which original indices they map to
        valid_urls_seen: list[str] = []
        for url, is_valid in validity:
            if is_valid:
                valid_urls_seen.append(url)

        valid_urls = deduplicate_urls(valid_urls_seen)

        # Fetch valid URLs concurrently
        # Map from normalized URL to PageData result
        fetch_results: dict[str, PageData] = {}
        if valid_urls and self._client and self._semaphore:
            fetched = await asyncio.gather(
                *[self._fetch_single(u) for u in valid_urls],
                return_exceptions=False,
            )
            # Map by normalized URL for dedup lookup
            from scraper_service.urls import normalize_url
            for page_data in fetched:
                normalized = normalize_url(page_data.url)
                fetch_results[normalized] = page_data

        # Build results in input order -- invalid URLs get error PageData at their index
        results: list[PageData] = []
        from scraper_service.urls import normalize_url
        for url, is_valid in validity:
            if not is_valid:
                results.append(PageData(
                    url=url,
                    final_url=url,
                    status_code=None,
                    fetched_at=datetime.now(timezone.utc),
                    render_method=RenderMethod.FAILED,
                    error=f"Invalid URL: {url}",
                    error_type=ErrorType.INVALID_URL,
                ))
            else:
                normalized = normalize_url(url)
                pd: PageData | None = fetch_results.get(normalized)
                if pd is not None:
                    # For duplicate URLs, create a PageData with the original URL but same fetched data
                    if url != pd.url:
                        results.append(PageData(
                            url=url,
                            final_url=pd.final_url,
                            status_code=pd.status_code,
                            fetched_at=pd.fetched_at,
                            render_method=pd.render_method,
                            html=pd.html,
                            error=pd.error,
                        ))
                    else:
                        results.append(pd)
                else:
                    results.append(PageData(
                        url=url,
                        final_url=url,
                        status_code=None,
                        fetched_at=datetime.now(timezone.utc),
                        render_method=RenderMethod.FAILED,
                        error="URL not fetched (internal error)",
                    ))

        self._log.info("fetch_completed", total=len(results))
        return results

    async def scrape(
        self,
        urls: list[str],
        sinks: list[SinkConfig] | None = None,
    ) -> list[ScrapedPage]:
        """Full pipeline: fetch -> extract -> sinks.

        Must be called within the async context manager. Raises
        RuntimeError if the httpx client has not been initialized.
        """
        if self._client is None:
            raise RuntimeError(
                "Scraper.scrape() called outside async context manager. "
                "Use: async with Scraper() as s: await s.scrape(urls)"
            )
        pages = await self.fetch(urls)
        scraped: list[ScrapedPage] = []
        for page in pages:
            if page.html:
                extraction = extract_page(page.html, page.url, response_headers=page.response_headers)
            else:
                extraction = ExtractionResult()
            scraped.append(ScrapedPage(
                page_data=page,
                extraction_result=extraction,
            ))
        if sinks:
            sink_objs = await build_sinks(sinks, self._settings)
            await run_sinks(scraped, sink_objs)
        return scraped

    async def _fetch_single(self, url: str) -> PageData:
        """Fetch a single URL with three-tier escalation.

        Tier 1: httpx (fast, static HTML)
        Tier 2: XHR sniffing (extract embedded framework data)
        Tier 3: Playwright (full browser render)

        If force_render_method is set, only that tier is used.
        Checks domain-level circuit breaker before fetching.
        """
        assert self._client is not None
        assert self._semaphore is not None
        assert self._browser_manager is not None

        domain = urlparse(url).netloc.lower()

        # Circuit breaker: skip fetch if domain has 5+ consecutive failures
        if self._circuit_breaker.get(domain, 0) >= 5:
            return PageData(
                url=url,
                final_url=url,
                render_method=RenderMethod.FAILED,
                error=f"Circuit breaker tripped for {domain} after 5 consecutive failures",
                error_type=ErrorType.CIRCUIT_BREAKER,
            )

        async with self._semaphore:
            # Robots.txt check (D-07, D-08, D-10, D-11)
            # Runs after circuit breaker -- no point checking robots for a tripped domain
            if self._respect_robots and self._robots_checker:
                allowed = await self._robots_checker.is_allowed(url)
                if not allowed:
                    self._log.info("robots_denied", url=url)
                    return PageData(
                        url=url,
                        final_url=url,
                        render_method=RenderMethod.FAILED,
                        error=f"Blocked by robots.txt for {urlparse(url).netloc}",
                        error_type=ErrorType.ROBOTS_DENIED,
                    )

            # If forced to Playwright, skip httpx entirely
            if self._force_render_method == RenderMethod.PLAYWRIGHT:
                result = await self._browser_manager.fetch_page(url)
                self._log.info(
                    "fetch_completed",
                    url=url,
                    render_method=result.render_method.value,
                    forced=True,
                )
                self._update_circuit_breaker(domain, result)
                return result

            # Tier 1: httpx
            httpx_result = await self._fetch_httpx(url)
            if self._force_render_method == RenderMethod.HTTPX:
                self._update_circuit_breaker(domain, httpx_result)
                return httpx_result
            if httpx_result.error:
                is_403 = "403" in (httpx_result.error or "")
                if is_403:
                    self._log.info(
                        "tier_escalation",
                        url=url,
                        from_tier="httpx",
                        to_tier="playwright",
                        reason=httpx_result.error,
                    )
                    result = await self._browser_manager.fetch_page(url)
                    self._update_circuit_breaker(domain, result)
                    return result
                self._update_circuit_breaker(domain, httpx_result)
                return httpx_result

            # Check content sufficiency
            html = httpx_result.html or ""
            if is_content_sufficient(html, self._settings.min_body_chars):
                self._log.info("fetch_completed", url=url, render_method="httpx")
                self._update_circuit_breaker(domain, httpx_result)
                return httpx_result

            self._log.info(
                "tier_escalation",
                url=url,
                from_tier="httpx",
                reason="insufficient_content",
            )

            # If forced to XHR, try XHR only (no Playwright)
            if self._force_render_method == RenderMethod.XHR:
                xhr_html = extract_xhr_content(html)
                if xhr_html:
                    result = self._make_xhr_result(url, httpx_result, xhr_html)
                    self._update_circuit_breaker(domain, result)
                    return result
                self._update_circuit_breaker(domain, httpx_result)
                return httpx_result  # Return httpx as best effort

            # Tier 2: XHR sniffing
            xhr_html = extract_xhr_content(html)
            if xhr_html:
                # Re-check sufficiency on XHR-reconstructed HTML
                if is_content_sufficient(xhr_html, self._settings.min_body_chars):
                    self._log.info(
                        "tier_escalation",
                        url=url,
                        from_tier="httpx",
                        to_tier="xhr",
                    )
                    result = self._make_xhr_result(url, httpx_result, xhr_html)
                    self._update_circuit_breaker(domain, result)
                    return result
                # XHR data found but insufficient -- escalate
                self._log.info(
                    "tier_escalation",
                    url=url,
                    from_tier="xhr",
                    to_tier="playwright",
                    reason="xhr_insufficient",
                )

            # Tier 3: Playwright
            self._log.info(
                "tier_escalation",
                url=url,
                from_tier="httpx",
                to_tier="playwright",
            )
            result = await self._browser_manager.fetch_page(url)
            self._log.info(
                "fetch_completed",
                url=url,
                render_method=result.render_method.value,
            )
            self._update_circuit_breaker(domain, result)
            return result

    def _update_circuit_breaker(self, domain: str, result: PageData) -> None:
        """Update the per-domain failure counter after a fetch attempt."""
        if result.error:
            self._circuit_breaker[domain] = self._circuit_breaker.get(domain, 0) + 1
        else:
            self._circuit_breaker[domain] = 0

    async def _fetch_httpx(self, url: str) -> PageData:
        """Fetch a URL using httpx with retry logic and error isolation.

        This is the Tier 1 fetch -- always tried first unless forced to
        Playwright. Tries direct first (no proxy). On 403/429/network
        errors, falls back to proxy if use_proxy=True and proxy_url is set.
        Classifies failures into ErrorType categories.
        """
        headers = {
            **_BROWSER_HEADERS,
            "User-Agent": random.choice(self._settings.user_agent_pool),
        }
        t0 = time.monotonic()
        try:
            # Direct fetch -- no proxy on first attempt (D-18)
            response = await self._do_fetch(url, headers, proxy=None)
            duration_ms = round((time.monotonic() - t0) * 1000, 1)
            return PageData(
                url=url,
                final_url=str(response.url),
                status_code=response.status_code,
                fetched_at=datetime.now(timezone.utc),
                render_method=RenderMethod.HTTPX,
                html=response.text,
                response_headers=_extract_headers(response),
                fetch_duration_ms=duration_ms,
            )
        except Exception as exc:
            # Try proxy fallback before giving up
            if self._should_try_proxy(exc):
                proxy_result = await self._try_proxy_fallback(url, headers, exc)
                if proxy_result is not None:
                    return proxy_result

            # Classify error type based on the original exception
            if isinstance(exc, httpx.TimeoutException):
                error_type: ErrorType | None = ErrorType.TIMEOUT
            elif isinstance(exc, httpx.HTTPStatusError):
                error_type = ErrorType.HTTP_5XX if exc.response.status_code >= 500 else ErrorType.HTTP_4XX
            elif isinstance(exc, httpx.NetworkError):
                error_type = ErrorType.NETWORK
            else:
                error_type = None

            self._log.warning("fetch_failed", url=url, error=str(exc))
            return PageData(
                url=url,
                final_url=url,
                status_code=None,
                fetched_at=datetime.now(timezone.utc),
                render_method=RenderMethod.FAILED,
                error=str(exc),
                error_type=error_type,
            )

    def _should_try_proxy(self, exc: Exception) -> bool:
        """Check if the error warrants a proxy fallback attempt."""
        if not self._settings.use_proxy:
            return False
        if not self._settings.proxy_url:
            self._log.warning(
                "proxy_fallback_skipped",
                reason="use_proxy=true but proxy_url is empty",
            )
            return False
        if isinstance(exc, httpx.HTTPStatusError):
            return exc.response.status_code in (403, 429)
        if isinstance(exc, (httpx.NetworkError, httpx.TimeoutException)):
            return True
        return False

    async def _try_proxy_fallback(
        self, url: str, headers: dict[str, str], original_exc: Exception,
    ) -> PageData | None:
        """Single proxy attempt outside the main retry loop (D-18).

        Returns PageData on success, None if proxy also fails (so the
        caller falls through to error classification with the original error).
        """
        self._log.info("proxy_fallback", url=url, reason=str(original_exc))
        assert self._client is not None
        t0 = time.monotonic()
        try:
            response = await self._client.get(
                url, headers=headers, proxy=self._settings.proxy_url,
            )
            response.raise_for_status()
            duration_ms = round((time.monotonic() - t0) * 1000, 1)
            return PageData(
                url=url,
                final_url=str(response.url),
                status_code=response.status_code,
                fetched_at=datetime.now(timezone.utc),
                render_method=RenderMethod.HTTPX,
                html=response.text,
                response_headers=_extract_headers(response),
                fetch_duration_ms=duration_ms,
            )
        except Exception as proxy_exc:
            self._log.warning(
                "proxy_fallback_failed", url=url, error=str(proxy_exc),
            )
            return None

    @staticmethod
    def _make_xhr_result(
        url: str,
        httpx_result: PageData,
        xhr_html: str,
    ) -> PageData:
        """Build a PageData for XHR-tier results using httpx metadata."""
        return PageData(
            url=url,
            final_url=httpx_result.final_url,
            status_code=httpx_result.status_code,
            render_method=RenderMethod.XHR,
            html=xhr_html,
        )

    async def _do_fetch(
        self,
        url: str,
        headers: dict[str, str],
        proxy: str | None,
    ) -> httpx.Response:
        """Perform HTTP GET with retry logic using tenacity.

        Args:
            url: URL to fetch.
            headers: Request headers including User-Agent.
            proxy: Optional proxy URL.

        Returns:
            httpx.Response on success.

        Raises:
            httpx.HTTPStatusError: For 4xx responses (not retried).
            httpx.TimeoutException: If all retries timeout.
            httpx.NetworkError: If all retries fail.
            RuntimeError: If unreachable code path.
        """
        assert self._client is not None
        kwargs: dict[str, Any] = {"headers": headers}
        if proxy:
            kwargs["proxy"] = proxy

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self._settings.max_retries),
            wait=WaitRetryAfter(
                fallback=wait_exponential(
                    multiplier=self._settings.retry_backoff, min=1, max=10
                ),
            ),
            retry=retry_if_exception(_is_retryable),
            reraise=True,
        ):
            with attempt:
                response = await self._client.get(url, **kwargs)
                response.raise_for_status()
                return response
        raise RuntimeError("unreachable")  # for type checker
