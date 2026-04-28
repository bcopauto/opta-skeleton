"""SQLAlchemy async engine, session factory, and ORM model for scraped_pages."""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from scraper_service.models import ScrapedPage


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class ScrapedPageRow(Base):
    """ORM model for scraped_pages table.

    Hybrid schema: ~20 key columns for filtering/sorting + one JSON column
    for the full ExtractionResult. Upsert on url.
    """

    __tablename__ = "scraped_pages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(String(2083), unique=True, nullable=False, index=True)

    # Fetch-level columns
    final_url: Mapped[str | None] = mapped_column(String(2083))
    status_code: Mapped[int | None] = mapped_column(Integer)
    render_method: Mapped[str | None] = mapped_column(String(20))
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Extraction key columns
    title: Mapped[str | None] = mapped_column(String(500))
    meta_description: Mapped[str | None] = mapped_column(String(1000))
    word_count: Mapped[int | None] = mapped_column(Integer)
    h1_count: Mapped[int | None] = mapped_column(Integer)
    h2_count: Mapped[int | None] = mapped_column(Integer)
    total_headings: Mapped[int | None] = mapped_column(Integer)
    image_count: Mapped[int | None] = mapped_column(Integer)
    alt_coverage_pct: Mapped[float | None] = mapped_column(Float)
    internal_links: Mapped[int | None] = mapped_column(Integer)
    external_links: Mapped[int | None] = mapped_column(Integer)
    canonical_url: Mapped[str | None] = mapped_column(String(2083))
    is_https: Mapped[bool | None] = mapped_column(Boolean)
    jsonld_types: Mapped[str | None] = mapped_column(Text)  # JSON array as text
    robots_noindex: Mapped[bool | None] = mapped_column(Boolean)
    has_faq: Mapped[bool | None] = mapped_column(Boolean)

    # Full extraction data
    extraction_json: Mapped[dict | None] = mapped_column("extraction_json", JSON)


def create_engine_and_session(
    connection_string: str,
    pool_size: int = 5,
) -> tuple[AsyncEngine, async_sessionmaker]:
    """Create async engine and session factory for MySQL.

    Args:
        connection_string: mysql+aiomysql://user:pass@host:3306/dbname
        pool_size: Connection pool size (default 5).

    Returns:
        Tuple of (engine, session_factory).
    """
    engine = create_async_engine(
        connection_string,
        pool_size=pool_size,
        pool_recycle=3600,
        pool_pre_ping=True,
        echo=False,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, session_factory


def extract_row_values(page: ScrapedPage) -> dict:
    """Extract flat row values from ScrapedPage for MySQL insert.

    Maps ScrapedPage fields to ScrapedPageRow columns. jsonld_types
    list is JSON-serialized. Full ExtractionResult goes to extraction_json
    via model_dump(mode="json").
    """
    pd = page.page_data
    er = page.extraction_result

    jsonld_types_str: str | None = None
    if er.jsonld.jsonld_types:
        jsonld_types_str = json.dumps(er.jsonld.jsonld_types)

    return {
        "url": pd.url,
        "final_url": pd.final_url,
        "status_code": pd.status_code,
        "render_method": pd.render_method.value,
        "fetched_at": pd.fetched_at,
        "title": er.title.title,
        "meta_description": er.meta_desc.meta_description,
        "word_count": er.body_text.word_count,
        "h1_count": er.headings.h1_count,
        "h2_count": er.headings.h2_count,
        "total_headings": er.headings.total_headings,
        "image_count": er.images.total_images,
        "alt_coverage_pct": er.images.alt_coverage_pct,
        "internal_links": er.links.internal_links,
        "external_links": er.links.external_links,
        "canonical_url": er.meta.canonical_url,
        "is_https": er.technical.is_https,
        "jsonld_types": jsonld_types_str,
        "robots_noindex": er.meta.robots_noindex,
        "has_faq": er.faq.has_faq,
        "extraction_json": er.model_dump(mode="json"),
    }
