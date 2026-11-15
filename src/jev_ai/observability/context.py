"""Contexto de la petición para trazas y llamadas a modelos."""

from __future__ import annotations

from contextvars import ContextVar, Token
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from jev_ai.observability.recorder import ModelCallRecord, TraceRecorder
from jev_ai.observability.usage import TokenUsage

_trace_id: ContextVar[UUID | None] = ContextVar("jev_trace_id", default=None)
_recorder: ContextVar[TraceRecorder | None] = ContextVar("jev_trace_recorder", default=None)


def set_trace_id(trace_id: UUID) -> Token[UUID | None]:
    """Asocia un ``trace_id`` al contexto de la petición."""
    return _trace_id.set(trace_id)


def reset_trace_id(token: Token[UUID | None]) -> None:
    """Restaura el ``trace_id`` anterior."""
    _trace_id.reset(token)


def current_trace_id() -> UUID | None:
    """Devuelve el ``trace_id`` activo, si existe."""
    return _trace_id.get()


def set_trace_recorder(recorder: TraceRecorder) -> Token[TraceRecorder | None]:
    """Activa el recolector que recibirá spans y llamadas a modelos."""
    return _recorder.set(recorder)


def reset_trace_recorder(token: Token[TraceRecorder | None]) -> None:
    """Desactiva el recolector activo."""
    _recorder.reset(token)


def record_model_call(
    *,
    provider: str,
    model: str,
    call_type: str,
    status: str,
    latency_ms: float,
    usage: TokenUsage | None = None,
    estimated_cost_usd: Decimal | None = None,
    price_version: str | None = None,
    service_tier: str | None = None,
    error_type: str | None = None,
) -> None:
    """Añade una llamada al recolector activo; no falla si no hay traza."""
    recorder = _recorder.get()
    if recorder is None:
        return
    recorder.add_model_call(
        ModelCallRecord(
            provider=provider,
            model=model,
            call_type=call_type,
            status=status,
            latency_ms=round(latency_ms, 2),
            created_at=datetime.now(UTC),
            usage=usage,
            estimated_cost_usd=estimated_cost_usd,
            price_version=price_version,
            service_tier=service_tier,
            error_type=error_type,
        )
    )
