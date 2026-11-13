"""Tests de las métricas de evaluación del clasificador."""

from pathlib import Path

import pytest

from jev_ai.ai.jev.classifier import RuleBasedClassifier
from jev_ai.ai.jev.evaluation import (
    ClassificationCase,
    evaluate_classifier,
    load_cases,
)
from jev_ai.ai.jev.intents import Intent, IntentClassifier, IntentResult

DATASET = Path(__file__).resolve().parents[2] / "mocks" / "datasets" / "intents.json"


class FixedClassifier(IntentClassifier):
    """Clasificador de prueba que devuelve una intención según el mensaje."""

    def __init__(self, predictions: dict[str, Intent]) -> None:
        self._predictions = predictions

    async def classify(self, message: str) -> IntentResult:
        return IntentResult(
            intent=self._predictions[message],
            confidence=0.95,
            reason="fixed",
        )


def _cases() -> list[ClassificationCase]:
    return [
        ClassificationCase("top", Intent.TOP_ADS_BY_METRIC),
        ClassificationCase("campaign", Intent.CAMPAIGN_PERFORMANCE),
        ClassificationCase("compare", Intent.COMPARE_PERIODS),
        ClassificationCase("help", Intent.HELP),
        ClassificationCase("unknown", Intent.UNKNOWN),
    ]


@pytest.mark.asyncio
async def test_perfect_predictions_have_full_metrics() -> None:
    classifier = FixedClassifier(
        {
            "top": Intent.TOP_ADS_BY_METRIC,
            "campaign": Intent.CAMPAIGN_PERFORMANCE,
            "compare": Intent.COMPARE_PERIODS,
            "help": Intent.HELP,
            "unknown": Intent.UNKNOWN,
        }
    )

    report = await evaluate_classifier(_cases(), classifier)

    assert report.accuracy == 1.0
    assert report.macro_f1 == 1.0
    assert report.failures == ()
    assert all(score.support == 1 for score in report.per_intent.values())


@pytest.mark.asyncio
async def test_confusion_matrix_and_failures() -> None:
    classifier = FixedClassifier(
        {
            "top": Intent.TOP_ADS_BY_METRIC,
            "campaign": Intent.CAMPAIGN_PERFORMANCE,
            "compare": Intent.COMPARE_PERIODS,
            "help": Intent.UNKNOWN,
            "unknown": Intent.UNKNOWN,
        }
    )

    report = await evaluate_classifier(_cases(), classifier)

    assert report.accuracy == pytest.approx(0.8)
    assert report.macro_precision == pytest.approx(0.7)
    assert report.macro_recall == pytest.approx(0.8)
    assert report.macro_f1 == pytest.approx(0.733333, abs=1e-6)
    assert report.confusion[(Intent.HELP, Intent.UNKNOWN)] == 1
    assert len(report.failures) == 1
    assert report.failures[0].expected is Intent.HELP
    assert report.failures[0].predicted is Intent.UNKNOWN


@pytest.mark.asyncio
async def test_versioned_dataset_meets_thresholds() -> None:
    cases = load_cases(DATASET)
    report = await evaluate_classifier(cases, RuleBasedClassifier())

    assert report.total >= 60
    assert report.accuracy >= 0.90
    assert report.macro_f1 >= 0.85
    assert report.failures == ()
    assert all(score.support > 0 for score in report.per_intent.values())
