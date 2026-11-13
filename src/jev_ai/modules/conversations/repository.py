"""Consultas de persistencia del módulo de conversaciones."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from jev_ai.modules.conversations.models import Conversation, Message


async def list_conversations(
    session: AsyncSession,
    organization_id: UUID,
    *,
    limit: int,
    offset: int,
) -> list[Conversation]:
    """Lista conversaciones de la organización, de la más reciente a la más antigua."""
    query = (
        select(Conversation)
        .where(Conversation.organization_id == organization_id)
        .order_by(Conversation.updated_at.desc(), Conversation.id)
        .limit(limit)
        .offset(offset)
    )
    return list((await session.scalars(query)).all())


async def get_conversation(
    session: AsyncSession,
    organization_id: UUID,
    conversation_id: UUID,
) -> Conversation | None:
    """Busca una conversación por id dentro de la organización."""
    return await session.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.organization_id == organization_id,
        )
    )


async def get_conversation_for_update(
    session: AsyncSession,
    organization_id: UUID,
    conversation_id: UUID,
) -> Conversation | None:
    """Bloquea la conversación hasta el final de la transacción.

    Serializa los envíos concurrentes para que ``sequence`` no se repita y el
    historial se lea de forma consistente.
    """
    return await session.scalar(
        select(Conversation)
        .where(
            Conversation.id == conversation_id,
            Conversation.organization_id == organization_id,
        )
        .with_for_update()
    )


async def list_messages(
    session: AsyncSession,
    organization_id: UUID,
    conversation_id: UUID,
    *,
    limit: int,
    offset: int,
) -> list[Message]:
    """Lista mensajes en orden de conversación."""
    query = (
        select(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.organization_id == organization_id,
        )
        .order_by(Message.sequence)
        .limit(limit)
        .offset(offset)
    )
    return list((await session.scalars(query)).all())


async def list_recent_messages(
    session: AsyncSession,
    organization_id: UUID,
    conversation_id: UUID,
    *,
    limit: int,
) -> list[Message]:
    """Devuelve los últimos mensajes en orden ascendente."""
    query = (
        select(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.organization_id == organization_id,
        )
        .order_by(Message.sequence.desc())
        .limit(limit)
    )
    messages = list((await session.scalars(query)).all())
    messages.reverse()
    return messages


async def next_sequence(
    session: AsyncSession,
    conversation_id: UUID,
) -> int:
    """Calcula la siguiente posición de la conversación."""
    last_sequence = await session.scalar(
        select(func.max(Message.sequence)).where(
            Message.conversation_id == conversation_id,
        )
    )
    return (last_sequence or 0) + 1
