"""Debug dump output sink (SINK-05)."""
from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path

import structlog

from scraper_service.models import ScrapedPage
from scraper_service.sinks import BaseSink


class DebugSink(BaseSink):
    """Write debug dumps for each scraped page to per-URL directories.

    Directory structure:
        {base_dir}/{job_id}/{url_hash_16chars}/
            page.html        -- raw HTML (if available)
            meta.json        -- fetch metadata (render_method, status, etc.)
            extraction.json  -- full ExtractionResult
            screenshot.png   -- Playwright screenshot (if available)

    Args:
        base_dir: Root directory for debug dumps.
        job_id: Identifier for this scraping job (used as subdirectory).
    """

    def __init__(self, base_dir: str | Path, job_id: str = "default") -> None:
        self._base_dir = Path(base_dir)
        self._job_id = job_id
        self._log = structlog.get_logger()

    async def write(self, pages: list[ScrapedPage]) -> None:
        """Write debug files for each page."""
        for page in pages:
            url_hash = hashlib.sha256(
                page.page_data.url.encode()
            ).hexdigest()[:16]
            dump_dir = self._base_dir / self._job_id / url_hash
            dump_dir.mkdir(parents=True, exist_ok=True)

            # Raw HTML (skip if None)
            if page.page_data.html is not None:
                await asyncio.to_thread(
                    (dump_dir / "page.html").write_text,
                    page.page_data.html,
                    encoding="utf-8",
                )

            # Fetch metadata (exclude html, xhr_responses, and binary data)
            meta = page.page_data.model_dump(
                mode="json",
                exclude={"html", "xhr_responses"},
            )
            await asyncio.to_thread(
                (dump_dir / "meta.json").write_text,
                json.dumps(meta, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            # Full extraction result
            extraction_json = page.extraction_result.model_dump(mode="json")
            await asyncio.to_thread(
                (dump_dir / "extraction.json").write_text,
                json.dumps(extraction_json, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            # Screenshot (skip if None -- no placeholder, no empty file)
            if page.screenshot_bytes is not None:
                await asyncio.to_thread(
                    (dump_dir / "screenshot.png").write_bytes,
                    page.screenshot_bytes,
                )

        self._log.info(
            "debug_sink_wrote",
            base_dir=str(self._base_dir),
            job_id=self._job_id,
            page_count=len(pages),
        )
