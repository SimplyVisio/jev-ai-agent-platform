"""Proveedor de decisiones determinista para desarrollo sin TypeSafe."""

import asyncio
from typing import Any

from jev_ai.ai.jev.classifier import classify_intent
from jev_ai.ai.jev.contracts import (
    BoxAnswer,
    BoxCoordinates,
    BoxQuestion,
    ChoiceAnswer,
    ChoiceQuestion,
    DecisionProvider,
    DecisionRequest,
    DecisionResponse,
    DecisionResult,
    NoulAnswer,
    NoulQuestion,
    ScoreAnswer,
    ScoreQuestion,
)
from jev_ai.ai.jev.errors import JevError
from jev_ai.ai.jev.intents import Intent

_INTENT_VALUES = frozenset(intent.value for intent in Intent)


class MockDecisionProvider(DecisionProvider):
    """Jev simulado, determinista y sin llamadas externas.

    Las preguntas de intención usan las mismas reglas que ``RuleBasedClassifier``
    para que el flujo offline sea reproducible. El resto de preguntas recibe una
    respuesta válida y trivial. No mide la calidad de un Jev real.

    Args:
        delay: Segundos de latencia simulada.
        error: Error de dominio que se lanza en cada llamada.
    """

    def __init__(
        self,
        *,
        delay: float = 0.0,
        error: JevError | None = None,
    ) -> None:
        self._delay = delay
        self._error = error

    @property
    def provider_name(self) -> str:
        """Identidad usada en las métricas de observabilidad."""
        return "mock"

    @property
    def model_name(self) -> str:
        """El mock no consume un modelo real."""
        return "deterministic"

    async def decide(self, request: DecisionRequest) -> DecisionResult:
        """Responde todas las preguntas de forma determinista."""
        if self._delay > 0:
            await asyncio.sleep(self._delay)
        if self._error is not None:
            raise self._error

        answers = {
            name: self._answer(name, question, request.state)
            for name, question in request.questions.items()
        }
        return DecisionResult(
            response=DecisionResponse(model=self.model_name, answers=answers),
        )

    def _answer(self, name: str, question: Any, state: Any) -> Any:
        """Genera la respuesta adecuada para cada tipo de pregunta."""
        if isinstance(question, ChoiceQuestion):
            if name == "intent" and set(question.criteria) == _INTENT_VALUES:
                result = classify_intent(_message_from_state(state))
                return ChoiceAnswer(
                    type="choice",
                    choice=result.intent.value,
                    confidence=result.confidence,
                    probabilities={result.intent.value: result.confidence},
                )
            choice = next(iter(question.criteria))
            return ChoiceAnswer(
                type="choice",
                choice=choice,
                confidence=1.0,
                probabilities={choice: 1.0},
            )

        if isinstance(question, NoulQuestion):
            return NoulAnswer(type="noul", noul=1.0, confidence=1.0)

        if isinstance(question, ScoreQuestion):
            return ScoreAnswer(
                type="score",
                score=0,
                confidence=1.0,
                probabilities={"0": 1.0},
                legend={str(index): level for index, level in enumerate(question.criteria)},
            )

        if isinstance(question, BoxQuestion):
            return BoxAnswer(
                type="box",
                box=BoxCoordinates(top=0.0, bottom=1.0, left=0.0, right=1.0),
                confidence=1.0,
            )

        raise ValueError(f"unsupported question type for {name}")

    @classmethod
    def default(cls) -> "MockDecisionProvider":
        """Proveedor offline listo para usar como clasificador."""
        return cls()


def _message_from_state(state: Any) -> str:
    """Extrae el mensaje de un estado simple o de un diccionario."""
    if isinstance(state, str):
        return state
    if isinstance(state, dict):
        message = state.get("message")
        return message if isinstance(message, str) else ""
    return ""
