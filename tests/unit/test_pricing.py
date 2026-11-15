"""Tests del cálculo determinista de costes estimados."""

from decimal import Decimal

import pytest

from jev_ai.observability.pricing import PRICE_VERSION, estimate_cost, find_price
from jev_ai.observability.usage import TokenUsage


def test_finds_exact_and_versioned_model_names() -> None:
    assert find_price("openai", "gpt-5.1") is not None
    assert find_price("openai", "gpt-5.1-2026-01-01") is not None
    assert find_price("openai", "gpt-5") is not None
    assert find_price("openai", "unknown-model") is None


def test_calculates_input_output_and_cache_costs() -> None:
    cost = estimate_cost(
        "openai",
        "gpt-5",
        TokenUsage(
            input_tokens=1_000_000,
            cached_input_tokens=1_000_000,
            output_tokens=1_000_000,
        ),
    )

    assert cost is not None
    assert cost.amount_usd == Decimal("11.37500000")
    assert cost.price_version == PRICE_VERSION


def test_jev_only_charges_input_tokens() -> None:
    cost = estimate_cost(
        "typesafe",
        "jev-1.13.0",
        TokenUsage(input_tokens=1_000_000, output_tokens=1_000_000),
    )

    assert cost is not None
    assert cost.amount_usd == Decimal("0.04200000")


def test_does_not_invent_costs_for_unknown_models_or_tiers() -> None:
    usage = TokenUsage(input_tokens=100, output_tokens=50)

    assert estimate_cost("openai", "unknown", usage) is None
    assert estimate_cost("openai", "gpt-5", usage, service_tier="batch") is None
    assert estimate_cost("openai", "gpt-5", None) is None


def test_rejects_cache_tokens_without_a_cache_price() -> None:
    cost = estimate_cost(
        "typesafe",
        "jev-1.13.0",
        TokenUsage(cached_input_tokens=1),
    )

    assert cost is None


def test_token_usage_rejects_negative_counters() -> None:
    with pytest.raises(ValueError, match="input_tokens"):
        TokenUsage(input_tokens=-1)
