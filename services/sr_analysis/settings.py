"""Configuration via pydantic-settings with ANALYSIS_ env var prefix (D-14).

Required vars (no defaults — service raises ValidationError at startup if missing):
  ANALYSIS_GEMINI_API_KEY  — Gemini API key
  ANALYSIS_GEMINI_MODEL    — Gemini model name (e.g. gemini-2.5-flash)
  ANALYSIS_PORT            — Port the service listens on

Optional vars (with defaults):
  ANALYSIS_MAX_CONCURRENT_GEMINI_CALLS  — default 3
  ANALYSIS_TOKEN_CEILING_PER_MODULE     — default 100000
  ANALYSIS_LOG_LEVEL                    — default INFO

"""
from __future__ import annotations

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables with ANALYSIS_ prefix.

    Fields with no default are required — service raises ValidationError at startup
    if the corresponding env var is missing or empty (ANLYS-01).
    """

    model_config = SettingsConfigDict(
        env_prefix="ANALYSIS_",
        extra="ignore",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # Required — no defaults → ValidationError at startup if missing
    gemini_api_key: SecretStr      # ANALYSIS_GEMINI_API_KEY
    gemini_model: str             # ANALYSIS_GEMINI_MODEL
    port: int                     # ANALYSIS_PORT

    # Optional with sensible defaults
    max_concurrent_gemini_calls: int = 3
    token_ceiling_per_module: int = 100_000
    log_level: str = "INFO"
    bc_best_practices_path: str = "config/bc_best_practices.yaml"

    # Async job management
    max_concurrent_jobs: int = 10
    job_ttl_minutes: int = 60
