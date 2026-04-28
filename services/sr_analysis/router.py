from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from analysis_service.bc_config import BcBestPracticesConfig
from analysis_service.gemini_client import GeminiClient, get_gemini_client
from analysis_service.logging import bind_correlation_id, get_logger
from analysis_service.models import (
    AnalysisJobState,
    AnalysisJobStatus,
    AnalysisRequest,
    AnalysisResult,
    ContentBestPracticesResult,
    InformationGapResult,
    LlmOptimizationResult,
    SchemaJsonLdResult,
)
from analysis_service.modules.content_best_practices_l1 import score_content_best_practices_l1
from analysis_service.modules.content_best_practices_l2 import score_content_best_practices_l2
from analysis_service.modules.h1_meta_optimization import score_h1_meta_optimization
from analysis_service.modules.html_element_gap import score_html_element_gap
from analysis_service.modules.information_gap import score_information_gap
from analysis_service.modules.llm_optimization import score_llm_optimization
from analysis_service.modules.overall_score import score_overall
from analysis_service.modules.schema_json_ld import score_schema_json_ld
from analysis_service.modules.schema_markup import score_schema_markup
from analysis_service.modules.serp_feature_opportunity import score_serp_feature_opportunity
from analysis_service.settings import Settings

router = APIRouter()
logger = get_logger()

_jobs: dict[str, AnalysisJobState] = {}
_gemini_semaphore: asyncio.Semaphore | None = None


def get_bc_config(request: Request) -> BcBestPracticesConfig:
    return request.app.state.bc_best_practices


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


async def _safe_async_call(
    coro: Any,
    *,
    timeout: float = 30.0,
    module_name: str = "",
    cid: str = "",
) -> Any:
    try:
        async with _gemini_semaphore:  # type: ignore[union-attr]
            return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        logger.error("module_timeout", module=module_name, timeout=timeout, correlation_id=cid)
        return None
    except Exception as exc:
        logger.error("module_failed", module=module_name, error=str(exc), correlation_id=cid)
        return None


async def _run_analysis_pipeline(
    request: AnalysisRequest,
    gemini_client: GeminiClient,
    bc_config: BcBestPracticesConfig,
    cid: str,
    job_state: AnalysisJobState | None = None,
) -> AnalysisResult:
    """Shared analysis pipeline used by both sync and async endpoints.

    When job_state is provided (async path), mutates job_state.result and
    job_state.completed_modules after each module completes.
    """
    result = AnalysisResult()
    if job_state is not None:
        job_state.result = result

    # === WAVE 1: Deterministic modules (no external calls) ===
    try:
        html_element_gap = score_html_element_gap(request.target, request.competitors)
        if html_element_gap:
            result.html_element_gap = html_element_gap
            if job_state is not None:
                job_state.completed_modules.append("html_element_gap")
    except Exception as exc:
        logger.error("module_failed", module="html_element_gap", error=str(exc), correlation_id=cid)

    try:
        serp_feature_opportunity = score_serp_feature_opportunity(request.target, request.serp_features)
        if serp_feature_opportunity:
            result.serp_feature_opportunity = serp_feature_opportunity
            if job_state is not None:
                job_state.completed_modules.append("serp_feature_opportunity")
    except Exception as exc:
        logger.error("module_failed", module="serp_feature_opportunity", error=str(exc), correlation_id=cid)

    try:
        h1_meta_optimization = score_h1_meta_optimization(request.target, request.keyword)
        if h1_meta_optimization:
            result.h1_meta_optimization = h1_meta_optimization
            if job_state is not None:
                job_state.completed_modules.append("h1_meta_optimization")
    except Exception as exc:
        logger.error("module_failed", module="h1_meta_optimization", error=str(exc), correlation_id=cid)

    try:
        schema_markup = score_schema_markup(request.target, request.competitors, request.page_type)
        if schema_markup:
            result.schema_markup = schema_markup
            if job_state is not None:
                job_state.completed_modules.append("schema_markup")
    except Exception as exc:
        logger.error("module_failed", module="schema_markup", error=str(exc), correlation_id=cid)

    best_practices_l2_result: ContentBestPracticesResult | None = None
    try:
        best_practices_l2_result = score_content_best_practices_l2(
            request.target, request.page_type, bc_config,
        )
        if best_practices_l2_result is not None:
            if job_state is not None:
                job_state.completed_modules.append("content_best_practices_l2")
    except Exception as exc:
        logger.error("module_failed", module="content_best_practices_l2", error=str(exc), correlation_id=cid)

    deterministic_results = [
        result.html_element_gap, result.serp_feature_opportunity,
        result.h1_meta_optimization, result.schema_markup, best_practices_l2_result,
    ]
    if all(r is None for r in deterministic_results):
        raise HTTPException(
            status_code=500,
            detail="All deterministic scoring modules failed. Check logs for details.",
        )

    missing_types = result.schema_markup.missing_types if result.schema_markup else []

    # === WAVE 2: Gemini modules concurrent (30s per-module timeout) ===
    info_gap_result, bp_l1_result, llm_opt_result, schema_gen_result = await asyncio.gather(
        _safe_async_call(
            score_information_gap(
                request.target, request.competitors, request.keyword,
                request.page_type, gemini_client,
            ),
            timeout=60.0, module_name="information_gap", cid=cid,
        ),
        _safe_async_call(
            score_content_best_practices_l1(
                request.target, request.keyword, request.page_type,
                request.market, gemini_client,
            ),
            timeout=30.0, module_name="content_best_practices_l1", cid=cid,
        ),
        _safe_async_call(
            score_llm_optimization(
                request.target, request.keyword, request.page_type,
                gemini_client,
            ),
            timeout=30.0, module_name="llm_optimization", cid=cid,
        ),
        _safe_async_call(
            score_schema_json_ld(
                request.target, missing_types, request.keyword,
                request.page_type, gemini_client,
            ),
            timeout=30.0, module_name="schema_json_ld", cid=cid,
        ),
    )

    if isinstance(info_gap_result, InformationGapResult):
        result.information_gap = info_gap_result
        if job_state is not None:
            job_state.completed_modules.append("information_gap")

    # Merge L1 + L2 into single ContentBestPracticesResult
    content_best_practices: ContentBestPracticesResult | None = None
    if best_practices_l2_result is not None or bp_l1_result is not None:
        if best_practices_l2_result is not None:
            content_best_practices = best_practices_l2_result
        else:
            content_best_practices = ContentBestPracticesResult()

        if bp_l1_result is not None and isinstance(bp_l1_result, ContentBestPracticesResult):
            content_best_practices = ContentBestPracticesResult(
                l1_score=bp_l1_result.l1_score,
                intent_summary=bp_l1_result.intent_summary,
                best_practices=bp_l1_result.best_practices,
                structural_suggestions=bp_l1_result.structural_suggestions,
                l2_score=content_best_practices.l2_score,
                rules_applied=content_best_practices.rules_applied,
                passed=content_best_practices.passed,
                failed=content_best_practices.failed,
                not_verifiable=content_best_practices.not_verifiable,
            )
    result.content_best_practices = content_best_practices
    if content_best_practices is not None and job_state is not None:
        job_state.completed_modules.append("content_best_practices")

    if isinstance(schema_gen_result, SchemaJsonLdResult):
        result.schema_json_ld = schema_gen_result
        if job_state is not None:
            job_state.completed_modules.append("schema_json_ld")

    if isinstance(llm_opt_result, LlmOptimizationResult):
        result.llm_optimization = llm_opt_result
        if job_state is not None:
            job_state.completed_modules.append("llm_optimization")

    # Overall Score + Priority List
    overall_score_value, priority_modules = score_overall(result)
    result.overall_score = overall_score_value
    result.priority_modules = priority_modules

    return result


@router.post("/analyze")
async def analyze(
    request: AnalysisRequest,
    gemini_client: GeminiClient = Depends(get_gemini_client),
    bc_config: BcBestPracticesConfig = Depends(get_bc_config),
) -> AnalysisResult:
    cid = bind_correlation_id()
    logger.info(
        "analyze_started",
        correlation_id=cid,
        keyword=request.keyword,
        market=request.market,
        page_type=request.page_type,
        device=request.device,
        competitor_count=len(request.competitors),
        has_serp_features=request.serp_features is not None,
    )
    result = await _run_analysis_pipeline(request, gemini_client, bc_config, cid)
    logger.info(
        "analyze_completed",
        correlation_id=cid,
        overall_score=result.overall_score,
    )
    return result


async def _run_analysis_job(
    job_id: str,
    request: AnalysisRequest,
    gemini_client: GeminiClient,
    bc_config: BcBestPracticesConfig,
) -> None:
    job = _jobs[job_id]
    job.status = AnalysisJobStatus.RUNNING
    cid = bind_correlation_id(job_id)
    logger.info("async_analyze_started", correlation_id=cid, job_id=job_id)
    try:
        result = await _run_analysis_pipeline(
            request, gemini_client, bc_config, cid, job_state=job,
        )
        job.result = result
        job.status = AnalysisJobStatus.COMPLETED
        job.completed_at = datetime.now(timezone.utc).isoformat()
        logger.info("async_analyze_completed", correlation_id=cid, job_id=job_id)
    except Exception as exc:
        job.status = AnalysisJobStatus.FAILED
        job.error = str(exc)
        job.completed_at = datetime.now(timezone.utc).isoformat()
        logger.error("async_analyze_failed", correlation_id=cid, job_id=job_id, error=str(exc))


@router.post("/analyze/async", status_code=202, response_model=None)
async def analyze_async(
    request: AnalysisRequest,
    background_tasks: BackgroundTasks,
    gemini_client: GeminiClient = Depends(get_gemini_client),
    bc_config: BcBestPracticesConfig = Depends(get_bc_config),
    settings: Settings = Depends(get_settings),
) -> dict[str, str] | JSONResponse:
    running = sum(1 for j in _jobs.values() if j.status == AnalysisJobStatus.RUNNING)
    if running >= settings.max_concurrent_jobs:
        return JSONResponse(
            status_code=429,
            content={
                "detail": f"Maximum concurrent jobs ({settings.max_concurrent_jobs}) reached. Try again later.",
                "error_code": "TOO_MANY_JOBS",
            },
        )
    job_id = str(uuid.uuid4())
    _jobs[job_id] = AnalysisJobState(
        job_id=job_id,
        status=AnalysisJobStatus.PENDING,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    background_tasks.add_task(_run_analysis_job, job_id, request, gemini_client, bc_config)
    return {"job_id": job_id}


@router.get("/analyze/{job_id}", response_model=None)
async def get_analysis_job(job_id: str) -> AnalysisJobState | JSONResponse:
    job = _jobs.get(job_id)
    if job is None:
        return JSONResponse(
            status_code=404,
            content={
                "detail": f"Job {job_id} not found. Jobs are stored in memory and lost on process restart.",
                "error_code": "JOB_NOT_FOUND",
            },
        )
    if job.result is not None:
        overall_score, priority_modules = score_overall(job.result)
        job.result.overall_score = overall_score
        job.result.priority_modules = priority_modules
    return job


async def _cleanup_expired_jobs(ttl_minutes: int = 60) -> None:
    stall_minutes = ttl_minutes * 2
    while True:
        await asyncio.sleep(300)
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=ttl_minutes)
        stall_cutoff = now - timedelta(minutes=stall_minutes)
        expired = [
            jid for jid, job in _jobs.items()
            if (
                job.status in (AnalysisJobStatus.COMPLETED, AnalysisJobStatus.FAILED)
                and job.completed_at is not None
                and datetime.fromisoformat(job.completed_at) < cutoff
            ) or (
                job.status in (AnalysisJobStatus.PENDING, AnalysisJobStatus.RUNNING)
                and datetime.fromisoformat(job.created_at) < stall_cutoff
            )
        ]
        for jid in expired:
            del _jobs[jid]
        if expired:
            logger.info("jobs_cleaned", evicted=len(expired))


@router.get("/health")
async def health(
    gemini_client: GeminiClient = Depends(get_gemini_client),
) -> dict[str, str]:
    try:
        await gemini_client.count_tokens("health")
        return {"status": "ok", "gemini": "reachable"}
    except Exception:
        return {"status": "degraded", "gemini": "unreachable"}
