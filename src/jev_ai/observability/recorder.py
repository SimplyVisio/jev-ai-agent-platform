"""Recolector en memoria y persistencia de trazas."""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from time import perf_counter
from typing import Any
from uuid import UUID, uuid4

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from jev_ai.observability.models import ModelCall, Span, Trace
from jev_ai.observability.usage import TokenUsage

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class SpanRecord:
    """Datos de un nodo o dependencia antes de persistirse."""

    name: str
    kind: str
    status: str
    duration_ms: float
    started_at: datetime
    finished_at: datetime
    attributes: dict[str, Any] | None = None
    error_type: str | None = None


@dataclass(frozen=True)
class ModelCallRecord:
    """Datos de una llamada a un modelo antes de persistirse."""

    provider: str
    model: str
    call_type: str
    status: str
    latency_ms: float
    created_at: datetime
    usage: TokenUsage | None = None
    estimated_cost_usd: Decimal | None = None
    price_version: str | None = None
    service_tier: str | None = None
    error_type: str | None = None


@dataclass
class TraceRecorder:
    """Acumula una traza y la escribe sin bloquear la respuesta al usuario."""

    organization_id: UUID
    trace_id: UUID
    conversation_id: UUID | None = None
    details: dict[str, Any] = field(default_factory=dict)
    spans: list[SpanRecord] = field(default_factory=list)
    model_calls: list[ModelCallRecord] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    duration_ms: float | None = None
    status: str = "error"
    intent: str | None = None
    error_code: str | None = None
    _start_perf: float = field(default_factory=perf_counter, repr=False)

    def finish(
        self,
        *,
        status: str,
        intent: str | None = None,
        error_code: str | None = None,
    ) -> None:
        """Cierra la traza con el estado final del grafo."""
        self.finished_at = datetime.now(UTC)
        self.duration_ms = round((perf_counter() - self._start_perf) * 1000, 2)
        self.status = status
        self.intent = intent
        self.error_code = error_code

    def add_span(
        self,
        *,
        name: str,
        kind: str,
        duration_ms: float,
        status: str = "ok",
        attributes: dict[str, Any] | None = None,
        error_type: str | None = None,
    ) -> None:
        """Añade un span con tiempos aproximados y metadatos acotados."""
        finished_at = datetime.now(UTC)
        self.spans.append(
            SpanRecord(
                name=name,
                kind=kind,
                status=status,
                duration_ms=round(duration_ms, 2),
                started_at=finished_at - timedelta(milliseconds=duration_ms),
                finished_at=finished_at,
                attributes=attributes,
                error_type=error_type,
            )
        )

    def add_model_call(self, record: ModelCallRecord) -> None:
        """Añade una llamada a modelo al lote de persistencia."""
        self.model_calls.append(record)

    async def persist(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> bool:
        """Escribe traza, spans y llamadas en una transacción independiente."""
        if self.finished_at is None:
            self.finish(status=self.status, intent=self.intent, error_code=self.error_code)

        details = dict(self.details)
        details.update(
            {
                "span_count": len(self.spans),
                "model_call_count": len(self.model_calls),
            }
        )
        trace = Trace(
            id=self.trace_id,
            organization_id=self.organization_id,
            conversation_id=self.conversation_id,
            status=self.status,
            intent=self.intent,
            error_code=self.error_code,
            started_at=self.started_at,
            finished_at=self.finished_at,
            duration_ms=self.duration_ms,
            details=details,
        )
        spans = [
            Span(
                trace_id=self.trace_id,
                organization_id=self.organization_id,
                name=span.name,
                kind=span.kind,
                status=span.status,
                started_at=span.started_at,
                finished_at=span.finished_at,
                duration_ms=span.duration_ms,
                error_type=span.error_type,
                attributes=span.attributes,
            )
            for span in self.spans
        ]
        model_calls = [
            ModelCall(
                trace_id=self.trace_id,
                organization_id=self.organization_id,
                conversation_id=self.conversation_id,
                provider=call.provider,
                model=call.model,
                call_type=call.call_type,
                status=call.status,
                input_tokens=None if call.usage is None else call.usage.input_tokens,
                output_tokens=None if call.usage is None else call.usage.output_tokens,
                cached_input_tokens=(
                    None if call.usage is None else call.usage.cached_input_tokens
                ),
                cache_write_tokens=(None if call.usage is None else call.usage.cache_write_tokens),
                reasoning_tokens=(None if call.usage is None else call.usage.reasoning_tokens),
                latency_ms=call.latency_ms,
                estimated_cost_usd=call.estimated_cost_usd,
                price_version=call.price_version,
                service_tier=call.service_tier,
                error_type=call.error_type,
                created_at=call.created_at,
            )
            for call in self.model_calls
        ]

        try:
            async with session_factory() as session:
                session.add(trace)
                await session.flush()
                session.add_all(spans)
                session.add_all(model_calls)
                await session.commit()
        except Exception:
            logger.exception(
                "trace_persist_failed",
                trace_id=str(self.trace_id),
                organization_id=str(self.organization_id),
            )
            return False
        return True


def new_trace_id() -> UUID:
    """Genera un identificador de traza opaco para una petición."""
    return uuid4()
