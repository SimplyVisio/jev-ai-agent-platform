"""Nodos del grafo de chat. No contienen reglas de negocio.

Cada nodo actualiza solo la parte del estado que le corresponde. La clasificación,
la validación y la ejecución viven en sus módulos; aquí solo se orquesta el orden y
se traducen errores a estados del flujo.
"""

from typing import Literal

from langchain_core.runnables import RunnableConfig

from jev_ai.ai.executor import execute_query_plan
from jev_ai.ai.jev.intents import Intent, IntentClassifier
from jev_ai.ai.jev.plans import PlanParseError, parse_query_plan
from jev_ai.ai.jev.policies import validate_query_plan
from jev_ai.ai.llm.base import LLMProvider
from jev_ai.ai.llm.mock import LLMError, LLMNoResponseError
from jev_ai.ai.replies import HELP_TEXT, render_reply
from jev_ai.ai.status import ChatStatus
from jev_ai.ai.workflows.state import ChatState
from jev_ai.modules.marketing.service import MarketingNotFoundError

MIN_CONFIDENCE = 0.9
_CLARIFICATION = "No estoy seguro de lo que necesitas. " + HELP_TEXT
_MISSING_CAMPAIGN = (
    "No pude identificar la campaña o el periodo. "
    "Indica el nombre de la campaña entre comillas y el mes."
)


class ChatNodes:
    """Nodos con las dependencias del flujo inyectadas."""

    def __init__(self, classifier: IntentClassifier, llm: LLMProvider) -> None:
        self._classifier = classifier
        self._llm = llm

    async def classify_intent(self, state: ChatState) -> dict:
        """Clasifica el mensaje dentro del catálogo cerrado."""
        result = await self._classifier.classify(state["message"])
        return {
            "intent": result.intent,
            "confidence": result.confidence,
        }

    def route_after_classify(self, state: ChatState) -> Literal["help", "clarify", "plan"]:
        """Decide si hay que responder ayuda, pedir aclaración o proponer un plan."""
        intent = state.get("intent", Intent.UNKNOWN)
        confidence = state.get("confidence", 0.0)
        if intent is Intent.HELP:
            return "help"
        if intent is Intent.UNKNOWN or confidence < MIN_CONFIDENCE:
            return "clarify"
        return "plan"

    async def help(self, _state: ChatState) -> dict:
        """Devuelve el texto de ayuda sin llamar al LLM."""
        return {"status": ChatStatus.OK, "reply": HELP_TEXT}

    async def clarify(self, state: ChatState) -> dict:
        """Cierra con una petición de aclaración, conservando el texto ya preparado."""
        return {
            "status": ChatStatus.NEEDS_CLARIFICATION,
            "reply": state.get("reply", _CLARIFICATION),
        }

    async def error(self, state: ChatState) -> dict:
        """Cierra con un error de proveedor."""
        return {
            "status": ChatStatus.ERROR,
            "reply": state.get("reply", "El proveedor de lenguaje no está disponible."),
        }

    async def propose_plan(self, state: ChatState) -> dict:
        """Pide al LLM un plan y lo convierte en un ``QueryPlan`` tipado."""
        try:
            raw_plan = await self._llm.generate(state["message"])
        except LLMNoResponseError:
            return {
                "status": ChatStatus.NEEDS_CLARIFICATION,
                "reply": _MISSING_CAMPAIGN,
                "plan": None,
            }
        except LLMError as exc:
            return {
                "status": ChatStatus.ERROR,
                "reply": f"El proveedor de lenguaje no está disponible: {exc}",
                "plan": None,
            }

        try:
            return {"plan": parse_query_plan(raw_plan)}
        except PlanParseError:
            return {
                "status": ChatStatus.NEEDS_CLARIFICATION,
                "reply": _CLARIFICATION,
                "plan": None,
            }

    def route_after_propose(self, state: ChatState) -> Literal["validate", "clarify", "error"]:
        """Separa errores de proveedor, aclaraciones y planes listos para validar."""
        status = state.get("status")
        if status is ChatStatus.ERROR:
            return "error"
        if status is ChatStatus.NEEDS_CLARIFICATION:
            return "clarify"
        return "validate"

    async def validate_plan(self, state: ChatState) -> dict:
        """Aplica las políticas deterministas de JEV AI."""
        plan = state.get("plan")
        if plan is None:
            return {
                "status": ChatStatus.NEEDS_CLARIFICATION,
                "reply": _CLARIFICATION,
            }

        decision = validate_query_plan(
            plan,
            expected_intent=state["intent"],
        )
        if not decision.accepted:
            details = "; ".join(violation.message for violation in decision.violations)
            return {
                "status": ChatStatus.NEEDS_CLARIFICATION,
                "reply": f"El plan no pasó la validación: {details}.",
                "errors": [violation.code for violation in decision.violations],
            }

        if state["dry_run"]:
            return {
                "status": ChatStatus.OK,
                "reply": "Plan validado. No se ejecutó la consulta.",
            }
        return {"status": ChatStatus.OK, "errors": []}

    def route_after_validate(self, state: ChatState) -> Literal["execute", "clarify", "finish"]:
        """Ejecuta solo planes aceptados y no simulados."""
        if state.get("status") is ChatStatus.NEEDS_CLARIFICATION:
            return "clarify"
        if state["dry_run"]:
            return "finish"
        return "execute"

    async def execute_service(self, state: ChatState, config: RunnableConfig) -> dict:
        """Ejecuta el plan con los servicios de aplicación y la sesión de la petición."""
        plan = state["plan"]
        if plan is None:
            return {
                "status": ChatStatus.NEEDS_CLARIFICATION,
                "reply": _CLARIFICATION,
            }

        session = config["configurable"]["session"]
        try:
            data = await execute_query_plan(
                session,
                state["organization_id"],
                plan,
            )
        except MarketingNotFoundError:
            return {
                "status": ChatStatus.NEEDS_CLARIFICATION,
                "reply": "No encontré esa campaña en tu organización.",
                "data": None,
            }
        return {"data": data}

    def route_after_execute(self, state: ChatState) -> Literal["respond", "clarify"]:
        """Distingue una ejecución exitosa de una campaña inexistente."""
        if state.get("status") is ChatStatus.NEEDS_CLARIFICATION:
            return "clarify"
        return "respond"

    async def generate_response(self, state: ChatState) -> dict:
        """Redacta la respuesta desde plantillas y los datos ya validados."""
        plan = state["plan"]
        if plan is None:
            return {"status": ChatStatus.NEEDS_CLARIFICATION, "reply": _CLARIFICATION}
        return {
            "status": ChatStatus.OK,
            "reply": render_reply(plan, state.get("data")),
        }
