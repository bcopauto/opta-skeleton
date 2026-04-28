from __future__ import annotations

import pytest

from analysis_service.gemini_client import FakeGeminiClient
from analysis_service.models import (
    ExtractionResult,
    GeminiLlmDimension,
    LlmOptimizationGeminiResponse,
    PageType,
)
from analysis_service.modules.llm_optimization import (
    _compute_deterministic_signals,
    _compute_result,
    score_llm_optimization,
)


# --- _compute_deterministic_signals tests ---


def test_signals_returns_5_keys() -> None:
    signals = _compute_deterministic_signals(ExtractionResult())
    assert set(signals.keys()) == {"faq_format", "structured_data", "table_list_summaries", "heading_specificity", "freshness_signals"}


def test_empty_extraction_all_zero() -> None:
    signals = _compute_deterministic_signals(ExtractionResult())
    assert all(v == 0.0 for v in signals.values())


def test_faq_format_has_faq_3_items() -> None:
    er = ExtractionResult()
    er.faq.has_faq = True
    er.faq.total_faq_items = 3
    signals = _compute_deterministic_signals(er)
    assert signals["faq_format"] == 100.0


def test_faq_format_has_faq_1_item() -> None:
    er = ExtractionResult()
    er.faq.has_faq = True
    er.faq.total_faq_items = 1
    signals = _compute_deterministic_signals(er)
    assert 30.0 <= signals["faq_format"] <= 40.0


def test_faq_format_no_faq() -> None:
    signals = _compute_deterministic_signals(ExtractionResult())
    assert signals["faq_format"] == 0.0


def test_structured_data_zero() -> None:
    signals = _compute_deterministic_signals(ExtractionResult())
    assert signals["structured_data"] == 0.0


def test_structured_data_1_block() -> None:
    er = ExtractionResult()
    er.jsonld.jsonld_count = 1
    signals = _compute_deterministic_signals(er)
    assert 30.0 <= signals["structured_data"] <= 35.0


def test_structured_data_3_plus() -> None:
    er = ExtractionResult()
    er.jsonld.jsonld_count = 5
    signals = _compute_deterministic_signals(er)
    assert signals["structured_data"] == 100.0


def test_table_list_summaries_zero() -> None:
    signals = _compute_deterministic_signals(ExtractionResult())
    assert signals["table_list_summaries"] == 0.0


def test_table_list_summaries_1() -> None:
    er = ExtractionResult()
    er.tables.table_count = 1
    signals = _compute_deterministic_signals(er)
    assert signals["table_list_summaries"] == 25.0


def test_table_list_summaries_4_plus() -> None:
    er = ExtractionResult()
    er.tables.table_count = 2
    er.lists.ul_count = 1
    er.lists.ol_count = 1
    signals = _compute_deterministic_signals(er)
    assert signals["table_list_summaries"] == 100.0


def test_heading_specificity_with_questions() -> None:
    er = ExtractionResult()
    er.headings.h2_texts = ["What is SEO?", "Benefits", "How does it work?", "Tools"]
    signals = _compute_deterministic_signals(er)
    assert signals["heading_specificity"] == 50.0


def test_heading_specificity_long_headings() -> None:
    er = ExtractionResult()
    er.headings.h2_texts = ["This is a very long heading indeed", "Short"]
    signals = _compute_deterministic_signals(er)
    assert signals["heading_specificity"] == 50.0


def test_freshness_both_dates() -> None:
    er = ExtractionResult()
    er.freshness.published_date = "2024-01-01"
    er.freshness.modified_date = "2024-06-01"
    signals = _compute_deterministic_signals(er)
    assert signals["freshness_signals"] == 100.0


def test_freshness_one_date() -> None:
    er = ExtractionResult()
    er.freshness.published_date = "2024-01-01"
    signals = _compute_deterministic_signals(er)
    assert signals["freshness_signals"] == 50.0


def test_freshness_no_dates() -> None:
    signals = _compute_deterministic_signals(ExtractionResult())
    assert signals["freshness_signals"] == 0.0


# --- _compute_result tests ---


def _gemini_resp(scores: list[tuple[str, float]]) -> LlmOptimizationGeminiResponse:
    return LlmOptimizationGeminiResponse(
        dimensions=[
            GeminiLlmDimension(name=n, score=s, recommendation=f"rec_{n}" if s < 80 else None)
            for n, s in scores
        ],
    )


def test_result_8_dimensions() -> None:
    det = {"faq_format": 100.0, "structured_data": 100.0, "table_list_summaries": 100.0, "heading_specificity": 100.0, "freshness_signals": 100.0}
    gem = _gemini_resp([("direct_answers", 100.0), ("entity_clarity", 100.0), ("quotable_passages", 100.0)])
    result = _compute_result(det, gem)
    assert len(result.dimensions) == 8


def test_5_deterministic_3_gemini() -> None:
    det = {"faq_format": 50.0, "structured_data": 50.0, "table_list_summaries": 50.0, "heading_specificity": 50.0, "freshness_signals": 50.0}
    gem = _gemini_resp([("direct_answers", 70.0), ("entity_clarity", 80.0), ("quotable_passages", 60.0)])
    result = _compute_result(det, gem)
    det_dims = [d for d in result.dimensions if d.source == "deterministic"]
    gem_dims = [d for d in result.dimensions if d.source == "gemini"]
    assert len(det_dims) == 5
    assert len(gem_dims) == 3


def test_blended_score_formula() -> None:
    det = {"faq_format": 100.0, "structured_data": 100.0, "table_list_summaries": 100.0, "heading_specificity": 100.0, "freshness_signals": 100.0}
    gem = _gemini_resp([("direct_answers", 100.0), ("entity_clarity", 100.0), ("quotable_passages", 100.0)])
    result = _compute_result(det, gem)
    assert result.score == 100.0


def test_blended_score_all_zero() -> None:
    det = {"faq_format": 0.0, "structured_data": 0.0, "table_list_summaries": 0.0, "heading_specificity": 0.0, "freshness_signals": 0.0}
    gem = _gemini_resp([("direct_answers", 0.0), ("entity_clarity", 0.0), ("quotable_passages", 0.0)])
    result = _compute_result(det, gem)
    assert result.score == 0.0


def test_deterministic_signals_dict_populated() -> None:
    det = {"faq_format": 50.0, "structured_data": 60.0, "table_list_summaries": 70.0, "heading_specificity": 80.0, "freshness_signals": 90.0}
    gem = _gemini_resp([("direct_answers", 70.0), ("entity_clarity", 80.0), ("quotable_passages", 60.0)])
    result = _compute_result(det, gem)
    assert len(result.deterministic_signals) == 5


def test_recommendations_from_gemini() -> None:
    det = {"faq_format": 0.0, "structured_data": 0.0, "table_list_summaries": 0.0, "heading_specificity": 0.0, "freshness_signals": 0.0}
    gem = _gemini_resp([("direct_answers", 70.0), ("entity_clarity", 80.0), ("quotable_passages", 60.0)])
    result = _compute_result(det, gem)
    assert len(result.recommendations) == 2


# --- Full async function ---


@pytest.mark.asyncio
async def test_score_llm_optimization_full() -> None:
    fixture = _gemini_resp([("direct_answers", 70.0), ("entity_clarity", 80.0), ("quotable_passages", 60.0)])
    client = FakeGeminiClient(responses={LlmOptimizationGeminiResponse: fixture})
    result = await score_llm_optimization(ExtractionResult(), "casino", PageType.COMPARATOR, client)
    assert result.score is not None
    assert len(result.dimensions) == 8
    assert result.deterministic_signals is not None


@pytest.mark.asyncio
async def test_prompt_includes_deterministic_signals() -> None:
    from unittest.mock import AsyncMock

    mock_client = AsyncMock()
    mock_client.generate.return_value = _gemini_resp([("direct_answers", 70.0), ("entity_clarity", 80.0), ("quotable_passages", 60.0)])
    await score_llm_optimization(ExtractionResult(), "casino", PageType.COMPARATOR, mock_client)
    prompt_arg = mock_client.generate.call_args[0][0]
    assert "PRE-COMPUTED DETERMINISTIC SIGNALS:" in prompt_arg
