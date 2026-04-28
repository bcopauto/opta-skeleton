"""Tests for RobotsChecker -- per-domain robots.txt fetch, cache, and checking."""
from __future__ import annotations

from unittest import mock

import httpx
import pytest

from scraper_service.robots import RobotsChecker


def _mock_response(text: str, status_code: int = 200) -> mock.Mock:
    """Build a mock httpx.Response."""
    resp = mock.Mock(spec=httpx.Response)
    resp.status_code = status_code
    resp.text = text
    return resp


@pytest.mark.asyncio
async def test_is_allowed_returns_true_for_allowed_url():
    """URL allowed by robots.txt returns True."""
    robots_txt = "User-agent: *\nDisallow: /private\n"
    client = mock.AsyncMock(spec=httpx.AsyncClient)
    client.get.return_value = _mock_response(robots_txt)

    checker = RobotsChecker(client, timeout=5)
    result = await checker.is_allowed("https://example.com/public")

    assert result is True


@pytest.mark.asyncio
async def test_is_allowed_returns_false_for_disallowed_url():
    """URL blocked by Disallow: /path returns False."""
    robots_txt = "User-agent: *\nDisallow: /private\n"
    client = mock.AsyncMock(spec=httpx.AsyncClient)
    client.get.return_value = _mock_response(robots_txt)

    checker = RobotsChecker(client, timeout=5)
    result = await checker.is_allowed("https://example.com/private/secret")

    assert result is False


@pytest.mark.asyncio
async def test_caches_per_domain_single_fetch():
    """Second call for same domain does NOT fetch robots.txt again."""
    robots_txt = "User-agent: *\nDisallow: /nope\n"
    client = mock.AsyncMock(spec=httpx.AsyncClient)
    client.get.return_value = _mock_response(robots_txt)

    checker = RobotsChecker(client, timeout=5)
    await checker.is_allowed("https://example.com/page1")
    await checker.is_allowed("https://example.com/page2")

    assert client.get.call_count == 1


@pytest.mark.asyncio
async def test_different_domains_get_separate_fetches():
    """Different domains each trigger their own robots.txt fetch."""
    robots_txt = "User-agent: *\nAllow: /\n"
    client = mock.AsyncMock(spec=httpx.AsyncClient)
    client.get.return_value = _mock_response(robots_txt)

    checker = RobotsChecker(client, timeout=5)
    await checker.is_allowed("https://alpha.com/page")
    await checker.is_allowed("https://beta.com/page")

    assert client.get.call_count == 2


@pytest.mark.asyncio
async def test_404_robots_allows_all():
    """robots.txt returning 404 means allow everything."""
    client = mock.AsyncMock(spec=httpx.AsyncClient)
    client.get.return_value = _mock_response("Not Found", status_code=404)

    checker = RobotsChecker(client, timeout=5)
    result = await checker.is_allowed("https://example.com/anything")

    assert result is True


@pytest.mark.asyncio
async def test_500_robots_allows_all():
    """robots.txt returning 500 means allow everything (D-08)."""
    client = mock.AsyncMock(spec=httpx.AsyncClient)
    client.get.return_value = _mock_response("Error", status_code=500)

    checker = RobotsChecker(client, timeout=5)
    result = await checker.is_allowed("https://example.com/anything")

    assert result is True


@pytest.mark.asyncio
async def test_timeout_allows_all():
    """Timeout fetching robots.txt means allow everything (D-08)."""
    client = mock.AsyncMock(spec=httpx.AsyncClient)
    client.get.side_effect = httpx.TimeoutException("timed out")

    checker = RobotsChecker(client, timeout=5)
    result = await checker.is_allowed("https://example.com/anything")

    assert result is True


@pytest.mark.asyncio
async def test_network_error_allows_all():
    """Network error fetching robots.txt means allow everything (D-08)."""
    client = mock.AsyncMock(spec=httpx.AsyncClient)
    client.get.side_effect = httpx.NetworkError("DNS resolution failed")

    checker = RobotsChecker(client, timeout=5)
    result = await checker.is_allowed("https://example.com/anything")

    assert result is True


@pytest.mark.asyncio
async def test_wildcard_user_agent_rules_used():
    """Checks against wildcard (*) User-Agent rules (D-10)."""
    # Only a specific bot is disallowed, wildcard is allowed
    robots_txt = "User-agent: Googlebot\nDisallow: /\n\nUser-agent: *\nDisallow: /secret\n"
    client = mock.AsyncMock(spec=httpx.AsyncClient)
    client.get.return_value = _mock_response(robots_txt)

    checker = RobotsChecker(client, timeout=5)

    # /public is allowed for wildcard UA
    assert await checker.is_allowed("https://example.com/public") is True
    # /secret is disallowed for wildcard UA
    assert await checker.is_allowed("https://example.com/secret") is False
