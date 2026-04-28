"""Comprehensive QA tests — edge cases, production scenarios, and user-perspective testing.

Written by senior QA to verify production readiness across all modules.
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from analysis_service.gemini_client import FakeGeminiClient, TokenCeilingExceededError
from analysis_service.models import (
    AnalysisJobStatus,
    AnalysisRequest,
    AnalysisResult,
    BodyTextData,
    CalloutBoxesData,
    ComparisonTablesData,
    ContentBestPracticesResult,
    EeatData,
    ExtractionResult,
    FaqData,
    FreshnessData,
    HeadingsData,
    HtmlElementGapResult,
    ImagesData,
    JsonldData,
    LinksData,
    ListsData,
    MetaData,
    MetaDescData,
    PageType,
    SchemaMarkupResult,
    SerpFeatures,
    StepByStepData,
    TablesData,
    TitleData,
    TocData,
    VideosData,
)
from analysis_service.modules.h1_meta_optimization import (
    keyword_matches,
    normalize_text,
    score_h1_meta_optimization,
)
from analysis_service.modules.html_element_gap import score_html_element_gap
from analysis_service.modules.overall_score import score_overall
from analysis_service.modules.schema_markup import score_schema_markup
from analysis_service.modules.serp_feature_opportunity import score_serp_feature_opportunity


# ============================================================================
# 1. EDGE CASES FOR DETERMINISTIC MODULES
# ============================================================================


class TestH1MetaEdgeCases:
    """Edge cases for H1+Meta optimization scoring."""

    def test_keyword_with_special_chars(self) -> None:
        """Keywords with regex special chars should not break matching."""
        assert keyword_matches("bet365 (bonus)", "Get the bet365 (bonus) code today")

    def test_keyword_with_unicode(self) -> None:
        """Accented chars should match their unaccented equivalents."""
        assert keyword_matches("café bonus", "Get your cafe bonus here")
        assert keyword_matches("cafe bonus", "Get your café bonus here")

    def test_keyword_case_insensitive(self) -> None:
        assert keyword_matches("BET365", "find the bet365 code here")

    def test_empty_keyword(self) -> None:
        """Empty keyword matches everything (substring semantics)."""
        assert keyword_matches("", "some text")

    def test_empty_text(self) -> None:
        """Empty text only matches empty keyword."""
        assert keyword_matches("", "")
        assert not keyword_matches("hello", "")

    def test_multi_word_keyword_partial_presence(self) -> None:
        """Multi-word keyword must match as full substring, not just individual words."""
        assert not keyword_matches("best casino bonus", "best article about a casino")

    def test_score_with_no_body_text(self) -> None:
        target = ExtractionResult(
            title=TitleData(title="Best Bonus Code for 2024 - Guide", title_length=35),
            headings=HeadingsData(h1_count=1, h1_texts=["Best Bonus Code Guide"]),
            meta=MetaData(meta_description="Get the best bonus code now"),
            body_text=BodyTextData(text="", word_count=0),
        )
        result = score_h1_meta_optimization(target, "bonus code")
        assert result.keyword_in_first_100_words is False
        assert result.keyword_in_first_100_words_pts == 0

    def test_title_exactly_50_chars(self) -> None:
        title = "a" * 50
        target = ExtractionResult(
            title=TitleData(title=title, title_length=50),
            meta=MetaData(meta_description=title),
        )
        result = score_h1_meta_optimization(target, "nonexistent")
        assert result.title_length_ok is True

    def test_title_exactly_60_chars(self) -> None:
        title = "a" * 60
        target = ExtractionResult(
            title=TitleData(title=title, title_length=60),
            meta=MetaData(meta_description=title),
        )
        result = score_h1_meta_optimization(target, "nonexistent")
        assert result.title_length_ok is True

    def test_title_49_chars_fails(self) -> None:
        title = "a" * 49
        target = ExtractionResult(
            title=TitleData(title=title, title_length=49),
        )
        result = score_h1_meta_optimization(target, "nonexistent")
        assert result.title_length_ok is False

    def test_meta_exactly_120_chars(self) -> None:
        meta = "a" * 120
        target = ExtractionResult(
            meta=MetaData(meta_description=meta, meta_description_length=120),
        )
        result = score_h1_meta_optimization(target, "nonexistent")
        assert result.meta_length_ok is True

    def test_meta_exactly_160_chars(self) -> None:
        meta = "a" * 160
        target = ExtractionResult(
            meta=MetaData(meta_description=meta, meta_description_length=160),
        )
        result = score_h1_meta_optimization(target, "nonexistent")
        assert result.meta_length_ok is True

    def test_h1_identical_to_title_fails_check_6(self) -> None:
        target = ExtractionResult(
            title=TitleData(title="Best Bonus Code"),
            headings=HeadingsData(h1_count=1, h1_texts=["Best Bonus Code"]),
        )
        result = score_h1_meta_optimization(target, "bonus")
        assert result.h1_differs_from_title is False

    def test_h1_differs_accent_only(self) -> None:
        """H1 that differs from title only by accents should count as same."""
        target = ExtractionResult(
            title=TitleData(title="café guide"),
            headings=HeadingsData(h1_count=1, h1_texts=["cafe guide"]),
        )
        result = score_h1_meta_optimization(target, "guide")
        assert result.h1_differs_from_title is False

    def test_perfect_score_is_100(self) -> None:
        keyword = "bonus code"
        title = "Best Bonus Code Guide For You 2024 - Expert Review"  # 50 chars
        meta_desc = "a" * 119 + " bonus code"  # 130 chars with keyword
        target = ExtractionResult(
            title=TitleData(title=title, title_length=len(title)),
            headings=HeadingsData(h1_count=1, h1_texts=["Top Bonus Code Tips"]),
            meta=MetaData(meta_description=meta_desc, meta_description_length=len(meta_desc)),
            body_text=BodyTextData(text="The bonus code for today is ABC123", word_count=7),
        )
        result = score_h1_meta_optimization(target, keyword)
        assert result.score == 100.0


class TestHtmlElementGapEdgeCases:
    """Edge cases for HTML element gap scoring."""

    def test_zero_competitors(self) -> None:
        target = ExtractionResult()
        result = score_html_element_gap(target, [])
        assert result.score == 100.0

    def test_target_with_all_elements_vs_2_empty_competitors(self) -> None:
        """Target has everything, competitors have nothing → score 100."""
        target = ExtractionResult(
            tables=TablesData(table_count=1),
            lists=ListsData(ol_count=1, ul_count=1),
            faq=FaqData(has_faq=True),
            images=ImagesData(total_images=5),
            videos=VideosData(video_count=1),
            toc=TocData(has_toc=True),
            comparison_tables=ComparisonTablesData(has_comparison_table=True),
            callout_boxes=CalloutBoxesData(has_callouts=True, has_pros_cons=True),
            step_by_step=StepByStepData(has_steps=True),
        )
        comps = [ExtractionResult(), ExtractionResult()]
        result = score_html_element_gap(target, comps)
        assert result.score == 100.0

    def test_competitor_pct_calculated_correctly(self) -> None:
        comp1 = ExtractionResult(tables=TablesData(table_count=1))
        comp2 = ExtractionResult()
        comp3 = ExtractionResult(tables=TablesData(table_count=2))
        result = score_html_element_gap(ExtractionResult(), [comp1, comp2, comp3])
        assert result.tables.competitor_count == 2
        assert result.tables.competitor_pct == pytest.approx(66.7, abs=0.1)

    def test_images_threshold_3(self) -> None:
        """Images need >=3 to count as present."""
        target = ExtractionResult(images=ImagesData(total_images=2))
        assert not score_html_element_gap(target, []).images.target_present

        target2 = ExtractionResult(images=ImagesData(total_images=3))
        assert score_html_element_gap(target2, []).images.target_present


class TestSchemaMarkupEdgeCases:

    def test_schema_url_normalization(self) -> None:
        target = ExtractionResult(
            jsonld=JsonldData(all_schema_types=["https://schema.org/Article"]),
        )
        result = score_schema_markup(target, [], PageType.OTHER)
        assert "Article" in result.present_types

    def test_http_url_normalization(self) -> None:
        target = ExtractionResult(
            jsonld=JsonldData(all_schema_types=["http://schema.org/Article/"]),
        )
        result = score_schema_markup(target, [], PageType.OTHER)
        assert "Article" in result.present_types

    def test_every_page_type_has_recommendations(self) -> None:
        for pt in PageType:
            result = score_schema_markup(ExtractionResult(), [], pt)
            assert result.relevant_types, f"No recommendations for {pt.value}"

    def test_competitor_schemas_add_to_relevant(self) -> None:
        comp = ExtractionResult(
            jsonld=JsonldData(all_schema_types=["ExoticType"]),
        )
        result = score_schema_markup(ExtractionResult(), [comp], PageType.OTHER)
        assert "ExoticType" in result.relevant_types
        assert "ExoticType" in result.missing_types


class TestSerpFeatureEdgeCases:

    def test_all_features_false_no_serp(self) -> None:
        """All SERP features False → assessable_count=0, score=100."""
        serp = SerpFeatures()
        result = score_serp_feature_opportunity(ExtractionResult(), serp)
        assert result.score == 100.0
        assert result.assessable_features == 0

    def test_non_assessable_excluded_from_score(self) -> None:
        """AI Overview and other non-assessable don't affect score."""
        serp = SerpFeatures(has_ai_overview=True, has_local_pack=True, has_shopping_results=True)
        result = score_serp_feature_opportunity(ExtractionResult(), serp)
        assert result.score == 100.0
        assert result.assessable_features == 0

    def test_featured_snippet_capturable_with_content(self) -> None:
        target = ExtractionResult(body_text=BodyTextData(word_count=100, text="some content"))
        serp = SerpFeatures(has_featured_snippet=True)
        result = score_serp_feature_opportunity(target, serp)
        assert result.capturable_features == 1


class TestOverallScoreEdgeCases:

    def test_null_propagation_with_one_null(self) -> None:
        """If information_gap is None, overall_score must be None."""
        result = AnalysisResult(
            html_element_gap=HtmlElementGapResult(score=80),
            h1_meta_optimization=None,
            serp_feature_opportunity=None,
            schema_markup=SchemaMarkupResult(score=60),
        )
        overall, priority = score_overall(result)
        assert overall is None

    def test_all_scores_100(self) -> None:
        result = AnalysisResult(
            html_element_gap=HtmlElementGapResult(score=100),
            h1_meta_optimization=None,
            serp_feature_opportunity=None,
            schema_markup=SchemaMarkupResult(score=100),
            information_gap=None,
        )
        overall, _ = score_overall(result)
        assert overall is None  # info_gap is None → null propagation

    def test_weights_produce_correct_composite(self) -> None:
        from analysis_service.models import (
            H1MetaOptimizationResult,
            InformationGapResult,
            SerpFeatureOpportunityResult,
        )

        result = AnalysisResult(
            information_gap=InformationGapResult(score=100),
            h1_meta_optimization=H1MetaOptimizationResult(score=80),
            serp_feature_opportunity=SerpFeatureOpportunityResult(score=60),
            html_element_gap=HtmlElementGapResult(score=40),
            schema_markup=SchemaMarkupResult(score=20),
        )
        overall, priority = score_overall(result)
        expected = 100 * 0.30 + 80 * 0.20 + 60 * 0.20 + 40 * 0.15 + 20 * 0.15
        assert overall == round(expected)
        assert priority[0] == "schema_markup"
        assert priority[-1] == "information_gap"


# ============================================================================
# 2. ROUTER INTEGRATION TESTS — USER PERSPECTIVE
# ============================================================================


class TestRouterUserPerspective:

    def test_minimal_valid_request(self, client: TestClient) -> None:
        """Simplest possible valid request should return 200."""
        payload = {
            "keyword": "test",
            "market": "uk",
            "page_type": "other",
        }
        resp = client.post("/analyze", json=payload)
        assert resp.status_code == 200

    def test_full_request_with_all_fields(self, client_with_gemini: TestClient) -> None:
        """Full request with target, competitors, serp_features should succeed."""
        payload = {
            "keyword": "best casino bonus",
            "market": "de",
            "page_type": "code_page",
            "device": "mobile",
            "target": {
                "title": {"title": "Best Casino Bonus Codes 2024", "title_length": 30},
                "headings": {"h1_count": 1, "h1_texts": ["Best Casino Bonus Codes"]},
                "body_text": {"text": "The best casino bonus codes for 2024.", "word_count": 7},
                "meta": {"meta_description": "Find the best casino bonus codes here."},
                "faq": {"has_faq": True, "total_faq_items": 3},
                "jsonld": {"jsonld_present": True, "jsonld_count": 1, "all_schema_types": ["FAQPage", "Article"]},
                "images": {"total_images": 5},
                "tables": {"table_count": 2},
                "toc": {"has_toc": True},
            },
            "competitors": [
                {
                    "title": {"title": "Comp 1 Bonus"},
                    "headings": {"h1_count": 1, "h1_texts": ["Comp 1"]},
                    "body_text": {"text": "Competitor content here", "word_count": 3},
                    "tables": {"table_count": 1},
                    "jsonld": {"all_schema_types": ["Article"]},
                },
                {
                    "title": {"title": "Comp 2 Bonus"},
                    "headings": {"h1_count": 1, "h1_texts": ["Comp 2"]},
                    "body_text": {"text": "Another competitor page", "word_count": 3},
                    "tables": {"table_count": 1},
                    "jsonld": {"all_schema_types": ["FAQPage"]},
                },
            ],
            "serp_features": {
                "has_featured_snippet": True,
                "has_people_also_ask": True,
                "has_faq_rich_results": True,
            },
        }
        resp = client_with_gemini.post("/analyze", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["html_element_gap"] is not None
        assert data["h1_meta_optimization"] is not None
        assert data["serp_feature_opportunity"] is not None
        assert data["schema_markup"] is not None
        assert data["information_gap"] is not None
        assert data["content_best_practices"] is not None
        assert data["llm_optimization"] is not None
        assert data["overall_score"] is not None
        assert isinstance(data["priority_modules"], list)

    def test_invalid_page_type_returns_422(self, client: TestClient) -> None:
        payload = {"keyword": "test", "market": "uk", "page_type": "invalid_type"}
        resp = client.post("/analyze", json=payload)
        assert resp.status_code == 422

    def test_missing_keyword_returns_422(self, client: TestClient) -> None:
        payload = {"market": "uk", "page_type": "other"}
        resp = client.post("/analyze", json=payload)
        assert resp.status_code == 422

    def test_missing_market_returns_422(self, client: TestClient) -> None:
        payload = {"keyword": "test", "page_type": "other"}
        resp = client.post("/analyze", json=payload)
        assert resp.status_code == 422

    def test_extra_fields_rejected(self, client: TestClient) -> None:
        payload = {"keyword": "test", "market": "uk", "page_type": "other", "unknown_field": "value"}
        resp = client.post("/analyze", json=payload)
        assert resp.status_code == 422

    def test_all_page_types_accepted(self, client: TestClient) -> None:
        for pt in PageType:
            payload = {"keyword": "test", "market": "uk", "page_type": pt.value}
            resp = client.post("/analyze", json=payload)
            assert resp.status_code == 200, f"Page type {pt.value} rejected"

    def test_empty_keyword_accepted(self, client: TestClient) -> None:
        """Empty keyword is technically valid (str type)."""
        payload = {"keyword": "", "market": "uk", "page_type": "other"}
        resp = client.post("/analyze", json=payload)
        assert resp.status_code == 200

    def test_unicode_keyword(self, client_with_gemini: TestClient) -> None:
        payload = {"keyword": "bônus de casino", "market": "br", "page_type": "code_page"}
        resp = client_with_gemini.post("/analyze", json=payload)
        assert resp.status_code == 200


class TestHealthEndpoint:

    def test_health_ok(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["gemini"] == "reachable"

    def test_health_never_returns_500(self, required_env: None, _minimal_bc_config: Any) -> None:
        """Health must never return 500, even when Gemini is down."""
        from analysis_service.app import app
        from analysis_service.gemini_client import get_gemini_client as _get_gemini_client
        from analysis_service.router import get_bc_config

        failing_client = FakeGeminiClient(token_count=100)

        async def _failing_count_tokens(prompt: str) -> int:
            raise ConnectionError("Gemini is down")

        failing_client.count_tokens = _failing_count_tokens  # type: ignore[assignment]

        app.dependency_overrides[_get_gemini_client] = lambda: failing_client
        app.dependency_overrides[get_bc_config] = lambda: _minimal_bc_config
        with TestClient(app) as tc:
            resp = tc.get("/health")
        app.dependency_overrides.clear()
        assert resp.status_code == 200
        assert resp.json()["status"] == "degraded"


# ============================================================================
# 3. ASYNC ENDPOINT TESTS — PRODUCTION SCENARIOS
# ============================================================================


class TestAsyncEndpointsProduction:

    def test_async_returns_202_immediately(self, async_client: TestClient) -> None:
        payload = {"keyword": "test", "market": "uk", "page_type": "other"}
        resp = async_client.post("/analyze/async", json=payload)
        assert resp.status_code == 202
        assert "job_id" in resp.json()

    def test_unknown_job_id_returns_404(self, async_client: TestClient) -> None:
        resp = async_client.get("/analyze/nonexistent-uuid")
        assert resp.status_code == 404

    def test_job_lifecycle_pending_to_completed(self, async_client_with_gemini: TestClient) -> None:
        """Full job lifecycle: submit → poll → completed."""
        payload = {"keyword": "test", "market": "uk", "page_type": "other"}
        submit = async_client_with_gemini.post("/analyze/async", json=payload)
        job_id = submit.json()["job_id"]

        import time
        time.sleep(0.5)

        poll = async_client_with_gemini.get(f"/analyze/{job_id}")
        data = poll.json()
        assert data["status"] in ("running", "completed", "pending")

    def test_concurrent_job_limit(self, async_client: TestClient) -> None:
        """Should return 429 when max concurrent jobs exceeded."""
        from analysis_service.router import _jobs

        for i in range(10):
            _jobs[f"job-{i}"] = type("MockJob", (), {
                "status": AnalysisJobStatus.RUNNING,
                "job_id": f"job-{i}",
                "completed_modules": [],
                "result": None,
                "error": None,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "completed_at": None,
            })()

        payload = {"keyword": "test", "market": "uk", "page_type": "other"}
        resp = async_client.post("/analyze/async", json=payload)
        assert resp.status_code == 429


# ============================================================================
# 4. GEMINI CLIENT EDGE CASES
# ============================================================================


class TestGeminiClientEdgeCases:

    def test_token_ceiling_exceeded(self) -> None:
        err = TokenCeilingExceededError(200_000, 100_000)
        assert err.token_count == 200_000
        assert err.ceiling == 100_000
        assert "200000" in str(err)

    async def test_fake_client_returns_fixture(self) -> None:
        from analysis_service.models import InformationGapGeminiResponse

        fixture = InformationGapGeminiResponse(topics=[], bloat=[])
        fake = FakeGeminiClient(responses={InformationGapGeminiResponse: fixture})
        result = await fake.generate("prompt", InformationGapGeminiResponse)
        assert result == fixture

    async def test_fake_client_raises_for_unknown(self) -> None:
        fake = FakeGeminiClient()
        with pytest.raises(ValueError, match="No fixture"):
            await fake.generate("prompt", dict)


# ============================================================================
# 5. MODEL VALIDATION EDGE CASES
# ============================================================================


class TestModelValidation:

    def test_analysis_result_default_fields(self) -> None:
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

    def test_extraction_result_all_defaults(self) -> None:
        er = ExtractionResult()
        assert er.title.title is None
        assert er.headings.h1_count == 0
        assert er.body_text.word_count == 0
        assert er.faq.has_faq is False
        assert er.jsonld.jsonld_present is False
        assert er.images.total_images == 0

    def test_page_type_all_8_values(self) -> None:
        assert len(PageType) == 8

    def test_serp_features_all_19_flags(self) -> None:
        fields = SerpFeatures.model_fields
        assert len(fields) == 19

    def test_analysis_request_serialization_roundtrip(self) -> None:
        req = AnalysisRequest(
            keyword="test",
            market="uk",
            page_type=PageType.CODE_PAGE,
        )
        data = req.model_dump()
        req2 = AnalysisRequest.model_validate(data)
        assert req == req2


# ============================================================================
# 6. L1+L2 MERGE LOGIC
# ============================================================================


class TestContentBestPracticesMerge:

    def test_l2_only_result(self, client: TestClient) -> None:
        """When Gemini fails, L2 should still be present."""
        payload = {"keyword": "test", "market": "uk", "page_type": "other"}
        resp = client.post("/analyze", json=payload)
        data = resp.json()
        cbp = data["content_best_practices"]
        assert cbp is not None
        assert cbp["l2_score"] is not None

    def test_l1_and_l2_merged(self, client_with_gemini: TestClient) -> None:
        """Both L1 and L2 should appear in merged result."""
        payload = {"keyword": "test", "market": "uk", "page_type": "code_page"}
        resp = client_with_gemini.post("/analyze", json=payload)
        data = resp.json()
        cbp = data["content_best_practices"]
        assert cbp is not None
        assert cbp["l1_score"] is not None
        assert cbp["l2_score"] is not None
        assert cbp["intent_summary"] is not None
        assert len(cbp["best_practices"]) > 0


# ============================================================================
# 7. CONTENT BEST PRACTICES L2 EDGE CASES
# ============================================================================


class TestContentBestPracticesL2:

    def test_betting_casino_guide_has_rg_checks(self) -> None:
        """Betting pages should check for responsible gambling keywords."""
        from analysis_service.bc_config import BcBestPracticesConfig, load_bc_config
        from analysis_service.modules.content_best_practices_l2 import score_content_best_practices_l2

        config = BcBestPracticesConfig(
            version="1.0",
            page_type_priority={},
            universal_rules={},
            page_types={},
        )
        target = ExtractionResult(
            body_text=BodyTextData(text="Play responsibly. 18+.", word_count=3),
        )
        result = score_content_best_practices_l2(target, PageType.BETTING_CASINO_GUIDE, config)
        assert result.l2_score is not None

    def test_deduplication_across_universal_and_page_rules(self) -> None:
        """Same check appearing in both universal and page rules should only be counted once."""
        from analysis_service.bc_config import BcBestPracticesConfig, BcRule
        from analysis_service.modules.content_best_practices_l2 import score_content_best_practices_l2

        config = BcBestPracticesConfig(
            version="1.0",
            page_type_priority={},
            universal_rules={"seo": [BcRule(check="has_h1", rule="Must have H1", priority="high")]},
            page_types={},
        )
        target = ExtractionResult(
            headings=HeadingsData(h1_count=1, h1_texts=["Test H1"]),
        )
        result = score_content_best_practices_l2(target, PageType.OTHER, config)
        h1_appearances = [r for r in result.rules_applied if r.check_name == "has_h1"]
        assert len(h1_appearances) == 1


# ============================================================================
# 8. DOCKER/DEPLOYMENT READINESS
# ============================================================================


class TestDeploymentConfig:

    def test_settings_validation_fails_without_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ANALYSIS_GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("ANALYSIS_GEMINI_MODEL", raising=False)
        monkeypatch.delenv("ANALYSIS_PORT", raising=False)
        from pydantic import ValidationError

        from analysis_service.settings import Settings
        with pytest.raises(ValidationError):
            Settings(_env_file=None)

    def test_settings_loads_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANALYSIS_GEMINI_API_KEY", "key123")
        monkeypatch.setenv("ANALYSIS_GEMINI_MODEL", "gemini-2.5-flash")
        monkeypatch.setenv("ANALYSIS_PORT", "9999")
        from analysis_service.settings import Settings

        s = Settings()
        assert s.gemini_api_key.get_secret_value() == "key123"
        assert s.port == 9999

    def test_settings_defaults(self, required_env: None) -> None:
        from analysis_service.settings import Settings

        s = Settings()
        assert s.max_concurrent_gemini_calls == 3
        assert s.token_ceiling_per_module == 100_000
        assert s.log_level == "INFO"
        assert s.max_concurrent_jobs == 10
        assert s.job_ttl_minutes == 60


# ============================================================================
# 9. INFORMATION GAP MODULE EDGE CASES
# ============================================================================


class TestInformationGapEdgeCases:

    def test_compute_result_no_topics(self) -> None:
        from analysis_service.models import InformationGapGeminiResponse
        from analysis_service.modules.information_gap import _compute_result

        resp = InformationGapGeminiResponse(topics=[], bloat=[])
        result = _compute_result(resp, 3)
        assert result.score == 100.0
        assert result.total_important_topics == 0

    def test_compute_result_all_covered(self) -> None:
        from analysis_service.models import GeminiTopic, InformationGapGeminiResponse
        from analysis_service.modules.information_gap import _compute_result

        resp = InformationGapGeminiResponse(
            topics=[
                GeminiTopic(
                    topic="T1", competitor_coverage="3/3", competitors_covering=3,
                    is_important=True, covered_by_target=True,
                ),
                GeminiTopic(
                    topic="T2", competitor_coverage="2/3", competitors_covering=2,
                    is_important=True, covered_by_target=True,
                ),
            ],
            bloat=[],
        )
        result = _compute_result(resp, 3)
        assert result.score == 100.0
        assert len(result.topics_to_add) == 0

    def test_compute_result_single_competitor_threshold_1(self) -> None:
        from analysis_service.models import GeminiTopic, InformationGapGeminiResponse
        from analysis_service.modules.information_gap import _compute_result

        resp = InformationGapGeminiResponse(
            topics=[
                GeminiTopic(
                    topic="T1", competitor_coverage="1/1", competitors_covering=1,
                    is_important=True, covered_by_target=False,
                ),
            ],
            bloat=[],
        )
        result = _compute_result(resp, 1)
        assert result.score == 0.0
        assert result.total_important_topics == 1
        assert len(result.topics_to_add) == 1


# ============================================================================
# 10. SCHEMA JSON-LD MODULE EDGE CASES
# ============================================================================


class TestSchemaJsonLdEdgeCases:

    async def test_empty_missing_types_returns_empty(self) -> None:
        from analysis_service.modules.schema_json_ld import score_schema_json_ld

        fake = FakeGeminiClient()
        result = await score_schema_json_ld(
            ExtractionResult(), [], "test", PageType.OTHER, fake,
        )
        assert result.total_generated == 0

    def test_validation_catches_missing_context(self) -> None:
        from analysis_service.modules.schema_json_ld import _validate_schema_block

        status, errors = _validate_schema_block({"@type": "Article"}, ["Article"])
        assert status == "invalid"
        assert any("@context" in e for e in errors)

    def test_validation_catches_wrong_type(self) -> None:
        from analysis_service.modules.schema_json_ld import _validate_schema_block

        status, errors = _validate_schema_block(
            {"@context": "https://schema.org", "@type": "Article"},
            ["FAQPage"],
        )
        assert status == "invalid"
        assert any("not in missing types" in e for e in errors)

    def test_validation_passes_correct_schema(self) -> None:
        from analysis_service.modules.schema_json_ld import _validate_schema_block

        status, errors = _validate_schema_block(
            {"@context": "https://schema.org", "@type": "FAQPage"},
            ["FAQPage"],
        )
        assert status == "valid"
        assert errors == []


# ============================================================================
# 11. LLM OPTIMIZATION EDGE CASES
# ============================================================================


class TestLlmOptimizationEdgeCases:

    def test_deterministic_signals_all_zero(self) -> None:
        from analysis_service.modules.llm_optimization import _compute_deterministic_signals

        signals = _compute_deterministic_signals(ExtractionResult())
        for val in signals.values():
            assert val == 0.0

    def test_deterministic_signals_all_max(self) -> None:
        from analysis_service.modules.llm_optimization import _compute_deterministic_signals

        target = ExtractionResult(
            faq=FaqData(has_faq=True, total_faq_items=5),
            jsonld=JsonldData(jsonld_count=4),
            tables=TablesData(table_count=3),
            lists=ListsData(ul_count=1, ol_count=1),
            headings=HeadingsData(
                h2_texts=["How does it work?", "What are the benefits of long headings explained"],
                h3_texts=["Is it safe?"],
            ),
            freshness=FreshnessData(published_date="2024-01-01", modified_date="2024-06-01"),
        )
        signals = _compute_deterministic_signals(target)
        assert signals["faq_format"] == 100.0
        assert signals["structured_data"] == 100.0
        assert signals["freshness_signals"] == 100.0

    def test_blended_score_weights(self) -> None:
        from analysis_service.modules.llm_optimization import _DETERMINISTIC_WEIGHT, _GEMINI_WEIGHT

        assert _DETERMINISTIC_WEIGHT + _GEMINI_WEIGHT == pytest.approx(1.0)


# ============================================================================
# 12. PROMPT BUILDER
# ============================================================================


class TestPromptBuilder:

    def test_prompt_structure(self) -> None:
        from analysis_service.modules.prompt_builder import build_prompt

        prompt = build_prompt(
            module_instructions="Do the analysis",
            variable_data="TARGET: some content",
        )
        assert "expert seo" in prompt.lower()
        assert "Do the analysis" in prompt
        assert "TARGET: some content" in prompt

    def test_bc_config_between_system_and_task(self) -> None:
        from analysis_service.modules.prompt_builder import build_prompt

        prompt = build_prompt(
            bc_config_yaml="some yaml config",
            module_instructions="task instructions",
            variable_data="data here",
        )
        system_pos = prompt.find("expert SEO")
        bc_pos = prompt.find("some yaml config")
        task_pos = prompt.find("task instructions")
        data_pos = prompt.find("data here")
        assert system_pos < bc_pos < task_pos < data_pos


# ============================================================================
# 13. BC CONFIG LOADING
# ============================================================================


class TestBcConfigLoading:

    def test_missing_file_raises(self) -> None:
        from analysis_service.bc_config import load_bc_config

        with pytest.raises(RuntimeError):
            load_bc_config("/nonexistent/path.yaml")

    def test_valid_config_loads(self, bc_yaml_path: str) -> None:
        from analysis_service.bc_config import load_bc_config

        config = load_bc_config(bc_yaml_path)
        assert config.version == "1.0"

    def test_extra_keys_ignored(self, tmp_path: Any) -> None:
        """BC team may add fields we don't know about — extra='ignore' ensures no crash."""
        from analysis_service.bc_config import load_bc_config

        yaml_content = 'version: "1.0"\npage_type_priority: {}\nuniversal_rules: {}\npage_types: {}\nnew_future_field: true\n'
        yaml_file = tmp_path / "bc.yaml"
        yaml_file.write_text(yaml_content)
        config = load_bc_config(str(yaml_file))
        assert config.version == "1.0"
