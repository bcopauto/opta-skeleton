"""Tests for the 5 new SERP features, cost metadata, and feature count."""
from __future__ import annotations

import pytest

from scraper_service.serp.extractor import extract_features
from scraper_service.serp.models import CostMetadata, SerpFeatures, SerpResponse
from scraper_service.serp.scorer import calculate_difficulty_score


# ---------------------------------------------------------------------------
# New SERP feature flag tests
# ---------------------------------------------------------------------------


class TestNewSerpFeatures:
    def test_twitter_cards(self) -> None:
        features = extract_features({"twitter_results": [{"title": "tweet"}]})
        assert features.has_twitter_cards is True

    def test_twitter_cards_absent(self) -> None:
        features = extract_features({})
        assert features.has_twitter_cards is False

    def test_discussions_forums(self) -> None:
        features = extract_features({"discussions_and_forums": [{"title": "thread"}]})
        assert features.has_discussions_forums is True

    def test_discussions_forums_absent(self) -> None:
        features = extract_features({})
        assert features.has_discussions_forums is False

    def test_instant_answer_no_link(self) -> None:
        features = extract_features({"answer_box": {"snippet": "42 degrees"}})
        assert features.has_instant_answer is True
        # Also has_featured_snippet should be True (answer_box present)
        assert features.has_featured_snippet is True

    def test_instant_answer_not_calculator(self) -> None:
        features = extract_features({"answer_box": {"type": "calculator", "result": "42"}})
        assert features.has_instant_answer is False
        assert features.has_calculator is True

    def test_instant_answer_false_when_link_present(self) -> None:
        features = extract_features({"answer_box": {"snippet": "Answer", "link": "https://example.com"}})
        assert features.has_instant_answer is False
        assert features.has_featured_snippet is True

    def test_calculator(self) -> None:
        features = extract_features({"answer_box": {"type": "calculator", "result": "100"}})
        assert features.has_calculator is True

    def test_calculator_absent(self) -> None:
        features = extract_features({})
        assert features.has_calculator is False

    def test_faq_rich_results_via_questions(self) -> None:
        features = extract_features({
            "organic_results": [
                {"title": "Result", "rich_snippet": {"bottom": {"questions": [{"q": "What?"}]}}}
            ]
        })
        assert features.has_faq_rich_results is True

    def test_faq_rich_results_via_detected_extensions(self) -> None:
        features = extract_features({
            "organic_results": [
                {"title": "Result", "rich_snippet": {"bottom": {"detected_extensions": {"faq": True}}}}
            ]
        })
        assert features.has_faq_rich_results is True

    def test_faq_rich_results_absent(self) -> None:
        features = extract_features({"organic_results": [{"title": "Result"}]})
        assert features.has_faq_rich_results is False


class TestAllFlagsOnEmptyData:
    def test_all_19_false(self) -> None:
        features = extract_features({})
        for field_name in SerpFeatures.model_fields:
            assert getattr(features, field_name) is False


class TestFeatureCount:
    def test_exactly_19_fields(self) -> None:
        assert len(SerpFeatures.model_fields) == 19


# ---------------------------------------------------------------------------
# Saturation scoring with new features
# ---------------------------------------------------------------------------


class TestSaturationWithNewFeatures:
    def test_new_features_increase_saturation(self) -> None:
        from scraper_service.serp.models import OrganicResult

        # Only old features
        features_old = SerpFeatures(has_ads_top=True, has_featured_snippet=True)
        score_old = calculate_difficulty_score(features_old, [], "test keyword")

        # Old + new features
        features_new = SerpFeatures(
            has_ads_top=True,
            has_featured_snippet=True,
            has_twitter_cards=True,
            has_discussions_forums=True,
            has_faq_rich_results=True,
        )
        score_new = calculate_difficulty_score(features_new, [], "test keyword")

        # More features should increase the saturation component
        assert score_new.component_breakdown["feature_saturation"] > score_old.component_breakdown["feature_saturation"]


# ---------------------------------------------------------------------------
# Cost metadata tests
# ---------------------------------------------------------------------------


class TestCostMetadata:
    def test_defaults(self) -> None:
        cost = CostMetadata()
        assert cost.serp_api_calls == 1
        assert cost.serp_api_credits_used is None
        assert cost.serp_api_total_time_taken is None
        assert cost.fetch_duration_ms is None

    def test_with_values(self) -> None:
        cost = CostMetadata(
            serp_api_calls=1,
            serp_api_credits_used=1.0,
            serp_api_total_time_taken=2.5,
            fetch_duration_ms=1500.3,
        )
        assert cost.serp_api_credits_used == 1.0
        assert cost.fetch_duration_ms == 1500.3

    def test_serialization(self) -> None:
        cost = CostMetadata(fetch_duration_ms=100.0)
        data = cost.model_dump()
        assert data["serp_api_calls"] == 1
        assert data["fetch_duration_ms"] == 100.0


class TestSerpResponseWithCost:
    def test_cost_field_optional(self) -> None:
        """SerpResponse works without cost (backward compat)."""
        from scraper_service.serp.models import DifficultyScore, SerpSnapshot

        resp = SerpResponse(
            keyword="test",
            keyword_norm="test",
            market="US",
            language="en",
            features=SerpFeatures(),
            organic_results=[],
            paa_items=[],
            ads_top=[],
            ads_bottom=[],
            featured_snippet=None,
            shopping_results=[],
            top_stories=[],
            knowledge_panel=None,
            videos=[],
            images=[],
            serp_urls=[],
            snapshot=SerpSnapshot(),
            difficulty_score=DifficultyScore(total_score=50.0, label="Medium", component_breakdown={}),
        )
        assert resp.cost is None

    def test_cost_field_populated(self) -> None:
        from scraper_service.serp.models import DifficultyScore, SerpSnapshot

        cost = CostMetadata(serp_api_calls=1, fetch_duration_ms=200.0)
        resp = SerpResponse(
            keyword="test",
            keyword_norm="test",
            market="US",
            language="en",
            features=SerpFeatures(),
            organic_results=[],
            paa_items=[],
            ads_top=[],
            ads_bottom=[],
            featured_snippet=None,
            shopping_results=[],
            top_stories=[],
            knowledge_panel=None,
            videos=[],
            images=[],
            serp_urls=[],
            snapshot=SerpSnapshot(),
            difficulty_score=DifficultyScore(total_score=50.0, label="Medium", component_breakdown={}),
            cost=cost,
        )
        assert resp.cost is not None
        assert resp.cost.fetch_duration_ms == 200.0
        # Verify it serializes
        data = resp.model_dump(mode="json")
        assert data["cost"]["serp_api_calls"] == 1
