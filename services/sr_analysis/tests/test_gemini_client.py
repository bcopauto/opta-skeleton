from __future__ import annotations

import pytest
from pydantic import BaseModel

from analysis_service.gemini_client import (
    FakeGeminiClient,
    GeminiClient,
    GeminiClientImpl,
    TokenCeilingExceededError,
    get_gemini_client,
)


class SampleResponse(BaseModel):
    score: float
    items: list[str]


@pytest.mark.asyncio
async def test_fake_client_count_tokens():
    client = FakeGeminiClient(token_count=42)
    result = await client.count_tokens("test prompt")
    assert result == 42


@pytest.mark.asyncio
async def test_fake_client_generate_returns_fixture():
    fixture = SampleResponse(score=0.85, items=["a", "b"])
    client = FakeGeminiClient(responses={SampleResponse: fixture})
    result = await client.generate("test", SampleResponse)
    assert result.score == 0.85
    assert result.items == ["a", "b"]


@pytest.mark.asyncio
async def test_fake_client_generate_raises_for_unknown_schema():
    client = FakeGeminiClient()
    with pytest.raises(ValueError, match="SampleResponse"):
        await client.generate("test", SampleResponse)


def test_fake_client_satisfies_protocol():
    assert isinstance(FakeGeminiClient(), GeminiClient)


def test_token_ceiling_exceeded_error_message():
    exc = TokenCeilingExceededError(150000, 100000)
    assert "150000" in str(exc)
    assert "100000" in str(exc)


def test_get_gemini_client_returns_impl(required_env):
    result = get_gemini_client()
    assert isinstance(result, GeminiClientImpl)


def test_gemini_client_impl_has_correct_model(required_env):
    from analysis_service.settings import Settings

    client = GeminiClientImpl(Settings())
    assert client._model == "gemini-2.5-flash"


def test_gemini_client_impl_has_correct_ceiling(required_env):
    from analysis_service.settings import Settings

    client = GeminiClientImpl(Settings())
    assert client._token_ceiling == 100_000
