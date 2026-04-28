from __future__ import annotations

import json
from typing import Any, Protocol, TypeVar, runtime_checkable

from google import genai
from google.genai import types

from analysis_service.logging import get_logger
from analysis_service.settings import Settings

T = TypeVar("T")
logger = get_logger()


class TokenCeilingExceededError(Exception):
    def __init__(self, token_count: int, ceiling: int) -> None:
        super().__init__(f"Token count {token_count} exceeds ceiling {ceiling}")
        self.token_count = token_count
        self.ceiling = ceiling


@runtime_checkable
class GeminiClient(Protocol):
    async def generate(self, prompt: str, schema: type[T]) -> T: ...
    async def count_tokens(self, prompt: str) -> int: ...


class GeminiClientImpl:
    def __init__(self, settings: Settings) -> None:
        self._model = settings.gemini_model
        self._token_ceiling = settings.token_ceiling_per_module
        self._client = genai.Client(
            api_key=settings.gemini_api_key.get_secret_value(),
            http_options=types.HttpOptions(
                api_version="v1beta",
                retry_options=types.HttpRetryOptions(
                    initial_delay=2.0,
                    attempts=5,
                    exp_base=2,
                    http_status_codes=[429, 503],
                ),
            ),
        )

    async def count_tokens(self, prompt: str) -> int:
        response = await self._client.aio.models.count_tokens(
            model=self._model, contents=prompt
        )
        return response.total_tokens

    async def generate(self, prompt: str, schema: type[T]) -> T:
        token_count = await self.count_tokens(prompt)
        if token_count > self._token_ceiling:
            logger.error(
                "token_ceiling_exceeded",
                token_count=token_count,
                ceiling=self._token_ceiling,
            )
            raise TokenCeilingExceededError(token_count, self._token_ceiling)

        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )

        usage = response.usage_metadata
        logger.info(
            "gemini_call_complete",
            total_token_count=usage.total_token_count if usage else 0,
            cached_content_token_count=getattr(usage, "cached_content_token_count", None) or 0 if usage else 0,
        )

        parsed = response.parsed
        if parsed is not None:
            return schema.model_validate(parsed.model_dump())
        raw_text = response.text
        if raw_text:
            return schema.model_validate(json.loads(raw_text))
        raise ValueError("Gemini returned neither parsed result nor text")


class FakeGeminiClient:
    def __init__(self, responses: dict[type[Any], Any] | None = None, token_count: int = 100) -> None:
        self._responses = responses or {}
        self._token_count = token_count

    async def count_tokens(self, prompt: str) -> int:
        return self._token_count

    async def generate(self, prompt: str, schema: type[T]) -> T:
        if schema in self._responses:
            return self._responses[schema]
        raise ValueError(f"No fixture configured for {schema.__name__}")


def get_gemini_client() -> GeminiClientImpl:
    settings = Settings()
    return GeminiClientImpl(settings)
