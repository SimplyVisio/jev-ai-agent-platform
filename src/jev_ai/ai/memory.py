"""Construcción del contexto acotado de una conversación.

La memoria es explícita y tiene presupuesto: no se envía todo el historial al LLM.
Se conservan los mensajes más recientes que caben en ``MEMORY_MAX_CHARS`` y el
último plan válido para resolver seguimientos como "¿y en septiembre?".
"""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from jev_ai.ai.jev.plans import PlanParseError, QueryPlan, parse_query_plan
from jev_ai.ai.llm.base import ContextMessage, LLMContext
from jev_ai.modules.conversations import service as conversations
from jev_ai.modules.conversations.models import Message, MessageRole

MEMORY_MESSAGE_LIMIT = 10
MEMORY_MAX_CHARS = 4000


def trim_context(
    messages: Sequence[Message],
    *,
    max_chars: int = MEMORY_MAX_CHARS,
) -> tuple[ContextMessage, ...]:
    """Conserva los mensajes recientes que caben en el presupuesto.

    Si el mensaje más reciente no cabe, se recorta por el final. No se salta un
    mensaje antiguo para incluir otro más pequeño: el contexto debe ser contiguo.
    """
    selected: list[ContextMessage] = []
    total = 0
    for message in reversed(messages):
        remaining = max_chars - total
        if remaining <= 0:
            break
        content = message.content
        if len(content) > remaining:
            if not selected:
                selected.append(ContextMessage(role=message.role, content=content[:remaining]))
            break
        selected.append(ContextMessage(role=message.role, content=content))
        total += len(content)

    selected.reverse()
    return tuple(selected)


def _last_valid_plan(messages: Sequence[Message]) -> QueryPlan | None:
    """Devuelve el plan válido más reciente, ignorando datos corruptos."""
    for message in reversed(messages):
        if message.role != MessageRole.ASSISTANT or message.query_plan is None:
            continue
        try:
            return parse_query_plan(message.query_plan)
        except PlanParseError:
            continue
    return None


async def load_context(
    session: AsyncSession,
    organization_id: UUID,
    conversation_id: UUID,
    *,
    limit: int = MEMORY_MESSAGE_LIMIT,
    max_chars: int = MEMORY_MAX_CHARS,
) -> LLMContext:
    """Carga los últimos mensajes y el último plan de la conversación."""
    messages = await conversations.list_recent_messages(
        session,
        organization_id,
        conversation_id,
        limit=limit,
    )
    return LLMContext(
        messages=trim_context(messages, max_chars=max_chars),
        last_plan=_last_valid_plan(messages),
    )
