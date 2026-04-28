"""Tests for MySQL sink: ScrapedPageRow ORM model, extract_row_values, MySQLSink."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import String

from scraper_service.models import (
    ExtractionResult,
    PageData,
    RenderMethod,
    ScrapedPage,
)
from scraper_service.settings import Settings
from scraper_service.sinks.db import ScrapedPageRow, extract_row_values
from scraper_service.sinks.mysql_sink import MySQLSink


# ---------------------------------------------------------------------------
# ScrapedPageRow column tests
# ---------------------------------------------------------------------------


class TestScrapedPageRowColumns:
    def test_has_all_key_columns(self) -> None:
        """ScrapedPageRow has ~20 key columns plus extraction_json."""
        columns = {c.name for c in ScrapedPageRow.__table__.columns}
        expected = {
            "id",
            "url",
            "final_url",
            "status_code",
            "render_method",
            "fetched_at",
            "title",
            "meta_description",
            "word_count",
            "h1_count",
            "h2_count",
            "total_headings",
            "image_count",
            "alt_coverage_pct",
            "internal_links",
            "external_links",
            "canonical_url",
            "is_https",
            "jsonld_types",
            "robots_noindex",
            "has_faq",
            "extraction_json",
        }
        assert expected.issubset(columns), f"Missing columns: {expected - columns}"

    def test_url_column_is_unique_indexed_not_nullable(self) -> None:
        """url is String(2083), unique, indexed, not nullable."""
        url_col = ScrapedPageRow.__table__.columns["url"]
        assert url_col.unique is True
        assert not url_col.nullable
        # Check index exists
        indexed_cols = [frozenset(idx.columns.keys()) for idx in ScrapedPageRow.__table__.indexes]
        assert frozenset({"url"}) in indexed_cols

    def test_url_column_type_is_string_2083(self) -> None:
        """url column type is String with length 2083."""
        url_col = ScrapedPageRow.__table__.columns["url"]
        assert isinstance(url_col.type, String)
        assert url_col.type.length == 2083


# ---------------------------------------------------------------------------
# extract_row_values tests
# ---------------------------------------------------------------------------


class TestExtractRowValues:
    def test_maps_all_key_columns(
        self,
        sample_scraped_page: ScrapedPage,
    ) -> None:
        """extract_row_values maps all ~20 columns from ScrapedPage."""
        row = extract_row_values(sample_scraped_page)
        assert row["url"] == "https://example.com/page"
        assert row["final_url"] == "https://example.com/page"
        assert row["status_code"] == 200
        assert row["render_method"] == "httpx"
        assert row["fetched_at"] == datetime(2026, 4, 8, 12, 0, 0, tzinfo=timezone.utc)
        assert row["title"] == "Test Page"
        assert row["meta_description"] == "A test page"
        assert row["word_count"] == 2
        assert row["h1_count"] == 1
        assert row["h2_count"] == 0
        assert row["total_headings"] == 1

    def test_jsonld_types_serialized_to_json_string(self) -> None:
        """jsonld_types list is JSON-serialized as a string."""
        page = ScrapedPage(
            page_data=PageData(url="https://example.com/x", final_url="https://example.com/x"),
            extraction_result=ExtractionResult(
                jsonld={"jsonld_types": ["Article", "FAQPage"]},
            ),
        )
        row = extract_row_values(page)
        assert row["jsonld_types"] == json.dumps(["Article", "FAQPage"])

    def test_jsonld_types_none_when_empty(self) -> None:
        """Empty jsonld_types list becomes None."""
        page = ScrapedPage(
            page_data=PageData(url="https://example.com/x", final_url="https://example.com/x"),
            extraction_result=ExtractionResult(),
        )
        row = extract_row_values(page)
        assert row["jsonld_types"] is None

    def test_extraction_json_contains_full_result(self) -> None:
        """extraction_json stores full ExtractionResult via model_dump."""
        er = ExtractionResult(
            title={"title": "Full Test", "title_length": 9},
            body_text={"word_count": 100},
        )
        page = ScrapedPage(
            page_data=PageData(url="https://example.com/x", final_url="https://example.com/x"),
            extraction_result=er,
        )
        row = extract_row_values(page)
        assert row["extraction_json"]["title"]["title"] == "Full Test"
        assert row["extraction_json"]["body_text"]["word_count"] == 100

    def test_render_method_stored_as_string(self) -> None:
        """render_method enum is stored as its value string."""
        page = ScrapedPage(
            page_data=PageData(
                url="https://example.com/x",
                final_url="https://example.com/x",
                render_method=RenderMethod.PLAYWRIGHT,
            ),
            extraction_result=ExtractionResult(),
        )
        row = extract_row_values(page)
        assert row["render_method"] == "playwright"

    def test_extracts_image_link_meta_fields(self) -> None:
        """Verify image, link, meta, technical field extraction."""
        page = ScrapedPage(
            page_data=PageData(url="https://example.com/x", final_url="https://example.com/x"),
            extraction_result=ExtractionResult(
                images={"total_images": 10, "alt_coverage_pct": 80.0},
                links={"internal_links": 5, "external_links": 3},
                meta={"canonical_url": "https://example.com/canonical", "robots_noindex": True},
                technical={"is_https": True},
                faq={"has_faq": True},
            ),
        )
        row = extract_row_values(page)
        assert row["image_count"] == 10
        assert row["alt_coverage_pct"] == 80.0
        assert row["internal_links"] == 5
        assert row["external_links"] == 3
        assert row["canonical_url"] == "https://example.com/canonical"
        assert row["is_https"] is True
        assert row["robots_noindex"] is True
        assert row["has_faq"] is True


# ---------------------------------------------------------------------------
# MySQLSink tests (mocked database)
# ---------------------------------------------------------------------------


class TestMySQLSink:
    async def test_write_calls_upsert(
        self,
        sample_scraped_page: ScrapedPage,
    ) -> None:
        """write() calls session.execute with a mysql_insert upsert statement."""
        mock_session = AsyncMock()
        mock_session.begin = MagicMock(return_value=AsyncMock())
        # Context manager for session factory
        mock_session_factory = MagicMock()
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        sink = MySQLSink(session_factory=mock_session_factory)
        await sink.write([sample_scraped_page])

        mock_session.execute.assert_awaited_once()
        # Verify the statement targets our table
        call_args = mock_session.execute.call_args
        stmt = call_args[0][0]
        assert stmt.table.name == "scraped_pages"

    async def test_write_empty_pages_is_noop(self) -> None:
        """write([]) returns without touching the database."""
        mock_session_factory = MagicMock()
        sink = MySQLSink(session_factory=mock_session_factory)
        await sink.write([])
        # session_factory should never be called
        mock_session_factory.assert_not_called()

    async def test_write_batch_multiple_pages(
        self,
        sample_scraped_pages: list[ScrapedPage],
    ) -> None:
        """write() handles multiple pages in a single execute call."""
        mock_session = AsyncMock()
        mock_session.begin = MagicMock(return_value=AsyncMock())
        mock_session_factory = MagicMock()
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        sink = MySQLSink(session_factory=mock_session_factory)
        await sink.write(sample_scraped_pages)

        mock_session.execute.assert_awaited_once()

    async def test_close_disposes_engine(self) -> None:
        """close() disposes the async engine."""
        mock_engine = AsyncMock()
        sink = MySQLSink(session_factory=MagicMock(), _engine=mock_engine)
        await sink.close()
        mock_engine.dispose.assert_awaited_once()
        assert sink._engine is None

    async def test_close_noop_without_engine(self) -> None:
        """close() is safe when no engine was provided."""
        sink = MySQLSink(session_factory=MagicMock())
        await sink.close()  # Should not raise

    async def test_create_raises_on_empty_connection_string(self) -> None:
        """create() raises ValueError when connection string is empty."""
        settings = Settings()
        with pytest.raises(ValueError, match="SCRAPER_MYSQL_CONNECTION_STRING"):
            await MySQLSink.create(settings)

    async def test_create_succeeds_with_connection_string(self) -> None:
        """create() builds a sink when connection string is provided."""
        settings = Settings(mysql_connection_string="mysql+aiomysql://u:p@localhost/db")
        sink = await MySQLSink.create(settings)
        assert sink._session_factory is not None
        assert sink._engine is not None
        # Clean up
        await sink.close()
