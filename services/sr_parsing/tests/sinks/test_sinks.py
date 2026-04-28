"""Integration tests for run_sinks() parallel orchestrator (SINK-06)."""
from __future__ import annotations

import pytest

from scraper_service.models import ScrapedPage
from scraper_service.sinks import BaseSink, run_sinks


class MockSink(BaseSink):
    """Trivial sink that tracks whether write() was called."""

    def __init__(self, *, fail: bool = False) -> None:
        self.wrote = False
        self._fail = fail

    async def write(self, pages: list[ScrapedPage]) -> None:
        self.wrote = True
        if self._fail:
            raise RuntimeError("mock failure")


class TestRunSinksOrchestrator:
    async def test_two_working_sinks_returns_empty(
        self,
        sample_scraped_pages: list[ScrapedPage],
    ):
        a = MockSink()
        b = MockSink()
        failures = await run_sinks(sample_scraped_pages, [a, b])
        assert failures == []
        assert a.wrote is True
        assert b.wrote is True

    async def test_one_failing_sink_other_completes(
        self,
        sample_scraped_pages: list[ScrapedPage],
    ):
        ok = MockSink()
        bad = MockSink(fail=True)
        failures = await run_sinks(sample_scraped_pages, [ok, bad])
        assert len(failures) == 1
        assert isinstance(failures[0], RuntimeError)
        assert ok.wrote is True
        assert bad.wrote is True

    async def test_empty_sinks_list_returns_empty(
        self,
        sample_scraped_pages: list[ScrapedPage],
    ):
        failures = await run_sinks(sample_scraped_pages, [])
        assert failures == []

    async def test_all_sinks_failing_returns_all_exceptions(
        self,
        sample_scraped_pages: list[ScrapedPage],
    ):
        a = MockSink(fail=True)
        b = MockSink(fail=True)
        failures = await run_sinks(sample_scraped_pages, [a, b])
        assert len(failures) == 2
        for f in failures:
            assert isinstance(f, RuntimeError)

    async def test_failure_logged_with_sink_name(
        self,
        sample_scraped_pages: list[ScrapedPage],
        capsys,
    ):
        bad = MockSink(fail=True)
        await run_sinks(sample_scraped_pages, [bad])
        out = capsys.readouterr().out
        # structlog prints to stdout via PrintLoggerFactory
        assert "sink_failed" in out
        assert "MockSink" in out
