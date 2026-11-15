"""Tests de instrumentación de proveedores sin base de datos."""

from uuid import uuid4

import pytest

from jev_ai.ai.llm.base import LLMContext, LLMProvider, LLMResult
from jev_ai.ai.llm.errors import LLMTimeoutError
from jev_ai.ai.llm.instrumented import InstrumentedLLMProvider
from jev_ai.observability.context import reset_trace_recorder, set_trace_recorder
from jev_ai.observability.recorder import TraceRecorder
from jev_ai.observability.usage import TokenUsage


class FakeProvider(LLMProvider):
    """Proveedor controlado para comprobar la telemetría."""

    def __init__(self, *, error: Exception | None = None) -> None:
        self._error = error

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def model_name(self) -> str:
        return "gpt-5"

    async def generate(
        self,
        prompt: str,
        *,
        context: LLMContext | None = None,
    ) -> LLMResult:
        if self._error is not None:
            raise self._error
        return LLMResult(
            content='{"operation": "compare_periods"}',
            usage=TokenUsage(
                input_tokens=1_000_000,
                cached_input_tokens=1_000_000,
                output_tokens=1_000_000,
            ),
        )


def recorder() -> TraceRecorder:
    return TraceRecorder(organization_id=uuid4(), trace_id=uuid4())


@pytest.mark.asyncio
async def test_records_usage_latency_and_estimated_cost() -> None:
    trace = recorder()
    token = set_trace_recorder(trace)
    try:
        result = await InstrumentedLLMProvider(FakeProvider()).generate("consulta")
    finally:
        reset_trace_recorder(token)

    assert result.content.startswith('{"operation"')
    assert len(trace.model_calls) == 1
    call = trace.model_calls[0]
    assert call.provider == "openai"
    assert call.model == "gpt-5"
    assert call.status == "ok"
    assert call.usage == TokenUsage(
        input_tokens=1_000_000,
        cached_input_tokens=1_000_000,
        output_tokens=1_000_000,
    )
    assert str(call.estimated_cost_usd) == "11.37500000"
    assert call.latency_ms >= 0


@pytest.mark.asyncio
async def test_records_provider_error_and_reraises() -> None:
    trace = recorder()
    token = set_trace_recorder(trace)
    try:
        with pytest.raises(LLMTimeoutError):
            await InstrumentedLLMProvider(FakeProvider(error=LLMTimeoutError("timeout"))).generate(
                "consulta"
            )
    finally:
        reset_trace_recorder(token)

    assert len(trace.model_calls) == 1
    assert trace.model_calls[0].status == "error"
    assert trace.model_calls[0].error_type == "LLMTimeoutError"
    assert trace.model_calls[0].estimated_cost_usd is None
