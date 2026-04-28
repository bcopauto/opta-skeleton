"""Tests for CSV file output sink with dotted-key flattening (SINK-03)."""
from __future__ import annotations

import csv
import json

import pytest

from scraper_service.models import ExtractionResult, PageData, RenderMethod, ScrapedPage
from scraper_service.sinks.csv_sink import CSVSink, flatten_scraped_page


class TestFlattenScrapedPage:
    """Unit tests for the flatten helper."""

    def test_flatten_produces_dotted_keys(self, sample_scraped_page):
        flat = flatten_scraped_page(sample_scraped_page)
        assert "headings.h1_count" in flat
        assert flat["headings.h1_count"] == 1

    def test_flatten_skips_html(self, sample_scraped_page):
        flat = flatten_scraped_page(sample_scraped_page)
        assert "html" not in flat

    def test_flatten_skips_xhr_responses(self, sample_scraped_page):
        flat = flatten_scraped_page(sample_scraped_page)
        assert "xhr_responses" not in flat

    def test_flatten_skips_screenshot_bytes(self, sample_scraped_page):
        page = ScrapedPage(
            page_data=sample_scraped_page.page_data,
            extraction_result=sample_scraped_page.extraction_result,
            screenshot_bytes=b"\x89PNG",
        )
        flat = flatten_scraped_page(page)
        assert "screenshot_bytes" not in flat

    def test_flatten_json_encodes_lists(self, sample_scraped_page):
        flat = flatten_scraped_page(sample_scraped_page)
        # headings.h1_texts is a list -> should be JSON string
        h1_texts = flat["headings.h1_texts"]
        parsed = json.loads(h1_texts)
        assert parsed == ["Test Page"]

    def test_flatten_json_encodes_dicts(self):
        page = ScrapedPage(
            page_data=PageData(url="https://x.com", final_url="https://x.com"),
            extraction_result=ExtractionResult(
                jsonld={"jsonld_blocks": [{"@type": "Article"}]},
            ),
        )
        flat = flatten_scraped_page(page)
        jsonld_blocks = flat["jsonld.jsonld_blocks"]
        parsed = json.loads(jsonld_blocks)
        assert parsed == [{"@type": "Article"}]

    def test_flatten_extraction_errors(self):
        page = ScrapedPage(
            page_data=PageData(
                url="https://example.com",
                final_url="https://example.com",
            ),
            extraction_result=ExtractionResult(
                errors={"tables": "boom"},
            ),
        )
        flat = flatten_scraped_page(page)
        assert "extraction_errors" in flat
        parsed = json.loads(flat["extraction_errors"])
        assert parsed == {"tables": "boom"}

    def test_flatten_default_extraction(self):
        """All-default ExtractionResult should flatten without error."""
        page = ScrapedPage(
            page_data=PageData(url="https://x.com", final_url="https://x.com"),
            extraction_result=ExtractionResult(),
        )
        flat = flatten_scraped_page(page)
        # Should have dotted keys for every section
        assert "headings.h1_count" in flat
        assert "title.title" in flat
        assert "url" in flat

    def test_flatten_empty_errors_gives_empty_string(self):
        page = ScrapedPage(
            page_data=PageData(url="https://x.com", final_url="https://x.com"),
            extraction_result=ExtractionResult(errors={}),
        )
        flat = flatten_scraped_page(page)
        assert flat["extraction_errors"] == ""


class TestCSVSinkWrite:
    """Integration tests for CSV file output."""

    async def test_csv_sink_creates_file(
        self, tmp_path, sample_scraped_pages
    ):
        sink = CSVSink(tmp_path / "out.csv")
        await sink.write(sample_scraped_pages)
        assert (tmp_path / "out.csv").exists()

    async def test_csv_sink_header_has_dotted_keys(
        self, tmp_path, sample_scraped_pages
    ):
        sink = CSVSink(tmp_path / "out.csv")
        await sink.write(sample_scraped_pages)
        content = (tmp_path / "out.csv").read_text(encoding="utf-8")
        reader = csv.reader(content.splitlines())
        header = next(reader)
        assert "headings.h1_count" in header

    async def test_csv_sink_one_row_per_page(
        self, tmp_path, sample_scraped_pages
    ):
        sink = CSVSink(tmp_path / "out.csv")
        await sink.write(sample_scraped_pages)
        content = (tmp_path / "out.csv").read_text(encoding="utf-8")
        reader = csv.reader(content.splitlines())
        rows = list(reader)
        # header + 2 data rows
        assert len(rows) == 3

    async def test_csv_sink_consistent_columns(
        self, tmp_path, sample_scraped_pages
    ):
        """Two writes with different data should produce identical headers."""
        sink = CSVSink(tmp_path / "out.csv")
        await sink.write(sample_scraped_pages)

        content1 = (tmp_path / "out.csv").read_text(encoding="utf-8")
        header1 = content1.splitlines()[0]

        # Write a single page with minimal data
        page = ScrapedPage(
            page_data=PageData(url="https://x.com", final_url="https://x.com"),
            extraction_result=ExtractionResult(),
        )
        await sink.write([page])
        content2 = (tmp_path / "out.csv").read_text(encoding="utf-8")
        header2 = content2.splitlines()[0]

        assert header1 == header2

    async def test_csv_sink_empty_pages_header_only(self, tmp_path):
        sink = CSVSink(tmp_path / "out.csv")
        await sink.write([])
        content = (tmp_path / "out.csv").read_text(encoding="utf-8")
        lines = content.strip().splitlines()
        # Header row only, no data rows
        assert len(lines) == 1
        assert "url" in lines[0]

    async def test_csv_sink_utf8(self, tmp_path):
        page = ScrapedPage(
            page_data=PageData(
                url="https://example.com/cafe",
                final_url="https://example.com/cafe",
                status_code=200,
                render_method=RenderMethod.HTTPX,
            ),
            extraction_result={"title": {"title": "Cafe Munchn"}},
        )
        sink = CSVSink(tmp_path / "out.csv")
        await sink.write([page])
        content = (tmp_path / "out.csv").read_text(encoding="utf-8")
        assert "Cafe Munchn" in content


class TestCSVSinkClose:
    async def test_csv_sink_close_noop(self, tmp_path):
        sink = CSVSink(tmp_path / "out.csv")
        await sink.close()
