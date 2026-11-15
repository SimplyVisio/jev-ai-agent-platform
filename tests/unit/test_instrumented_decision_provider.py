"""Tests de instrumentación del motor de decisiones sin base de datos."""

from uuid import uuid4

import pytest

from jev_ai.ai.jev.contracts import (
    ChoiceQuestion,
    DecisionProvider,
    DecisionRequest,
    DecisionResponse,
    DecisionResult,
)
from jev_ai.ai.jev.errors import JevTimeoutError
from jev_ai.ai.jev.instrumented import InstrumentedDecisionProvider
from jev_ai.observability.context import reset_trace_recorder, set_trace_recorder
from jev_ai.observability.recorder import TraceRecorder
from jev_ai.observability.usage import TokenUsage

_REQUEST = DecisionRequest(
    state="Help! My payouts have been failing for 3 days.",
    questions={"department": ChoiceQuestion(instructions="Elige", criteria={"billing": "Cobros"})},
)


class FakeDecisionProvider(DecisionProvider):
    """Proveedor controlado para comprobar la telemetría."""

    def __init__(self, *, error: Exception | None = None) -> None:
        self._error = error

    @property
    def provider_name(self) -> str:
        return "typesafe"

    @property
    def model_name(self) -> str:
        return "jev-1.13.0"

    async def decide(self, request: DecisionRequest) -> DecisionResult:
        if self._error is not None:
            raise self._error
        return DecisionResult(
            response=DecisionResponse(
                model="jev-1.13.0",
                answers={"department": {"type": "choice", "choice": "billing"}},
                usage={"input_tokens": 1_000_000, "output_tokens": 1_000_000},
            )
        )


def recorder() -> TraceRecorder:
    return TraceRecorder(organization_id=uuid4(), trace_id=uuid4())


@pytest.mark.asyncio
async def test_records_decision_usage_latency_and_estimated_cost() -> None:
    trace = recorder()
    token = set_trace_recorder(trace)
    try:
        result = await InstrumentedDecisionProvider(FakeDecisionProvider()).decide(_REQUEST)
    finally:
        reset_trace_recorder(token)

    assert result.response.answers["department"].type == "choice"
    assert len(trace.model_calls) == 1
    call = trace.model_calls[0]
    assert call.provider == "typesafe"
    assert call.model == "jev-1.13.0"
    assert call.call_type == "decision"
    assert call.status == "ok"
    assert call.usage == TokenUsage(input_tokens=1_000_000, output_tokens=1_000_000)
    assert str(call.estimated_cost_usd) == "0.04200000"
    assert call.price_version is not None
    assert call.latency_ms >= 0


@pytest.mark.asyncio
async def test_records_decision_error_and_reraises() -> None:
    trace = recorder()
    token = set_trace_recorder(trace)
    try:
        with pytest.raises(JevTimeoutError):
            await InstrumentedDecisionProvider(
                FakeDecisionProvider(error=JevTimeoutError("timeout"))
            ).decide(_REQUEST)
    finally:
        reset_trace_recorder(token)

    assert len(trace.model_calls) == 1
    assert trace.model_calls[0].status == "error"
    assert trace.model_calls[0].call_type == "decision"
    assert trace.model_calls[0].error_type == "JevTimeoutError"
    assert trace.model_calls[0].estimated_cost_usd is None
