"""Modelos ORM de trazas, spans y llamadas a modelos."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from jev_ai.infrastructure.database.base import Base


class Trace(Base):
    """Ejecución observable de una petición de chat."""

    __tablename__ = "traces"
    __table_args__ = (
        Index("ix_traces_organization_id_started_at", "organization_id", "started_at"),
        Index("ix_traces_conversation_id_started_at", "conversation_id", "started_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
    )
    conversation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(30))
    intent: Mapped[str | None] = mapped_column(String(30), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)


class Span(Base):
    """Paso del grafo o llamada a una dependencia dentro de una traza."""

    __tablename__ = "spans"
    __table_args__ = (
        Index("ix_spans_trace_id_started_at", "trace_id", "started_at"),
        Index("ix_spans_organization_id_started_at", "organization_id", "started_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    trace_id: Mapped[UUID] = mapped_column(
        ForeignKey("traces.id", ondelete="CASCADE"),
        index=True,
    )
    parent_span_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("spans.id", ondelete="SET NULL"),
        nullable=True,
    )
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
    )
    name: Mapped[str] = mapped_column(String(80))
    kind: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    attributes: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)


class ModelCall(Base):
    """Llamada a un LLM o a un modelo de decisión como Jev."""

    __tablename__ = "model_calls"
    __table_args__ = (
        Index(
            "ix_model_calls_organization_id_created_at",
            "organization_id",
            "created_at",
        ),
        Index(
            "ix_model_calls_provider_model_created_at",
            "provider",
            "model",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    trace_id: Mapped[UUID] = mapped_column(
        ForeignKey("traces.id", ondelete="CASCADE"),
        index=True,
    )
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
    )
    conversation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
    )
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(120))
    call_type: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20))
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cached_input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cache_write_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reasoning_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_cost_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 8),
        nullable=True,
    )
    price_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    service_tier: Mapped[str | None] = mapped_column(String(30), nullable=True)
    error_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
