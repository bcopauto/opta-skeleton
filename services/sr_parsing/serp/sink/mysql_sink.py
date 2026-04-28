"""MySQL output sink for SERP with async SQLAlchemy 2.0."""
from __future__ import annotations

import structlog
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.ext.asyncio import async_sessionmaker

from scraper_service.serp.models import SerpResponse
from scraper_service.serp.sink import BaseSerpSink
from scraper_service.serp.sink.db import Base, SerpResultRow, create_engine_and_session, extract_serp_row_values
from scraper_service.settings import Settings


class SerpMySQLSink(BaseSerpSink):
    """Write SerpResponse data to MySQL serp_results table."""

    def __init__(
        self,
        session_factory: async_sessionmaker,
        _engine=None,
    ) -> None:
        self._session_factory = session_factory
        self._engine = _engine
        self._log = structlog.get_logger()

    @classmethod
    async def create(cls, settings: Settings) -> SerpMySQLSink:
        """Create SerpMySQLSink from Settings."""
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

    async def write(self, response: SerpResponse) -> None:
        """Upsert SERP response into serp_results table."""
        row = extract_serp_row_values(response)

        async with self._session_factory() as session:
            async with session.begin():
                stmt = mysql_insert(SerpResultRow).values([row])
                update_cols = {
                    col.name: stmt.inserted[col.name]
                    for col in SerpResultRow.__table__.columns
                    if col.name not in ("id", "keyword", "market", "language")
                }
                upsert_stmt = stmt.on_duplicate_key_update(**update_cols)
                await session.execute(upsert_stmt)

        self._log.info("serp_mysql_sink_wrote", keyword=response.keyword)

    async def close(self) -> None:
        """Dispose of the engine."""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
