"""Debug dump sink for SERP."""
from __future__ import annotations

import asyncio
from pathlib import Path

import structlog

from scraper_service.serp.models import SerpResponse
from scraper_service.serp.sink import BaseSerpSink


class SerpDebugSink(BaseSerpSink):
    """Write raw SERP HTML and screenshots to a debug directory."""

    def __init__(self, base_dir: str | Path, job_id: str = "default") -> None:
        self._base_dir = Path(base_dir) / job_id
        self._log = structlog.get_logger()

    async def write(self, response: SerpResponse) -> None:
        """Write compressed HTML and screenshot to disk."""
        self._base_dir.mkdir(parents=True, exist_ok=True)

        tasks = []

        # HTML
        if response.snapshot.html_compressed:
            html_path = self._base_dir / f"serp_{response.search_id}.html.gz"
            tasks.append(
                asyncio.to_thread(
                    html_path.write_bytes,
                    response.snapshot.html_compressed,
                )
            )

        # Screenshot
        if response.snapshot.screenshot_png:
            img_path = self._base_dir / f"serp_{response.search_id}.png"
            tasks.append(
                asyncio.to_thread(
                    img_path.write_bytes,
                    response.snapshot.screenshot_png,
                )
            )

        # Full JSON
        json_path = self._base_dir / f"serp_{response.search_id}.json"
        tasks.append(
            asyncio.to_thread(
                json_path.write_text,
                response.model_dump_json(indent=2),
                encoding="utf-8",
            )
        )

        await asyncio.gather(*tasks)
        self._log.info("serp_debug_sink_wrote", path=str(self._base_dir))
