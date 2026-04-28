"""Configuration via pydantic-settings with SCRAPER_ env var prefix."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


_BUILTIN_USER_AGENTS: list[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.4; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.3 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
]


class Settings(BaseSettings):
    """Application settings loaded from environment variables with SCRAPER_ prefix."""

    model_config = SettingsConfigDict(
        env_prefix="SCRAPER_",
        extra="ignore",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    timeout: int = 30
    max_retries: int = 3
    retry_backoff: float = 1.0
    max_pages_per_job: int = 100
    max_concurrent_requests: int = 10
    proxy_url: str = ""
    use_proxy: bool = False
    robots_timeout: int = 10
    user_agents: list[str] = []
    log_level: str = "INFO"
    debug_dump_dir: str = ""
    min_body_chars: int = 500
    headless: bool = True
    mysql_connection_string: str = ""
    pagespeed_api_key: str = ""

    @property
    def user_agent_pool(self) -> list[str]:
        if self.user_agents:
            return self.user_agents
        return list(_BUILTIN_USER_AGENTS)
