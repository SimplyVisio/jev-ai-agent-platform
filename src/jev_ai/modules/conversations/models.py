"""Entidades de conversaciones y mensajes del chatbot."""

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from jev_ai.infrastructure.database.base import Base


class MessageRole(StrEnum):
    """Autor de un mensaje dentro de una conversación."""

    USER = "user"
    ASSISTANT = "assistant"


class Conversation(Base):
    """Hilo de conversación de una organización.

    Attributes:
        id: Identificador UUID.
        organization_id: Organización propietaria; filtra todos los accesos.
        title: Título visible; se autogenera con el primer mensaje si falta.
        created_at: Fecha de alta asignada por PostgreSQL.
        updated_at: Última actividad de la conversación.
        messages: Mensajes ordenados por ``sequence``.
    """

    __tablename__ = "conversations"
    __table_args__ = (
        Index("ix_conversations_organization_id_updated_at", "organization_id", "updated_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
    )
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Message.sequence",
    )


class Message(Base):
    """Mensaje de usuario o del asistente.

    ``organization_id`` se desnormaliza para filtrar sin joins. ``sequence`` es
    monotónica por conversación y permite un orden estable incluso si dos mensajes
    comparten ``created_at``.

    Attributes:
        id: Identificador UUID.
        conversation_id: Conversación a la que pertenece.
        organization_id: Organización propietaria.
        sequence: Posición dentro de la conversación, empieza en 1.
        role: Autor del mensaje.
        content: Texto completo del mensaje.
        intent: Intención detectada en respuestas del asistente.
        confidence: Confianza del clasificador en respuestas del asistente.
        status: Estado del flujo en respuestas del asistente.
        query_plan: Plan validado y ejecutado, serializado como JSON.
        created_at: Fecha de alta asignada por PostgreSQL.
    """

    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint(
            "conversation_id",
            "sequence",
            name="uq_messages_conversation_id_sequence",
        ),
        Index("ix_messages_organization_id_created_at", "organization_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
    )
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
    )
    sequence: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    intent: Mapped[str | None] = mapped_column(String(30), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    query_plan: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
