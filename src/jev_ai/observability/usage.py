"""Uso normalizado de tokens entre proveedores."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TokenUsage:
    """Tokens de una llamada, normalizados para poder calcular costes.

    ``input_tokens`` son tokens de entrada sin caché; ``cached_input_tokens`` y
    ``cache_write_tokens`` se cobran a tarifas distintas. ``reasoning_tokens`` es
    informativo y ya está incluido en ``output_tokens``; no se suma otra vez.
    """

    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    cache_write_tokens: int = 0
    reasoning_tokens: int = 0

    def __post_init__(self) -> None:
        for name in (
            "input_tokens",
            "output_tokens",
            "cached_input_tokens",
            "cache_write_tokens",
            "reasoning_tokens",
        ):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} cannot be negative")
