"""FastAPI router with all scraper service endpoints."""
from __future__ import annotations

import asyncio
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse

from scraper_service.browser import BrowserManager
from scraper_service.fetcher import Scraper
from scraper_service.models import (
    JobState,
    JobStatus,
    ScrapeRequest,
    ScrapedPage,
    SerpRequest,
)
from scraper_service.pagespeed.client import fetch_pagespeed
from scraper_service.pagespeed.models import PageSpeedRequest, PageSpeedResult
from scraper_service.serp.pipeline import run_serp
from scraper_service.settings import Settings

router = APIRouter()

# Module-level in-memory stores (D-01, D-12).
# Lost on process restart. Fine for v1 single-instance deployment.
_jobs: dict[str, JobState] = {}
_serp_snapshots: dict[str, Any] = {}


def _reset_state() -> None:
    """Clear in-memory stores. For testing only."""
    _jobs.clear()
    _serp_snapshots.clear()


# ---------------------------------------------------------------------------
# POST /scrape (sync)
# ---------------------------------------------------------------------------


@router.post("/scrape")
async def scrape_sync(request: ScrapeRequest) -> list[ScrapedPage]:
    """Synchronous scrape: fetch + extract + sinks, return results inline."""
    settings = Settings()
    if len(request.urls) > settings.max_pages_per_job:
        return JSONResponse(  # type: ignore[return-value]
            status_code=422,
            content={
                "detail": (
                    f"Number of URLs ({len(request.urls)}) exceeds maximum "
                    f"allowed per job ({settings.max_pages_per_job}). "
                    f"Reduce URL count or increase SCRAPER_MAX_PAGES_PER_JOB."
                ),
                "error_code": "URL_LIMIT_EXCEEDED",
            },
        )
    async with Scraper(settings) as scraper:
        results = await scraper.scrape(
            urls=request.urls,
            sinks=request.sinks or None,
        )
    return results


# ---------------------------------------------------------------------------
# POST /scrape/async
# ---------------------------------------------------------------------------


async def _run_scrape_job(
    job_id: str,
    request: ScrapeRequest,
    settings: Settings,
) -> None:
    """Background task that runs the scrape pipeline for an async job."""
    _jobs[job_id].status = JobStatus.RUNNING
    try:
        async with Scraper(settings) as scraper:
            results = await scraper.scrape(
                urls=request.urls,
                sinks=request.sinks or None,
            )
        _jobs[job_id].status = JobStatus.COMPLETED
        _jobs[job_id].results = results
    except Exception as exc:
        _jobs[job_id].status = JobStatus.FAILED
        _jobs[job_id].error = str(exc)


@router.post("/scrape/async")
async def scrape_async(
    request: ScrapeRequest,
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    """Async scrape: accept job, run in background, return job_id."""
    settings = Settings()
    if len(request.urls) > settings.max_pages_per_job:
        return JSONResponse(  # type: ignore[return-value]
            status_code=422,
            content={
                "detail": (
                    f"Number of URLs ({len(request.urls)}) exceeds maximum "
                    f"allowed per job ({settings.max_pages_per_job}). "
                    f"Reduce URL count or increase SCRAPER_MAX_PAGES_PER_JOB."
                ),
                "error_code": "URL_LIMIT_EXCEEDED",
            },
        )
    job_id = str(uuid.uuid4())
    _jobs[job_id] = JobState(job_id=job_id, status=JobStatus.PENDING)
    background_tasks.add_task(_run_scrape_job, job_id, request, settings)
    return {"job_id": job_id, "status": "pending"}


# ---------------------------------------------------------------------------
# GET /scrape/{job_id}
# ---------------------------------------------------------------------------


@router.get("/scrape/{job_id}")
async def get_job(job_id: str) -> JobState:
    """Return current state of an async scrape job."""
    job = _jobs.get(job_id)
    if job is None:
        return JSONResponse(  # type: ignore[return-value]
            status_code=404,
            content={
                "detail": (
                    f"Job {job_id} not found. "
                    f"Jobs are stored in memory and lost on process restart."
                ),
                "error_code": "JOB_NOT_FOUND",
            },
        )
    return job


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------


@router.get("/health")
async def health() -> dict[str, Any]:
    """Liveness check with Playwright availability probe."""
    playwright_ok = False
    try:
        bm = BrowserManager(Settings())
        browser = await bm._ensure_browser()
        playwright_ok = browser.is_connected()
        await bm.close()
    except Exception:
        pass
    return {"status": "healthy", "playwright": playwright_ok}


# ---------------------------------------------------------------------------
# POST /serp
# ---------------------------------------------------------------------------


@router.post("/serp")
async def serp_search(request: SerpRequest) -> JSONResponse:
    """Run SERP pipeline and return full SerpResponse with snapshot_id."""
    settings = Settings()
    response = await run_serp(
        keyword=request.keyword,
        market=request.market,
        language=request.language,
        num=request.num,
        target_url=request.target_url,
    )
    snapshot_id = str(uuid.uuid4())
    _serp_snapshots[snapshot_id] = response

    # Run sinks if configured
    if request.sinks:
        from scraper_service.serp.sink import run_serp_sinks
        from scraper_service.serp.sink.factory import build_serp_sinks

        sinks = await build_serp_sinks(request.sinks, settings, job_id=snapshot_id)
        try:
            await run_serp_sinks(response, sinks)
        finally:
            for s in sinks:
                await s.close()

    return JSONResponse(
        content={"snapshot_id": snapshot_id, **response.model_dump(mode="json")},
    )


# ---------------------------------------------------------------------------
# GET /serp/{snapshot_id}
# ---------------------------------------------------------------------------


@router.get("/serp/{snapshot_id}")
async def get_serp_snapshot(snapshot_id: str) -> JSONResponse:
    """Retrieve a stored SERP snapshot by ID."""
    snapshot = _serp_snapshots.get(snapshot_id)
    if snapshot is None:
        return JSONResponse(
            status_code=404,
            content={
                "detail": (
                    f"SERP snapshot {snapshot_id} not found. "
                    f"Snapshots are stored in memory and lost on process restart."
                ),
                "error_code": "SNAPSHOT_NOT_FOUND",
            },
        )
    return JSONResponse(content=snapshot.model_dump(mode="json"))


# ---------------------------------------------------------------------------
# POST /pagespeed
# ---------------------------------------------------------------------------


@router.post("/pagespeed")
async def pagespeed(request: PageSpeedRequest) -> list[PageSpeedResult]:
    """Run PageSpeed Insights for one or more URLs."""
    settings = Settings()
    results = await asyncio.gather(*[
        fetch_pagespeed(
            url,
            strategy=request.strategy,
            api_key=settings.pagespeed_api_key,
        )
        for url in request.urls
    ])
    return list(results)
