"""Tests del proveedor LLM mock."""

import json

import pytest

from jev_ai.ai.llm.mock import (
    LLMConnectionError,
    LLMNoResponseError,
    MockLLMProvider,
    MockResponse,
)


@pytest.mark.asyncio
async def test_returns_fixed_response_before_planner() -> None:
    provider = MockLLMProvider(
        [MockResponse(pattern="hola", response="respuesta fija")],
        planner=lambda _prompt: {"operation": "compare_periods"},
    )

    assert await provider.generate("Hola, ¿qué tal?") == "respuesta fija"


@pytest.mark.asyncio
async def test_default_provider_returns_plan_json() -> None:
    provider = MockLLMProvider.default()

    raw = await provider.generate("Top 2 anuncios por ROAS en octubre de 2026")

    plan = json.loads(raw)
    assert plan["operation"] == "top_ads_by_metric"
    assert plan["metric"] == "roas"
    assert plan["limit"] == 2


@pytest.mark.asyncio
async def test_raises_when_there_is_no_response_or_plan() -> None:
    provider = MockLLMProvider(planner=lambda _prompt: None)

    with pytest.raises(LLMNoResponseError):
        await provider.generate("Quiero saber algo")


@pytest.mark.asyncio
async def test_can_simulate_provider_errors() -> None:
    provider = MockLLMProvider(error=LLMConnectionError("sin conexión"))

    with pytest.raises(LLMConnectionError, match="sin conexión"):
        await provider.generate("Top 5 anuncios por ROAS")
