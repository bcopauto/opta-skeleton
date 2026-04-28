"""Shared fixtures for sink tests."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from scraper_service.models import (
    ExtractionResult,
    PageData,
    RenderMethod,
    ScrapedPage,
)


@pytest.fixture
def sample_page_data() -> PageData:
    """PageData with realistic SEO values."""
    return PageData(
        url="https://example.com/page",
        final_url="https://example.com/page",
        status_code=200,
        fetched_at=datetime(2026, 4, 8, 12, 0, 0, tzinfo=timezone.utc),
        render_method=RenderMethod.HTTPX,
        html="<html><body><h1>Test Page</h1><p>Hello world</p></body></html>",
    )


@pytest.fixture
def sample_extraction_result() -> ExtractionResult:
    """ExtractionResult with non-default values for testing."""
    return ExtractionResult(
        title={"title": "Test Page", "title_length": 9},
        meta_desc={"meta_description": "A test page", "meta_description_length": 11},
        headings={
            "h1_count": 1,
            "h2_count": 0,
            "total_headings": 1,
            "h1_texts": ["Test Page"],
        },
        body_text={"word_count": 2, "char_count": 11, "text": "Hello world"},
    )


@pytest.fixture
def sample_scraped_page(
    sample_page_data: PageData,
    sample_extraction_result: ExtractionResult,
) -> ScrapedPage:
    """ScrapedPage combining fetch + extraction data."""
    return ScrapedPage(
        page_data=sample_page_data,
        extraction_result=sample_extraction_result,
    )


@pytest.fixture
def sample_scraped_pages(
    sample_scraped_page: ScrapedPage,
) -> list[ScrapedPage]:
    """Two ScrapedPage objects for batch testing."""
    page2_data = PageData(
        url="https://example.com/other",
        final_url="https://example.com/other",
        status_code=200,
        fetched_at=datetime(2026, 4, 8, 12, 1, 0, tzinfo=timezone.utc),
        render_method=RenderMethod.PLAYWRIGHT,
        html="<html><body><h1>Other</h1></body></html>",
    )
    page2 = ScrapedPage(
        page_data=page2_data,
        extraction_result=ExtractionResult(
            title={"title": "Other", "title_length": 5},
        ),
    )
    return [sample_scraped_page, page2]
