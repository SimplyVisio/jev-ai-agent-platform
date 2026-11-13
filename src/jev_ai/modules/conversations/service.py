"""Casos de uso de conversaciones.

El módulo no conoce la capa de IA: solo crea hilos, consulta mensajes y persiste
turnos. La generación de respuestas y el uso de memoria viven en ``ai/``.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from jev_ai.modules.conversations import repository
from jev_ai.modules.conversations.models import (
    Conversation,
    Message,
    MessageRole,
)


class ConversationNotFoundError(Exception):
    """Conversación inexistente dentro de la organización autenticada."""

    def __init__(self) -> None:
        super().__init__("Conversation not found")


async def create_conversation(
    session: AsyncSession,
    organization_id: UUID,
    *,
    title: str | None,
) -> Conversation:
    """Crea una conversación vacía para la organización."""
    conversation = Conversation(
        organization_id=organization_id,
        title=title,
    )
    session.add(conversation)
    await session.commit()
    await session.refresh(conversation)
    return conversation


async def list_conversations(
    session: AsyncSession,
    organization_id: UUID,
    *,
    limit: int,
    offset: int,
) -> list[Conversation]:
    """Lista las conversaciones de la organización."""
    return await repository.list_conversations(
        session,
        organization_id,
        limit=limit,
        offset=offset,
    )


async def get_conversation(
    session: AsyncSession,
    organization_id: UUID,
    conversation_id: UUID,
) -> Conversation:
    """Devuelve una conversación o lanza ``ConversationNotFoundError``."""
    conversation = await repository.get_conversation(
        session,
        organization_id,
        conversation_id,
    )
    if conversation is None:
        raise ConversationNotFoundError()
    return conversation


async def get_conversation_for_update(
    session: AsyncSession,
    organization_id: UUID,
    conversation_id: UUID,
) -> Conversation:
    """Bloquea una conversación para añadir mensajes en orden."""
    conversation = await repository.get_conversation_for_update(
        session,
        organization_id,
        conversation_id,
    )
    if conversation is None:
        raise ConversationNotFoundError()
    return conversation


async def list_messages(
    session: AsyncSession,
    organization_id: UUID,
    conversation_id: UUID,
    *,
    limit: int,
    offset: int,
) -> list[Message]:
    """Lista los mensajes de una conversación de la organización."""
    await get_conversation(session, organization_id, conversation_id)
    return await repository.list_messages(
        session,
        organization_id,
        conversation_id,
        limit=limit,
        offset=offset,
    )


async def list_recent_messages(
    session: AsyncSession,
    organization_id: UUID,
    conversation_id: UUID,
    *,
    limit: int,
) -> list[Message]:
    """Devuelve los últimos mensajes para construir el contexto del LLM."""
    return await repository.list_recent_messages(
        session,
        organization_id,
        conversation_id,
        limit=limit,
    )


async def next_message_sequence(
    session: AsyncSession,
    conversation_id: UUID,
) -> int:
    """Devuelve la siguiente posición libre de la conversación."""
    return await repository.next_sequence(session, conversation_id)


async def add_message(
    session: AsyncSession,
    conversation: Conversation,
    *,
    sequence: int,
    role: MessageRole,
    content: str,
    intent: str | None = None,
    confidence: float | None = None,
    status: str | None = None,
    query_plan: dict[str, Any] | None = None,
) -> Message:
    """Añade un mensaje sin confirmar la transacción.

    El caso de uso que orquesta la respuesta confirma usuario y asistente juntos.
    """
    message = Message(
        conversation_id=conversation.id,
        organization_id=conversation.organization_id,
        sequence=sequence,
        role=role,
        content=content,
        intent=intent,
        confidence=confidence,
        status=status,
        query_plan=query_plan,
    )
    session.add(message)
    await session.flush()
    return message


def set_auto_title(conversation: Conversation, first_message: str) -> None:
    """Usa el primer mensaje como título si la conversación no tiene uno."""
    if not conversation.title:
        conversation.title = first_message.strip()[:120]


def touch(conversation: Conversation) -> None:
    """Actualiza la marca de actividad de la conversación."""
    conversation.updated_at = datetime.now(UTC)
