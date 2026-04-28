from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from analysis_service.bc_config import BcBestPracticesConfig, load_bc_config


def test_load_valid_config():
    config = load_bc_config("config/bc_best_practices.yaml")
    assert config.version == "1.0"
    assert len(config.page_type_priority) == 8
    assert "code_page" in config.page_type_priority
    assert config.page_type_priority["code_page"].priority == 1


def test_load_valid_config_universal_rules():
    config = load_bc_config("config/bc_best_practices.yaml")
    assert "linking" in config.universal_rules
    assert "freshness" in config.universal_rules
    assert "eeat" in config.universal_rules
    assert len(config.universal_rules["linking"]) > 0
    first_rule = config.universal_rules["linking"][0]
    assert first_rule.rule is not None
    assert first_rule.check is not None


def test_load_valid_config_page_types():
    config = load_bc_config("config/bc_best_practices.yaml")
    assert len(config.page_types) == 8
    assert "code_page" in config.page_types
    assert config.page_types["code_page"].mandatory_elements is not None
    assert len(config.page_types["code_page"].mandatory_elements) > 0


def test_load_missing_file_raises_runtime_error():
    with pytest.raises(RuntimeError, match="not found"):
        load_bc_config("/nonexistent/path/file.yaml")


def test_load_empty_yaml_raises_runtime_error(tmp_path: Path):
    yaml_file = tmp_path / "empty.yaml"
    yaml_file.write_text("")
    with pytest.raises(RuntimeError, match="empty"):
        load_bc_config(str(yaml_file))


def test_load_invalid_yaml_raises_runtime_error(tmp_path: Path):
    yaml_file = tmp_path / "invalid.yaml"
    yaml_file.write_text(yaml.dump({"page_type_priority": "not_a_dict"}))
    with pytest.raises(RuntimeError, match="validation failed"):
        load_bc_config(str(yaml_file))


def test_bc_config_allows_extra_keys(tmp_path: Path):
    yaml_file = tmp_path / "extra.yaml"
    data = {
        "version": "1.0",
        "page_type_priority": {},
        "universal_rules": {},
        "page_types": {},
        "extra_unknown_key": "should_be_ignored",
    }
    yaml_file.write_text(yaml.dump(data))
    config = load_bc_config(str(yaml_file))
    assert config.version == "1.0"


def test_settings_has_bc_path_field(monkeypatch: pytest.MonkeyPatch):
    from analysis_service.settings import Settings

    monkeypatch.setenv("ANALYSIS_GEMINI_API_KEY", "test-api-key")
    monkeypatch.setenv("ANALYSIS_GEMINI_MODEL", "gemini-2.5-flash")
    monkeypatch.setenv("ANALYSIS_PORT", "6969")
    monkeypatch.delenv("ANALYSIS_BC_BEST_PRACTICES_PATH", raising=False)
    settings = Settings()
    assert settings.bc_best_practices_path == "config/bc_best_practices.yaml"


def test_settings_bc_path_env_override(monkeypatch: pytest.MonkeyPatch, required_env):
    from analysis_service.settings import Settings

    monkeypatch.setenv("ANALYSIS_BC_BEST_PRACTICES_PATH", "/custom/path.yaml")
    settings = Settings()
    assert settings.bc_best_practices_path == "/custom/path.yaml"
