"""Test configuration and fixtures."""
from __future__ import annotations

from typing import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from scraper_service.settings import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings()


@pytest.fixture
def app() -> FastAPI:
    """Create FastAPI app with scraper router mounted at /scraper."""
    from scraper_service.router import router

    app = FastAPI()
    app.include_router(router, prefix="/scraper")
    return app


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """Async HTTP test client for endpoint tests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
