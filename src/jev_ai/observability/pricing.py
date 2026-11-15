"""Tarifas de lista y cálculo de coste estimado por llamada.

Los importes son estimaciones: no incluyen descuentos, créditos, impuestos ni
facturación negociada. El coste se calcula con ``Decimal`` y una versión de tarifas
para que el histórico no cambie cuando el proveedor actualice precios.
"""

from dataclasses import dataclass
from decimal import Decimal

from jev_ai.observability.usage import TokenUsage

PRICE_VERSION = "2026-11-13"
_MILLION = Decimal("1000000")


@dataclass(frozen=True)
class ModelPrice:
    """Tarifa estándar de un modelo por millón de tokens."""

    provider: str
    model: str
    input_per_million: Decimal
    output_per_million: Decimal
    cached_input_per_million: Decimal | None = None
    cache_write_per_million: Decimal | None = None


@dataclass(frozen=True)
class CostEstimate:
    """Coste calculado y versión de la tabla de precios aplicada."""

    amount_usd: Decimal
    price_version: str = PRICE_VERSION


_PRICES = (
    ModelPrice(
        provider="openai",
        model="gpt-4o-mini",
        input_per_million=Decimal("0.15"),
        cached_input_per_million=Decimal("0.075"),
        output_per_million=Decimal("0.60"),
    ),
    ModelPrice(
        provider="openai",
        model="gpt-5.1",
        input_per_million=Decimal("1.25"),
        cached_input_per_million=Decimal("0.125"),
        output_per_million=Decimal("10.00"),
    ),
    ModelPrice(
        provider="openai",
        model="gpt-5",
        input_per_million=Decimal("1.25"),
        cached_input_per_million=Decimal("0.125"),
        output_per_million=Decimal("10.00"),
    ),
    ModelPrice(
        provider="anthropic",
        model="claude-sonnet-4-6",
        input_per_million=Decimal("3.00"),
        cached_input_per_million=Decimal("0.30"),
        cache_write_per_million=Decimal("3.75"),
        output_per_million=Decimal("15.00"),
    ),
    ModelPrice(
        provider="anthropic",
        model="claude-sonnet-4-5",
        input_per_million=Decimal("3.00"),
        cached_input_per_million=Decimal("0.30"),
        cache_write_per_million=Decimal("3.75"),
        output_per_million=Decimal("15.00"),
    ),
    ModelPrice(
        provider="google",
        model="gemini-3.5-flash",
        input_per_million=Decimal("1.50"),
        cached_input_per_million=Decimal("0.15"),
        output_per_million=Decimal("9.00"),
    ),
    ModelPrice(
        provider="google",
        model="gemini-2.5-flash",
        input_per_million=Decimal("0.30"),
        cached_input_per_million=Decimal("0.03"),
        output_per_million=Decimal("2.50"),
    ),
    ModelPrice(
        provider="typesafe",
        model="jev-1.13.0",
        input_per_million=Decimal("0.042"),
        output_per_million=Decimal("0"),
    ),
)


def find_price(provider: str, model: str) -> ModelPrice | None:
    """Busca la tarifa exacta o por prefijo de versión del modelo."""
    provider_key = provider.casefold()
    model_key = model.casefold()
    candidates = [
        price
        for price in _PRICES
        if price.provider == provider_key
        and (model_key == price.model or model_key.startswith(f"{price.model}-"))
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda price: len(price.model))


def estimate_cost(
    provider: str,
    model: str,
    usage: TokenUsage | None,
    *,
    service_tier: str = "standard",
) -> CostEstimate | None:
    """Calcula el coste estándar; devuelve ``None`` si no es fiable.

    Un modelo desconocido o un tier distinto de ``standard`` no se estima para no
    inventar importes. Los tokens de razonamiento no se cobran aparte porque ya
    forman parte de los tokens de salida.
    """
    if usage is None or service_tier != "standard":
        return None
    price = find_price(provider, model)
    if price is None:
        return None

    if usage.cached_input_tokens and price.cached_input_per_million is None:
        return None
    if usage.cache_write_tokens and price.cache_write_per_million is None:
        return None

    amount = (
        Decimal(usage.input_tokens) * price.input_per_million
        + Decimal(usage.cached_input_tokens) * (price.cached_input_per_million or Decimal("0"))
        + Decimal(usage.cache_write_tokens) * (price.cache_write_per_million or Decimal("0"))
        + Decimal(usage.output_tokens) * price.output_per_million
    ) / _MILLION
    return CostEstimate(amount_usd=amount.quantize(Decimal("0.00000001")))
