"""Tests for the PageSpeed Insights module."""
from __future__ import annotations

from unittest import mock
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from pydantic import ValidationError

from scraper_service.pagespeed.client import _parse_psi_response, fetch_pagespeed
from scraper_service.pagespeed.models import PageSpeedRequest, PageSpeedResult


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


class TestPageSpeedRequest:
    def test_valid_request(self) -> None:
        req = PageSpeedRequest(urls=["https://example.com"])
        assert req.strategy == "mobile"
        assert req.urls == ["https://example.com"]

    def test_desktop_strategy(self) -> None:
        req = PageSpeedRequest(urls=["https://example.com"], strategy="desktop")
        assert req.strategy == "desktop"

    def test_empty_urls_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PageSpeedRequest(urls=[])

    def test_rejects_extra_fields(self) -> None:
        with pytest.raises(ValidationError):
            PageSpeedRequest(urls=["https://example.com"], unknown="field")


class TestPageSpeedResult:
    def test_defaults(self) -> None:
        result = PageSpeedResult(url="https://example.com")
        assert result.strategy == "mobile"
        assert result.performance_score is None
        assert result.lcp_ms is None
        assert result.cls is None
        assert result.error is None
        assert result.raw_json is None

    def test_with_error(self) -> None:
        result = PageSpeedResult(url="https://x.com", error="timeout")
        assert result.error == "timeout"
        assert result.performance_score is None

    def test_with_metrics(self) -> None:
        result = PageSpeedResult(
            url="https://x.com",
            performance_score=85.0,
            lcp_ms=1200.5,
            fcp_ms=800.0,
        )
        assert result.performance_score == 85.0
        assert result.lcp_ms == 1200.5


# ---------------------------------------------------------------------------
# _parse_psi_response tests
# ---------------------------------------------------------------------------


_MOCK_PSI_JSON = {
    "lighthouseResult": {
        "categories": {
            "performance": {"score": 0.72}
        },
        "audits": {
            "largest-contentful-paint": {"numericValue": 2500.3},
            "cumulative-layout-shift": {"numericValue": 0.12},
            "first-contentful-paint": {"numericValue": 1100.0},
            "server-response-time": {"numericValue": 350.5},
            "speed-index": {"numericValue": 3200.0},
            "total-blocking-time": {"numericValue": 150.0},
        },
    }
}


class TestParsePsiResponse:
    def test_full_response(self) -> None:
        result = _parse_psi_response("https://x.com", "mobile", _MOCK_PSI_JSON)
        assert result.performance_score == 72.0  # 0.72 * 100
        assert result.lcp_ms == 2500.3
        assert result.cls == 0.1  # rounded
        assert result.fcp_ms == 1100.0
        assert result.ttfb_ms == 350.5
        assert result.speed_index == 3200.0
        assert result.total_blocking_time == 150.0
        assert result.raw_json == _MOCK_PSI_JSON

    def test_empty_lighthouse(self) -> None:
        result = _parse_psi_response("https://x.com", "mobile", {})
        assert result.performance_score is None
        assert result.lcp_ms is None
        assert result.error is None

    def test_missing_audits(self) -> None:
        data = {"lighthouseResult": {"categories": {"performance": {"score": 0.5}}, "audits": {}}}
        result = _parse_psi_response("https://x.com", "desktop", data)
        assert result.performance_score == 50.0
        assert result.lcp_ms is None


# ---------------------------------------------------------------------------
# fetch_pagespeed async tests
# ---------------------------------------------------------------------------


class TestFetchPagespeed:
    @pytest.mark.asyncio
    async def test_success(self) -> None:
        mock_response = mock.Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = _MOCK_PSI_JSON
        mock_response.raise_for_status = mock.Mock()

        with patch("scraper_service.pagespeed.client.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.get = AsyncMock(return_value=mock_response)
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            result = await fetch_pagespeed("https://example.com", strategy="mobile")

        assert result.performance_score == 72.0
        assert result.error is None

    @pytest.mark.asyncio
    async def test_api_error(self) -> None:
        with patch("scraper_service.pagespeed.client.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.get = AsyncMock(side_effect=httpx.HTTPStatusError(
                "500 Server Error",
                request=mock.Mock(),
                response=mock.Mock(status_code=500),
            ))
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            result = await fetch_pagespeed("https://example.com")

        assert result.error is not None
        assert "500" in result.error
        assert result.performance_score is None

    @pytest.mark.asyncio
    async def test_timeout(self) -> None:
        with patch("scraper_service.pagespeed.client.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.get = AsyncMock(side_effect=httpx.ReadTimeout("timed out"))
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            result = await fetch_pagespeed("https://example.com")

        assert result.error is not None
        assert result.performance_score is None


# ---------------------------------------------------------------------------
# Router endpoint test
# ---------------------------------------------------------------------------


class TestPagespeedEndpoint:
    @pytest.mark.asyncio
    async def test_pagespeed_endpoint(self, client) -> None:
        with patch("scraper_service.router.fetch_pagespeed", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = PageSpeedResult(
                url="https://example.com",
                strategy="mobile",
                performance_score=85.0,
            )
            response = await client.post(
                "/scraper/pagespeed",
                json={"urls": ["https://example.com"], "strategy": "mobile"},
            )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["performance_score"] == 85.0

    @pytest.mark.asyncio
    async def test_pagespeed_empty_urls(self, client) -> None:
        response = await client.post(
            "/scraper/pagespeed",
            json={"urls": []},
        )
        assert response.status_code == 422
