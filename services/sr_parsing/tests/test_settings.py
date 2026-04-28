"""Tests for Settings class."""
import os

import pytest
from pydantic import ValidationError

from scraper_service.settings import Settings


def test_default_values():
    """Settings with no env vars uses production defaults."""
    s = Settings()
    assert s.timeout == 30
    assert s.max_retries == 3
    assert s.retry_backoff == 1.0
    assert s.max_concurrent_requests == 10
    assert s.max_pages_per_job == 100
    assert s.proxy_url == ""
    assert s.log_level == "INFO"
    assert s.debug_dump_dir == ""


def test_env_var_override():
    """Settings respects SCRAPER_ prefixed env vars."""
    os.environ["SCRAPER_TIMEOUT"] = "60"
    try:
        s = Settings()
        assert s.timeout == 60
    finally:
        os.environ.pop("SCRAPER_TIMEOUT", None)


def test_scraper_prefix():
    """Settings uses SCRAPER_ env var prefix."""
    os.environ["SCRAPER_PROXY_URL"] = "http://proxy:8080"
    try:
        s = Settings()
        assert s.proxy_url == "http://proxy:8080"
    finally:
        os.environ.pop("SCRAPER_PROXY_URL", None)


def test_log_level_env_var():
    """Settings.log_level maps to SCRAPER_LOG_LEVEL env var."""
    os.environ["SCRAPER_LOG_LEVEL"] = "DEBUG"
    try:
        s = Settings()
        assert s.log_level == "DEBUG"
    finally:
        os.environ.pop("SCRAPER_LOG_LEVEL", None)


def test_empty_proxy_means_no_proxy():
    """Settings with no SCRAPER_PROXY_URL has empty proxy_url."""
    s = Settings()
    assert s.proxy_url == ""


def test_default_user_agents_empty():
    """Settings.user_agents defaults to empty list."""
    s = Settings()
    assert s.user_agents == []


def test_user_agent_pool_builtin():
    """Settings.user_agent_pool returns built-in UA list when user_agents is empty."""
    s = Settings()
    pool = s.user_agent_pool
    assert len(pool) >= 6
    assert all("Mozilla" in ua for ua in pool)


def test_custom_user_agents():
    """Settings with SCRAPER_USER_AGENTS uses custom list instead of built-in."""
    os.environ["SCRAPER_USER_AGENTS"] = '["custom-ua"]'
    try:
        s = Settings()
        assert s.user_agents == ["custom-ua"]
        assert s.user_agent_pool == ["custom-ua"]
    finally:
        os.environ.pop("SCRAPER_USER_AGENTS", None)


def test_settings_creates_without_env_file():
    """Settings() succeeds even with no .env file."""
    s = Settings()
    assert s.timeout == 30  # Just verify it loaded with defaults
