"""CSV file output sink for SERP with flattening."""
from __future__ import annotations

import asyncio
import csv
import json
from io import StringIO
from pathlib import Path
from typing import Any

import structlog

from scraper_service.serp.models import SerpResponse
from scraper_service.serp.sink import BaseSerpSink


def flatten_serp_response(response: SerpResponse) -> dict[str, Any]:
    """Flatten SerpResponse into a flat dict with dotted keys."""
    flat: dict[str, Any] = {}
    data = response.model_dump(mode="json")

    # Skip large/binary fields
    skip_fields = {"snapshot"}

    def _flatten(obj: Any, prefix: str = "") -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in skip_fields and not prefix:
                    continue
                new_prefix = f"{prefix}.{k}" if prefix else k
                if isinstance(v, (dict, list)):
                    if isinstance(v, list) or (isinstance(v, dict) and any(isinstance(val, (dict, list)) for val in v.values())):
                         flat[new_prefix] = json.dumps(v, ensure_ascii=False)
                    else:
                        _flatten(v, new_prefix)
                else:
                    flat[new_prefix] = v
        else:
            flat[prefix] = obj

    _flatten(data)
    return flat


class SerpCSVSink(BaseSerpSink):
    """Write SerpResponse data as a flattened CSV row."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._log = structlog.get_logger()

    async def write(self, response: SerpResponse) -> None:
        """Flatten response and write as CSV."""
        flat_data = flatten_serp_response(response)
        columns = sorted(flat_data.keys())

        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=columns)
        writer.writeheader()
        writer.writerow(flat_data)

        content = output.getvalue()

        self._path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(
            self._path.write_text,
            content,
            encoding="utf-8",
        )
        self._log.info("serp_csv_sink_wrote", path=str(self._path), keyword=response.keyword)
