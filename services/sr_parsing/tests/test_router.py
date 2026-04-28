"""Integration tests for the FastAPI router endpoints."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from scraper_service.models import (
    ExtractionResult,
    JobStatus,
    PageData,
    RenderMethod,
    ScrapedPage,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_scraped_page(url: str = "https://example.com") -> ScrapedPage:
    """Build a minimal ScrapedPage for mocking."""
    return ScrapedPage(
        page_data=PageData(
            url=url,
            final_url=url,
            status_code=200,
            render_method=RenderMethod.HTTPX,
        ),
        extraction_result=ExtractionResult(),
    )


@pytest.fixture(autouse=True)
def _reset_router_state() -> None:
    """Clear in-memory stores before each test to prevent leakage."""
    from scraper_service.router import _reset_state
    _reset_state()


# ---------------------------------------------------------------------------
# POST /scraper/scrape (sync)
# ---------------------------------------------------------------------------


async def test_scrape_sync_returns_list(client: AsyncClient) -> None:
    """POST /scraper/scrape returns 200 with list of ScrapedPage dicts."""
    mock_scraper = AsyncMock()
    mock_scraper.scrape = AsyncMock(return_value=[_make_scraped_page()])
    mock_scraper.__aenter__ = AsyncMock(return_value=mock_scraper)
    mock_scraper.__aexit__ = AsyncMock(return_value=None)

    with patch("scraper_service.router.Scraper", return_value=mock_scraper):
        resp = await client.post(
            "/scraper/scrape",
            json={"urls": ["https://example.com"]},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert "page_data" in data[0]
    assert "extraction_result" in data[0]


async def test_scrape_sync_url_limit_exceeded(client: AsyncClient) -> None:
    """POST /scraper/scrape with too many URLs returns 422 URL_LIMIT_EXCEEDED."""
    # Default max_pages_per_job is 100, send 101 URLs
    urls = [f"https://example.com/{i}" for i in range(101)]
    resp = await client.post("/scraper/scrape", json={"urls": urls})

    assert resp.status_code == 422
    data = resp.json()
    assert data["error_code"] == "URL_LIMIT_EXCEEDED"
    assert "exceeds maximum allowed per job" in data["detail"]


async def test_scrape_sync_empty_urls_422(client: AsyncClient) -> None:
    """POST /scraper/scrape with empty urls list returns 422 (Pydantic)."""
    resp = await client.post("/scraper/scrape", json={"urls": []})
    assert resp.status_code == 422


async def test_scrape_sync_response_shape(client: AsyncClient) -> None:
    """Response contains page_data and extraction_result keys."""
    mock_scraper = AsyncMock()
    mock_scraper.scrape = AsyncMock(return_value=[_make_scraped_page()])
    mock_scraper.__aenter__ = AsyncMock(return_value=mock_scraper)
    mock_scraper.__aexit__ = AsyncMock(return_value=None)

    with patch("scraper_service.router.Scraper", return_value=mock_scraper):
        resp = await client.post(
            "/scraper/scrape",
            json={"urls": ["https://example.com"]},
        )

    page = resp.json()[0]
    assert page["page_data"]["url"] == "https://example.com"
    assert page["page_data"]["status_code"] == 200
    assert "extraction_result" in page


# ---------------------------------------------------------------------------
# POST /scraper/scrape/async
# ---------------------------------------------------------------------------


async def test_scrape_async_returns_job_id(client: AsyncClient) -> None:
    """POST /scraper/scrape/async returns 200 with job_id and pending status."""
    mock_scraper = AsyncMock()
    mock_scraper.scrape = AsyncMock(return_value=[_make_scraped_page()])
    mock_scraper.__aenter__ = AsyncMock(return_value=mock_scraper)
    mock_scraper.__aexit__ = AsyncMock(return_value=None)

    with patch("scraper_service.router.Scraper", return_value=mock_scraper):
        resp = await client.post(
            "/scraper/scrape/async",
            json={"urls": ["https://example.com"]},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "job_id" in data
    assert data["status"] == "pending"


async def test_scrape_async_job_id_is_uuid(client: AsyncClient) -> None:
    """Job ID from async endpoint is a valid UUID4 string."""
    import uuid

    mock_scraper = AsyncMock()
    mock_scraper.scrape = AsyncMock(return_value=[_make_scraped_page()])
    mock_scraper.__aenter__ = AsyncMock(return_value=mock_scraper)
    mock_scraper.__aexit__ = AsyncMock(return_value=None)

    with patch("scraper_service.router.Scraper", return_value=mock_scraper):
        resp = await client.post(
            "/scraper/scrape/async",
            json={"urls": ["https://example.com"]},
        )

    job_id = resp.json()["job_id"]
    parsed = uuid.UUID(job_id, version=4)
    assert str(parsed) == job_id


async def test_scrape_async_background_completes(client: AsyncClient) -> None:
    """Background task eventually updates job status to completed."""
    mock_scraper = AsyncMock()
    mock_scraper.scrape = AsyncMock(return_value=[_make_scraped_page()])
    mock_scraper.__aenter__ = AsyncMock(return_value=mock_scraper)
    mock_scraper.__aexit__ = AsyncMock(return_value=None)

    with patch("scraper_service.router.Scraper", return_value=mock_scraper):
        resp = await client.post(
            "/scraper/scrape/async",
            json={"urls": ["https://example.com"]},
        )
        job_id = resp.json()["job_id"]

        # Give background task time to run
        await asyncio.sleep(0.2)

        status_resp = await client.get(f"/scraper/scrape/{job_id}")

    assert status_resp.status_code == 200
    data = status_resp.json()
    assert data["status"] == "completed"
    assert data["results"] is not None
    assert len(data["results"]) == 1


async def test_scrape_async_url_limit_exceeded(client: AsyncClient) -> None:
    """POST /scrape/async with too many URLs returns 422."""
    urls = [f"https://example.com/{i}" for i in range(101)]
    resp = await client.post("/scraper/scrape/async", json={"urls": urls})

    assert resp.status_code == 422
    assert resp.json()["error_code"] == "URL_LIMIT_EXCEEDED"


# ---------------------------------------------------------------------------
# GET /scraper/scrape/{job_id}
# ---------------------------------------------------------------------------


async def test_get_job_not_found(client: AsyncClient) -> None:
    """GET /scraper/scrape/{job_id} with nonexistent ID returns 404."""
    resp = await client.get("/scraper/scrape/nonexistent-id")

    assert resp.status_code == 404
    data = resp.json()
    assert data["error_code"] == "JOB_NOT_FOUND"
    assert "not found" in data["detail"]
    assert "stored in memory" in data["detail"]


async def test_get_job_pending(client: AsyncClient) -> None:
    """GET with pending job returns status pending and null results."""
    from scraper_service.router import _jobs
    from scraper_service.models import JobState

    _jobs["test-job-1"] = JobState(job_id="test-job-1", status=JobStatus.PENDING)

    resp = await client.get("/scraper/scrape/test-job-1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "pending"
    assert data["results"] is None


async def test_get_job_completed(client: AsyncClient) -> None:
    """GET with completed job returns results."""
    from scraper_service.router import _jobs
    from scraper_service.models import JobState

    _jobs["test-job-2"] = JobState(
        job_id="test-job-2",
        status=JobStatus.COMPLETED,
        results=[_make_scraped_page()],
    )

    resp = await client.get("/scraper/scrape/test-job-2")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert len(data["results"]) == 1


# ---------------------------------------------------------------------------
# GET /scraper/health
# ---------------------------------------------------------------------------


async def test_health_returns_200(client: AsyncClient) -> None:
    """GET /scraper/health returns 200 with status healthy."""
    with patch("scraper_service.router.BrowserManager") as mock_bm_cls:
        mock_bm = AsyncMock()
        mock_browser = MagicMock()
        mock_browser.is_connected.return_value = True
        mock_bm._ensure_browser = AsyncMock(return_value=mock_browser)
        mock_bm.close = AsyncMock()
        mock_bm_cls.return_value = mock_bm

        resp = await client.get("/scraper/health")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["playwright"] is True


async def test_health_playwright_unavailable(client: AsyncClient) -> None:
    """Health returns 200 with playwright=false when Playwright is not available."""
    with patch("scraper_service.router.BrowserManager") as mock_bm_cls:
        mock_bm_cls.side_effect = Exception("Playwright not installed")

        resp = await client.get("/scraper/health")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["playwright"] is False


# ---------------------------------------------------------------------------
# POST /scraper/serp
# ---------------------------------------------------------------------------


async def test_serp_returns_response(client: AsyncClient) -> None:
    """POST /scraper/serp returns 200 with SerpResponse-shaped dict."""
    mock_response = {
        "keyword": "test",
        "keyword_norm": "test",
        "market": "US",
        "language": "en",
        "features": {"has_organic_results": True},
        "organic_results": [],
        "paa_items": [],
        "ads_top": [],
        "ads_bottom": [],
        "featured_snippet": None,
        "shopping_results": [],
        "top_stories": [],
        "knowledge_panel": None,
        "videos": [],
        "images": [],
        "serp_urls": [],
        "snapshot": {"html_compressed": None, "html_sha256": "", "html_bytes_len": None, "html_encoding": "", "screenshot_png": None, "screenshot_width": None, "screenshot_height": None},
        "difficulty_score": {"total_score": 50.0, "label": "Medium", "component_breakdown": {}},
        "search_id": "",
        "search_status": "",
    }

    with patch("scraper_service.router.run_serp", new_callable=AsyncMock) as mock_run:
        from scraper_service.serp.models import SerpResponse
        resp_obj = SerpResponse(**mock_response)
        mock_run.return_value = resp_obj

        resp = await client.post(
            "/scraper/serp",
            json={"keyword": "test", "market": "US", "language": "en"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["keyword"] == "test"
    assert "snapshot_id" in data


async def test_serp_stores_snapshot(client: AsyncClient) -> None:
    """POST /serp stores snapshot in memory and returns snapshot_id."""
    mock_response = {
        "keyword": "seo tools",
        "keyword_norm": "seo tools",
        "market": "US",
        "language": "en",
        "features": {},
        "organic_results": [],
        "paa_items": [],
        "ads_top": [],
        "ads_bottom": [],
        "featured_snippet": None,
        "shopping_results": [],
        "top_stories": [],
        "knowledge_panel": None,
        "videos": [],
        "images": [],
        "serp_urls": [],
        "snapshot": {},
        "difficulty_score": {"total_score": 25.0, "label": "Easy", "component_breakdown": {}},
        "search_id": "",
        "search_status": "",
    }

    with patch("scraper_service.router.run_serp", new_callable=AsyncMock) as mock_run:
        from scraper_service.serp.models import SerpResponse
        resp_obj = SerpResponse(**mock_response)
        mock_run.return_value = resp_obj

        resp = await client.post(
            "/scraper/serp",
            json={"keyword": "seo tools", "market": "US", "language": "en"},
        )

    data = resp.json()
    snapshot_id = data["snapshot_id"]

    # Verify it can be retrieved
    get_resp = await client.get(f"/scraper/serp/{snapshot_id}")
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert get_data["keyword"] == "seo tools"


# ---------------------------------------------------------------------------
# GET /scraper/serp/{snapshot_id}
# ---------------------------------------------------------------------------


async def test_serp_snapshot_not_found(client: AsyncClient) -> None:
    """GET /scraper/serp/{snapshot_id} with nonexistent ID returns 404."""
    resp = await client.get("/scraper/serp/nonexistent-id")

    assert resp.status_code == 404
    data = resp.json()
    assert data["error_code"] == "SNAPSHOT_NOT_FOUND"
    assert "not found" in data["detail"]
    assert "stored in memory" in data["detail"]
