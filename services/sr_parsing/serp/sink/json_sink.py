"""JSON file output sink for SERP."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import structlog

from scraper_service.serp.models import SerpResponse
from scraper_service.serp.sink import BaseSerpSink


class SerpJSONSink(BaseSerpSink):
    """Write SerpResponse data as pretty-printed JSON to a file."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._log = structlog.get_logger()

    async def write(self, response: SerpResponse) -> None:
        """Serialize response as pretty-printed JSON."""
        data = response.model_dump(mode="json")
        content = json.dumps(data, indent=2, ensure_ascii=False)

        self._path.parent.mkdir(parents=True, exist_ok=True)

        await asyncio.to_thread(
            self._path.write_text,
            content,
            encoding="utf-8",
        )
        self._log.info("serp_json_sink_wrote", path=str(self._path), keyword=response.keyword)
