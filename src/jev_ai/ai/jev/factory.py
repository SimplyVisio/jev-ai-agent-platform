"""Selección del proveedor de decisiones según la configuración."""

from jev_ai.ai.jev.client import TypeSafeJevProvider
from jev_ai.ai.jev.contracts import DecisionProvider
from jev_ai.ai.jev.mock import MockDecisionProvider
from jev_ai.config import Settings


def build_decision_provider(settings: Settings) -> DecisionProvider:
    """Construye Jev mock o TypeSafe; el mock es la opción segura.

    Raises:
        ValueError: Si se elige TypeSafe sin ``TYPESAFE_API_KEY``.
    """
    if settings.jev_provider == "mock":
        return MockDecisionProvider.default()

    api_key = (settings.typesafe_api_key or "").strip()
    if not api_key:
        raise ValueError("TYPESAFE_API_KEY is required when JEV_PROVIDER=typesafe")
    return TypeSafeJevProvider(
        api_key=api_key,
        model=settings.jev_model,
        base_url=settings.jev_base_url,
        timeout=settings.jev_timeout_seconds,
        max_retries=settings.jev_max_retries,
    )
