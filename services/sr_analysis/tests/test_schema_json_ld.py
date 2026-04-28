from __future__ import annotations

import json

import pytest

from analysis_service.gemini_client import FakeGeminiClient
from analysis_service.models import (
    ExtractionResult,
    GeminiGeneratedSchema,
    PageType,
    SchemaJsonLdGeminiResponse,
)
from analysis_service.modules.schema_json_ld import (
    _validate_schema_block,
    score_schema_json_ld,
)


# --- _validate_schema_block tests ---


def test_valid_json_ld() -> None:
    block = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": []}
    status, errors = _validate_schema_block(block, ["FAQPage"])
    assert status == "valid"
    assert errors == []


def test_missing_context() -> None:
    block = {"@type": "FAQPage"}
    status, errors = _validate_schema_block(block, ["FAQPage"])
    assert status == "invalid"
    assert any("@context" in e for e in errors)


def test_missing_type() -> None:
    block = {"@context": "https://schema.org"}
    status, errors = _validate_schema_block(block, ["FAQPage"])
    assert status == "invalid"
    assert any("@type" in e for e in errors)


def test_type_not_in_missing_types() -> None:
    block = {"@context": "https://schema.org", "@type": "Article"}
    status, errors = _validate_schema_block(block, ["FAQPage"])
    assert status == "invalid"
    assert any("not in missing types" in e for e in errors)


def test_type_in_missing_types_valid() -> None:
    block = {"@context": "https://schema.org", "@type": "FAQPage"}
    status, errors = _validate_schema_block(block, ["FAQPage", "Article"])
    assert status == "valid"


# --- score_schema_json_ld tests ---


@pytest.mark.asyncio
async def test_empty_missing_types_returns_empty() -> None:
    client = FakeGeminiClient()
    result = await score_schema_json_ld(ExtractionResult(), [], "kw", PageType.OTHER, client)
    assert result.total_generated == 0
    assert result.generated_schemas == []


@pytest.mark.asyncio
async def test_calls_gemini_with_missing_types() -> None:
    fixture = SchemaJsonLdGeminiResponse(
        schemas=[
            GeminiGeneratedSchema(
                schema_type="FAQPage",
                json_ld=json.dumps({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": []}),
            ),
        ],
    )
    client = FakeGeminiClient(responses={SchemaJsonLdGeminiResponse: fixture})
    result = await score_schema_json_ld(ExtractionResult(), ["FAQPage"], "kw", PageType.COMPARATOR, client)
    assert result.total_generated == 1
    assert result.valid_count == 1
    assert result.invalid_count == 0


@pytest.mark.asyncio
async def test_valid_plus_invalid_equals_total() -> None:
    fixture = SchemaJsonLdGeminiResponse(
        schemas=[
            GeminiGeneratedSchema(schema_type="FAQPage", json_ld=json.dumps({"@context": "https://schema.org", "@type": "FAQPage"})),
            GeminiGeneratedSchema(schema_type="Article", json_ld=json.dumps({"@type": "Article"})),
        ],
    )
    client = FakeGeminiClient(responses={SchemaJsonLdGeminiResponse: fixture})
    result = await score_schema_json_ld(ExtractionResult(), ["FAQPage", "Article"], "kw", PageType.OTHER, client)
    assert result.valid_count + result.invalid_count == result.total_generated


@pytest.mark.asyncio
async def test_json_ld_is_string_not_dict() -> None:
    fixture = SchemaJsonLdGeminiResponse(
        schemas=[
            GeminiGeneratedSchema(schema_type="FAQPage", json_ld=json.dumps({"@context": "https://schema.org", "@type": "FAQPage"})),
        ],
    )
    client = FakeGeminiClient(responses={SchemaJsonLdGeminiResponse: fixture})
    result = await score_schema_json_ld(ExtractionResult(), ["FAQPage"], "kw", PageType.OTHER, client)
    assert isinstance(result.generated_schemas[0].json_ld, str)


@pytest.mark.asyncio
async def test_prompt_includes_missing_types() -> None:
    from unittest.mock import AsyncMock

    mock_client = AsyncMock()
    mock_client.generate.return_value = SchemaJsonLdGeminiResponse(schemas=[])
    await score_schema_json_ld(ExtractionResult(), ["FAQPage", "Article"], "kw", PageType.OTHER, mock_client)
    prompt_arg = mock_client.generate.call_args[0][0]
    assert "FAQPage" in prompt_arg
    assert "Article" in prompt_arg
