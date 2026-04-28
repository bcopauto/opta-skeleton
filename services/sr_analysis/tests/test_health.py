from __future__ import annotations

from fastapi.testclient import TestClient

from analysis_service.gemini_client import get_gemini_client


def test_health_ok(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "gemini": "reachable"}


def test_health_degraded_when_gemini_unreachable(required_env):
    class FailingGeminiClient:
        async def count_tokens(self, prompt: str) -> int:
            raise ConnectionError("Gemini API unreachable")

        async def generate(self, prompt: str, schema: type) -> None:
            raise ConnectionError("Gemini API unreachable")

    from analysis_service.app import app

    app.dependency_overrides[get_gemini_client] = lambda: FailingGeminiClient()
    test_client = TestClient(app)
    response = test_client.get("/health")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "degraded", "gemini": "unreachable"}


def test_health_degraded_on_generic_exception(required_env):
    class GenericFailClient:
        async def count_tokens(self, prompt: str) -> int:
            raise Exception("unknown error")

        async def generate(self, prompt: str, schema: type) -> None:
            raise Exception("unknown error")

    from analysis_service.app import app

    app.dependency_overrides[get_gemini_client] = lambda: GenericFailClient()
    test_client = TestClient(app)
    response = test_client.get("/health")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "degraded", "gemini": "unreachable"}


def test_health_response_is_json(client: TestClient):
    response = client.get("/health")
    assert "application/json" in response.headers["content-type"]
