"""Interfaz de proveedores LLM."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from jev_ai.ai.jev.plans import QueryPlan


@dataclass(frozen=True)
class ContextMessage:
    """Mensaje previo que puede acompañar al prompt actual."""

    role: str
    content: str


@dataclass(frozen=True)
class LLMContext:
    """Contexto acotado de una conversación.

    ``messages`` contiene solo los últimos mensajes que caben en el presupuesto de
    caracteres. ``last_plan`` permite resolver seguimientos deterministas sin
    depender de que el LLM recuerde el plan anterior.
    """

    messages: tuple[ContextMessage, ...] = ()
    last_plan: QueryPlan | None = None


class LLMProvider(ABC):
    """Contrato mínimo de un proveedor de lenguaje.

    El proveedor real se añadirá después. El resto del sistema solo depende de esta
    interfaz, de modo que el mock determinista puede sustituirlo sin cambiar el flujo.
    """

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        *,
        context: LLMContext | None = None,
    ) -> str:
        """Genera una respuesta de texto para el mensaje del usuario.

        ``context`` es opcional: los proveedores reales pueden incorporarlo al prompt;
        el mock lo usa para resolver seguimientos con reglas deterministas.
        """
