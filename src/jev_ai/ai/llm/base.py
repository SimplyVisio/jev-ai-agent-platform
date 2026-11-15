"""Interfaz de proveedores LLM."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from jev_ai.ai.jev.plans import QueryPlan
from jev_ai.observability.usage import TokenUsage


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


@dataclass(frozen=True)
class LLMResult:
    """Contenido generado y uso facturable reportado por el proveedor."""

    content: str
    usage: TokenUsage | None = None
    service_tier: str = "standard"


class LLMProvider(ABC):
    """Contrato mínimo de un proveedor de lenguaje.

    El resto del sistema solo depende de esta interfaz, de modo que el mock
    determinista puede sustituir al proveedor real sin cambiar el flujo. Las
    propiedades de identidad permiten registrar la llamada sin adivinar el modelo.
    """

    @property
    def provider_name(self) -> str:
        """Nombre estable del proveedor para métricas."""
        return self.__class__.__name__

    @property
    def model_name(self) -> str:
        """Modelo usado por el proveedor; el mock no tiene uno real."""
        return "unknown"

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        *,
        context: LLMContext | None = None,
    ) -> LLMResult:
        """Genera una respuesta de texto para el mensaje del usuario.

        ``context`` es opcional: los proveedores reales pueden incorporarlo al prompt;
        el mock lo usa para resolver seguimientos con reglas deterministas.
        """
