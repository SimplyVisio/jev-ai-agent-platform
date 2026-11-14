"""Proveedor LLM mock determinista para desarrollo sin API key ni túnel.

Puede devolver respuestas fijas por patrón, simular errores o latencia y, por
defecto, proponer un ``QueryPlan`` a partir de un vocabulario cerrado.
"""

import asyncio
import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from jev_ai.ai.llm.base import LLMContext, LLMProvider
from jev_ai.ai.llm.errors import LLMError, LLMNoResponseError
from jev_ai.ai.llm.plan_builder import build_follow_up_plan, build_plan_from_message


@dataclass(frozen=True)
class MockResponse:
    """Respuesta fija que se activa cuando el prompt contiene un patrón."""

    pattern: str
    response: str
    case_sensitive: bool = False

    def matches(self, prompt: str) -> bool:
        """Indica si el prompt contiene el patrón."""
        if self.case_sensitive:
            return self.pattern in prompt
        return self.pattern.lower() in prompt.lower()


class MockLLMProvider(LLMProvider):
    """LLM simulado, determinista y sin dependencias externas.

    Args:
        responses: Respuestas fijas evaluadas antes del planificador.
        delay: Segundos de latencia simulada.
        error: Excepción que se lanzará en cada llamada.
        planner: Función que propone un plan; por defecto usa el traductor offline.
    """

    def __init__(
        self,
        responses: Iterable[MockResponse] = (),
        *,
        delay: float = 0.0,
        error: LLMError | None = None,
        planner: Callable[[str], dict[str, Any] | None] = build_plan_from_message,
    ) -> None:
        self._responses = tuple(responses)
        self._delay = delay
        self._error = error
        self._planner = planner

    async def generate(
        self,
        prompt: str,
        *,
        context: LLMContext | None = None,
    ) -> str:
        """Devuelve una respuesta fija o un plan JSON determinista."""
        if self._delay > 0:
            await asyncio.sleep(self._delay)
        if self._error is not None:
            raise self._error

        for response in self._responses:
            if response.matches(prompt):
                return response.response

        plan = self._planner(prompt)
        if plan is None and context is not None:
            plan = build_follow_up_plan(prompt, context)
        if plan is not None:
            return json.dumps(plan, ensure_ascii=False)
        raise LLMNoResponseError("No mock response or plan for the prompt")

    @classmethod
    def default(cls) -> "MockLLMProvider":
        """Proveedor offline listo para usar en el endpoint de chat."""
        return cls()
