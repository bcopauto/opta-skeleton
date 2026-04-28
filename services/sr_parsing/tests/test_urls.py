"""Tests for URL validation, normalization, and deduplication."""

from __future__ import annotations

from scraper_service.urls import deduplicate_urls, is_valid_url, normalize_url


def test_is_valid_https() -> None:
    """is_valid_url("https://example.com") == True"""
    assert is_valid_url("https://example.com") is True


def test_is_valid_http() -> None:
    """is_valid_url("http://example.com") == True"""
    assert is_valid_url("http://example.com") is True


def test_is_invalid_no_scheme() -> None:
    """is_valid_url("example.com") == False"""
    assert is_valid_url("example.com") is False


def test_is_invalid_ftp() -> None:
    """is_valid_url("ftp://example.com") == False"""
    assert is_valid_url("ftp://example.com") is False


def test_is_invalid_spaces() -> None:
    """is_valid_url("https://example.com/path with spaces") == False"""
    assert is_valid_url("https://example.com/path with spaces") is False


def test_is_invalid_empty_netloc() -> None:
    """is_valid_url("https://") == False"""
    assert is_valid_url("https://") is False


def test_normalize_lowercase_scheme_host() -> None:
    """normalize_url("HTTPS://EXAMPLE.COM/Path") == "https://example.com/Path\""""
    assert normalize_url("HTTPS://EXAMPLE.COM/Path") == "https://example.com/Path"


def test_normalize_strip_trailing_slash() -> None:
    """normalize_url("https://example.com/path/") == "https://example.com/path\""""
    assert normalize_url("https://example.com/path/") == "https://example.com/path"


def test_normalize_root_path_keeps_slash() -> None:
    """normalize_url("https://example.com/") == "https://example.com\" (per D-12: strip trailing slash)"""
    assert normalize_url("https://example.com/") == "https://example.com"


def test_normalize_sort_query_params() -> None:
    """normalize_url("https://example.com/?b=2&a=1") == "https://example.com/?a=1&b=2\""""
    assert normalize_url("https://example.com/?b=2&a=1") == "https://example.com/?a=1&b=2"


def test_normalize_strip_fragment() -> None:
    """normalize_url("https://example.com/path#section") == "https://example.com/path\""""
    assert normalize_url("https://example.com/path#section") == "https://example.com/path"


def test_normalize_remove_default_port_443() -> None:
    """normalize_url("https://example.com:443/path") == "https://example.com/path\""""
    assert normalize_url("https://example.com:443/path") == "https://example.com/path"


def test_normalize_remove_default_port_80() -> None:
    """normalize_url("http://example.com:80/path") == "http://example.com/path\""""
    assert normalize_url("http://example.com:80/path") == "http://example.com/path"


def test_normalize_keep_nondefault_port() -> None:
    """normalize_url("https://example.com:8080/path") == "https://example.com:8080/path\""""
    assert normalize_url("https://example.com:8080/path") == "https://example.com:8080/path"


def test_deduplicate_removes_exact_duplicates() -> None:
    """deduplicate_urls(["https://a.com", "https://a.com"]) == ["https://a.com\"]"""
    assert deduplicate_urls(["https://a.com", "https://a.com"]) == ["https://a.com"]


def test_deduplicate_after_normalization() -> None:
    """deduplicate_urls(["https://example.com", "https://example.com/", "https://EXAMPLE.COM"]) == ["https://example.com\"]"""
    result = deduplicate_urls(["https://example.com", "https://example.com/", "https://EXAMPLE.COM"])
    assert result == ["https://example.com"]


def test_deduplicate_preserves_order() -> None:
    """deduplicate_urls(["https://c.com", "https://a.com", "https://b.com", "https://a.com"]) == ["https://c.com", "https://a.com", "https://b.com\"]"""
    result = deduplicate_urls(["https://c.com", "https://a.com", "https://b.com", "https://a.com"])
    assert result == ["https://c.com", "https://a.com", "https://b.com"]


def test_deduplicate_empty() -> None:
    """deduplicate_urls([]) == []"""
    assert deduplicate_urls([]) == []


def test_deduplicate_single() -> None:
    """deduplicate_urls(["https://example.com"]) == ["https://example.com\"]"""
    assert deduplicate_urls(["https://example.com"]) == ["https://example.com"]
