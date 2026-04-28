"""Sink factory: maps SinkType enum to concrete sink classes."""
from __future__ import annotations

from scraper_service.models import SinkConfig, SinkType
from scraper_service.settings import Settings
from scraper_service.sinks import BaseSink
from scraper_service.sinks.csv_sink import CSVSink
from scraper_service.sinks.debug_sink import DebugSink
from scraper_service.sinks.json_sink import JSONSink
from scraper_service.sinks.mysql_sink import MySQLSink


async def build_sinks(
    configs: list[SinkConfig],
    settings: Settings,
    job_id: str = "default",
) -> list[BaseSink]:
    """Instantiate concrete sink objects from a list of SinkConfig.

    Raises ValueError for unknown SinkType values.
    """
    sinks: list[BaseSink] = []
    for cfg in configs:
        if cfg.type == SinkType.JSON:
            path = cfg.config.get("path", "output.json")
            sinks.append(JSONSink(path))
        elif cfg.type == SinkType.CSV:
            path = cfg.config.get("path", "output.csv")
            sinks.append(CSVSink(path))
        elif cfg.type == SinkType.DATABASE:
            sink = await MySQLSink.create(settings)
            sinks.append(sink)
        elif cfg.type == SinkType.DEBUG_DUMP:
            base_dir = cfg.config.get(
                "path", settings.debug_dump_dir or "/tmp/scraper_debug"
            )
            sinks.append(DebugSink(base_dir, job_id=job_id))
        else:
            raise ValueError(f"Unknown sink type: {cfg.type}")
    return sinks
