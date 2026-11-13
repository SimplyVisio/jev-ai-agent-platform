"""Tests del grafo de chat sin base de datos."""

from typing import Any
from uuid import uuid4

import pytest

from jev_ai.ai.jev.classifier import RuleBasedClassifier
from jev_ai.ai.jev.plans import parse_query_plan
from jev_ai.ai.llm.base import LLMContext, LLMProvider
from jev_ai.ai.llm.mock import (
    LLMConnectionError,
    MockLLMProvider,
    MockResponse,
)
from jev_ai.ai.status import ChatStatus
from jev_ai.ai.workflows import build_chat_graph


async def invoke(
    message: str,
    *,
    llm: LLMProvider | None = None,
    dry_run: bool = False,
    context: LLMContext | None = None,
) -> dict[str, Any]:
    graph = build_chat_graph(RuleBasedClassifier(), llm or MockLLMProvider.default())
    return await graph.ainvoke(
        {
            "message": message,
            "organization_id": uuid4(),
            "dry_run": dry_run,
            "conversation_id": None,
            "context": context,
            "user_id": None,
        },
        {"configurable": {"session": None}},
    )


@pytest.mark.asyncio
async def test_help_route_skips_llm_and_database() -> None:
    state = await invoke("Hola, ¿qué puedes hacer?")

    assert state["status"] is ChatStatus.OK
    assert state["intent"].value == "help"
    assert "Prueba con" in state["reply"]
    assert "plan" not in state


@pytest.mark.asyncio
async def test_unknown_route_asks_for_clarification() -> None:
    state = await invoke("Quiero saber algo")

    assert state["status"] is ChatStatus.NEEDS_CLARIFICATION
    assert state["intent"].value == "unknown"
    assert "No estoy seguro" in state["reply"]


@pytest.mark.asyncio
async def test_llm_error_becomes_error_status() -> None:
    state = await invoke(
        "Top 3 anuncios por ROAS",
        llm=MockLLMProvider(error=LLMConnectionError("sin conexión")),
    )

    assert state["status"] is ChatStatus.ERROR
    assert "sin conexión" in state["reply"]


@pytest.mark.asyncio
async def test_invalid_llm_output_asks_for_clarification() -> None:
    state = await invoke(
        "Top 3 anuncios por ROAS",
        llm=MockLLMProvider([MockResponse(pattern="anuncios", response="esto no es json")]),
    )

    assert state["status"] is ChatStatus.NEEDS_CLARIFICATION
    assert state["plan"] is None
    assert "No estoy seguro" in state["reply"]


@pytest.mark.asyncio
async def test_policy_rejection_stops_before_execution() -> None:
    state = await invoke("Top 3 anuncios por alcance en octubre de 2026")

    assert state["status"] is ChatStatus.NEEDS_CLARIFICATION
    assert state["plan"] is not None
    assert "metric_not_rankable" in state["errors"]
    assert "no se puede ordenar" in state["reply"]


@pytest.mark.asyncio
async def test_dry_run_validates_without_executing() -> None:
    state = await invoke("Top 3 anuncios por ROAS", dry_run=True)

    assert state["status"] is ChatStatus.OK
    assert state["plan"].operation.value == "top_ads_by_metric"
    assert "Plan validado" in state["reply"]
    assert "data" not in state


@pytest.mark.asyncio
async def test_follow_up_with_context_uses_previous_plan() -> None:
    context = LLMContext(
        last_plan=parse_query_plan(
            {
                "operation": "top_ads_by_metric",
                "metric": "roas",
                "date_from": "2026-10-01",
                "date_to": "2026-10-31",
                "limit": 5,
            }
        )
    )

    state = await invoke("¿Y en septiembre de 2026?", context=context, dry_run=True)

    assert state["status"] is ChatStatus.OK
    assert state["intent"].value == "top_ads_by_metric"
    assert state["plan"].date_from.isoformat() == "2026-09-01"
