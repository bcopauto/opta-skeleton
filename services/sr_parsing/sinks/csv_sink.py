"""CSV file output sink with dotted-key flattening (SINK-03)."""
from __future__ import annotations

import asyncio
import csv
import json
from io import StringIO
from pathlib import Path
from typing import Any

import structlog

from scraper_service.models import ExtractionResult, PageData, ScrapedPage
from scraper_service.sinks import BaseSink


# Fields from PageData to skip in CSV (too large or binary)
_SKIP_PAGE_DATA_FIELDS: frozenset[str] = frozenset({"html", "xhr_responses"})

# Fields from ScrapedPage to skip
_SKIP_SCRAPED_PAGE_FIELDS: frozenset[str] = frozenset({"screenshot_bytes"})


def _get_full_column_schema() -> list[str]:
    """Generate the complete column list from the full ExtractionResult schema.

    Uses ExtractionResult with all defaults to enumerate every possible
    dotted key. This ensures consistent column ordering regardless of which
    fields have data.
    """
    empty_er = ExtractionResult()
    er_dump = empty_er.model_dump(mode="json")

    empty_pd = PageData(url="", final_url="")
    pd_dump = empty_pd.model_dump(mode="json")

    columns: list[str] = []
    for key in sorted(pd_dump.keys()):
        if key not in _SKIP_PAGE_DATA_FIELDS:
            columns.append(key)

    for section_name in sorted(er_dump.keys()):
        if section_name == "errors":
            columns.append("extraction_errors")
            continue
        section_data = er_dump[section_name]
        if isinstance(section_data, dict):
            for field_name in sorted(section_data.keys()):
                columns.append(f"{section_name}.{field_name}")
        else:
            columns.append(section_name)

    return columns


def flatten_scraped_page(page: ScrapedPage) -> dict[str, Any]:
    """Flatten ScrapedPage into a flat dict with dotted keys.

    Nested dicts become dotted keys. Lists and complex structures become
    JSON-encoded strings. PageData.html, .xhr_responses and
    ScrapedPage.screenshot_bytes are excluded.
    """
    flat: dict[str, Any] = {}

    # PageData top-level fields
    pd = page.page_data.model_dump(mode="json")
    for key, value in pd.items():
        if key in _SKIP_PAGE_DATA_FIELDS:
            continue
        flat[key] = value

    # ExtractionResult sub-models with dotted prefixes
    er = page.extraction_result.model_dump(mode="json")
    for section_name, section_data in er.items():
        if section_name == "errors":
            if section_data:
                flat["extraction_errors"] = json.dumps(section_data)
            else:
                flat["extraction_errors"] = ""
            continue
        if isinstance(section_data, dict):
            for field_name, field_value in section_data.items():
                full_key = f"{section_name}.{field_name}"
                if isinstance(field_value, (list, dict)):
                    if field_value:
                        flat[full_key] = json.dumps(field_value)
                    else:
                        # Empty list/dict: empty string for CSV readability
                        flat[full_key] = ""
                else:
                    flat[full_key] = field_value
        else:
            flat[section_name] = section_data

    return flat


class CSVSink(BaseSink):
    """Write ScrapedPage data as flattened CSV with dotted keys.

    Column order is derived from the full ExtractionResult schema, ensuring
    consistent headers across runs regardless of data variation.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._log = structlog.get_logger()
        self._columns: list[str] | None = None

    async def write(self, pages: list[ScrapedPage]) -> None:
        """Flatten pages and write as CSV."""
        if self._columns is None:
            self._columns = _get_full_column_schema()

        rows = [flatten_scraped_page(p) for p in pages]

        output = StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=self._columns,
            extrasaction="ignore",
            quoting=csv.QUOTE_MINIMAL,
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

        content = output.getvalue()

        self._path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(
            self._path.write_text,
            content,
            encoding="utf-8",
        )
        self._log.info("csv_sink_wrote", path=str(self._path), row_count=len(pages))
