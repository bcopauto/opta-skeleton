"""Output sinks for the SERP pipeline."""
from __future__ import annotations

from abc import ABC, abstractmethod

from scraper_service.serp.models import SerpResponse


class BaseSerpSink(ABC):
    """Base class for all SERP output sinks."""

    @abstractmethod
    async def write(self, response: SerpResponse) -> None:
        """Write SERP response to the sink target."""
        ...

    async def close(self) -> None:
        """Clean up resources. Default is no-op."""
        pass


async def run_serp_sinks(
    response: SerpResponse,
    sinks: list[BaseSerpSink],
) -> list[Exception]:
    """Run all SERP sinks in parallel, collect failures."""
    import asyncio
    import structlog

    log = structlog.get_logger()

    async def _safe_write(sink: BaseSerpSink) -> None:
        try:
            await sink.write(response)
        except Exception as exc:
            log.error("serp_sink_failed", sink=type(sink).__name__, error=str(exc))
            raise

    results = await asyncio.gather(
        *[_safe_write(s) for s in sinks],
        return_exceptions=True,
    )

    failures = [r for r in results if isinstance(r, Exception)]
    if failures:
        log.warning("serp_sinks_partial_failure", failed=len(failures), total=len(sinks))
    return failures
