"""Tests for analysis_service Settings (ANLYS-01)."""
from __future__ import annotations

import pytest
from pydantic import ValidationError


def test_settings_requires_gemini_api_key() -> None:
    """Settings() raises ValidationError when ANALYSIS_GEMINI_API_KEY is missing."""
    import os
    env_backup = {}
    for key in ("ANALYSIS_GEMINI_API_KEY", "ANALYSIS_GEMINI_MODEL", "ANALYSIS_PORT"):
        env_backup[key] = os.environ.pop(key, None)
    try:
        from analysis_service.settings import Settings
        with pytest.raises(ValidationError):
            Settings(_env_file=None)
    finally:
        for key, val in env_backup.items():
            if val is not None:
                os.environ[key] = val


def test_settings_loads_all_required_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings loads ANALYSIS_GEMINI_API_KEY, ANALYSIS_GEMINI_MODEL, ANALYSIS_PORT."""
    monkeypatch.setenv("ANALYSIS_GEMINI_API_KEY", "my-api-key")
    monkeypatch.setenv("ANALYSIS_GEMINI_MODEL", "gemini-2.5-flash")
    monkeypatch.setenv("ANALYSIS_PORT", "6969")
    from analysis_service.settings import Settings
    s = Settings()
    assert s.gemini_api_key.get_secret_value() == "my-api-key"
    assert s.gemini_model == "gemini-2.5-flash"
    assert s.port == 6969


def test_settings_defaults_for_optional_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Optional settings have sensible defaults without explicit env vars."""
    monkeypatch.setenv("ANALYSIS_GEMINI_API_KEY", "key")
    monkeypatch.setenv("ANALYSIS_GEMINI_MODEL", "gemini-2.5-flash")
    monkeypatch.setenv("ANALYSIS_PORT", "6969")
    from analysis_service.settings import Settings
    s = Settings()
    assert s.max_concurrent_gemini_calls == 3
    assert s.token_ceiling_per_module == 100_000
    assert s.log_level == "INFO"


def test_settings_env_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings uses ANALYSIS_ prefix — bare GEMINI_API_KEY is ignored."""
    monkeypatch.setenv("ANALYSIS_GEMINI_API_KEY", "prefixed-key")
    monkeypatch.setenv("ANALYSIS_GEMINI_MODEL", "gemini-2.5-flash")
    monkeypatch.setenv("ANALYSIS_PORT", "6969")
    from analysis_service.settings import Settings
    s = Settings()
    assert s.gemini_api_key.get_secret_value() == "prefixed-key"
