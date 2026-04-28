"""Integration tests for extract_page() runner."""
from __future__ import annotations

import pytest

from scraper_service.extractors import EXTRACTOR_NAMES, extract_page
from scraper_service.models import ExtractionResult


def test_extract_page_full_html(full_page_html: str) -> None:
    """extract_page on a full page returns ExtractionResult with populated sub-models."""
    result = extract_page(full_page_html, "https://example.com/seo-tools")

    assert isinstance(result, ExtractionResult)
    assert result.title.title == "Best SEO Tools 2025 - Complete Guide"
    assert result.headings.h1_count == 1
    assert result.jsonld.jsonld_present is True
    assert result.images.total_images >= 3
    assert result.links.total_links > 5
    assert result.errors == {}


def test_extract_page_minimal_html(minimal_html: str) -> None:
    """extract_page on bare HTML returns ExtractionResult with defaults, no errors."""
    result = extract_page(minimal_html, "https://example.com")

    assert isinstance(result, ExtractionResult)
    assert result.errors == {}
    # Title should be None on empty page
    assert result.title.title is None
    assert result.headings.total_headings == 0


def test_extract_page_garbage_html() -> None:
    """extract_page on garbage input returns ExtractionResult without raising."""
    result = extract_page("garbage html", "https://example.com")

    assert isinstance(result, ExtractionResult)
    # Should not crash -- some extractors may have errors but that is fine


def test_extract_page_empty_string() -> None:
    """extract_page on empty string returns ExtractionResult with defaults."""
    result = extract_page("", "https://example.com")

    assert isinstance(result, ExtractionResult)
    # All sub-models should be defaults
    assert result.title.title is None
    assert result.headings.total_headings == 0
    assert result.images.total_images == 0


def test_extractor_names_count() -> None:
    """EXTRACTOR_NAMES has exactly 20 entries (20 unique extractor modules)."""
    assert len(EXTRACTOR_NAMES) == 20


def test_extractor_names_match_sub_models() -> None:
    """Each name in EXTRACTOR_NAMES corresponds to a sub-model field on ExtractionResult."""
    result = ExtractionResult()
    for name in EXTRACTOR_NAMES:
        assert hasattr(result, name), f"ExtractionResult missing field for extractor '{name}'"


def test_extract_page_error_isolation(monkeypatch: pytest.MonkeyPatch) -> None:
    """One extractor raising does not prevent others from running."""
    import scraper_service.extractors.runner as runner_mod

    def broken_extract(tree, url):
        raise RuntimeError("intentional test failure")

    # Swap the first extractor entry with a failing version
    original = runner_mod._EXTRACTORS[0]
    runner_mod._EXTRACTORS[0] = ("title", broken_extract)

    try:
        result = extract_page(
            "<html><head><title>Test</title></head><body><h1>Hello</h1></body></html>",
            "https://example.com",
        )

        # Title extractor should have errored
        assert "title" in result.errors
        assert "intentional test failure" in result.errors["title"]

        # But other extractors still ran
        assert result.headings.h1_count == 1
    finally:
        runner_mod._EXTRACTORS[0] = original
