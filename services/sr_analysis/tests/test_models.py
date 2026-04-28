"""Tests for analysis_service Pydantic models."""
from __future__ import annotations

import pytest
from pydantic import ValidationError


def test_analysis_result_all_none_by_default() -> None:
    """AnalysisResult() produces all module fields as None."""
    from analysis_service.models import AnalysisResult
    result = AnalysisResult()
    assert result.html_element_gap is None
    assert result.h1_meta_optimization is None
    assert result.serp_feature_opportunity is None
    assert result.schema_markup is None
    assert result.information_gap is None
    assert result.content_best_practices is None
    assert result.schema_json_ld is None
    assert result.llm_optimization is None
    assert result.overall_score is None
    assert result.priority_modules == []


def test_analysis_result_rejects_extra_fields() -> None:
    """AnalysisResult with unknown field raises ValidationError (extra='forbid')."""
    from analysis_service.models import AnalysisResult
    with pytest.raises(ValidationError):
        AnalysisResult(unknown_module="value")  # type: ignore[call-arg]


def test_element_breakdown_defaults() -> None:
    """ElementBreakdown defaults: target_present=False, competitor_count=0, competitor_pct=0.0."""
    from analysis_service.models import ElementBreakdown
    eb = ElementBreakdown()
    assert eb.target_present is False
    assert eb.competitor_count == 0
    assert eb.competitor_pct == 0.0


def test_html_element_gap_has_all_11_elements() -> None:
    """HtmlElementGapResult has all 11 ElementBreakdown fields per D-09/D-10."""
    from analysis_service.models import ElementBreakdown, HtmlElementGapResult
    result = HtmlElementGapResult()
    for field in ("tables", "ordered_lists", "unordered_lists", "faq", "images", "videos", "toc",
                  "comparison_charts", "callout_boxes", "step_by_step", "pros_cons"):
        assert hasattr(result, field), f"Missing field: {field}"
        assert isinstance(getattr(result, field), ElementBreakdown)


def test_h1_meta_has_7_check_pairs() -> None:
    """H1MetaOptimizationResult has 7 bool+pts pairs per D-09."""
    from analysis_service.models import H1MetaOptimizationResult
    result = H1MetaOptimizationResult()
    pairs = [
        ("keyword_in_title", "keyword_in_title_pts"),
        ("keyword_in_h1", "keyword_in_h1_pts"),
        ("keyword_in_meta_description", "keyword_in_meta_description_pts"),
        ("title_length_ok", "title_length_pts"),
        ("meta_length_ok", "meta_length_pts"),
        ("h1_differs_from_title", "h1_differs_from_title_pts"),
        ("keyword_in_first_100_words", "keyword_in_first_100_words_pts"),
    ]
    for bool_field, pts_field in pairs:
        assert hasattr(result, bool_field), f"Missing bool field: {bool_field}"
        assert hasattr(result, pts_field), f"Missing pts field: {pts_field}"
        assert getattr(result, bool_field) is False
        assert getattr(result, pts_field) == 0


def test_serp_feature_opportunity_result_defaults() -> None:
    """SerpFeatureOpportunityResult per D-08."""
    from analysis_service.models import SerpFeatureOpportunityResult
    result = SerpFeatureOpportunityResult()
    assert result.capturable_features == 0
    assert result.assessable_features == 0
    assert result.feature_details == []


def test_schema_markup_result_defaults() -> None:
    """SchemaMarkupResult per D-11."""
    from analysis_service.models import SchemaMarkupResult
    result = SchemaMarkupResult()
    assert result.missing_types == []
    assert result.present_types == []
    assert result.relevant_types == []


def test_extraction_result_has_h3_texts() -> None:
    """ExtractionResult.headings has h3_texts field (D-02 gap fill)."""
    from analysis_service.models import ExtractionResult
    er = ExtractionResult()
    assert hasattr(er.headings, "h3_texts")
    assert er.headings.h3_texts == []


def test_extraction_result_has_has_pros_cons() -> None:
    """ExtractionResult.callout_boxes has has_pros_cons field (D-02 gap fill)."""
    from analysis_service.models import ExtractionResult
    er = ExtractionResult()
    assert hasattr(er.callout_boxes, "has_pros_cons")
    assert er.callout_boxes.has_pros_cons is False


def test_page_type_enum_has_8_values() -> None:
    """PageType enum has exactly 8 values per D-05."""
    from analysis_service.models import PageType
    values = {e.value for e in PageType}
    expected = {
        "code_page", "registration_page", "comparator", "operator_review",
        "app_page", "betting_casino_guide", "timely_content", "other",
    }
    assert values == expected


def test_serp_features_has_19_flags() -> None:
    """SerpFeatures (copied from scraper_service D-03) has 19 boolean fields."""
    from analysis_service.models import SerpFeatures
    sf = SerpFeatures()
    fields = SerpFeatures.model_fields
    assert len(fields) == 19
    assert all(v is False for v in sf.model_dump().values())


def test_analysis_request_valid_construction() -> None:
    """AnalysisRequest accepts valid input per D-04."""
    from analysis_service.models import AnalysisRequest, ExtractionResult, PageType
    req = AnalysisRequest(
        target=ExtractionResult(),
        competitors=[ExtractionResult()],
        keyword="best seo tools",
        market="US",
        page_type=PageType.COMPARATOR,
    )
    assert req.keyword == "best seo tools"
    assert req.device == "desktop"
    assert req.serp_features is None


# ---------------------------------------------------------------------------
# Phase 12: Expanded Gemini result models
# ---------------------------------------------------------------------------


def test_information_gap_result_full_fields() -> None:
    from analysis_service.models import InformationGapResult, TopicToAdd, TopicToTrim
    result = InformationGapResult(
        score=75.0,
        breakdown="3 of 4 important topics covered",
        topics_to_add=[TopicToAdd(topic="t", competitor_coverage="2/3", competitors_covering=2, importance="High")],
        topics_to_trim=[TopicToTrim(section="s", reason="r", recommendation="trim")],
        total_important_topics=4,
        covered_important_topics=3,
    )
    assert result.score == 75.0
    assert len(result.topics_to_add) == 1
    assert result.topics_to_add[0].topic == "t"
    assert result.topics_to_trim[0].recommendation == "trim"


def test_topic_to_add_fields() -> None:
    from analysis_service.models import TopicToAdd
    t = TopicToAdd(
        topic="Payment methods", competitor_coverage="2/3", competitors_covering=2,
        importance="High", covered_by_target=False, suggested_heading="H", content_summary="S",
    )
    assert t.topic == "Payment methods"
    assert t.suggested_heading == "H"


def test_topic_to_trim_fields() -> None:
    from analysis_service.models import TopicToTrim
    t = TopicToTrim(section="Weekly Promos", reason="temporal", recommendation="remove")
    assert t.section == "Weekly Promos"


def test_content_best_practices_result_full_fields() -> None:
    from analysis_service.models import (
        BestPracticeItem, ContentBestPracticesResult, L2NotVerifiable, L2RuleResult, StructuralSuggestion,
    )
    result = ContentBestPracticesResult(
        l1_score=80.0, intent_summary="User wants promo",
        best_practices=[BestPracticeItem(name="n", description="d", passed=True)],
        structural_suggestions=[StructuralSuggestion(heading="H", rationale="R")],
        l2_score=90.0,
        rules_applied=[L2RuleResult(check_name="c", source="s", rule_text="r", priority="high", status="passed")],
        passed=["c"], failed=[], not_verifiable=[L2NotVerifiable(check_name="x", reason="html")],
    )
    assert result.l1_score == 80.0
    assert result.l2_score == 90.0
    assert len(result.not_verifiable) == 1


def test_best_practice_item_fields() -> None:
    from analysis_service.models import BestPracticeItem
    bp = BestPracticeItem(name="n", description="d", passed=True, evidence="e", recommendation="r")
    assert bp.passed is True


def test_structural_suggestion_fields() -> None:
    from analysis_service.models import StructuralSuggestion
    ss = StructuralSuggestion(heading="H", rationale="R")
    assert ss.heading == "H"


def test_l2_rule_result_fields() -> None:
    from analysis_service.models import L2RuleResult
    r = L2RuleResult(check_name="c", source="s", rule_text="t", priority="high", status="passed", reason=None)
    assert r.status == "passed"


def test_l2_not_verifiable_fields() -> None:
    from analysis_service.models import L2NotVerifiable
    nv = L2NotVerifiable(check_name="cta_above_fold", reason="Requires raw HTML")
    assert nv.reason == "Requires raw HTML"


def test_schema_json_ld_result_full_fields() -> None:
    from analysis_service.models import GeneratedSchema, SchemaJsonLdResult
    result = SchemaJsonLdResult(
        generated_schemas=[GeneratedSchema(schema_type="FAQPage", json_ld='{"@type":"FAQPage"}', status="valid")],
        total_generated=1, valid_count=1, invalid_count=0,
    )
    assert result.total_generated == 1
    assert result.generated_schemas[0].status == "valid"


def test_generated_schema_fields() -> None:
    from analysis_service.models import GeneratedSchema
    gs = GeneratedSchema(schema_type="FAQPage", json_ld="{}", status="valid", validation_errors=[])
    assert gs.schema_type == "FAQPage"


def test_llm_optimization_result_full_fields() -> None:
    from analysis_service.models import LlmDimension, LlmOptimizationResult
    result = LlmOptimizationResult(
        score=72.0,
        dimensions=[LlmDimension(name="direct_answers", score=70.0, source="gemini")],
        deterministic_signals={"faq_format": 100.0},
        recommendations=["Add more answers"],
    )
    assert result.score == 72.0
    assert len(result.dimensions) == 1


def test_llm_dimension_fields() -> None:
    from analysis_service.models import LlmDimension
    d = LlmDimension(name="entity_clarity", score=80.0, source="deterministic", evidence="e", recommendation=None)
    assert d.source == "deterministic"


def test_all_new_models_reject_extra_fields() -> None:
    from analysis_service.models import (
        BestPracticeItem, GeneratedSchema, L2NotVerifiable, L2RuleResult,
        LlmDimension, StructuralSuggestion, TopicToAdd, TopicToTrim,
    )
    for model_cls, kwargs in [
        (TopicToAdd, {"topic": "t", "competitor_coverage": "1/1", "competitors_covering": 1, "importance": "H"}),
        (TopicToTrim, {"section": "s", "reason": "r", "recommendation": "trim"}),
        (BestPracticeItem, {"name": "n", "description": "d"}),
        (StructuralSuggestion, {"heading": "h", "rationale": "r"}),
        (L2RuleResult, {"check_name": "c", "source": "s", "rule_text": "t", "priority": "h", "status": "passed"}),
        (L2NotVerifiable, {"check_name": "c", "reason": "r"}),
        (GeneratedSchema, {"schema_type": "FAQ", "json_ld": "{}", "status": "valid"}),
        (LlmDimension, {"name": "n", "score": 50.0, "source": "gemini"}),
    ]:
        with pytest.raises(ValidationError):
            model_cls(**kwargs, bogus="x")  # type: ignore[call-arg]


def test_information_gap_gemini_response() -> None:
    from analysis_service.models import GeminiTopic, InformationGapGeminiResponse
    r = InformationGapGeminiResponse(
        topics=[GeminiTopic(topic="t", competitor_coverage="2/3", competitors_covering=2, is_important=True, covered_by_target=False)],
        bloat=[],
    )
    assert len(r.topics) == 1


def test_content_best_practices_l1_gemini_response() -> None:
    from analysis_service.models import ContentBestPracticesL1GeminiResponse, GeminiBestPractice, GeminiStructuralSuggestion
    r = ContentBestPracticesL1GeminiResponse(
        intent_summary="intent",
        best_practices=[GeminiBestPractice(name="n", description="d", **{"pass": True})],
        structural_suggestions=[GeminiStructuralSuggestion(heading="h", rationale="r")],
    )
    assert r.best_practices[0].pass_ is True


def test_schema_json_ld_gemini_response() -> None:
    from analysis_service.models import GeminiGeneratedSchema, SchemaJsonLdGeminiResponse
    r = SchemaJsonLdGeminiResponse(
        schemas=[GeminiGeneratedSchema(schema_type="FAQPage", json_ld='{"@type": "FAQPage"}')],
    )
    assert "FAQPage" in r.schemas[0].json_ld


def test_llm_optimization_gemini_response() -> None:
    from analysis_service.models import GeminiLlmDimension, LlmOptimizationGeminiResponse
    r = LlmOptimizationGeminiResponse(
        dimensions=[GeminiLlmDimension(name="direct_answers", score=70.0)],
    )
    assert r.dimensions[0].score == 70.0


def test_analysis_result_with_expanded_models() -> None:
    from analysis_service.models import AnalysisResult, InformationGapResult, LlmOptimizationResult
    result = AnalysisResult(
        information_gap=InformationGapResult(score=75.0, total_important_topics=4, covered_important_topics=3),
        llm_optimization=LlmOptimizationResult(score=60.0),
    )
    assert result.information_gap is not None
    assert result.information_gap.total_important_topics == 4
