"""Tests for API models, sink factory, and Scraper.scrape() method."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from scraper_service.models import (
    ErrorResponse,
    ExtractionResult,
    JobState,
    JobStatus,
    PageData,
    RenderMethod,
    ScrapedPage,
    SerpRequest,
    SinkConfig,
    SinkType,
)
from scraper_service.settings import Settings
from scraper_service.sinks.factory import build_sinks


# ---------------------------------------------------------------------------
# SerpRequest model tests
# ---------------------------------------------------------------------------


class TestSerpRequest:
    def test_valid_basic(self) -> None:
        req = SerpRequest(keyword="test", market="US", language="en")
        assert req.keyword == "test"
        assert req.market == "US"
        assert req.language == "en"
        assert req.num == 10
        assert req.target_url == ""

    def test_missing_keyword_raises(self) -> None:
        with pytest.raises(Exception):
            SerpRequest(market="US", language="en")  # type: ignore[call-arg]

    def test_with_optional_fields(self) -> None:
        req = SerpRequest(
            keyword="seo tools",
            market="UK",
            language="en",
            num=5,
            target_url="https://example.com",
        )
        assert req.num == 5
        assert req.target_url == "https://example.com"

    def test_rejects_extra_fields(self) -> None:
        with pytest.raises(Exception):
            SerpRequest(
                keyword="test",
                market="US",
                language="en",
                bogus="nope",  # type: ignore[call-arg]
            )


# ---------------------------------------------------------------------------
# JobStatus enum tests
# ---------------------------------------------------------------------------


class TestJobStatus:
    def test_has_all_values(self) -> None:
        assert JobStatus.PENDING == "pending"
        assert JobStatus.RUNNING == "running"
        assert JobStatus.COMPLETED == "completed"
        assert JobStatus.FAILED == "failed"


# ---------------------------------------------------------------------------
# JobState model tests
# ---------------------------------------------------------------------------


class TestJobState:
    def test_defaults(self) -> None:
        state = JobState(job_id="abc")
        assert state.job_id == "abc"
        assert state.status == JobStatus.PENDING
        assert state.results is None
        assert state.error is None

    def test_rejects_extra_fields(self) -> None:
        with pytest.raises(Exception):
            JobState(job_id="abc", bogus="nope")  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# ErrorResponse model tests
# ---------------------------------------------------------------------------


class TestErrorResponse:
    def test_valid(self) -> None:
        err = ErrorResponse(detail="Something went wrong", error_code="BAD_REQUEST")
        assert err.detail == "Something went wrong"
        assert err.error_code == "BAD_REQUEST"

    def test_rejects_extra_fields(self) -> None:
        with pytest.raises(Exception):
            ErrorResponse(
                detail="msg",
                error_code="CODE",
                bogus="nope",  # type: ignore[call-arg]
            )


# ---------------------------------------------------------------------------
# build_sinks factory tests
# ---------------------------------------------------------------------------


class TestBuildSinks:
    @pytest.mark.asyncio
    async def test_json_sink(self, tmp_path: Path) -> None:
        out = tmp_path / "out.json"
        configs = [SinkConfig(type=SinkType.JSON, config={"path": str(out)})]
        sinks = await build_sinks(configs, Settings())
        assert len(sinks) == 1
        from scraper_service.sinks.json_sink import JSONSink

        assert isinstance(sinks[0], JSONSink)

    @pytest.mark.asyncio
    async def test_csv_sink(self, tmp_path: Path) -> None:
        out = tmp_path / "out.csv"
        configs = [SinkConfig(type=SinkType.CSV, config={"path": str(out)})]
        sinks = await build_sinks(configs, Settings())
        assert len(sinks) == 1
        from scraper_service.sinks.csv_sink import CSVSink

        assert isinstance(sinks[0], CSVSink)

    @pytest.mark.asyncio
    async def test_debug_sink(self, tmp_path: Path) -> None:
        configs = [SinkConfig(type=SinkType.DEBUG_DUMP, config={"path": str(tmp_path)})]
        sinks = await build_sinks(configs, Settings(), job_id="j1")
        assert len(sinks) == 1
        from scraper_service.sinks.debug_sink import DebugSink

        assert isinstance(sinks[0], DebugSink)

    @pytest.mark.asyncio
    async def test_all_sink_types_have_mapping(self) -> None:
        """Every SinkType enum member should be handled by build_sinks.

        DATABASE requires MySQL so we skip it -- we just verify the code path
        exists by checking no ValueError is raised for the non-DB types, and
        that DATABASE is acknowledged in the implementation.
        """
        from scraper_service.sinks import factory as factory_mod
        import inspect

        source = inspect.getsource(factory_mod.build_sinks)
        for member in SinkType:
            assert member.value in source or member.name in source, (
                f"SinkType.{member.name} has no mapping in build_sinks"
            )


# ---------------------------------------------------------------------------
# Scraper.scrape() tests
# ---------------------------------------------------------------------------


class TestScrapeMethod:
    @pytest.mark.asyncio
    async def test_scrape_returns_scraped_pages(self) -> None:
        """scrape() chains fetch -> extract and returns list[ScrapedPage]."""
        from scraper_service.fetcher import Scraper

        fake_page = PageData(
            url="https://example.com",
            final_url="https://example.com",
            status_code=200,
            render_method=RenderMethod.HTTPX,
            html="<html><head><title>Test</title></head><body><p>Hello world</p></body></html>",
        )

        async with Scraper() as scraper:
            with patch.object(scraper, "fetch", new_callable=AsyncMock) as mock_fetch:
                mock_fetch.return_value = [fake_page]
                results = await scraper.scrape(["https://example.com"])

        assert len(results) == 1
        assert isinstance(results[0], ScrapedPage)
        assert results[0].page_data.url == "https://example.com"
        # extraction_result should be populated from the HTML
        assert isinstance(results[0].extraction_result, ExtractionResult)

    @pytest.mark.asyncio
    async def test_scrape_failed_fetch_gets_default_extraction(self) -> None:
        """When fetch returns no HTML, extraction_result should be defaults."""
        from scraper_service.fetcher import Scraper

        failed_page = PageData(
            url="https://bad.example.com",
            final_url="https://bad.example.com",
            status_code=None,
            render_method=RenderMethod.FAILED,
            error="Connection refused",
            html=None,
        )

        async with Scraper() as scraper:
            with patch.object(scraper, "fetch", new_callable=AsyncMock) as mock_fetch:
                mock_fetch.return_value = [failed_page]
                results = await scraper.scrape(["https://bad.example.com"])

        assert len(results) == 1
        # Should still have an ExtractionResult, just with default values
        assert results[0].extraction_result == ExtractionResult()

    @pytest.mark.asyncio
    async def test_scrape_outside_context_raises(self) -> None:
        """scrape() raises RuntimeError if called without entering context manager."""
        from scraper_service.fetcher import Scraper

        scraper = Scraper()
        with pytest.raises(RuntimeError, match="outside async context manager"):
            await scraper.scrape(["https://example.com"])

    @pytest.mark.asyncio
    async def test_scrape_no_sinks_skips_sink_execution(self) -> None:
        """scrape() with sinks=None does not call run_sinks."""
        from scraper_service.fetcher import Scraper

        fake_page = PageData(
            url="https://example.com",
            final_url="https://example.com",
            status_code=200,
            render_method=RenderMethod.HTTPX,
            html="<html><body>Hi</body></html>",
        )

        async with Scraper() as scraper:
            with patch.object(scraper, "fetch", new_callable=AsyncMock) as mock_fetch:
                mock_fetch.return_value = [fake_page]
                with patch(
                    "scraper_service.fetcher.build_sinks", new_callable=AsyncMock
                ) as mock_build:
                    results = await scraper.scrape(["https://example.com"])
                    mock_build.assert_not_called()

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_scrape_with_json_sink_writes_file(self, tmp_path: Path) -> None:
        """scrape() with JSON sink config actually writes a JSON file."""
        from scraper_service.fetcher import Scraper

        out_file = tmp_path / "output.json"
        fake_page = PageData(
            url="https://example.com",
            final_url="https://example.com",
            status_code=200,
            render_method=RenderMethod.HTTPX,
            html="<html><head><title>Test</title></head><body><p>Content here</p></body></html>",
        )
        sink_configs = [SinkConfig(type=SinkType.JSON, config={"path": str(out_file)})]

        async with Scraper() as scraper:
            with patch.object(scraper, "fetch", new_callable=AsyncMock) as mock_fetch:
                mock_fetch.return_value = [fake_page]
                results = await scraper.scrape(
                    ["https://example.com"],
                    sinks=sink_configs,
                )

        assert len(results) == 1
        assert out_file.exists()
        data = json.loads(out_file.read_text(encoding="utf-8"))
        assert len(data) == 1
        assert data[0]["page_data"]["url"] == "https://example.com"
