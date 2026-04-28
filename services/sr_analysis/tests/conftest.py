"""Shared pytest fixtures for analysis_service tests."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Generator

import pytest
from fastapi.testclient import TestClient

from analysis_service.bc_config import BcBestPracticesConfig, load_bc_config
from analysis_service.gemini_client import FakeGeminiClient, get_gemini_client
from analysis_service.router import get_bc_config, get_settings


@pytest.fixture
def bc_yaml_path(tmp_path: Path) -> str:
    """Create a minimal valid bc_best_practices.yaml for tests."""
    yaml_content = 'version: "1.0"\npage_type_priority: {}\nuniversal_rules: {}\npage_types: {}\n'
    yaml_file = tmp_path / "bc_best_practices.yaml"
    yaml_file.write_text(yaml_content)
    return str(yaml_file)


@pytest.fixture
def required_env(monkeypatch: pytest.MonkeyPatch, bc_yaml_path: str) -> None:
    """Set required env vars so Settings() does not raise ValidationError."""
    monkeypatch.setenv("ANALYSIS_GEMINI_API_KEY", "test-api-key")
    monkeypatch.setenv("ANALYSIS_GEMINI_MODEL", "gemini-2.5-flash")
    monkeypatch.setenv("ANALYSIS_PORT", "6969")
    monkeypatch.setenv("ANALYSIS_BC_BEST_PRACTICES_PATH", bc_yaml_path)


@pytest.fixture
def fake_gemini_client() -> FakeGeminiClient:
    """FakeGeminiClient with default token count of 100."""
    return FakeGeminiClient(token_count=100)


@pytest.fixture
def _minimal_bc_config(bc_yaml_path: str) -> BcBestPracticesConfig:
    return load_bc_config(bc_yaml_path)


def _setup_client_overrides(
    app: object,
    gemini_client: FakeGeminiClient,
    bc_config: BcBestPracticesConfig,
    required_env: None,
) -> None:
    """Wire dependency overrides and init semaphore for all test clients."""
    import analysis_service.router as _router
    from analysis_service.settings import Settings

    settings = Settings()
    app.dependency_overrides[get_gemini_client] = lambda: gemini_client  # type: ignore[attr-defined]
    app.dependency_overrides[get_bc_config] = lambda: bc_config  # type: ignore[attr-defined]
    app.dependency_overrides[get_settings] = lambda: settings  # type: ignore[attr-defined]
    if _router._gemini_semaphore is None:
        _router._gemini_semaphore = asyncio.Semaphore(settings.max_concurrent_gemini_calls)


@pytest.fixture
def client(required_env: None, fake_gemini_client: FakeGeminiClient, _minimal_bc_config: BcBestPracticesConfig) -> Generator[TestClient, None, None]:
    """FastAPI TestClient with required env vars and FakeGeminiClient injected."""
    from analysis_service.app import app

    _setup_client_overrides(app, fake_gemini_client, _minimal_bc_config, required_env)
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def fake_gemini_client_with_fixtures() -> FakeGeminiClient:
    """FakeGeminiClient pre-loaded with response fixtures for all 4 Gemini modules."""
    from typing import Any

    from analysis_service.models import (
        ContentBestPracticesL1GeminiResponse,
        GeminiBestPractice,
        GeminiBloat,
        GeminiGeneratedSchema,
        GeminiLlmDimension,
        GeminiStructuralSuggestion,
        GeminiTopic,
        InformationGapGeminiResponse,
        LlmOptimizationGeminiResponse,
        SchemaJsonLdGeminiResponse,
    )

    responses: dict[type, Any] = {
        InformationGapGeminiResponse: InformationGapGeminiResponse(
            topics=[
                GeminiTopic(
                    topic="Payment methods",
                    competitor_coverage="2/3",
                    competitors_covering=2,
                    is_important=True,
                    covered_by_target=True,
                    suggested_heading="Payment Methods Guide",
                    content_summary="Explain deposit and withdrawal options.",
                ),
                GeminiTopic(
                    topic="Customer support",
                    competitor_coverage="3/3",
                    competitors_covering=3,
                    is_important=True,
                    covered_by_target=False,
                    suggested_heading="Customer Support Contacts",
                    content_summary="List phone, email, and chat options.",
                ),
            ],
            bloat=[
                GeminiBloat(
                    section="Weekly Promotions",
                    reason="Temporal content that expires quickly",
                    recommendation="remove",
                ),
            ],
        ),
        ContentBestPracticesL1GeminiResponse: ContentBestPracticesL1GeminiResponse(
            intent_summary="User wants a promotional code and registration guide.",
            best_practices=[
                GeminiBestPractice(
                    name="Code prominently displayed",
                    description="Promo code visible in first viewport",
                    pass_=True,
                    evidence="Code found in first paragraph",
                    recommendation=None,
                ),
                GeminiBestPractice(
                    name="Step-by-step guide",
                    description="Clear registration steps",
                    pass_=False,
                    evidence="No numbered steps found",
                    recommendation="Add numbered registration steps",
                ),
            ],
            structural_suggestions=[
                GeminiStructuralSuggestion(
                    heading="How to Register",
                    rationale="Users need clear registration flow",
                ),
            ],
        ),
        SchemaJsonLdGeminiResponse: SchemaJsonLdGeminiResponse(
            schemas=[
                GeminiGeneratedSchema(
                    schema_type="FAQPage",
                    json_ld='{"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": []}',
                ),
            ],
        ),
        LlmOptimizationGeminiResponse: LlmOptimizationGeminiResponse(
            dimensions=[
                GeminiLlmDimension(
                    name="direct_answers",
                    score=70.0,
                    evidence="Some direct answers found",
                    recommendation="Add more concise answers",
                ),
                GeminiLlmDimension(
                    name="entity_clarity",
                    score=80.0,
                    evidence="Key entities well-defined",
                    recommendation=None,
                ),
                GeminiLlmDimension(
                    name="quotable_passages",
                    score=60.0,
                    evidence="Few self-contained quotable sentences",
                    recommendation="Create standalone summary sentences",
                ),
            ],
        ),
    }
    return FakeGeminiClient(responses=responses, token_count=100)


@pytest.fixture
def client_with_gemini(
    required_env: None, fake_gemini_client_with_fixtures: FakeGeminiClient, _minimal_bc_config: BcBestPracticesConfig,
) -> Generator[TestClient, None, None]:
    """FastAPI TestClient with FakeGeminiClient pre-loaded with all module fixtures."""
    from analysis_service.app import app

    _setup_client_overrides(app, fake_gemini_client_with_fixtures, _minimal_bc_config, required_env)
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def async_client(required_env: None, fake_gemini_client: FakeGeminiClient, _minimal_bc_config: BcBestPracticesConfig) -> Generator[TestClient, None, None]:
    """FastAPI TestClient for async endpoint tests — clears _jobs between tests."""
    from analysis_service.app import app
    from analysis_service.router import _jobs

    _jobs.clear()
    _setup_client_overrides(app, fake_gemini_client, _minimal_bc_config, required_env)
    yield TestClient(app)
    app.dependency_overrides.clear()
    _jobs.clear()


@pytest.fixture
def async_client_with_gemini(
    required_env: None, fake_gemini_client_with_fixtures: FakeGeminiClient, _minimal_bc_config: BcBestPracticesConfig,
) -> Generator[TestClient, None, None]:
    """TestClient with FakeGeminiClient fixtures — for async endpoint integration tests."""
    from analysis_service.app import app
    from analysis_service.router import _jobs

    _jobs.clear()
    _setup_client_overrides(app, fake_gemini_client_with_fixtures, _minimal_bc_config, required_env)
    yield TestClient(app)
    app.dependency_overrides.clear()
    _jobs.clear()
