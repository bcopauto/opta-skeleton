from __future__ import annotations

import pytest

from analysis_service.gemini_client import FakeGeminiClient
from analysis_service.models import (
    ExtractionResult,
    GeminiBloat,
    GeminiTopic,
    InformationGapGeminiResponse,
    PageType,
)
from analysis_service.modules.information_gap import (
    _build_variable_data,
    _compute_result,
    score_information_gap,
)


def _make_topic(
    topic: str = "T",
    competitors_covering: int = 2,
    is_important: bool = True,
    covered_by_target: bool = False,
) -> GeminiTopic:
    return GeminiTopic(
        topic=topic,
        competitor_coverage=f"{competitors_covering}/3",
        competitors_covering=competitors_covering,
        is_important=is_important,
        covered_by_target=covered_by_target,
    )


# --- _compute_result tests ---


def test_score_1_of_4_important_covered() -> None:
    resp = InformationGapGeminiResponse(
        topics=[
            _make_topic("A", 2, True, True),
            _make_topic("B", 2, True, False),
            _make_topic("C", 3, True, False),
            _make_topic("D", 2, True, False),
        ],
    )
    result = _compute_result(resp, 3)
    assert result.score == 25.0


def test_score_0_important_topics() -> None:
    resp = InformationGapGeminiResponse(topics=[_make_topic("A", 1, False, False)])
    result = _compute_result(resp, 3)
    assert result.score == 100.0


def test_score_all_covered() -> None:
    resp = InformationGapGeminiResponse(
        topics=[_make_topic("A", 2, True, True), _make_topic("B", 3, True, True)],
    )
    result = _compute_result(resp, 3)
    assert result.score == 100.0


def test_score_0_covered() -> None:
    resp = InformationGapGeminiResponse(
        topics=[_make_topic("A", 2, True, False), _make_topic("B", 2, True, False), _make_topic("C", 2, True, False)],
    )
    result = _compute_result(resp, 3)
    assert result.score == 0.0


def test_single_competitor_threshold_1() -> None:
    resp = InformationGapGeminiResponse(
        topics=[_make_topic("A", 1, True, True), _make_topic("B", 1, True, False)],
    )
    result = _compute_result(resp, 1)
    assert result.score == 50.0
    assert result.total_important_topics == 2


def test_3_competitors_threshold_2() -> None:
    resp = InformationGapGeminiResponse(
        topics=[
            _make_topic("A", 1, True, False),
            _make_topic("B", 2, True, True),
        ],
    )
    result = _compute_result(resp, 3)
    assert result.total_important_topics == 1
    assert result.score == 100.0


def test_topics_to_add_sorted_by_competitors_desc() -> None:
    resp = InformationGapGeminiResponse(
        topics=[
            _make_topic("A", 2, True, False),
            _make_topic("B", 3, True, False),
        ],
    )
    result = _compute_result(resp, 3)
    assert result.topics_to_add[0].topic == "B"
    assert result.topics_to_add[1].topic == "A"


def test_topics_to_trim_from_bloat() -> None:
    resp = InformationGapGeminiResponse(
        topics=[],
        bloat=[GeminiBloat(section="Promos", reason="temporal", recommendation="remove")],
    )
    result = _compute_result(resp, 3)
    assert len(result.topics_to_trim) == 1
    assert result.topics_to_trim[0].section == "Promos"


def test_breakdown_string_format() -> None:
    resp = InformationGapGeminiResponse(
        topics=[_make_topic("A", 2, True, True), _make_topic("B", 2, True, False)],
    )
    result = _compute_result(resp, 3)
    assert result.breakdown == "1 of 2 important topics covered"


# --- _build_variable_data tests ---


def test_variable_data_contains_keyword() -> None:
    er = ExtractionResult()
    data = _build_variable_data(er, [], "best casino", PageType.COMPARATOR)
    assert "KEYWORD: best casino" in data
    assert "PAGE TYPE: comparator" in data


def test_variable_data_truncates_long_content() -> None:
    er = ExtractionResult()
    er.body_text.text = " ".join(["word"] * 5000)
    data = _build_variable_data(er, [], "kw", PageType.OTHER)
    assert "[truncated]" in data


def test_variable_data_includes_competitors() -> None:
    target = ExtractionResult()
    comp = ExtractionResult()
    comp.headings.h1_texts = ["Comp Title"]
    data = _build_variable_data(target, [comp], "kw", PageType.OTHER)
    assert "COMPETITOR 1:" in data
    assert "Comp Title" in data


# --- Full async function ---


@pytest.mark.asyncio
async def test_score_information_gap_full() -> None:
    fixture = InformationGapGeminiResponse(
        topics=[
            _make_topic("Payment", 2, True, True),
            _make_topic("Support", 3, True, False),
        ],
        bloat=[GeminiBloat(section="Promos", reason="temporal", recommendation="remove")],
    )
    client = FakeGeminiClient(responses={InformationGapGeminiResponse: fixture})
    target = ExtractionResult()
    result = await score_information_gap(target, [ExtractionResult()], "casino", PageType.COMPARATOR, client)
    assert result.score == 50.0
    assert result.total_important_topics == 2
    assert len(result.topics_to_add) == 1
    assert len(result.topics_to_trim) == 1
