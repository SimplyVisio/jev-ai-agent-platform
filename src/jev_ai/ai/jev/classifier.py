"""Clasificador determinista de intenciones basado en reglas.

Es la primera implementación de ``IntentClassifier``. El dataset versionado en
``mocks/datasets/query_plans.json`` permite medir su precisión y detectar regresiones.
"""

import re

from jev_ai.ai.jev.contracts import (
    ChoiceAnswer,
    ChoiceQuestion,
    DecisionProvider,
    DecisionRequest,
)
from jev_ai.ai.jev.errors import JevError, JevResponseError
from jev_ai.ai.jev.intents import Intent, IntentClassifier, IntentResult

_UNSUPPORTED = re.compile(
    r"\b(elimina|eliminar|borra|borrar|pausa|pausar|crea|crear|actualiza|actualizar"
    r"|cambia|cambiar|sube|subir|baja|bajar|ajusta|ajustar|env[ií]a|enviar"
    r"|descarga|descargar|exporta|exportar|programa|programar|cancela|cancelar)\b",
    re.IGNORECASE,
)
_COMPARE = re.compile(
    r"\b(compar(?:a|ar|aci[oó]n|ativ[oa]|e|en|ando)|vs\.?|frente a|diferencia entre)\b",
    re.IGNORECASE,
)
_TOP_ADS = re.compile(
    r"\b(top|mejores|mejor|ranking)\b.*\b(anuncios?|ads?)\b"
    r"|\b(anuncios?|ads?)\b.*\b(top|mejores|mejor|ranking)\b",
    re.IGNORECASE,
)
_CAMPAIGN = re.compile(r"\bcampa[nñ]a\b", re.IGNORECASE)
_HELP = re.compile(
    r"\b(ayuda|help|hola|buenas|qu[eé] puedes hacer|comandos"
    r"|c[oó]mo funciona(?:s)?|para qu[eé] sirves|qu[eé] sabes hacer)\b",
    re.IGNORECASE,
)


def classify_intent(message: str) -> IntentResult:
    """Clasifica un mensaje con reglas ordenadas por prioridad."""
    if _UNSUPPORTED.search(message):
        return IntentResult(Intent.UNKNOWN, 0.95, "unsupported_action")
    if _COMPARE.search(message):
        return IntentResult(Intent.COMPARE_PERIODS, 0.95, "compare_keyword")
    if _TOP_ADS.search(message):
        return IntentResult(Intent.TOP_ADS_BY_METRIC, 0.95, "top_ads_keyword")
    if _CAMPAIGN.search(message):
        return IntentResult(Intent.CAMPAIGN_PERFORMANCE, 0.95, "campaign_keyword")
    if _HELP.search(message):
        return IntentResult(Intent.HELP, 0.95, "help_keyword")
    return IntentResult(Intent.UNKNOWN, 0.2, "no_rule_matched")


class RuleBasedClassifier(IntentClassifier):
    """Implementación offline y determinista de ``IntentClassifier``."""

    async def classify(self, message: str) -> IntentResult:
        """Clasifica el mensaje sin llamar a ningún modelo externo."""
        return classify_intent(message)


_INTENT_QUESTION = "intent"
_INTENT_VALUES = frozenset(intent.value for intent in Intent)
_INTENT_CRITERIA = {
    Intent.TOP_ADS_BY_METRIC.value: (
        "El usuario pide un ranking o los mejores anuncios según una métrica."
    ),
    Intent.CAMPAIGN_PERFORMANCE.value: (
        "El usuario pregunta por los resultados de una campaña concreta."
    ),
    Intent.COMPARE_PERIODS.value: (
        "El usuario compara dos periodos o pregunta por la evolución entre ambos."
    ),
    Intent.HELP.value: ("El usuario saluda, pide ayuda o pregunta qué puede hacer el chatbot."),
    Intent.UNKNOWN.value: (
        "No encaja en las anteriores o pide crear, modificar, borrar, pausar, "
        "exportar o programar algo."
    ),
}


class JevIntentClassifier(IntentClassifier):
    """Clasificador que delega la decisión en un ``DecisionProvider``.

    Args:
        provider: Cliente Jev real o mock.
        fallback: Clasificador determinista usado si Jev falla o devuelve una
            opción fuera del catálogo. Sin fallback, el error se propaga.
    """

    def __init__(
        self,
        provider: DecisionProvider,
        *,
        fallback: IntentClassifier | None = None,
    ) -> None:
        self._provider = provider
        self._fallback = fallback

    async def classify(self, message: str) -> IntentResult:
        """Pregunta a Jev por la intención y valida que esté en el catálogo."""
        request = DecisionRequest(
            state={"message": message},
            questions={
                _INTENT_QUESTION: ChoiceQuestion(
                    instructions=(
                        "Clasifica la intención del mensaje dentro del catálogo cerrado. "
                        "Elige unknown si pide una acción de escritura o no encaja."
                    ),
                    criteria=_INTENT_CRITERIA,
                )
            },
        )
        try:
            result = await self._provider.decide(request)
        except JevError as exc:
            if self._fallback is None:
                raise
            return await self._fallback_result(message, type(exc).__name__)

        answer = result.response.answers.get(_INTENT_QUESTION)
        if not isinstance(answer, ChoiceAnswer) or answer.choice not in _INTENT_VALUES:
            if self._fallback is None:
                raise JevResponseError("Jev returned an intent outside the catalog")
            return await self._fallback_result(message, "invalid_intent")

        confidence = answer.confidence
        if confidence is None:
            confidence = max((answer.probabilities or {}).values(), default=0.0)
        reason = f"jev:{self._provider.provider_name}:{result.response.model}"
        return IntentResult(Intent(answer.choice), confidence, reason)

    async def _fallback_result(self, message: str, cause: str) -> IntentResult:
        """Usa el clasificador local conservando el motivo del fallback."""
        if self._fallback is None:
            raise JevResponseError(f"Jev classification failed: {cause}")
        result = await self._fallback.classify(message)
        return IntentResult(
            result.intent,
            result.confidence,
            f"jev_fallback:{cause}:{result.reason}",
        )
