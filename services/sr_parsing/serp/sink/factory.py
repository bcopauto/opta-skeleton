"""SERP Sink factory."""
from __future__ import annotations

from scraper_service.models import SinkConfig, SinkType
from scraper_service.settings import Settings
from scraper_service.serp.sink import BaseSerpSink
from scraper_service.serp.sink.csv_sink import SerpCSVSink
from scraper_service.serp.sink.debug_sink import SerpDebugSink
from scraper_service.serp.sink.json_sink import SerpJSONSink
from scraper_service.serp.sink.mysql_sink import SerpMySQLSink


async def build_serp_sinks(
    configs: list[SinkConfig],
    settings: Settings,
    job_id: str = "serp_default",
) -> list[BaseSerpSink]:
    """Instantiate concrete SERP sink objects."""
    sinks: list[BaseSerpSink] = []
    for cfg in configs:
        if cfg.type == SinkType.JSON:
            path = cfg.config.get("path", "serp_output.json")
            sinks.append(SerpJSONSink(path))
        elif cfg.type == SinkType.CSV:
            path = cfg.config.get("path", "serp_output.csv")
            sinks.append(SerpCSVSink(path))
        elif cfg.type == SinkType.DATABASE:
            sink = await SerpMySQLSink.create(settings)
            sinks.append(sink)
        elif cfg.type == SinkType.DEBUG_DUMP:
            base_dir = cfg.config.get(
                "path", settings.debug_dump_dir or "/tmp/serp_debug"
            )
            sinks.append(SerpDebugSink(base_dir, job_id=job_id))
        else:
            raise ValueError(f"Unknown sink type: {cfg.type}")
    return sinks
