"""Async SerpAPI HTTP client.

Fetches JSON results, raw HTML, and screenshots from SerpAPI.
No Django dependencies -- uses httpx for all HTTP calls.
"""
from __future__ import annotations

import base64
import os
from typing import Any

import httpx
import structlog

from scraper_service.serp.models import SerpSnapshot

logger = structlog.get_logger()

SERPAPI_JSON_BASE = "https://serpapi.com/search.json"
SERPAPI_HTML_BASE = "https://serpapi.com/search.html"


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def _api_key() -> str:
    """Read SERPAPI_API_KEY from environment, raise if missing."""
    key = os.environ.get("SERPAPI_API_KEY", "")
    if not key:
        raise RuntimeError(
            "SERPAPI_API_KEY is not configured. Set the SERPAPI_API_KEY environment variable."
        )
    return key


# ---------------------------------------------------------------------------
# Parameter helpers
# ---------------------------------------------------------------------------


def _hl(language: str) -> str:
    """Extract language code: 'pt-BR' -> 'pt', default 'en'."""
    if not language:
        return "en"
    return (language.split("-", 1)[0] or "en").lower()


def _gl(market: str) -> str:
    """Lowercase market code: 'US' -> 'us', default 'us'."""
    return (market or "us").lower()


def _build_params(
    keyword: str, market: str, language: str, num: int, api_key: str
) -> dict[str, Any]:
    return {
        "engine": "google",
        "q": keyword,
        "num": num,
        "hl": _hl(language),
        "gl": _gl(market),
        "api_key": api_key,
        "screenshot": "true",
    }


# ---------------------------------------------------------------------------
# PNG dimension parsing (no Pillow)
# ---------------------------------------------------------------------------


def _png_dimensions(png_bytes: bytes) -> tuple[int | None, int | None]:
    """Read width/height from PNG IHDR chunk. Returns (None, None) on bad data."""
    if len(png_bytes) < 24:
        return None, None
    if png_bytes[:8] != b"\x89PNG\r\n\x1a\n":
        return None, None
    if png_bytes[12:16] != b"IHDR":
        return None, None
    width = int.from_bytes(png_bytes[16:20], "big")
    height = int.from_bytes(png_bytes[20:24], "big")
    return width, height


# ---------------------------------------------------------------------------
# Screenshot extraction
# ---------------------------------------------------------------------------


async def extract_screenshot_png(
    data: dict[str, Any],
    http_client: httpx.AsyncClient | None = None,
) -> bytes | None:
    """Pull raw PNG bytes from the SerpAPI JSON response.

    Handles three formats:
      - base64 data URL: "data:image/png;base64,..."
      - HTTP URL string: "https://..."
      - dict with "link" key: {"link": "https://..."}

    For HTTP URLs, uses the provided client or creates a temporary one.
    """
    shot = data.get("screenshot")
    if not shot:
        return None

    # base64 data URL
    if isinstance(shot, str) and shot.startswith("data:image/png;base64,"):
        return base64.b64decode(shot.split(",", 1)[1])

    # Resolve URL from string or dict
    url: str | None = None
    if isinstance(shot, str) and shot.startswith("http"):
        url = shot
    elif isinstance(shot, dict) and shot.get("link"):
        url = shot["link"]

    if url:
        client = http_client
        own_client = False
        try:
            if client is None:
                client = httpx.AsyncClient(timeout=40.0)
                own_client = True
            resp = await client.get(url)
            if resp.status_code < 400:
                return resp.content
        except Exception:
            logger.warning("screenshot_download_failed", url=url)
        finally:
            if own_client and client is not None:
                await client.aclose()

    return None


# ---------------------------------------------------------------------------
# SerpApiClient
# ---------------------------------------------------------------------------


class SerpApiClient:
    """Async client for SerpAPI search.json and search.html endpoints."""

    def __init__(
        self,
        api_key: str | None = None,
        timeout: float = 40.0,
        html_timeout: float = 60.0,
    ) -> None:
        self._api_key = api_key or _api_key()
        self._timeout = timeout
        self._html_timeout = html_timeout
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> SerpApiClient:
        self._client = httpx.AsyncClient(timeout=self._timeout)
        return self

    async def __aexit__(self, *exc: Any) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def fetch(
        self,
        keyword: str,
        market: str,
        language: str,
        num: int = 10,
    ) -> SerpSnapshot:
        """Fetch SERP data from SerpAPI. Returns a populated SerpSnapshot."""
        assert self._client is not None, "Use 'async with SerpApiClient()'"

        params = _build_params(keyword, market, language, num, self._api_key)

        # -- JSON request --
        try:
            json_resp = await self._client.get(SERPAPI_JSON_BASE, params=params)
        except Exception as exc:
            logger.error("serpapi_json_request_failed", error=str(exc))
            json_resp = None

        if json_resp is not None and json_resp.status_code < 400:
            try:
                data: dict[str, Any] = json_resp.json() if json_resp.text else {}
            except Exception:
                data = {}
        else:
            data = {}

        # -- HTML fetch: raw_html_file first, then fallback to HTML endpoint --
        html_text: str | None = None

        raw_html_url = (data.get("search_metadata") or {}).get("raw_html_file")
        if raw_html_url and self._client:
            try:
                html_resp = await self._client.get(
                    raw_html_url, timeout=self._html_timeout
                )
                if html_resp.status_code < 400:
                    html_text = html_resp.text
            except Exception:
                logger.debug("raw_html_fetch_failed", url=raw_html_url)

        if html_text is None and self._client:
            try:
                html_resp = await self._client.get(
                    SERPAPI_HTML_BASE, params=params, timeout=self._html_timeout
                )
                if html_resp.status_code < 400:
                    html_text = html_resp.text
            except Exception:
                logger.debug("html_endpoint_fallback_failed")

        # -- Build snapshot --
        snapshot = SerpSnapshot()
        if html_text:
            snapshot.compress_html(html_text)

        # -- Screenshot --
        png_bytes = await extract_screenshot_png(data, http_client=self._client)
        if png_bytes:
            snapshot.screenshot_png = png_bytes
            width, height = _png_dimensions(png_bytes)
            snapshot.screenshot_width = width
            snapshot.screenshot_height = height

        return snapshot


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------


async def fetch_serp(
    keyword: str,
    market: str,
    language: str,
    num: int = 10,
    api_key: str | None = None,
) -> tuple[dict[str, Any], str | None, SerpSnapshot]:
    """One-shot SERP fetch. Returns (json_data, html_text_or_None, snapshot).

    Wraps SerpApiClient in an async context manager for single-use calls.
    """
    async with SerpApiClient(api_key=api_key) as client:
        # We need the raw data too, so we replicate the fetch logic here
        # rather than calling client.fetch() (which only returns the snapshot).
        params = _build_params(keyword, market, language, num, client._api_key)

        # -- JSON --
        assert client._client is not None
        try:
            json_resp = await client._client.get(SERPAPI_JSON_BASE, params=params)
        except Exception as exc:
            logger.error("serpapi_json_request_failed", error=str(exc))
            json_resp = None

        if json_resp is not None and json_resp.status_code < 400:
            try:
                data = json_resp.json() if json_resp.text else {}
            except Exception:
                data = {}
        else:
            data = {}

        # -- HTML --
        html_text: str | None = None
        raw_html_url = (data.get("search_metadata") or {}).get("raw_html_file")
        if raw_html_url and client._client:
            try:
                html_resp = await client._client.get(
                    raw_html_url, timeout=client._html_timeout
                )
                if html_resp.status_code < 400:
                    html_text = html_resp.text
            except Exception:
                pass

        if html_text is None and client._client:
            try:
                html_resp = await client._client.get(
                    SERPAPI_HTML_BASE, params=params, timeout=client._html_timeout
                )
                if html_resp.status_code < 400:
                    html_text = html_resp.text
            except Exception:
                pass

        # -- Snapshot --
        snapshot = SerpSnapshot()
        if html_text:
            snapshot.compress_html(html_text)

        png_bytes = await extract_screenshot_png(data, http_client=client._client)
        if png_bytes:
            snapshot.screenshot_png = png_bytes
            w, h = _png_dimensions(png_bytes)
            snapshot.screenshot_width = w
            snapshot.screenshot_height = h

        return data, html_text, snapshot
