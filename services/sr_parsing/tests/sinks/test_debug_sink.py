"""Tests for debug dump output sink (SINK-05)."""
from __future__ import annotations

import hashlib
import json

import pytest

from scraper_service.models import (
    ExtractionResult,
    PageData,
    RenderMethod,
    ScrapedPage,
)
from scraper_service.sinks.debug_sink import DebugSink


def _make_page(
    url: str = "https://example.com/page",
    html: str | None = "<html><body>Hello</body></html>",
    screenshot_bytes: bytes | None = None,
) -> ScrapedPage:
    return ScrapedPage(
        page_data=PageData(
            url=url,
            final_url=url,
            status_code=200,
            render_method=RenderMethod.HTTPX,
            html=html,
        ),
        extraction_result=ExtractionResult(
            title={"title": "Test", "title_length": 4},
        ),
        screenshot_bytes=screenshot_bytes,
    )


def _url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


class TestDebugSinkDirectoryStructure:
    async def test_creates_per_url_directory(self, tmp_path):
        page = _make_page()
        sink = DebugSink(tmp_path, job_id="job1")
        await sink.write([page])
        expected_dir = tmp_path / "job1" / _url_hash(page.page_data.url)
        assert expected_dir.is_dir()

    async def test_creates_parent_dirs(self, tmp_path):
        deep_base = tmp_path / "does" / "not" / "exist"
        page = _make_page()
        sink = DebugSink(deep_base, job_id="j")
        await sink.write([page])
        assert (deep_base / "j" / _url_hash(page.page_data.url)).is_dir()

    async def test_multiple_pages_creates_multiple_dirs(self, tmp_path):
        pages = [_make_page(url=f"https://example.com/p{i}") for i in range(3)]
        sink = DebugSink(tmp_path, job_id="multi")
        await sink.write(pages)
        for page in pages:
            expected = tmp_path / "multi" / _url_hash(page.page_data.url)
            assert expected.is_dir()

    async def test_url_hash_is_sha256_first_16(self, tmp_path):
        url = "https://example.com/page"
        page = _make_page(url=url)
        sink = DebugSink(tmp_path, job_id="hash")
        await sink.write([page])
        expected_hash = hashlib.sha256(url.encode()).hexdigest()[:16]
        assert (tmp_path / "hash" / expected_hash).is_dir()


class TestDebugSinkPageHtml:
    async def test_writes_page_html(self, tmp_path):
        html = "<html><body>Hello world</body></html>"
        page = _make_page(html=html)
        sink = DebugSink(tmp_path, job_id="j")
        await sink.write([page])
        dump_dir = tmp_path / "j" / _url_hash(page.page_data.url)
        content = (dump_dir / "page.html").read_text(encoding="utf-8")
        assert content == html

    async def test_skips_page_html_when_none(self, tmp_path):
        page = _make_page(html=None)
        sink = DebugSink(tmp_path, job_id="j")
        await sink.write([page])
        dump_dir = tmp_path / "j" / _url_hash(page.page_data.url)
        assert not (dump_dir / "page.html").exists()


class TestDebugSinkMetaJson:
    async def test_writes_meta_json(self, tmp_path):
        page = _make_page()
        sink = DebugSink(tmp_path, job_id="j")
        await sink.write([page])
        dump_dir = tmp_path / "j" / _url_hash(page.page_data.url)
        meta = json.loads((dump_dir / "meta.json").read_text(encoding="utf-8"))
        assert meta["url"] == "https://example.com/page"
        assert meta["status_code"] == 200
        assert meta["render_method"] == "httpx"

    async def test_meta_excludes_html(self, tmp_path):
        page = _make_page(html="<html>stuff</html>")
        sink = DebugSink(tmp_path, job_id="j")
        await sink.write([page])
        dump_dir = tmp_path / "j" / _url_hash(page.page_data.url)
        meta = json.loads((dump_dir / "meta.json").read_text(encoding="utf-8"))
        assert "html" not in meta

    async def test_meta_excludes_xhr_responses(self, tmp_path):
        page = _make_page()
        sink = DebugSink(tmp_path, job_id="j")
        await sink.write([page])
        dump_dir = tmp_path / "j" / _url_hash(page.page_data.url)
        meta = json.loads((dump_dir / "meta.json").read_text(encoding="utf-8"))
        assert "xhr_responses" not in meta


class TestDebugSinkExtractionJson:
    async def test_writes_extraction_json(self, tmp_path):
        page = _make_page()
        sink = DebugSink(tmp_path, job_id="j")
        await sink.write([page])
        dump_dir = tmp_path / "j" / _url_hash(page.page_data.url)
        extraction = json.loads(
            (dump_dir / "extraction.json").read_text(encoding="utf-8")
        )
        assert extraction["title"]["title"] == "Test"
        assert "headings" in extraction
        assert "errors" in extraction


class TestDebugSinkScreenshot:
    async def test_writes_screenshot_when_present(self, tmp_path):
        png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 10
        page = _make_page(screenshot_bytes=png_bytes)
        sink = DebugSink(tmp_path, job_id="j")
        await sink.write([page])
        dump_dir = tmp_path / "j" / _url_hash(page.page_data.url)
        assert (dump_dir / "screenshot.png").read_bytes() == png_bytes

    async def test_skips_screenshot_when_none(self, tmp_path):
        page = _make_page(screenshot_bytes=None)
        sink = DebugSink(tmp_path, job_id="j")
        await sink.write([page])
        dump_dir = tmp_path / "j" / _url_hash(page.page_data.url)
        assert not (dump_dir / "screenshot.png").exists()
