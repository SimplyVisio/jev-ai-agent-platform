"""Schemas HTTP del módulo de conversaciones."""

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints

from jev_ai.modules.conversations.models import MessageRole

Title = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]
MessageText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=1000),
]


class ConversationCreate(BaseModel):
    """Datos para abrir una conversación."""

    title: Title | None = None


class ConversationRead(BaseModel):
    """Conversación expuesta por la API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    title: str | None
    created_at: datetime
    updated_at: datetime


class MessageRead(BaseModel):
    """Mensaje expuesto por la API, con la trazabilidad del asistente."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    conversation_id: UUID
    sequence: int
    role: MessageRole
    content: str
    intent: str | None
    confidence: float | None
    status: str | None
    query_plan: dict[str, Any] | None
    created_at: datetime


class SendMessageRequest(BaseModel):
    """Mensaje del usuario dentro de una conversación."""

    message: MessageText
