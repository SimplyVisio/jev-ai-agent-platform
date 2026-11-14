"""Entrada de la capa de chat: delega el flujo en el grafo de LangGraph."""

from dataclasses import dataclass
from time import perf_counter
from typing import Any
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from sqlalchemy.ext.asyncio import AsyncSession

from jev_ai.ai.jev.intents import Intent, IntentClassifier
from jev_ai.ai.jev.plans import QueryPlan, plan_to_dict
from jev_ai.ai.llm.base import LLMContext, LLMProvider
from jev_ai.ai.memory import load_context
from jev_ai.ai.status import ChatStatus
from jev_ai.ai.workflows import ChatState, build_chat_graph
from jev_ai.modules.conversations import service as conversations
from jev_ai.modules.conversations.models import (
    Conversation,
    Message,
    MessageRole,
)


@dataclass(frozen=True)
class ChatTraceStep:
    """Evento real de un nodo del grafo para depuración."""

    node: str
    detail: str
    duration_ms: float


@dataclass(frozen=True)
class ChatResult:
    """Resultado interno que el endpoint serializa."""

    status: ChatStatus
    intent: Intent
    confidence: float
    reply: str
    query_plan: QueryPlan | None = None
    data: Any = None
    trace: tuple[ChatTraceStep, ...] = ()


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
        conversation_id: UUID | None = None,
        context: LLMContext | None = None,
    ) -> ChatResult:
        """Procesa un mensaje y devuelve respuesta, plan y datos.

        El grafo se compila una vez; la sesión viaja en la configuración de la
        invocación, no en el estado, para no acoplar el workflow a la base de datos.
        """
        initial_state: ChatState = {
            "message": message,
            "organization_id": organization_id,
            "dry_run": dry_run,
            "conversation_id": conversation_id,
            "context": context,
            "user_id": None,
        }
        config: RunnableConfig = {"configurable": {"session": session}}
        final_state: ChatState = dict(initial_state)
        trace: list[ChatTraceStep] = []
        last_step = perf_counter()

        async for update in self._graph.astream(
            initial_state,
            config,
            stream_mode="updates",
        ):
            now = perf_counter()
            for node, node_update in update.items():
                if not isinstance(node_update, dict):
                    continue
                final_state.update(node_update)
                trace.append(
                    ChatTraceStep(
                        node=node,
                        detail=_describe_step(node, final_state),
                        duration_ms=round((now - last_step) * 1000, 2),
                    )
                )
                last_step = now

        return ChatResult(
            status=final_state.get("status", ChatStatus.ERROR),
            intent=final_state.get("intent", Intent.UNKNOWN),
            confidence=final_state.get("confidence", 0.0),
            reply=final_state.get("reply", ""),
            query_plan=final_state.get("plan"),
            data=final_state.get("data"),
            trace=tuple(trace),
        )


@dataclass(frozen=True)
class PersistentChatResult:
    """Resultado de un turno persistido."""

    result: ChatResult
    conversation: Conversation
    user_message: Message
    assistant_message: Message


def _describe_step(node: str, state: ChatState) -> str:
    """Resume un nodo sin exponer datos sensibles ni resultados completos."""
    if node == "classify_intent":
        return (
            f"intent={state.get('intent', Intent.UNKNOWN).value}; "
            f"confidence={state.get('confidence', 0.0):.2f}; "
            f"rule={state.get('intent_reason', '-')}"
        )
    if node == "propose_plan":
        plan = state.get("plan")
        if plan is None:
            return f"sin plan; status={state.get('status', ChatStatus.NEEDS_CLARIFICATION).value}"
        return f"plan={plan_to_dict(plan)}"
    if node == "validate_plan":
        if state.get("status") is ChatStatus.NEEDS_CLARIFICATION:
            return f"plan rechazado; errores={state.get('errors', [])}"
        return "plan aceptado por las políticas de JEV AI"
    if node == "execute_service":
        plan = state.get("plan")
        if plan is None:
            return "sin plan para ejecutar"
        data = state.get("data")
        rows = len(data) if isinstance(data, list) else 1 if data is not None else 0
        return (
            "consultando PostgreSQL con SQLAlchemy: "
            f"{plan.operation.value} {plan.date_from}→{plan.date_to}; filas={rows}"
        )
    if node == "generate_response":
        return f"generando respuesta desde plantilla; caracteres={len(state.get('reply', ''))}"
    if node == "help":
        return "ayuda resuelta sin LLM ni PostgreSQL"
    if node == "clarify":
        return "aclaración solicitada al usuario"
    if node == "error":
        return "error del proveedor de lenguaje"
    return "nodo ejecutado"


class PersistentChatService:
    """Guarda cada turno y reutiliza el mismo grafo que el chat stateless."""

    def __init__(self, chat: ChatService) -> None:
        self._chat = chat

    async def send_message(
        self,
        session: AsyncSession,
        organization_id: UUID,
        conversation_id: UUID,
        message: str,
    ) -> PersistentChatResult:
        """Valida la conversación, procesa el mensaje y guarda ambos turnos.

        La conversación se bloquea antes de leer el historial y calcular
        ``sequence``. Usuario y asistente se confirman en una sola transacción.
        """
        conversation = await conversations.get_conversation_for_update(
            session,
            organization_id,
            conversation_id,
        )
        context = await load_context(
            session,
            organization_id,
            conversation_id,
        )
        sequence = await conversations.next_message_sequence(session, conversation_id)

        user_message = await conversations.add_message(
            session,
            conversation,
            sequence=sequence,
            role=MessageRole.USER,
            content=message,
        )
        conversations.set_auto_title(conversation, message)

        result = await self._chat.handle(
            session,
            organization_id,
            message,
            conversation_id=conversation_id,
            context=context,
        )
        assistant_message = await conversations.add_message(
            session,
            conversation,
            sequence=sequence + 1,
            role=MessageRole.ASSISTANT,
            content=result.reply,
            intent=result.intent.value,
            confidence=result.confidence,
            status=result.status.value,
            query_plan=(None if result.query_plan is None else plan_to_dict(result.query_plan)),
        )
        conversations.touch(conversation)
        await session.commit()

        return PersistentChatResult(
            result=result,
            conversation=conversation,
            user_message=user_message,
            assistant_message=assistant_message,
        )
