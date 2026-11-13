"""Tests del clasificador de intenciones por reglas."""

import pytest

from jev_ai.ai.jev.classifier import RuleBasedClassifier, classify_intent
from jev_ai.ai.jev.intents import Intent


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("¿Cuáles son los 5 mejores anuncios por ROAS?", Intent.TOP_ADS_BY_METRIC),
        ("Quiero un ranking de anuncios por CPL", Intent.TOP_ADS_BY_METRIC),
        ("¿Cómo va la campaña Demo?", Intent.CAMPAIGN_PERFORMANCE),
        ("Compara este mes con el mes pasado", Intent.COMPARE_PERIODS),
        ("¿Qué puedes hacer?", Intent.HELP),
        ("Hola", Intent.HELP),
        ("Quiero saber algo", Intent.UNKNOWN),
    ],
)
def test_classifies_closed_intents(message: str, expected: Intent) -> None:
    assert classify_intent(message).intent is expected


def test_compare_has_priority_over_campaign_keyword() -> None:
    result = classify_intent("Compara la campaña Demo con la campaña Beta")

    assert result.intent is Intent.COMPARE_PERIODS
    assert result.confidence >= 0.9


@pytest.mark.asyncio
async def test_rule_based_classifier_implements_contract() -> None:
    result = await RuleBasedClassifier().classify("Top 3 anuncios por gasto")

    assert result.intent is Intent.TOP_ADS_BY_METRIC
    assert result.reason == "top_ads_keyword"
