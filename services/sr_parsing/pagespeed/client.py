"""Async client for Google PageSpeed Insights API v5."""
from __future__ import annotations

from typing import Any

import httpx
import structlog

from scraper_service.pagespeed.models import PageSpeedResult

PSI_API_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"

logger = structlog.get_logger()


def _parse_psi_response(
    url: str, strategy: str, data: dict[str, Any],
) -> PageSpeedResult:
    """Extract metrics from PSI API JSON response."""
    lighthouse = data.get("lighthouseResult") or {}
    categories = lighthouse.get("categories") or {}
    perf = categories.get("performance") or {}
    audits = lighthouse.get("audits") or {}

    def _metric_val(audit_key: str) -> float | None:
        audit = audits.get(audit_key) or {}
        val = audit.get("numericValue")
        if val is not None:
            return round(float(val), 1)
        return None

    score = perf.get("score")
    if score is not None:
        score = round(float(score) * 100, 1)

    return PageSpeedResult(
        url=url,
        strategy=strategy,
        performance_score=score,
        lcp_ms=_metric_val("largest-contentful-paint"),
        cls=_metric_val("cumulative-layout-shift"),
        inp_ms=_metric_val("interaction-to-next-paint"),
        fcp_ms=_metric_val("first-contentful-paint"),
        ttfb_ms=_metric_val("server-response-time"),
        speed_index=_metric_val("speed-index"),
        total_blocking_time=_metric_val("total-blocking-time"),
        raw_json=data,
    )


async def fetch_pagespeed(
    url: str,
    strategy: str = "mobile",
    api_key: str = "",
    timeout: float = 60.0,
) -> PageSpeedResult:
    """Call PSI API for a single URL. Never raises -- returns error in result."""
    params: dict[str, str] = {
        "url": url,
        "strategy": strategy,
        "category": "performance",
    }
    if api_key:
        params["key"] = api_key

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(PSI_API_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
            return _parse_psi_response(url, strategy, data)
    except Exception as exc:
        logger.warning("pagespeed_fetch_failed", url=url, error=str(exc))
        return PageSpeedResult(url=url, strategy=strategy, error=str(exc))
