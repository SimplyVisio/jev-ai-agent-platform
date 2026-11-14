"""Endpoints de conversaciones persistentes."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel

from jev_ai.ai.jev.intents import Intent
from jev_ai.ai.jev.plans import plan_to_dict
from jev_ai.ai.status import ChatStatus
from jev_ai.api.deps import (
    OrganizationDep,
    PersistentChatServiceDep,
    SessionDep,
)
from jev_ai.api.v1.schemas import TraceStep
from jev_ai.modules.conversations import service
from jev_ai.modules.conversations.schemas import (
    ConversationCreate,
    ConversationRead,
    MessageRead,
    SendMessageRequest,
)

router = APIRouter(tags=["conversations"])


class ConversationChatResponse(BaseModel):
    """Respuesta del chat persistente con identificadores de auditoría."""

    conversation_id: UUID
    user_message_id: UUID
    assistant_message_id: UUID
    status: ChatStatus
    intent: Intent
    confidence: float
    reply: str
    query_plan: dict[str, Any] | None = None
    data: Any = None
    trace: list[TraceStep] | None = None


@router.post("", response_model=ConversationRead, status_code=201)
async def create_conversation(
    payload: ConversationCreate,
    context: OrganizationDep,
    session: SessionDep,
):
    """Abre una conversación para la organización autenticada."""
    return await service.create_conversation(
        session,
        context.organization_id,
        title=payload.title,
    )


@router.get("", response_model=list[ConversationRead])
async def list_conversations(
    context: OrganizationDep,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """Lista las conversaciones de la organización."""
    return await service.list_conversations(
        session,
        context.organization_id,
        limit=limit,
        offset=offset,
    )


@router.get("/{conversation_id}", response_model=ConversationRead)
async def get_conversation(
    conversation_id: UUID,
    context: OrganizationDep,
    session: SessionDep,
):
    """Devuelve una conversación por id."""
    return await service.get_conversation(
        session,
        context.organization_id,
        conversation_id,
    )


@router.get("/{conversation_id}/messages", response_model=list[MessageRead])
async def list_messages(
    conversation_id: UUID,
    context: OrganizationDep,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """Lista los mensajes en orden de conversación."""
    return await service.list_messages(
        session,
        context.organization_id,
        conversation_id,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/{conversation_id}/messages",
    response_model=ConversationChatResponse,
    status_code=201,
)
async def send_message(
    conversation_id: UUID,
    payload: SendMessageRequest,
    context: OrganizationDep,
    session: SessionDep,
    persistent_chat: PersistentChatServiceDep,
) -> ConversationChatResponse:
    """Procesa un mensaje y persiste el turno completo."""
    outcome = await persistent_chat.send_message(
        session,
        context.organization_id,
        conversation_id,
        payload.message,
    )
    result = outcome.result
    return ConversationChatResponse(
        conversation_id=outcome.conversation.id,
        user_message_id=outcome.user_message.id,
        assistant_message_id=outcome.assistant_message.id,
        status=result.status,
        intent=result.intent,
        confidence=result.confidence,
        reply=result.reply,
        query_plan=(None if result.query_plan is None else plan_to_dict(result.query_plan)),
        data=result.data,
        trace=[TraceStep.model_validate(step) for step in result.trace] if payload.debug else None,
    )
