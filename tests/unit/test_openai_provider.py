"""Tests del proveedor OpenAI-compatible sin llamadas reales."""

import json
from datetime import date

import httpx
import pytest

from jev_ai.ai.jev.plans import MetricName, TopAdsByMetricPlan
from jev_ai.ai.llm.base import ContextMessage, LLMContext
from jev_ai.ai.llm.errors import (
    LLMConnectionError,
    LLMError,
    LLMNoResponseError,
    LLMTimeoutError,
)
from jev_ai.ai.llm.openai_compatible import OpenAICompatibleProvider

_PLAN = {
    "operation": "top_ads_by_metric",
    "metric": "roas",
    "date_from": "2026-10-01",
    "date_to": "2026-10-31",
    "limit": 3,
}


def provider(handler) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(
        api_key="test-key",
        model="test-model",
        base_url="https://llm.example/v1",
        timeout=5,
        transport=httpx.MockTransport(handler),
    )


def response_with_content(content: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={"choices": [{"message": {"content": content}}]},
    )


@pytest.mark.asyncio
async def test_returns_json_content_and_sends_expected_payload() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        captured["payload"] = json.loads(request.content)
        return response_with_content(json.dumps(_PLAN))

    result = await provider(handler).generate("Top 3 anuncios por ROAS en octubre de 2026")

    assert json.loads(result) == _PLAN
    request = captured["request"]
    assert str(request.url) == "https://llm.example/v1/chat/completions"
    assert request.headers["authorization"] == "Bearer test-key"
    payload = captured["payload"]
    assert payload["model"] == "test-model"
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["temperature"] == 0
    assert payload["messages"][-1] == {
        "role": "user",
        "content": "Top 3 anuncios por ROAS en octubre de 2026",
    }
    system = payload["messages"][0]["content"]
    assert "top_ads_by_metric" in system
    assert f"Fecha de referencia: {date.today().isoformat()}" in system


@pytest.mark.asyncio
async def test_includes_context_and_last_valid_plan() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        return response_with_content(json.dumps(_PLAN))

    plan = TopAdsByMetricPlan(
        operation="top_ads_by_metric",
        metric=MetricName.ROAS,
        date_from=date(2026, 10, 1),
        date_to=date(2026, 10, 31),
        limit=3,
    )
    context = LLMContext(
        messages=(
            ContextMessage(role="user", content="Top 3 anuncios por ROAS"),
            ContextMessage(role="assistant", content="Resultado de octubre"),
        ),
        last_plan=plan,
    )

    await provider(handler).generate("¿Y en septiembre de 2026?", context=context)

    system = captured["payload"]["messages"][0]["content"]
    assert "Último plan válido" in system
    assert "2026-10-01" in system
    assert "user: Top 3 anuncios por ROAS" in system
    assert "assistant: Resultado de octubre" in system


@pytest.mark.asyncio
async def test_maps_timeout_to_domain_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    with pytest.raises(LLMTimeoutError):
        await provider(handler).generate("consulta")


@pytest.mark.asyncio
async def test_maps_connection_failure_to_domain_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    with pytest.raises(LLMConnectionError):
        await provider(handler).generate("consulta")


@pytest.mark.asyncio
async def test_http_error_becomes_generic_llm_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "invalid key"}})

    with pytest.raises(LLMError, match="401"):
        await provider(handler).generate("consulta")


@pytest.mark.asyncio
async def test_malformed_response_becomes_llm_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not json")

    with pytest.raises(LLMError, match="message content"):
        await provider(handler).generate("consulta")


@pytest.mark.asyncio
async def test_empty_message_is_reported_as_no_response() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return response_with_content("   ")

    with pytest.raises(LLMNoResponseError):
        await provider(handler).generate("consulta")


def test_rejects_blank_api_key() -> None:
    with pytest.raises(ValueError, match="LLM_API_KEY"):
        OpenAICompatibleProvider(api_key="  ", model="test-model")
