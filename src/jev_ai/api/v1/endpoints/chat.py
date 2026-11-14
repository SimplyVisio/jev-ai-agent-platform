"""Endpoint de chat con QueryPlan y ejecución determinista."""

from typing import Annotated, Any

from fastapi import APIRouter
from pydantic import BaseModel, Field, StringConstraints

from jev_ai.ai.chat import ChatStatus
from jev_ai.ai.jev.intents import Intent
from jev_ai.ai.jev.plans import plan_to_dict
from jev_ai.api.deps import ChatServiceDep, OrganizationDep, SessionDep

router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    """Mensaje del usuario para el chatbot."""

    message: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=1000),
    ] = Field(description="Consulta en lenguaje natural.")
    dry_run: bool = Field(
        default=False,
        description="Valida y devuelve el plan sin ejecutar la consulta.",
    )


class ChatResponse(BaseModel):
    """Respuesta del chatbot con trazabilidad del plan."""

    status: ChatStatus
    intent: Intent
    confidence: float
    reply: str
    query_plan: dict[str, Any] | None = None
    data: Any = None


@router.post("", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    context: OrganizationDep,
    session: SessionDep,
    chat_service: ChatServiceDep,
) -> ChatResponse:
    """Traduce el mensaje a QueryPlan, lo valida y ejecuta con SQLAlchemy."""
    result = await chat_service.handle(
        session,
        context.organization_id,
        payload.message,
        dry_run=payload.dry_run,
    )
    return ChatResponse(
        status=result.status,
        intent=result.intent,
        confidence=result.confidence,
        reply=result.reply,
        query_plan=None if result.query_plan is None else plan_to_dict(result.query_plan),
        data=result.data,
    )
