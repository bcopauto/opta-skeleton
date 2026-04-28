"""Robots.txt checker with per-domain caching."""
from __future__ import annotations

from urllib.parse import urlparse

import httpx
import structlog

import robotexclusionrulesparser


class RobotsChecker:
    """Fetch and cache robots.txt per domain, check URL allowance.

    Uses robotexclusionrulesparser for parsing (D-09).
    Checks against wildcard (*) User-Agent rules (D-10).
    Failed fetches (timeout, 5xx, DNS) allow crawling (D-08).
    """

    def __init__(self, client: httpx.AsyncClient, timeout: int = 10) -> None:
        self._client = client
        self._timeout = timeout
        self._cache: dict[str, robotexclusionrulesparser.RobotExclusionRulesParser | None] = {}
        self._log = structlog.get_logger()

    async def is_allowed(self, url: str) -> bool:
        """Check if URL is allowed by robots.txt.

        Fetches robots.txt once per domain (scheme://netloc), caches the
        parsed result. Returns True if:
        - robots.txt allows the URL for wildcard UA
        - robots.txt could not be fetched (D-08)
        - robots.txt returned non-200 status
        """
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in self._cache:
            self._cache[origin] = await self._fetch_robots(origin)
        parser = self._cache[origin]
        if parser is None:
            return True
        return parser.is_allowed("*", url)

    async def _fetch_robots(
        self, origin: str,
    ) -> robotexclusionrulesparser.RobotExclusionRulesParser | None:
        """Fetch and parse robots.txt for a domain origin.

        Returns None on any error (D-08: failed fetch = allow all).
        """
        robots_url = f"{origin}/robots.txt"
        try:
            resp = await self._client.get(
                robots_url,
                timeout=self._timeout,
                follow_redirects=True,
            )
            if resp.status_code != 200:
                self._log.debug("robots_non_200", url=robots_url, status=resp.status_code)
                return None
            parser = robotexclusionrulesparser.RobotExclusionRulesParser()
            parser.parse(resp.text)
            return parser
        except Exception as exc:
            self._log.debug("robots_fetch_failed", url=robots_url, error=str(exc))
            return None
