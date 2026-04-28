"""Pydantic v2 models for PageSpeed Insights API."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class PageSpeedRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    urls: list[str] = Field(..., min_length=1)
    strategy: Literal["mobile", "desktop"] = "mobile"


class PageSpeedResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    strategy: str = "mobile"
    performance_score: float | None = None
    lcp_ms: float | None = None
    cls: float | None = None
    inp_ms: float | None = None
    fcp_ms: float | None = None
    ttfb_ms: float | None = None
    speed_index: float | None = None
    total_blocking_time: float | None = None
    error: str | None = None
    raw_json: dict[str, Any] | None = None
