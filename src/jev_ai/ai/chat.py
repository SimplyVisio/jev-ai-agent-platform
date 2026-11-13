"""Entrada de la capa de chat: delega el flujo en el grafo de LangGraph."""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from sqlalchemy.ext.asyncio import AsyncSession

from jev_ai.ai.jev.intents import Intent, IntentClassifier
from jev_ai.ai.jev.plans import QueryPlan
from jev_ai.ai.llm.base import LLMProvider
from jev_ai.ai.status import ChatStatus
from jev_ai.ai.workflows import ChatState, build_chat_graph


@dataclass(frozen=True)
class ChatResult:
    """Resultado interno que el endpoint serializa."""

    status: ChatStatus
    intent: Intent
    confidence: float
    reply: str
    query_plan: QueryPlan | None = None
    data: Any = None


class ChatService:
    """Orquesta el grafo de chat con las dependencias del endpoint."""

    def __init__(self, classifier: IntentClassifier, llm: LLMProvider) -> None:
        self._graph = build_chat_graph(classifier, llm)

    async def handle(
        self,
        session: AsyncSession,
        organization_id: UUID,
        message: str,
        *,
        dry_run: bool = False,
    ) -> ChatResult:
        """Procesa un mensaje y devuelve respuesta, plan y datos.

        El grafo se compila una vez; la sesión viaja en la configuración de la
        invocación, no en el estado, para no acoplar el workflow a la base de datos.
        """
        initial_state: ChatState = {
            "message": message,
            "organization_id": organization_id,
            "dry_run": dry_run,
            "conversation_id": None,
            "user_id": None,
        }
        config: RunnableConfig = {"configurable": {"session": session}}
        final_state = await self._graph.ainvoke(initial_state, config)

        return ChatResult(
            status=final_state.get("status", ChatStatus.ERROR),
            intent=final_state.get("intent", Intent.UNKNOWN),
            confidence=final_state.get("confidence", 0.0),
            reply=final_state.get("reply", ""),
            query_plan=final_state.get("plan"),
            data=final_state.get("data"),
        )
