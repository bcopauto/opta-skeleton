"""SQLAlchemy async engine, session factory, and ORM model for serp_results."""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from scraper_service.serp.models import SerpResponse


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class SerpResultRow(Base):
    """ORM model for serp_results table."""

    __tablename__ = "serp_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    keyword: Mapped[str] = mapped_column(String(500), nullable=False)
    market: Mapped[str] = mapped_column(String(10), nullable=False)
    language: Mapped[str] = mapped_column(String(10), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Key metrics
    difficulty_score: Mapped[float | None] = mapped_column(Float)
    organic_count: Mapped[int | None] = mapped_column(Integer)
    ads_count: Mapped[int | None] = mapped_column(Integer)

    # Feature flags
    has_ai_overview: Mapped[bool | None] = mapped_column(Boolean)
    has_featured_snippet: Mapped[bool | None] = mapped_column(Boolean)
    has_knowledge_panel: Mapped[bool | None] = mapped_column(Boolean)

    # Full data
    response_json: Mapped[dict | None] = mapped_column("response_json", JSON)

    # Unique constraint on keyword+market+language for upsert
    __table_args__ = (
        UniqueConstraint('keyword', 'market', 'language', name='_keyword_market_lang_uc'),
    )


def create_engine_and_session(
    connection_string: str,
    pool_size: int = 5,
) -> tuple[AsyncEngine, async_sessionmaker]:
    """Create async engine and session factory for MySQL."""
    engine = create_async_engine(
        connection_string,
        pool_size=pool_size,
        pool_recycle=3600,
        pool_pre_ping=True,
        echo=False,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, session_factory


def extract_serp_row_values(response: SerpResponse) -> dict:
    """Extract flat row values from SerpResponse for MySQL insert."""
    return {
        "keyword": response.keyword,
        "market": response.market,
        "language": response.language,
        "difficulty_score": response.difficulty_score.total_score,
        "organic_count": len(response.organic_results),
        "ads_count": len(response.ads_top) + len(response.ads_bottom),
        "has_ai_overview": response.features.has_ai_overview,
        "has_featured_snippet": response.features.has_featured_snippet,
        "has_knowledge_panel": response.features.has_knowledge_panel,
        "response_json": response.model_dump(mode="json"),
    }
