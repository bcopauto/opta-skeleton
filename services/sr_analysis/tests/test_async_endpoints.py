"""Tests for async analysis endpoints (Phase 13 — ANLYS-04)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from analysis_service.models import (
    AnalysisJobState,
    AnalysisJobStatus,
    AnalysisResult,
    H1MetaOptimizationResult,
    HtmlElementGapResult,
    InformationGapResult,
    SchemaMarkupResult,
    SerpFeatureOpportunityResult,
)

MINIMAL_REQUEST = {
    "target": {},
    "competitors": [],
    "keyword": "test keyword",
    "market": "US",
    "page_type": "other",
}


def test_analyze_async_returns_202(async_client: TestClient) -> None:
    resp = async_client.post("/analyze/async", json=MINIMAL_REQUEST)
    assert resp.status_code == 202
    data = resp.json()
    assert "job_id" in data
    import uuid
    uuid.UUID(data["job_id"])


def test_get_unknown_job_404(async_client: TestClient) -> None:
    resp = async_client.get("/analyze/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    assert resp.status_code == 404
    data = resp.json()
    assert data["error_code"] == "JOB_NOT_FOUND"


def test_get_job_returns_partial_result(async_client: TestClient) -> None:
    resp = async_client.post("/analyze/async", json=MINIMAL_REQUEST)
    assert resp.status_code == 202
    job_id = resp.json()["job_id"]

    poll = async_client.get(f"/analyze/{job_id}")
    assert poll.status_code == 200
    data = poll.json()
    assert "status" in data
    assert "completed_modules" in data
    assert "result" in data


def test_concurrent_job_limit_429(async_client: TestClient) -> None:
    from analysis_service.app import app
    from analysis_service.router import _jobs, get_settings
    from analysis_service.settings import Settings

    _jobs["existing"] = AnalysisJobState(
        job_id="existing",
        status=AnalysisJobStatus.RUNNING,
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    original_override = app.dependency_overrides.get(get_settings)
    settings_1_job = Settings.model_construct(
        gemini_api_key="k", gemini_model="m", port=6969,
        max_concurrent_gemini_calls=3, token_ceiling_per_module=100000,
        log_level="INFO", bc_best_practices_path="", max_concurrent_jobs=1,
        job_ttl_minutes=60,
    )
    app.dependency_overrides[get_settings] = lambda: settings_1_job
    try:
        resp = async_client.post("/analyze/async", json=MINIMAL_REQUEST)
        assert resp.status_code == 429
        data = resp.json()
        assert data["error_code"] == "TOO_MANY_JOBS"
    finally:
        if original_override is not None:
            app.dependency_overrides[get_settings] = original_override


def test_overall_score_recomputed_on_poll(async_client: TestClient) -> None:
    from analysis_service.router import _jobs

    result = AnalysisResult(
        html_element_gap=HtmlElementGapResult(score=80.0),
        h1_meta_optimization=H1MetaOptimizationResult(score=70.0),
        serp_feature_opportunity=SerpFeatureOpportunityResult(score=60.0),
        schema_markup=SchemaMarkupResult(score=50.0),
        information_gap=InformationGapResult(score=90.0),
    )
    job_id = "score-test"
    _jobs[job_id] = AnalysisJobState(
        job_id=job_id,
        status=AnalysisJobStatus.COMPLETED,
        result=result,
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    resp = async_client.get(f"/analyze/{job_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["result"]["overall_score"] is not None
    assert len(data["result"]["priority_modules"]) > 0


def test_overall_score_null_when_incomplete(async_client: TestClient) -> None:
    from analysis_service.router import _jobs

    result = AnalysisResult(
        html_element_gap=HtmlElementGapResult(score=80.0),
        h1_meta_optimization=H1MetaOptimizationResult(score=70.0),
        serp_feature_opportunity=SerpFeatureOpportunityResult(score=60.0),
        schema_markup=SchemaMarkupResult(score=50.0),
    )
    job_id = "incomplete-test"
    _jobs[job_id] = AnalysisJobState(
        job_id=job_id,
        status=AnalysisJobStatus.RUNNING,
        result=result,
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    resp = async_client.get(f"/analyze/{job_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["result"]["overall_score"] is None


def test_failed_job_preserves_partial(async_client: TestClient) -> None:
    from analysis_service.router import _jobs

    result = AnalysisResult(
        html_element_gap=HtmlElementGapResult(score=80.0),
    )
    job_id = "failed-test"
    _jobs[job_id] = AnalysisJobState(
        job_id=job_id,
        status=AnalysisJobStatus.FAILED,
        error="test error",
        result=result,
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    resp = async_client.get(f"/analyze/{job_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "failed"
    assert data["error"] == "test error"
    assert data["result"]["html_element_gap"] is not None
    assert data["result"]["html_element_gap"]["score"] == 80.0


def test_completed_modules_tracked(async_client_with_gemini: TestClient) -> None:
    resp = async_client_with_gemini.post("/analyze/async", json=MINIMAL_REQUEST)
    assert resp.status_code == 202
    job_id = resp.json()["job_id"]

    poll = async_client_with_gemini.get(f"/analyze/{job_id}")
    assert poll.status_code == 200
    data = poll.json()
    assert isinstance(data["completed_modules"], list)


def test_ttl_cleanup() -> None:
    from analysis_service.router import _cleanup_expired_jobs, _jobs

    _jobs.clear()
    old_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    _jobs["old-job"] = AnalysisJobState(
        job_id="old-job",
        status=AnalysisJobStatus.COMPLETED,
        completed_at=old_time,
        created_at=old_time,
    )
    _jobs["fresh-job"] = AnalysisJobState(
        job_id="fresh-job",
        status=AnalysisJobStatus.COMPLETED,
        completed_at=datetime.now(timezone.utc).isoformat(),
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    call_count = 0

    async def patched_sleep(seconds: float) -> None:
        nonlocal call_count
        call_count += 1
        if call_count > 1:
            raise asyncio.CancelledError

    async def run() -> None:
        with patch("analysis_service.router.asyncio.sleep", side_effect=patched_sleep):
            try:
                await _cleanup_expired_jobs(ttl_minutes=60)
            except asyncio.CancelledError:
                pass

    asyncio.run(run())

    assert "old-job" not in _jobs
    assert "fresh-job" in _jobs
    _jobs.clear()


def test_sync_analyze_still_works(client_with_gemini: TestClient) -> None:
    resp = client_with_gemini.post("/analyze", json=MINIMAL_REQUEST)
    assert resp.status_code == 200
    data = resp.json()
    assert "html_element_gap" in data
    assert "overall_score" in data
