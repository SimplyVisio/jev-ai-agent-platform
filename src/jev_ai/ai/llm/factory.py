"""Selección del proveedor LLM según la configuración de la aplicación."""

from jev_ai.ai.llm.base import LLMProvider
from jev_ai.ai.llm.mock import MockLLMProvider
from jev_ai.ai.llm.openai_compatible import OpenAICompatibleProvider
from jev_ai.config import Settings


def build_llm_provider(settings: Settings) -> LLMProvider:
    """Construye el proveedor configurado, con el mock como opción segura.

    Raises:
        ValueError: Si se elige OpenAI sin una API key.
    """
    if settings.llm_provider == "mock":
        return MockLLMProvider.default()

    api_key = (settings.llm_api_key or "").strip()
    if not api_key:
        raise ValueError("LLM_API_KEY is required when LLM_PROVIDER=openai")
    return OpenAICompatibleProvider(
        api_key=api_key,
        model=settings.llm_model,
        base_url=settings.llm_base_url,
        timeout=settings.llm_timeout_seconds,
    )
