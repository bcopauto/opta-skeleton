"""MySQL output sink with async SQLAlchemy 2.0 upsert."""
from __future__ import annotations

import structlog
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.ext.asyncio import async_sessionmaker

from scraper_service.models import ScrapedPage
from scraper_service.sinks import BaseSink
from scraper_service.sinks.db import Base, ScrapedPageRow, create_engine_and_session, extract_row_values
from scraper_service.settings import Settings


class MySQLSink(BaseSink):
    """Write ScrapedPage data to MySQL scraped_pages table.

    Uses INSERT ... ON DUPLICATE KEY UPDATE via SQLAlchemy's
    mysql-specific insert dialect.

    Lifecycle:
        sink = await MySQLSink.create(settings)
        await sink.write(pages)
        await sink.close()
    """

    def __init__(
        self,
        session_factory: async_sessionmaker,
        _engine=None,
    ) -> None:
        self._session_factory = session_factory
        self._engine = _engine
        self._log = structlog.get_logger()

    @classmethod
    async def create(cls, settings: Settings) -> MySQLSink:
        """Create MySQLSink from Settings.

        Raises ValueError if mysql_connection_string is empty.
        """
        conn_str = settings.mysql_connection_string
        if not conn_str:
            raise ValueError(
                "SCRAPER_MYSQL_CONNECTION_STRING is required for MySQL sink"
            )
        engine, session_factory = create_engine_and_session(conn_str)

        # Ensure table exists
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        return cls(session_factory=session_factory, _engine=engine)

    async def write(self, pages: list[ScrapedPage]) -> None:
        """Upsert pages into scraped_pages table in a single transaction.

        Uses mysql_insert().values() for batch insert with
        on_duplicate_key_update() for upsert behavior.
        """
        if not pages:
            return

        rows = [extract_row_values(p) for p in pages]

        async with self._session_factory() as session:
            async with session.begin():
                stmt = mysql_insert(ScrapedPageRow).values(rows)
                update_cols = {
                    col.name: stmt.inserted[col.name]
                    for col in ScrapedPageRow.__table__.columns
                    if col.name not in ("id", "url")
                }
                upsert_stmt = stmt.on_duplicate_key_update(**update_cols)
                await session.execute(upsert_stmt)

        self._log.info("mysql_sink_wrote", row_count=len(pages))

    async def close(self) -> None:
        """Dispose of the engine and its connection pool."""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
