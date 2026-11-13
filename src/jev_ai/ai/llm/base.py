"""Interfaz de proveedores LLM."""

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Contrato mínimo de un proveedor de lenguaje.

    El proveedor real se añadirá después. El resto del sistema solo depende de esta
    interfaz, de modo que el mock determinista puede sustituirlo sin cambiar el flujo.
    """

    @abstractmethod
    async def generate(self, prompt: str) -> str:
        """Genera una respuesta de texto para el mensaje del usuario."""
