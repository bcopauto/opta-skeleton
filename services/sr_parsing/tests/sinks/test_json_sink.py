"""Tests for JSON file output sink (SINK-02)."""
from __future__ import annotations

import json

import pytest

from scraper_service.models import PageData, RenderMethod, ScrapedPage
from scraper_service.sinks.json_sink import JSONSink


class TestJSONSinkWrite:
    """Core write behavior."""

    async def test_json_sink_creates_file(
        self, tmp_path, sample_scraped_pages
    ):
        sink = JSONSink(tmp_path / "out.json")
        await sink.write(sample_scraped_pages)
        assert (tmp_path / "out.json").exists()

    async def test_json_sink_pretty_printed(
        self, tmp_path, sample_scraped_pages
    ):
        sink = JSONSink(tmp_path / "out.json")
        await sink.write(sample_scraped_pages)
        content = (tmp_path / "out.json").read_text(encoding="utf-8")
        # Pretty-printed with indent=2 means 2-space indent
        assert '  "page_data"' in content

    async def test_json_sink_utf8_no_ascii_escape(self, tmp_path):
        page = ScrapedPage(
            page_data=PageData(
                url="https://example.com/cafe",
                final_url="https://example.com/cafe",
                status_code=200,
                render_method=RenderMethod.HTTPX,
            ),
            extraction_result={"title": {"title": "Cafe Munchn"}},
        )
        sink = JSONSink(tmp_path / "out.json")
        await sink.write([page])
        content = (tmp_path / "out.json").read_text(encoding="utf-8")
        assert "Cafe Munchn" in content
        assert "\\u00fc" not in content

    async def test_json_sink_content_is_serialized_pages(
        self, tmp_path, sample_scraped_pages
    ):
        sink = JSONSink(tmp_path / "out.json")
        await sink.write(sample_scraped_pages)
        content = (tmp_path / "out.json").read_text(encoding="utf-8")
        data = json.loads(content)
        assert isinstance(data, list)
        assert len(data) == 2
        # Verify structure matches model_dump(mode="json")
        expected = [p.model_dump(mode="json") for p in sample_scraped_pages]
        assert data == expected

    async def test_json_sink_empty_pages(self, tmp_path):
        sink = JSONSink(tmp_path / "out.json")
        await sink.write([])
        content = (tmp_path / "out.json").read_text(encoding="utf-8")
        assert json.loads(content) == []

    async def test_json_sink_creates_parent_dir(
        self, tmp_path, sample_scraped_pages
    ):
        deep_path = tmp_path / "a" / "b" / "c" / "out.json"
        sink = JSONSink(deep_path)
        await sink.write(sample_scraped_pages)
        assert deep_path.exists()


class TestJSONSinkClose:
    async def test_json_sink_close_noop(self, tmp_path):
        sink = JSONSink(tmp_path / "out.json")
        # Should complete without error
        await sink.close()
