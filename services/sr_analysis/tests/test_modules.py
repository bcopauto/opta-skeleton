"""Unit tests for deterministic scoring modules (DET-01 through DET-05, DET-07).

Wave 0 stubs — these tests FAIL until Wave 1 plans implement the modules.
Each test class covers one module function; full parametrized test cases are
added in Wave 1 plans alongside the implementations.
"""
from __future__ import annotations

import pytest


class TestHtmlElementGap:
    """Tests for score_html_element_gap (DET-02)."""

    def test_import(self) -> None:
        """Module and function are importable."""
        from analysis_service.modules.html_element_gap import score_html_element_gap  # noqa: F401

    def test_returns_result_type(self) -> None:
        """Returns HtmlElementGapResult."""
        from analysis_service.models import ExtractionResult, HtmlElementGapResult
        from analysis_service.modules.html_element_gap import score_html_element_gap

        result = score_html_element_gap(ExtractionResult(), [])
        assert isinstance(result, HtmlElementGapResult)

    def test_no_competitors_score_100(self) -> None:
        """Zero competitors → score=100 (nothing commonly used)."""
        from analysis_service.models import ExtractionResult
        from analysis_service.modules.html_element_gap import score_html_element_gap

        result = score_html_element_gap(ExtractionResult(), [])
        assert result.score == 100.0

    def test_target_missing_commonly_used_elements(self) -> None:
        """Target missing elements used by 2+ competitors → score < 100."""
        from analysis_service.models import (
            ExtractionResult,
            FaqData,
            TablesData,
        )
        from analysis_service.modules.html_element_gap import score_html_element_gap

        comp_with_table = ExtractionResult(
            tables=TablesData(table_count=1),
            faq=FaqData(has_faq=True),
        )
        result = score_html_element_gap(
            ExtractionResult(),
            [comp_with_table, comp_with_table],
        )
        assert result.score is not None
        assert result.score < 100.0

    def test_single_competitor_warning(self) -> None:
        """Single competitor triggers low_competitor_data_warning (D-11)."""
        from analysis_service.models import ExtractionResult, TablesData
        from analysis_service.modules.html_element_gap import score_html_element_gap

        comp = ExtractionResult(tables=TablesData(table_count=1))
        result = score_html_element_gap(ExtractionResult(), [comp])
        assert result.low_competitor_data_warning is not None

    def test_worked_example_6_of_9(self) -> None:
        """Scoring doc §Module 4 worked example: 6/9 → score=67."""
        from analysis_service.models import (
            CalloutBoxesData,
            ComparisonTablesData,
            ExtractionResult,
            FaqData,
            ImagesData,
            ListsData,
            StepByStepData,
            TablesData,
            TocData,
            VideosData,
        )
        from analysis_service.modules.html_element_gap import score_html_element_gap

        # Competitor has: tables, ordered_lists, unordered_lists, faq, images_3plus,
        #                 toc, pros_cons, step_by_step, comparison_charts (9 of 11 — no videos, no callout_boxes)
        def make_full_comp() -> ExtractionResult:
            return ExtractionResult(
                tables=TablesData(table_count=1),
                lists=ListsData(ol_count=1, ul_count=1),
                faq=FaqData(has_faq=True),
                images=ImagesData(total_images=3),
                toc=TocData(has_toc=True),
                callout_boxes=CalloutBoxesData(has_pros_cons=True),
                step_by_step=StepByStepData(has_steps=True),
                comparison_tables=ComparisonTablesData(has_comparison_table=True),
            )

        # Target has: tables, ordered_lists, unordered_lists, images_3plus, toc, step_by_step (6 of 9)
        target = ExtractionResult(
            tables=TablesData(table_count=1),
            lists=ListsData(ol_count=1, ul_count=1),
            images=ImagesData(total_images=3),
            toc=TocData(has_toc=True),
            step_by_step=StepByStepData(has_steps=True),
        )
        result = score_html_element_gap(target, [make_full_comp(), make_full_comp()])
        assert result.score == 67.0

    def test_element_breakdown_populated(self) -> None:
        """ElementBreakdown fields set correctly."""
        from analysis_service.models import ExtractionResult, TablesData
        from analysis_service.modules.html_element_gap import score_html_element_gap

        comp = ExtractionResult(tables=TablesData(table_count=1))
        result = score_html_element_gap(
            ExtractionResult(tables=TablesData(table_count=1)),
            [comp, comp],
        )
        assert result.tables.target_present is True
        assert result.tables.competitor_count == 2
        assert result.tables.competitor_pct == 100.0

    def test_all_commonly_used_target_has_all_score_100(self) -> None:
        """Target has all commonly-used elements → score=100."""
        from analysis_service.models import ExtractionResult, TablesData
        from analysis_service.modules.html_element_gap import score_html_element_gap

        comp = ExtractionResult(tables=TablesData(table_count=1))
        target = ExtractionResult(tables=TablesData(table_count=1))
        result = score_html_element_gap(target, [comp, comp])
        assert result.score == 100.0


class TestSerpFeatureOpportunity:
    """Tests for score_serp_feature_opportunity (DET-01)."""

    def test_import(self) -> None:
        from analysis_service.modules.serp_feature_opportunity import score_serp_feature_opportunity  # noqa: F401

    def test_none_serp_features_returns_none_score(self) -> None:
        """serp_features=None → score=None (D-07)."""
        from analysis_service.models import ExtractionResult, SerpFeatureOpportunityResult
        from analysis_service.modules.serp_feature_opportunity import score_serp_feature_opportunity

        result = score_serp_feature_opportunity(ExtractionResult(), None)
        assert isinstance(result, SerpFeatureOpportunityResult)
        assert result.score is None

    def test_no_assessable_features_score_100(self) -> None:
        """No assessable features detected → score=100."""
        from analysis_service.models import ExtractionResult, SerpFeatures
        from analysis_service.modules.serp_feature_opportunity import score_serp_feature_opportunity

        sf = SerpFeatures(has_ai_overview=True)  # ai_overview is non-assessable
        result = score_serp_feature_opportunity(ExtractionResult(), sf)
        assert result.score == 100.0

    def test_assessable_feature_not_captured(self) -> None:
        """Assessable feature present but page can't capture it → score < 100."""
        from analysis_service.models import ExtractionResult, SerpFeatures
        from analysis_service.modules.serp_feature_opportunity import score_serp_feature_opportunity

        sf = SerpFeatures(has_featured_snippet=True)
        # Target has no FAQ schema, no question headings, no direct answer in first 200 words
        result = score_serp_feature_opportunity(ExtractionResult(), sf)
        assert result.assessable_features >= 1
        assert result.score is not None

    def test_all_features_not_captured_score_zero(self) -> None:
        """Assessable features present but not captured → score=0.0."""
        from analysis_service.models import ExtractionResult, SerpFeatures
        from analysis_service.modules.serp_feature_opportunity import score_serp_feature_opportunity

        sf = SerpFeatures(has_featured_snippet=True)
        # Target has no body text → not capturable
        result = score_serp_feature_opportunity(ExtractionResult(), sf)
        assert result.score == 0.0
        assert result.assessable_features == 1
        assert result.capturable_features == 0

    def test_capturable_faq_feature(self) -> None:
        """PAA feature + target has FAQ → capturable → score=100."""
        from analysis_service.models import ExtractionResult, FaqData, SerpFeatures
        from analysis_service.modules.serp_feature_opportunity import score_serp_feature_opportunity

        sf = SerpFeatures(has_people_also_ask=True)
        target = ExtractionResult(faq=FaqData(has_faq=True))
        result = score_serp_feature_opportunity(target, sf)
        assert result.score == 100.0
        assert result.capturable_features == 1

    def test_capturable_images_feature(self) -> None:
        """Images feature + target has 3+ images → capturable."""
        from analysis_service.models import ExtractionResult, ImagesData, SerpFeatures
        from analysis_service.modules.serp_feature_opportunity import score_serp_feature_opportunity

        sf = SerpFeatures(has_images_results=True)
        target = ExtractionResult(images=ImagesData(total_images=3))
        result = score_serp_feature_opportunity(target, sf)
        assert result.capturable_features == 1
        assert result.score == 100.0

    def test_feature_details_populated(self) -> None:
        """feature_details list has FeatureDetail with correct fields."""
        from analysis_service.models import ExtractionResult, FaqData, SerpFeatures
        from analysis_service.modules.serp_feature_opportunity import score_serp_feature_opportunity

        sf = SerpFeatures(has_people_also_ask=True, has_ai_overview=True)
        target = ExtractionResult(faq=FaqData(has_faq=True))
        result = score_serp_feature_opportunity(target, sf)
        # Both features detected → 2 FeatureDetail items
        assert len(result.feature_details) == 2
        assessable_details = [d for d in result.feature_details if d.assessable]
        assert len(assessable_details) == 1
        assert assessable_details[0].capturable is True

    def test_non_assessable_excluded_from_count(self) -> None:
        """ai_overview detected → assessable_features=0, score=100."""
        from analysis_service.models import ExtractionResult, SerpFeatures
        from analysis_service.modules.serp_feature_opportunity import score_serp_feature_opportunity

        sf = SerpFeatures(has_ai_overview=True)
        result = score_serp_feature_opportunity(ExtractionResult(), sf)
        assert result.assessable_features == 0
        assert result.score == 100.0
        assert len(result.feature_details) == 1
        assert result.feature_details[0].assessable is False

    def test_mixed_assessable_partial_capture(self) -> None:
        """2 assessable features, 1 captured → score=50."""
        from analysis_service.models import ExtractionResult, FaqData, SerpFeatures
        from analysis_service.modules.serp_feature_opportunity import score_serp_feature_opportunity

        # people_also_ask (capturable if faq) + images (need 3+)
        sf = SerpFeatures(has_people_also_ask=True, has_images_results=True)
        target = ExtractionResult(faq=FaqData(has_faq=True))  # has faq, no 3+ images
        result = score_serp_feature_opportunity(target, sf)
        assert result.assessable_features == 2
        assert result.capturable_features == 1
        assert result.score == 50.0


class TestH1MetaOptimization:
    """Tests for score_h1_meta_optimization (DET-03)."""

    def test_import(self) -> None:
        from analysis_service.modules.h1_meta_optimization import score_h1_meta_optimization  # noqa: F401

    def test_returns_result_type(self) -> None:
        from analysis_service.models import ExtractionResult, H1MetaOptimizationResult
        from analysis_service.modules.h1_meta_optimization import score_h1_meta_optimization

        result = score_h1_meta_optimization(ExtractionResult(), "test keyword")
        assert isinstance(result, H1MetaOptimizationResult)

    def test_empty_page_score_zero(self) -> None:
        """All fields missing → score=0."""
        from analysis_service.models import ExtractionResult
        from analysis_service.modules.h1_meta_optimization import score_h1_meta_optimization

        result = score_h1_meta_optimization(ExtractionResult(), "test keyword")
        assert result.score == 0.0

    def test_perfect_score_all_checks_pass(self) -> None:
        """Page meeting all 7 checks → score=100 (worked example from scoring doc)."""
        from analysis_service.models import (
            BodyTextData,
            ExtractionResult,
            HeadingsData,
            MetaData,
            TitleData,
        )
        from analysis_service.modules.h1_meta_optimization import score_h1_meta_optimization

        # Based on scoring doc worked example: "codigo promocional 1xbet"
        target = ExtractionResult(
            title=TitleData(
                title="Codigo Promocional 1xBet: BETGOAL Marzo 2026 - Exclusivo",
                title_length=56,
            ),
            headings=HeadingsData(
                h1_texts=["Codigo Promocional 1xBet Mexico 2026"],
                h1_count=1,
            ),
            meta=MetaData(
                meta_description=(
                    "El codigo promocional 1xBet es BETGOAL (Bono VIP). "
                    "El codigo de registro 1xBet ofrece un bono de bienvenida "
                    "de hasta 300 EUR para apuestas deportivas."
                ),
            ),
            body_text=BodyTextData(
                text="codigo promocional 1xbet " * 20,
            ),
        )
        result = score_h1_meta_optimization(target, "codigo promocional 1xbet")
        assert result.score == 100.0

    def test_accent_stripped_keyword_matches(self) -> None:
        """Close-variant matching: 'codigo' matches 'código' (D-13)."""
        from analysis_service.models import ExtractionResult, HeadingsData, TitleData
        from analysis_service.modules.h1_meta_optimization import score_h1_meta_optimization

        target = ExtractionResult(
            title=TitleData(title="A" * 55),
            headings=HeadingsData(h1_texts=["código promocional es aquí"], h1_count=1),
        )
        result = score_h1_meta_optimization(target, "codigo promocional")
        assert result.keyword_in_h1 is True

    def test_multiple_h1_uses_first_and_warns(self) -> None:
        """Multiple H1 tags: first used for scoring, warning set (D-15)."""
        from analysis_service.models import ExtractionResult, HeadingsData
        from analysis_service.modules.h1_meta_optimization import score_h1_meta_optimization

        target = ExtractionResult(
            headings=HeadingsData(
                h1_texts=["First keyword heading", "Second heading"],
                h1_count=2,
            )
        )
        result = score_h1_meta_optimization(target, "keyword")
        assert result.keyword_in_h1 is True  # "keyword" in first H1
        assert result.multiple_h1_warning is not None
        assert "2" in result.multiple_h1_warning

    def test_title_length_boundaries_inclusive(self) -> None:
        """Title of exactly 50 and exactly 60 chars both pass (10 pts each)."""
        from analysis_service.models import ExtractionResult, TitleData
        from analysis_service.modules.h1_meta_optimization import score_h1_meta_optimization

        for length in (50, 60):
            target = ExtractionResult(title=TitleData(title="x" * length))
            result = score_h1_meta_optimization(target, "keyword")
            assert result.title_length_ok is True, f"Length {length} should pass"
            assert result.title_length_pts == 10

        # Boundary fails
        for length in (49, 61):
            target = ExtractionResult(title=TitleData(title="x" * length))
            result = score_h1_meta_optimization(target, "keyword")
            assert result.title_length_ok is False, f"Length {length} should fail"

    def test_meta_length_boundaries_inclusive(self) -> None:
        """Meta description of 120 and 160 chars both pass (10 pts)."""
        from analysis_service.models import ExtractionResult, MetaData
        from analysis_service.modules.h1_meta_optimization import score_h1_meta_optimization

        for length in (120, 160):
            target = ExtractionResult(meta=MetaData(meta_description="x" * length))
            result = score_h1_meta_optimization(target, "keyword")
            assert result.meta_length_ok is True, f"Meta length {length} should pass"

        for length in (119, 161):
            target = ExtractionResult(meta=MetaData(meta_description="x" * length))
            result = score_h1_meta_optimization(target, "keyword")
            assert result.meta_length_ok is False, f"Meta length {length} should fail"

    def test_h1_identical_to_title_check_6_fails(self) -> None:
        """H1 same as title → h1_differs_from_title=False, 0 pts."""
        from analysis_service.models import ExtractionResult, HeadingsData, TitleData
        from analysis_service.modules.h1_meta_optimization import score_h1_meta_optimization

        target = ExtractionResult(
            title=TitleData(title="Best SEO Tools 2026"),
            headings=HeadingsData(h1_texts=["Best SEO Tools 2026"], h1_count=1),
        )
        result = score_h1_meta_optimization(target, "seo tools")
        assert result.h1_differs_from_title is False
        assert result.h1_differs_from_title_pts == 0

    def test_first_100_words_from_body_text_field(self) -> None:
        """Keyword found in first 100 words from body_text.text (D-14)."""
        from analysis_service.models import BodyTextData, ExtractionResult
        from analysis_service.modules.h1_meta_optimization import score_h1_meta_optimization

        # Keyword in first 100 words only
        words = ["seo"] * 5 + ["other"] * 200
        target = ExtractionResult(
            body_text=BodyTextData(text=" ".join(words))
        )
        result = score_h1_meta_optimization(target, "seo")
        assert result.keyword_in_first_100_words is True

    def test_normalize_text_strips_accents(self) -> None:
        """normalize_text('código') == normalize_text('codigo')."""
        from analysis_service.modules.h1_meta_optimization import normalize_text

        assert normalize_text("código") == normalize_text("codigo")
        assert normalize_text("CÓDIGO PROMOCIONAL") == "codigo promocional"


class TestSchemaMarkup:
    """Tests for score_schema_markup (DET-04)."""

    def test_import(self) -> None:
        from analysis_service.modules.schema_markup import score_schema_markup  # noqa: F401

    def test_returns_result_type(self) -> None:
        from analysis_service.models import ExtractionResult, PageType, SchemaMarkupResult
        from analysis_service.modules.schema_markup import score_schema_markup

        result = score_schema_markup(ExtractionResult(), [], PageType.OTHER)
        assert isinstance(result, SchemaMarkupResult)

    def test_no_schemas_other_page_type(self) -> None:
        """No competitor schemas, page_type=other → relevant=3 recommended types, target has none → score=0."""
        from analysis_service.models import ExtractionResult, PageType
        from analysis_service.modules.schema_markup import score_schema_markup

        result = score_schema_markup(ExtractionResult(), [], PageType.OTHER)
        # Relevant = {Article, BreadcrumbList, WebPage} (D-16 for 'other' page type)
        assert len(result.relevant_types) == 3
        assert result.score == 0.0

    def test_worked_example_code_page(self) -> None:
        """Scoring doc worked example: 3/8 relevant types → score=38 (rounded)."""
        from analysis_service.models import ExtractionResult, JsonldData, PageType
        from analysis_service.modules.schema_markup import score_schema_markup

        target = ExtractionResult(
            jsonld=JsonldData(
                all_schema_types=["Article", "BreadcrumbList", "WebPage"],
            )
        )
        comp1 = ExtractionResult(jsonld=JsonldData(all_schema_types=["Article", "BreadcrumbList", "FAQPage", "WebPage"]))
        comp2 = ExtractionResult(jsonld=JsonldData(all_schema_types=["Article", "BreadcrumbList", "Organization"]))
        comp3 = ExtractionResult(jsonld=JsonldData(all_schema_types=["NewsArticle", "BreadcrumbList"]))
        comp4 = ExtractionResult(jsonld=JsonldData(all_schema_types=["Article", "FAQPage", "HowTo"]))
        comp5 = ExtractionResult(jsonld=JsonldData(all_schema_types=["Article", "BreadcrumbList"]))

        result = score_schema_markup(target, [comp1, comp2, comp3, comp4, comp5], PageType.CODE_PAGE)
        assert result.score == 38.0

    def test_url_normalized_to_short_type(self) -> None:
        """Full schema URL normalized to short type name (D-17)."""
        from analysis_service.models import ExtractionResult, JsonldData, PageType
        from analysis_service.modules.schema_markup import score_schema_markup

        target = ExtractionResult(
            jsonld=JsonldData(all_schema_types=["https://schema.org/Article"])
        )
        result = score_schema_markup(target, [], PageType.OTHER)
        assert "Article" in result.present_types

    def test_http_url_normalized(self) -> None:
        """http:// schema URL also normalized correctly."""
        from analysis_service.models import ExtractionResult, JsonldData, PageType
        from analysis_service.modules.schema_markup import score_schema_markup

        target = ExtractionResult(
            jsonld=JsonldData(all_schema_types=["http://schema.org/BreadcrumbList"])
        )
        result = score_schema_markup(target, [], PageType.OTHER)
        assert "BreadcrumbList" in result.present_types

    def test_relevant_types_sorted(self) -> None:
        """relevant_types field is a sorted list."""
        from analysis_service.models import ExtractionResult, PageType
        from analysis_service.modules.schema_markup import score_schema_markup

        result = score_schema_markup(ExtractionResult(), [], PageType.OTHER)
        assert result.relevant_types == sorted(result.relevant_types)

    def test_missing_types_populated(self) -> None:
        """missing_types = relevant - target schemas."""
        from analysis_service.models import ExtractionResult, PageType
        from analysis_service.modules.schema_markup import score_schema_markup

        result = score_schema_markup(ExtractionResult(), [], PageType.OTHER)
        assert set(result.missing_types) == set(result.relevant_types)

    def test_target_has_all_recommended(self) -> None:
        """Target has all recommended schemas → score=100 (no competitors)."""
        from analysis_service.models import ExtractionResult, JsonldData, PageType
        from analysis_service.modules.schema_markup import score_schema_markup

        target = ExtractionResult(
            jsonld=JsonldData(all_schema_types=["Article", "BreadcrumbList", "WebPage"])
        )
        result = score_schema_markup(target, [], PageType.OTHER)
        assert result.score == 100.0
        assert result.missing_types == []

    def test_competitor_schemas_added_to_relevant(self) -> None:
        """Competitor schemas outside recommended set included in relevant."""
        from analysis_service.models import ExtractionResult, JsonldData, PageType
        from analysis_service.modules.schema_markup import score_schema_markup

        comp = ExtractionResult(jsonld=JsonldData(all_schema_types=["Organization"]))
        result = score_schema_markup(ExtractionResult(), [comp], PageType.OTHER)
        assert "Organization" in result.relevant_types


class TestOverallScore:
    """Tests for score_overall (DET-05, DET-07)."""

    def test_import(self) -> None:
        from analysis_service.modules.overall_score import score_overall  # noqa: F401

    def test_null_module_returns_none_overall(self) -> None:
        """Any weighted module score=None → overall_score=None, priority_modules excludes nulls (D-20)."""
        from analysis_service.models import (
            AnalysisResult,
            H1MetaOptimizationResult,
            HtmlElementGapResult,
            SchemaMarkupResult,
            SerpFeatureOpportunityResult,
        )
        from analysis_service.modules.overall_score import score_overall

        partial = AnalysisResult(
            html_element_gap=HtmlElementGapResult(score=67.0),
            h1_meta_optimization=H1MetaOptimizationResult(score=100.0),
            serp_feature_opportunity=SerpFeatureOpportunityResult(score=100.0),
            schema_markup=SchemaMarkupResult(score=38.0),
            # information_gap is None (Phase 12)
        )
        overall, priority = score_overall(partial)
        assert overall is None
        assert "h1_meta_optimization" in priority or "html_element_gap" in priority

    def test_priority_list_ascending_order(self) -> None:
        """Priority list sorted ascending by score (D-22)."""
        from analysis_service.models import (
            AnalysisResult,
            H1MetaOptimizationResult,
            HtmlElementGapResult,
            InformationGapResult,
            SchemaMarkupResult,
            SerpFeatureOpportunityResult,
        )
        from analysis_service.modules.overall_score import score_overall

        full = AnalysisResult(
            html_element_gap=HtmlElementGapResult(score=67.0),
            h1_meta_optimization=H1MetaOptimizationResult(score=100.0),
            serp_feature_opportunity=SerpFeatureOpportunityResult(score=100.0),
            schema_markup=SchemaMarkupResult(score=38.0),
            information_gap=InformationGapResult(score=25.0),
        )
        _, priority = score_overall(full)
        # Lowest first: information_gap(25), schema_markup(38), html_element_gap(67)
        module_score_map = {
            "information_gap": 25.0,
            "schema_markup": 38.0,
            "html_element_gap": 67.0,
            "h1_meta_optimization": 100.0,
            "serp_feature_opportunity": 100.0,
        }
        scores = [module_score_map[name] for name in priority if name in module_score_map]
        assert scores == sorted(scores)

    def test_worked_example_all_modules(self) -> None:
        """Scoring doc §Module 7 worked example: overall=63."""
        from analysis_service.models import (
            AnalysisResult,
            H1MetaOptimizationResult,
            HtmlElementGapResult,
            InformationGapResult,
            SchemaMarkupResult,
            SerpFeatureOpportunityResult,
        )
        from analysis_service.modules.overall_score import score_overall

        full = AnalysisResult(
            information_gap=InformationGapResult(score=25.0),
            h1_meta_optimization=H1MetaOptimizationResult(score=100.0),
            serp_feature_opportunity=SerpFeatureOpportunityResult(score=100.0),
            html_element_gap=HtmlElementGapResult(score=67.0),
            schema_markup=SchemaMarkupResult(score=38.0),
        )
        overall, priority = score_overall(full)
        assert overall == 63.0

    def test_tie_broken_alphabetically(self) -> None:
        """Two modules at 100: h1_meta_optimization before serp_feature_opportunity."""
        from analysis_service.models import (
            AnalysisResult,
            H1MetaOptimizationResult,
            HtmlElementGapResult,
            InformationGapResult,
            SchemaMarkupResult,
            SerpFeatureOpportunityResult,
        )
        from analysis_service.modules.overall_score import score_overall

        full = AnalysisResult(
            information_gap=InformationGapResult(score=25.0),
            h1_meta_optimization=H1MetaOptimizationResult(score=100.0),
            serp_feature_opportunity=SerpFeatureOpportunityResult(score=100.0),
            html_element_gap=HtmlElementGapResult(score=67.0),
            schema_markup=SchemaMarkupResult(score=38.0),
        )
        _, priority = score_overall(full)
        h1_idx = priority.index("h1_meta_optimization")
        serp_idx = priority.index("serp_feature_opportunity")
        assert h1_idx < serp_idx

    def test_all_null_modules(self) -> None:
        """All module results None → overall=None, priority=[]."""
        from analysis_service.models import AnalysisResult
        from analysis_service.modules.overall_score import score_overall

        overall, priority = score_overall(AnalysisResult())
        assert overall is None
        assert priority == []

    def test_weights_sum_to_one(self) -> None:
        """_WEIGHTS values sum to exactly 1.0."""
        from analysis_service.modules.overall_score import _WEIGHTS

        assert abs(sum(_WEIGHTS.values()) - 1.0) < 1e-9

    def test_priority_only_non_null_modules(self) -> None:
        """Modules with null scores excluded from priority list."""
        from analysis_service.models import (
            AnalysisResult,
            H1MetaOptimizationResult,
            SchemaMarkupResult,
        )
        from analysis_service.modules.overall_score import score_overall

        partial = AnalysisResult(
            h1_meta_optimization=H1MetaOptimizationResult(score=75.0),
            schema_markup=SchemaMarkupResult(score=50.0),
        )
        _, priority = score_overall(partial)
        assert "h1_meta_optimization" in priority
        assert "schema_markup" in priority
        assert "information_gap" not in priority
        assert "html_element_gap" not in priority
        assert "serp_feature_opportunity" not in priority

    def test_priority_ascending_order_verified(self) -> None:
        """Priority list scores are strictly non-decreasing."""
        from analysis_service.models import (
            AnalysisResult,
            H1MetaOptimizationResult,
            HtmlElementGapResult,
            InformationGapResult,
            SchemaMarkupResult,
            SerpFeatureOpportunityResult,
        )
        from analysis_service.modules.overall_score import score_overall

        full = AnalysisResult(
            information_gap=InformationGapResult(score=25.0),
            h1_meta_optimization=H1MetaOptimizationResult(score=100.0),
            serp_feature_opportunity=SerpFeatureOpportunityResult(score=100.0),
            html_element_gap=HtmlElementGapResult(score=67.0),
            schema_markup=SchemaMarkupResult(score=38.0),
        )
        _, priority = score_overall(full)
        score_map = {
            "information_gap": 25.0,
            "schema_markup": 38.0,
            "html_element_gap": 67.0,
            "h1_meta_optimization": 100.0,
            "serp_feature_opportunity": 100.0,
        }
        scores_in_order = [score_map[m] for m in priority]
        assert scores_in_order == sorted(scores_in_order)
