"""JSON file output sink (SINK-02)."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import structlog

from scraper_service.models import ScrapedPage
from scraper_service.sinks import BaseSink


class JSONSink(BaseSink):
    """Write ScrapedPage data as pretty-printed JSON to a file.

    Output is UTF-8 with ensure_ascii=False so non-ASCII characters
    are preserved (not escaped to \\uXXXX sequences).
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._log = structlog.get_logger()

    async def write(self, pages: list[ScrapedPage]) -> None:
        """Serialize pages as pretty-printed JSON."""
        data = [p.model_dump(mode="json") for p in pages]
        content = json.dumps(data, indent=2, ensure_ascii=False)

        self._path.parent.mkdir(parents=True, exist_ok=True)

        await asyncio.to_thread(
            self._path.write_text,
            content,
            encoding="utf-8",
        )
        self._log.info("json_sink_wrote", path=str(self._path), page_count=len(pages))
