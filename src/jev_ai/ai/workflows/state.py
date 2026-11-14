"""Estado tipado que atraviesa el grafo de chat."""

from typing import Any, NotRequired, TypedDict
from uuid import UUID

from jev_ai.ai.jev.intents import Intent
from jev_ai.ai.jev.plans import QueryPlan
from jev_ai.ai.llm.base import LLMContext
from jev_ai.ai.status import ChatStatus


class ChatState(TypedDict):
    """Datos que cada nodo del grafo puede leer o actualizar.

    Los identificadores salen del contexto autenticado del servidor. El estado no
    sustituye los permisos: la ejecución sigue filtrando por ``organization_id``.
    """

    message: str
    organization_id: UUID
    dry_run: bool
    conversation_id: UUID | None
    context: NotRequired[LLMContext | None]
    user_id: UUID | None
    intent: NotRequired[Intent]
    confidence: NotRequired[float]
    intent_reason: NotRequired[str]
    plan: NotRequired[QueryPlan | None]
    data: NotRequired[Any]
    reply: NotRequired[str]
    status: NotRequired[ChatStatus]
    errors: NotRequired[list[str]]
