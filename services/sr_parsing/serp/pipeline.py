"""End-to-end SERP pipeline orchestration.

Wires together the SerpAPI client, extraction functions, and difficulty scorer
into a single coherent flow that returns a fully populated SerpResponse.

Public API:
  - SerpPipeline: async context manager for reuse across multiple calls
  - run_serp: one-shot convenience function
"""
from __future__ import annotations

import time
import unicodedata
from typing import Any

import structlog

from scraper_service.serp.client import fetch_serp
from scraper_service.serp.extractor import (
    extract_ads,
    extract_features,
    extract_featured_snippet,
    extract_images,
    extract_knowledge_panel,
    extract_organic_results,
    extract_paa_items,
    extract_serp_urls,
    extract_shopping,
    extract_top_stories,
    extract_videos,
)
from scraper_service.serp.models import (
    CostMetadata,
    SerpResponse,
    SerpSnapshot,
    normalize_keyword,
    normalize_language,
    normalize_market,
)
from scraper_service.serp.scorer import calculate_difficulty_score

logger = structlog.get_logger()


class SerpPipeline:
    """Orchestrates the SERP pipeline: fetch, extract, score, assemble.

    Use as an async context manager to reuse the underlying HTTP client
    across multiple run() calls:

        async with SerpPipeline(api_key="...") as pipeline:
            r1 = await pipeline.run("pizza", "US", "en")
            r2 = await pipeline.run("burger", "US", "en")
    """

    def __init__(
        self,
        api_key: str | None = None,
        timeout: float = 40.0,
        html_timeout: float = 60.0,
    ) -> None:
        self._api_key = api_key
        self._timeout = timeout
        self._html_timeout = html_timeout

    async def __aenter__(self) -> SerpPipeline:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        pass

    async def run(
        self,
        keyword: str,
        market: str,
        language: str,
        num: int = 10,
        target_url: str = "",
    ) -> SerpResponse:
        """Execute the full SERP pipeline and return a SerpResponse."""
        return await _execute_pipeline(
            keyword=keyword,
            market=market,
            language=language,
            num=num,
            target_url=target_url,
            api_key=self._api_key,
            timeout=self._timeout,
            html_timeout=self._html_timeout,
        )


async def run_serp(
    keyword: str,
    market: str,
    language: str,
    num: int = 10,
    target_url: str = "",
    api_key: str | None = None,
) -> SerpResponse:
    """One-shot SERP pipeline. Wraps SerpPipeline for single-use calls."""
    async with SerpPipeline(api_key=api_key) as pipeline:
        return await pipeline.run(
            keyword=keyword,
            market=market,
            language=language,
            num=num,
            target_url=target_url,
        )


async def _execute_pipeline(
    keyword: str,
    market: str,
    language: str,
    num: int,
    target_url: str,
    api_key: str | None,
    timeout: float,
    html_timeout: float,
) -> SerpResponse:
    """Core pipeline logic, separated for testability."""
    # 1. Normalize inputs
    keyword_normalized = unicodedata.normalize("NFC", keyword or "")
    keyword_normalized = " ".join(keyword_normalized.split())
    keyword_norm = normalize_keyword(keyword_normalized)
    market_norm = normalize_market(market)
    language_norm = normalize_language(language)

    if not keyword_normalized:
        raise ValueError("keyword must not be empty")

    logger.info(
        "serp_pipeline_start",
        keyword=keyword_normalized,
        keyword_norm=keyword_norm,
        market=market_norm,
        language=language_norm,
    )

    # 2. Fetch from SerpAPI
    data: dict[str, Any]
    html_text: str | None
    snapshot: SerpSnapshot

    t0 = time.monotonic()
    data, html_text, snapshot = await fetch_serp(
        keyword=keyword_normalized,
        market=market_norm,
        language=language_norm,
        num=num,
        api_key=api_key,
    )
    fetch_ms = round((time.monotonic() - t0) * 1000, 1)

    # 3. Extract search metadata
    search_metadata = data.get("search_metadata") or {}
    search_id = search_metadata.get("id", "")
    search_status = search_metadata.get("status", "")

    # 3b. Build cost metadata
    credits_raw = search_metadata.get("credits_used")
    time_raw = search_metadata.get("total_time_taken")
    cost = CostMetadata(
        serp_api_calls=1,
        serp_api_credits_used=float(credits_raw) if credits_raw is not None else None,
        serp_api_total_time_taken=float(time_raw) if time_raw is not None else None,
        fetch_duration_ms=fetch_ms,
    )

    # 4-13. Run all extractors (each never raises on bad input)
    features = extract_features(data)
    organic_results = extract_organic_results(data)
    paa_items = extract_paa_items(data)
    ads_top, ads_bottom = extract_ads(data)
    featured_snippet = extract_featured_snippet(data)
    shopping_results = extract_shopping(data)
    top_stories = extract_top_stories(data)
    knowledge_panel = extract_knowledge_panel(data)
    videos = extract_videos(data)
    images = extract_images(data)

    # 14. Extract deduplicated URLs with optional target injection
    serp_urls = extract_serp_urls(data, target_url=target_url)

    # 15. Compute difficulty score
    difficulty_score = calculate_difficulty_score(
        features, organic_results, keyword_norm
    )

    # 16. Assemble response
    response = SerpResponse(
        keyword=keyword_normalized,
        keyword_norm=keyword_norm,
        market=market_norm,
        language=language_norm,
        features=features,
        organic_results=organic_results,
        paa_items=paa_items,
        ads_top=ads_top,
        ads_bottom=ads_bottom,
        featured_snippet=featured_snippet,
        shopping_results=shopping_results,
        top_stories=top_stories,
        knowledge_panel=knowledge_panel,
        videos=videos,
        images=images,
        serp_urls=serp_urls,
        snapshot=snapshot,
        difficulty_score=difficulty_score,
        search_id=search_id,
        search_status=search_status,
        cost=cost,
    )

    logger.info(
        "serp_pipeline_complete",
        keyword=keyword_normalized,
        organics=len(organic_results),
        paa=len(paa_items),
        urls=len(serp_urls),
        score=difficulty_score.total_score,
        label=difficulty_score.label,
    )

    return response
