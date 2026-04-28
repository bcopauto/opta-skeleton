"""Tests for BaseSink ABC, ScrapedPage model, and run_sinks() orchestrator."""
from __future__ import annotations

import asyncio

import pytest
from pydantic import ValidationError

from scraper_service.models import (
    ExtractionResult,
    PageData,
    RenderMethod,
    ScrapedPage,
)
from scraper_service.settings import Settings
from scraper_service.sinks import BaseSink, run_sinks


# ---------------------------------------------------------------------------
# ScrapedPage model tests
# ---------------------------------------------------------------------------


class TestScrapedPageModel:
    def test_scraped_page_accepts_valid_data(
        self,
        sample_page_data: PageData,
        sample_extraction_result: ExtractionResult,
    ) -> None:
        page = ScrapedPage(
            page_data=sample_page_data,
            extraction_result=sample_extraction_result,
        )
        assert page.page_data.url == "https://example.com/page"
        assert page.extraction_result.title.title == "Test Page"

    def test_scraped_page_rejects_extra_fields(
        self,
        sample_page_data: PageData,
        sample_extraction_result: ExtractionResult,
    ) -> None:
        with pytest.raises(ValidationError):
            ScrapedPage(
                page_data=sample_page_data,
                extraction_result=sample_extraction_result,
                extra_field="not allowed",
            )

    def test_scraped_page_carries_html(
        self,
        sample_scraped_page: ScrapedPage,
    ) -> None:
        html = sample_scraped_page.page_data.html
        assert html is not None
        assert "<h1>Test Page</h1>" in html

    def test_scraped_page_screenshot_default_none(
        self,
        sample_scraped_page: ScrapedPage,
    ) -> None:
        assert sample_scraped_page.screenshot_bytes is None

    def test_scraped_page_screenshot_with_bytes(
        self,
        sample_page_data: PageData,
        sample_extraction_result: ExtractionResult,
    ) -> None:
        page = ScrapedPage(
            page_data=sample_page_data,
            extraction_result=sample_extraction_result,
            screenshot_bytes=b"\x89PNG\r\n",
        )
        assert page.screenshot_bytes == b"\x89PNG\r\n"


# ---------------------------------------------------------------------------
# BaseSink ABC tests
# ---------------------------------------------------------------------------


class TestBaseSinkABC:
    def test_base_sink_cannot_instantiate(self) -> None:
        with pytest.raises(TypeError):
            BaseSink()  # type: ignore[abstract]

    async def test_concrete_sink_write_called(
        self,
        sample_scraped_pages: list[ScrapedPage],
    ) -> None:
        written: list[list[ScrapedPage]] = []

        class StubSink(BaseSink):
            async def write(self, pages: list[ScrapedPage]) -> None:
                written.append(pages)

        sink = StubSink()
        await sink.write(sample_scraped_pages)
        assert len(written) == 1
        assert written[0] is sample_scraped_pages

    async def test_base_sink_close_noop(self) -> None:
        class StubSink(BaseSink):
            async def write(self, pages: list[ScrapedPage]) -> None:
                pass

        sink = StubSink()
        result = await sink.close()
        assert result is None


# ---------------------------------------------------------------------------
# run_sinks() orchestrator tests
# ---------------------------------------------------------------------------


class TestRunSinks:
    async def test_run_sinks_all_succeed(
        self,
        sample_scraped_pages: list[ScrapedPage],
    ) -> None:
        call_counts = [0, 0]

        class CountingSink(BaseSink):
            def __init__(self, idx: int) -> None:
                self.idx = idx

            async def write(self, pages: list[ScrapedPage]) -> None:
                call_counts[self.idx] += 1

        sinks = [CountingSink(0), CountingSink(1)]
        failures = await run_sinks(sample_scraped_pages, sinks)
        assert failures == []
        assert call_counts == [1, 1]

    async def test_run_sinks_partial_failure(
        self,
        sample_scraped_pages: list[ScrapedPage],
    ) -> None:
        called = [False, False]

        class OkSink(BaseSink):
            async def write(self, pages: list[ScrapedPage]) -> None:
                called[0] = True

        class FailSink(BaseSink):
            async def write(self, pages: list[ScrapedPage]) -> None:
                called[1] = True
                raise RuntimeError("sink exploded")

        failures = await run_sinks(
            sample_scraped_pages, [OkSink(), FailSink()]
        )
        assert len(failures) == 1
        assert isinstance(failures[0], RuntimeError)
        assert "sink exploded" in str(failures[0])
        # Both sinks were called despite failure
        assert called == [True, True]


# ---------------------------------------------------------------------------
# Settings tests
# ---------------------------------------------------------------------------


class TestSettingsMysql:
    def test_settings_has_mysql_connection_string(self) -> None:
        s = Settings()
        assert s.mysql_connection_string == ""
