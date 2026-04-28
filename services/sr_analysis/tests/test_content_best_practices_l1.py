from __future__ import annotations

import pytest

from analysis_service.gemini_client import FakeGeminiClient
from analysis_service.models import (
    ContentBestPracticesL1GeminiResponse,
    ExtractionResult,
    GeminiBestPractice,
    GeminiStructuralSuggestion,
    PageType,
)
from analysis_service.modules.content_best_practices_l1 import (
    _build_variable_data,
    _compute_result,
    score_content_best_practices_l1,
)


def _bp(name: str, passed: bool) -> GeminiBestPractice:
    return GeminiBestPractice(name=name, description="desc", pass_=passed)


# --- _compute_result tests ---


def test_l1_score_with_practices() -> None:
    resp = ContentBestPracticesL1GeminiResponse(
        intent_summary="intent",
        best_practices=[_bp("a", True), _bp("b", True), _bp("c", False)],
    )
    result = _compute_result(resp)
    assert result.l1_score == 67.0


def test_l1_score_zero_practices() -> None:
    resp = ContentBestPracticesL1GeminiResponse(intent_summary="intent", best_practices=[])
    result = _compute_result(resp)
    assert result.l1_score == 100.0


def test_l1_score_all_fail() -> None:
    resp = ContentBestPracticesL1GeminiResponse(
        intent_summary="intent",
        best_practices=[_bp("a", False), _bp("b", False)],
    )
    result = _compute_result(resp)
    assert result.l1_score == 0.0


def test_l1_score_all_pass() -> None:
    resp = ContentBestPracticesL1GeminiResponse(
        intent_summary="intent",
        best_practices=[_bp("a", True), _bp("b", True)],
    )
    result = _compute_result(resp)
    assert result.l1_score == 100.0


def test_intent_summary_populated() -> None:
    resp = ContentBestPracticesL1GeminiResponse(intent_summary="User wants promo code")
    result = _compute_result(resp)
    assert result.intent_summary == "User wants promo code"


def test_pass_field_mapped_to_passed() -> None:
    resp = ContentBestPracticesL1GeminiResponse(
        intent_summary="i",
        best_practices=[_bp("a", True), _bp("b", False)],
    )
    result = _compute_result(resp)
    assert result.best_practices[0].passed is True
    assert result.best_practices[1].passed is False


def test_structural_suggestions_mapped() -> None:
    resp = ContentBestPracticesL1GeminiResponse(
        intent_summary="i",
        structural_suggestions=[GeminiStructuralSuggestion(heading="H", rationale="R")],
    )
    result = _compute_result(resp)
    assert len(result.structural_suggestions) == 1
    assert result.structural_suggestions[0].heading == "H"


# --- _build_variable_data tests ---


def test_variable_data_has_keyword_and_market() -> None:
    data = _build_variable_data(ExtractionResult(), "casino", PageType.COMPARATOR, "GB")
    assert "KEYWORD: casino" in data
    assert "MARKET: GB" in data
    assert "PAGE TYPE: comparator" in data


def test_variable_data_includes_headings() -> None:
    er = ExtractionResult()
    er.headings.h1_texts = ["Top Casino"]
    data = _build_variable_data(er, "casino", PageType.COMPARATOR, "GB")
    assert "Top Casino" in data


# --- Full async function ---


@pytest.mark.asyncio
async def test_score_l1_full() -> None:
    fixture = ContentBestPracticesL1GeminiResponse(
        intent_summary="User wants promo",
        best_practices=[_bp("code_visible", True), _bp("steps", False)],
        structural_suggestions=[GeminiStructuralSuggestion(heading="H", rationale="R")],
    )
    client = FakeGeminiClient(responses={ContentBestPracticesL1GeminiResponse: fixture})
    result = await score_content_best_practices_l1(
        ExtractionResult(), "promo code", PageType.CODE_PAGE, "GB", client,
    )
    assert result.l1_score == 50.0
    assert result.intent_summary == "User wants promo"
    assert len(result.best_practices) == 2
