"""Tests for Pydantic models."""
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from scraper_service.models import ErrorType, PageData, RenderMethod, ScrapeRequest, SinkConfig, SinkType


def test_page_data_defaults():
    """PageData with minimal args uses defaults."""
    p = PageData(url="https://example.com", final_url="https://example.com")
    assert p.render_method == RenderMethod.HTTPX
    assert p.status_code is None
    assert p.error is None
    assert isinstance(p.fetched_at, datetime)


def test_page_data_with_all_fields():
    """PageData with all fields set explicitly."""
    fetched_at = datetime(2026, 4, 7, 12, 0, 0, tzinfo=timezone.utc)
    p = PageData(
        url="https://example.com",
        final_url="https://example.com/redirected",
        status_code=200,
        fetched_at=fetched_at,
        render_method=RenderMethod.PLAYWRIGHT,
        error="test error",
        html="<html>test</html>",
    )
    assert p.url == "https://example.com"
    assert p.final_url == "https://example.com/redirected"
    assert p.status_code == 200
    assert p.fetched_at == fetched_at
    assert p.render_method == RenderMethod.PLAYWRIGHT
    assert p.error == "test error"
    assert p.html == "<html>test</html>"


def test_page_data_rejects_extra_fields():
    """PageData rejects unknown fields."""
    with pytest.raises(ValidationError) as exc_info:
        PageData(
            url="https://example.com",
            final_url="https://example.com",
            unknown_field="value",
        )
    assert "extra_forbidden" in str(exc_info.value)


def test_page_data_strict_mode():
    """PageData strict mode rejects wrong types."""
    with pytest.raises(ValidationError) as exc_info:
        PageData(
            url="https://example.com",
            final_url="https://example.com",
            status_code="not_an_int",
        )
    assert "int_parsing" in str(exc_info.value).lower()


def test_scrape_request_minimal():
    """ScrapeRequest with minimal args uses defaults."""
    r = ScrapeRequest(urls=["https://example.com"])
    assert r.urls == ["https://example.com"]
    assert r.sinks == []
    assert r.respect_robots is False


def test_scrape_request_empty_urls():
    """ScrapeRequest rejects empty urls list."""
    with pytest.raises(ValidationError) as exc_info:
        ScrapeRequest(urls=[])
    assert "too_short" in str(exc_info.value).lower()


def test_scrape_request_rejects_extra_fields():
    """ScrapeRequest rejects unknown fields."""
    with pytest.raises(ValidationError) as exc_info:
        ScrapeRequest(urls=["https://example.com"], unknown_field="value")
    assert "extra_forbidden" in str(exc_info.value)


def test_sink_config_types():
    """SinkConfig accepts all valid sink types."""
    for sink_type in [SinkType.DATABASE, SinkType.CSV, SinkType.JSON, SinkType.DEBUG_DUMP]:
        config = SinkConfig(type=sink_type)
        assert config.type == sink_type
        assert config.config == {}


def test_sink_config_invalid_type():
    """SinkConfig rejects invalid sink type."""
    with pytest.raises(ValidationError) as exc_info:
        SinkConfig(type="invalid")
    assert "enum" in str(exc_info.value).lower()


def test_sink_config_with_config_dict():
    """SinkConfig accepts per-sink config dict."""
    config = SinkConfig(type=SinkType.JSON, config={"path": "/tmp/out.json"})
    assert config.type == SinkType.JSON
    assert config.config == {"path": "/tmp/out.json"}


def test_render_method_enum():
    """RenderMethod enum has correct values."""
    assert RenderMethod.HTTPX == "httpx"
    assert RenderMethod.PLAYWRIGHT == "playwright"
    assert RenderMethod.FAILED == "failed"


# ---------------------------------------------------------------------------
# ErrorType enum tests
# ---------------------------------------------------------------------------


def test_error_type_enum_members():
    """ErrorType has exactly 8 members matching D-12 spec."""
    expected = {
        "TIMEOUT", "NETWORK", "HTTP_4XX", "HTTP_5XX",
        "ROBOTS_DENIED", "CIRCUIT_BREAKER", "INVALID_URL", "PLAYWRIGHT_CRASH",
    }
    actual = {m.name for m in ErrorType}
    assert actual == expected
    assert len(ErrorType) == 8


def test_error_type_enum_values():
    """ErrorType values are lowercase strings."""
    assert ErrorType.TIMEOUT.value == "timeout"
    assert ErrorType.NETWORK.value == "network"
    assert ErrorType.HTTP_4XX.value == "http_4xx"
    assert ErrorType.HTTP_5XX.value == "http_5xx"
    assert ErrorType.ROBOTS_DENIED.value == "robots_denied"
    assert ErrorType.CIRCUIT_BREAKER.value == "circuit_breaker"
    assert ErrorType.INVALID_URL.value == "invalid_url"
    assert ErrorType.PLAYWRIGHT_CRASH.value == "playwright_crash"


def test_error_type_is_str_enum():
    """ErrorType members are also strings (str, Enum)."""
    assert isinstance(ErrorType.TIMEOUT, str)
    assert isinstance(ErrorType.CIRCUIT_BREAKER, str)


def test_page_data_error_type_defaults_none():
    """PageData without error_type defaults to None."""
    p = PageData(url="https://example.com", final_url="https://example.com")
    assert p.error_type is None


def test_page_data_error_type_set():
    """PageData accepts error_type=ErrorType.TIMEOUT."""
    p = PageData(
        url="https://example.com",
        final_url="https://example.com",
        error_type=ErrorType.TIMEOUT,
    )
    assert p.error_type == ErrorType.TIMEOUT


def test_page_data_error_type_in_dump():
    """error_type appears in model_dump() when set, is None when not set."""
    p_with = PageData(
        url="https://example.com",
        final_url="https://example.com",
        error_type=ErrorType.NETWORK,
    )
    dump_with = p_with.model_dump()
    assert dump_with["error_type"] == "network"

    p_without = PageData(url="https://example.com", final_url="https://example.com")
    dump_without = p_without.model_dump()
    assert dump_without["error_type"] is None


def test_error_type_importable_from_package():
    """ErrorType is exported from the scraper_service package."""
    from scraper_service import ErrorType as PkgErrorType
    assert PkgErrorType is ErrorType


def test_scrape_request_respect_robots_defaults_false():
    """ScrapeRequest.respect_robots defaults to False per D-06."""
    r = ScrapeRequest(urls=["https://example.com"])
    assert r.respect_robots is False
