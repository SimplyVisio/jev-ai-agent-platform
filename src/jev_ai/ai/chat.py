"""Flujo offline del chatbot: clasificar, proponer, validar, ejecutar y responder."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from jev_ai.ai.executor import execute_query_plan
from jev_ai.ai.jev.intents import Intent, IntentClassifier
from jev_ai.ai.jev.plans import PlanParseError, QueryPlan, parse_query_plan
from jev_ai.ai.jev.policies import validate_query_plan
from jev_ai.ai.llm.base import LLMProvider
from jev_ai.ai.llm.mock import LLMError, LLMNoResponseError
from jev_ai.ai.replies import HELP_TEXT, render_reply
from jev_ai.modules.marketing.service import MarketingNotFoundError

MIN_CONFIDENCE = 0.9

_CLARIFICATION = "No estoy seguro de lo que necesitas. " + HELP_TEXT


class ChatStatus(StrEnum):
    """Estado de una interacción de chat."""

    OK = "ok"
    NEEDS_CLARIFICATION = "needs_clarification"
    ERROR = "error"


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
    """Orquesta el flujo sin LangGraph y sin proveedor LLM real."""

    def __init__(self, classifier: IntentClassifier, llm: LLMProvider) -> None:
        self._classifier = classifier
        self._llm = llm

    async def handle(
        self,
        session: AsyncSession,
        organization_id: UUID,
        message: str,
        *,
        dry_run: bool = False,
    ) -> ChatResult:
        """Procesa un mensaje y devuelve respuesta, plan y datos."""
        classification = await self._classifier.classify(message)

        if classification.intent is Intent.HELP:
            return ChatResult(
                status=ChatStatus.OK,
                intent=classification.intent,
                confidence=classification.confidence,
                reply=HELP_TEXT,
            )

        if classification.intent is Intent.UNKNOWN or classification.confidence < MIN_CONFIDENCE:
            return ChatResult(
                status=ChatStatus.NEEDS_CLARIFICATION,
                intent=classification.intent,
                confidence=classification.confidence,
                reply=_CLARIFICATION,
            )

        try:
            raw_plan = await self._llm.generate(message)
        except LLMNoResponseError:
            return ChatResult(
                status=ChatStatus.NEEDS_CLARIFICATION,
                intent=classification.intent,
                confidence=classification.confidence,
                reply=(
                    "No pude identificar la campaña o el periodo. "
                    "Indica el nombre de la campaña entre comillas y el mes."
                ),
            )
        except LLMError as exc:
            return ChatResult(
                status=ChatStatus.ERROR,
                intent=classification.intent,
                confidence=classification.confidence,
                reply=f"El proveedor de lenguaje no está disponible: {exc}",
            )

        try:
            plan = parse_query_plan(raw_plan)
        except PlanParseError:
            return ChatResult(
                status=ChatStatus.NEEDS_CLARIFICATION,
                intent=classification.intent,
                confidence=classification.confidence,
                reply=_CLARIFICATION,
            )

        decision = validate_query_plan(
            plan,
            expected_intent=classification.intent,
        )
        if not decision.accepted:
            details = "; ".join(violation.message for violation in decision.violations)
            return ChatResult(
                status=ChatStatus.NEEDS_CLARIFICATION,
                intent=classification.intent,
                confidence=classification.confidence,
                reply=f"El plan no pasó la validación: {details}.",
                query_plan=plan,
            )

        if dry_run:
            return ChatResult(
                status=ChatStatus.OK,
                intent=classification.intent,
                confidence=classification.confidence,
                reply="Plan validado. No se ejecutó la consulta.",
                query_plan=plan,
            )

        try:
            data = await execute_query_plan(session, organization_id, plan)
        except MarketingNotFoundError:
            return ChatResult(
                status=ChatStatus.NEEDS_CLARIFICATION,
                intent=classification.intent,
                confidence=classification.confidence,
                reply="No encontré esa campaña en tu organización.",
                query_plan=plan,
            )

        return ChatResult(
            status=ChatStatus.OK,
            intent=classification.intent,
            confidence=classification.confidence,
            reply=render_reply(plan, data),
            query_plan=plan,
            data=data,
        )
