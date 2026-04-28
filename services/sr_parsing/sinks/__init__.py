"""Output sinks for the scraper service."""
from __future__ import annotations

from abc import ABC, abstractmethod

from scraper_service.models import ScrapedPage


class BaseSink(ABC):
    """Base class for all output sinks.

    Each sink implements async write() and optionally overrides close()
    for resource cleanup (connection pools, file handles).
    """

    @abstractmethod
    async def write(self, pages: list[ScrapedPage]) -> None:
        """Write scraped pages to the sink target.

        Args:
            pages: List of ScrapedPage objects with fetch + extraction data.
        """
        ...

    async def close(self) -> None:
        """Clean up resources. Default is no-op."""
        pass


async def run_sinks(
    pages: list[ScrapedPage],
    sinks: list[BaseSink],
) -> list[Exception]:
    """Run all sinks in parallel, collect failures without breaking others.

    Returns list of exceptions from failed sinks. Empty list = all succeeded.
    """
    import asyncio

    import structlog

    log = structlog.get_logger()

    async def _safe_write(sink: BaseSink) -> None:
        try:
            await sink.write(pages)
        except Exception as exc:
            log.error("sink_failed", sink=type(sink).__name__, error=str(exc))
            raise

    results = await asyncio.gather(
        *[_safe_write(s) for s in sinks],
        return_exceptions=True,
    )

    failures = [r for r in results if isinstance(r, Exception)]
    if failures:
        log.warning("sinks_partial_failure", failed=len(failures), total=len(sinks))
    return failures
