from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from analysis_service.bc_config import load_bc_config
from analysis_service.logging import configure_logging
from analysis_service.router import _cleanup_expired_jobs, router
from analysis_service.settings import Settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """FastAPI lifespan: configure logging, load bc_config, start TTL cleanup."""
    import analysis_service.router as _router

    settings = Settings()
    configure_logging(settings.log_level)
    app.state.settings = settings
    app.state.bc_best_practices = load_bc_config(settings.bc_best_practices_path)
    _router._gemini_semaphore = asyncio.Semaphore(settings.max_concurrent_gemini_calls)
    cleanup_task = asyncio.create_task(
        _cleanup_expired_jobs(settings.job_ttl_minutes)
    )
    yield
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Analysis Service",
    description="SEO analysis microservice — scores target pages against SERP competitors",
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(router)
