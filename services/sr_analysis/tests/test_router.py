"""Integration tests for POST /analyze endpoint (ANLYS-03, ANLYS-06, DET-01 through DET-07)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


_BASE_PAYLOAD: dict = {
    "target": {},
    "competitors": [],
    "keyword": "best casino sites",
    "market": "GB",
    "page_type": "comparator",
}


def test_analyze_returns_200_with_real_scores(client: TestClient) -> None:
    """POST /analyze returns 200 with real deterministic scores (not all-None after Phase 10)."""
    resp = client.post("/analyze", json=_BASE_PAYLOAD)
    assert resp.status_code == 200
    data = resp.json()
    # All 4 deterministic modules must return non-null results
    assert data["html_element_gap"] is not None
    assert data["h1_meta_optimization"] is not None
    assert data["schema_markup"] is not None
    # serp_feature_opportunity returns result object even when serp_features not in request
    assert data["serp_feature_opportunity"] is not None
    # overall_score is None when information_gap is null (plain client has no Gemini fixtures)
    assert data["overall_score"] is None
    # Gemini modules null with plain client (no fixtures configured)
    assert data["information_gap"] is None
    # content_best_practices is non-null: L2 (deterministic) runs in Wave 1
    assert data["content_best_practices"] is not None
    assert data["content_best_practices"]["l2_score"] is not None
    assert data["content_best_practices"]["l1_score"] is None  # L1 needs Gemini
    assert data["schema_json_ld"] is None
    assert data["llm_optimization"] is None


def test_analyze_html_element_gap_score_100_no_competitors(client: TestClient) -> None:
    """Empty target with no competitors → html_element_gap.score=100 (nothing commonly used)."""
    resp = client.post("/analyze", json=_BASE_PAYLOAD)
    assert resp.status_code == 200
    data = resp.json()
    assert data["html_element_gap"]["score"] == 100.0


def test_analyze_h1_meta_score_zero_empty_target(client: TestClient) -> None:
    """Empty target ExtractionResult → h1_meta_optimization.score=0 (all checks fail)."""
    resp = client.post("/analyze", json=_BASE_PAYLOAD)
    assert resp.status_code == 200
    data = resp.json()
    assert data["h1_meta_optimization"]["score"] == 0.0


def test_analyze_serp_features_none_returns_null_serp_score(client: TestClient) -> None:
    """Request without serp_features → serp_feature_opportunity.score=None (D-07)."""
    payload = {**_BASE_PAYLOAD, "serp_features": None}
    resp = client.post("/analyze", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["serp_feature_opportunity"]["score"] is None


def test_analyze_serp_features_provided_returns_real_score(client: TestClient) -> None:
    """Request with serp_features → serp_feature_opportunity.score is a float."""
    payload = {
        **_BASE_PAYLOAD,
        "serp_features": {"has_ai_overview": True},  # non-assessable only → score=100
    }
    resp = client.post("/analyze", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["serp_feature_opportunity"]["score"] == 100.0


def test_analyze_schema_markup_returns_score(client: TestClient) -> None:
    """POST with page_type → schema_markup.score is a float (0-100)."""
    resp = client.post("/analyze", json=_BASE_PAYLOAD)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["schema_markup"]["score"], (int, float))
    assert 0 <= data["schema_markup"]["score"] <= 100


def test_analyze_priority_modules_ascending(client: TestClient) -> None:
    """priority_modules contains modules sorted ascending by score."""
    payload = {
        **_BASE_PAYLOAD,
        "serp_features": {"has_ai_overview": True},  # gives serp_feature_opportunity a non-null score
    }
    resp = client.post("/analyze", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    priority = data["priority_modules"]
    assert isinstance(priority, list)
    module_scores = {
        "html_element_gap": data["html_element_gap"]["score"] if data["html_element_gap"] else None,
        "h1_meta_optimization": data["h1_meta_optimization"]["score"] if data["h1_meta_optimization"] else None,
        "serp_feature_opportunity": data["serp_feature_opportunity"]["score"] if data["serp_feature_opportunity"] else None,
        "schema_markup": data["schema_markup"]["score"] if data["schema_markup"] else None,
    }
    priority_scores = [
        module_scores[m] for m in priority if m in module_scores and module_scores[m] is not None
    ]
    assert priority_scores == sorted(priority_scores)


def test_analyze_overall_score_null_phase10(client: TestClient) -> None:
    """overall_score is None in Phase 10 — information_gap not wired (expected, D-21)."""
    payload = {**_BASE_PAYLOAD, "serp_features": {"has_ai_overview": True}}
    resp = client.post("/analyze", json=payload)
    assert resp.status_code == 200
    assert resp.json()["overall_score"] is None


def test_analyze_rejects_invalid_page_type(client: TestClient) -> None:
    """POST /analyze with invalid page_type returns 422."""
    payload = {**_BASE_PAYLOAD, "page_type": "not_a_valid_type"}
    resp = client.post("/analyze", json=payload)
    assert resp.status_code == 422


def test_analyze_rejects_missing_keyword(client: TestClient) -> None:
    """POST /analyze without keyword returns 422."""
    payload = {k: v for k, v in _BASE_PAYLOAD.items() if k != "keyword"}
    resp = client.post("/analyze", json=payload)
    assert resp.status_code == 422


def test_analyze_logs_correlation_id(client: TestClient) -> None:
    """POST /analyze completes without 500 (correlation ID binding smoke test)."""
    resp = client.post("/analyze", json=_BASE_PAYLOAD)
    assert resp.status_code == 200


def test_analyze_accepts_optional_serp_features(client: TestClient) -> None:
    """Both serp_features=null and with SerpFeatures object return 200."""
    base = {**_BASE_PAYLOAD}
    resp1 = client.post("/analyze", json={**base, "serp_features": None})
    assert resp1.status_code == 200

    resp2 = client.post("/analyze", json={**base, "serp_features": {"has_featured_snippet": True}})
    assert resp2.status_code == 200


# ---------------------------------------------------------------------------
# Phase 12: Wave 2 integration tests (Gemini modules)
# ---------------------------------------------------------------------------


def test_analyze_returns_all_9_modules(client_with_gemini: TestClient) -> None:
    payload = {
        "target": {},
        "competitors": [{}],
        "keyword": "best casino sites",
        "market": "GB",
        "page_type": "comparator",
        "serp_features": {"has_featured_snippet": True},
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


def test_analyze_information_gap_fields(client_with_gemini: TestClient) -> None:
    payload = {
        "target": {},
        "competitors": [{}],
        "keyword": "best casino sites",
        "market": "GB",
        "page_type": "comparator",
    }
    resp = client_with_gemini.post("/analyze", json=payload)
    assert resp.status_code == 200
    ig = resp.json()["information_gap"]
    assert ig is not None
    assert "score" in ig
    assert "topics_to_add" in ig
    assert "topics_to_trim" in ig
    assert "breakdown" in ig


def test_analyze_content_best_practices_has_l1_and_l2(client_with_gemini: TestClient) -> None:
    payload = {
        "target": {},
        "competitors": [],
        "keyword": "promo code",
        "market": "GB",
        "page_type": "code_page",
    }
    resp = client_with_gemini.post("/analyze", json=payload)
    assert resp.status_code == 200
    bp = resp.json()["content_best_practices"]
    assert bp is not None
    assert bp["l1_score"] is not None
    assert bp["l2_score"] is not None


def test_analyze_llm_optimization_dimensions(client_with_gemini: TestClient) -> None:
    payload = {
        "target": {},
        "competitors": [],
        "keyword": "best casino",
        "market": "GB",
        "page_type": "comparator",
    }
    resp = client_with_gemini.post("/analyze", json=payload)
    assert resp.status_code == 200
    llm = resp.json()["llm_optimization"]
    assert llm is not None
    assert llm["score"] is not None
    assert len(llm["dimensions"]) == 8


def test_analyze_gemini_failure_graceful(client: TestClient) -> None:
    payload = {
        "target": {},
        "competitors": [],
        "keyword": "best casino",
        "market": "GB",
        "page_type": "comparator",
    }
    resp = client.post("/analyze", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["html_element_gap"] is not None
    assert data["h1_meta_optimization"] is not None


def test_analyze_overall_score_now_computed(client_with_gemini: TestClient) -> None:
    payload = {
        "target": {},
        "competitors": [{}],
        "keyword": "best casino",
        "market": "GB",
        "page_type": "comparator",
        "serp_features": {"has_featured_snippet": True},
    }
    resp = client_with_gemini.post("/analyze", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["overall_score"] is not None
    assert isinstance(data["overall_score"], (int, float))
    assert 0 <= data["overall_score"] <= 100


def test_analyze_single_module_failure_returns_200(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """One module raises → HTTP 200 returned with that field null (ANLYS-06, D-23)."""
    import analysis_service.router as router_mod

    def boom(*args, **kwargs):  # noqa: ANN201, ANN002, ANN003
        raise RuntimeError("simulated module failure")

    # Patch the function as imported into the router's namespace
    monkeypatch.setattr(router_mod, "score_html_element_gap", boom)

    resp = client.post("/analyze", json=_BASE_PAYLOAD)
    assert resp.status_code == 200
    data = resp.json()
    # html_element_gap failed → null
    assert data["html_element_gap"] is None
    # Others still populated
    assert data["h1_meta_optimization"] is not None
    assert data["schema_markup"] is not None
