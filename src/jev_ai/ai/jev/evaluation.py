"""Evaluación medible del clasificador de intenciones.

Calcula accuracy, precision, recall y F1 por intención y macro. El dataset vive en
``mocks/datasets/intents.json`` y se ejecuta también en CI para detectar regresiones.
"""

import json
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from jev_ai.ai.jev.intents import Intent, IntentClassifier


@dataclass(frozen=True)
class ClassificationCase:
    """Mensaje con la intención que el clasificador debería devolver."""

    message: str
    expected_intent: Intent


@dataclass(frozen=True)
class IntentScore:
    """Métricas de una intención concreta."""

    precision: float
    recall: float
    f1: float
    support: int


@dataclass(frozen=True)
class ClassificationFailure:
    """Caso concreto mal clasificado."""

    message: str
    expected: Intent
    predicted: Intent
    confidence: float


@dataclass(frozen=True)
class EvaluationReport:
    """Resultado completo de evaluar un clasificador."""

    total: int
    accuracy: float
    macro_precision: float
    macro_recall: float
    macro_f1: float
    per_intent: dict[Intent, IntentScore]
    confusion: dict[tuple[Intent, Intent], int]
    failures: tuple[ClassificationFailure, ...]


def _ratio(numerator: int, denominator: int) -> float:
    return 0.0 if denominator == 0 else numerator / denominator


def load_cases(path: Path) -> list[ClassificationCase]:
    """Carga el dataset versionado de mensajes e intenciones."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [
        ClassificationCase(
            message=case["message"],
            expected_intent=Intent(case["intent"]),
        )
        for case in payload["cases"]
    ]


async def evaluate_classifier(
    cases: Sequence[ClassificationCase],
    classifier: IntentClassifier,
) -> EvaluationReport:
    """Ejecuta el clasificador sobre los casos y calcula la matriz de confusión."""
    predictions = [(case, await classifier.classify(case.message)) for case in cases]
    total = len(predictions)
    correct = sum(1 for case, result in predictions if case.expected_intent is result.intent)

    confusion: Counter[tuple[Intent, Intent]] = Counter()
    for case, result in predictions:
        confusion[(case.expected_intent, result.intent)] += 1

    per_intent: dict[Intent, IntentScore] = {}
    for intent in Intent:
        true_positive = sum(
            1
            for case, result in predictions
            if case.expected_intent is intent and result.intent is intent
        )
        false_positive = sum(
            1
            for case, result in predictions
            if case.expected_intent is not intent and result.intent is intent
        )
        false_negative = sum(
            1
            for case, result in predictions
            if case.expected_intent is intent and result.intent is not intent
        )
        support = sum(1 for case, _result in predictions if case.expected_intent is intent)
        precision = _ratio(true_positive, true_positive + false_positive)
        recall = _ratio(true_positive, true_positive + false_negative)
        f1 = _ratio(2 * precision * recall, precision + recall)
        per_intent[intent] = IntentScore(
            precision=precision,
            recall=recall,
            f1=f1,
            support=support,
        )

    intent_count = len(per_intent)
    failures = tuple(
        ClassificationFailure(
            message=case.message,
            expected=case.expected_intent,
            predicted=result.intent,
            confidence=result.confidence,
        )
        for case, result in predictions
        if case.expected_intent is not result.intent
    )

    return EvaluationReport(
        total=total,
        accuracy=_ratio(correct, total),
        macro_precision=sum(score.precision for score in per_intent.values()) / intent_count,
        macro_recall=sum(score.recall for score in per_intent.values()) / intent_count,
        macro_f1=sum(score.f1 for score in per_intent.values()) / intent_count,
        per_intent=per_intent,
        confusion=dict(confusion),
        failures=failures,
    )


def format_report(report: EvaluationReport) -> str:
    """Devuelve un informe legible para terminal o CI."""
    lines = [
        f"Casos evaluados: {report.total}",
        f"Accuracy:        {report.accuracy:.2%}",
        f"Macro precision: {report.macro_precision:.2%}",
        f"Macro recall:    {report.macro_recall:.2%}",
        f"Macro F1:        {report.macro_f1:.2%}",
        "",
        f"{'Intención':22} {'Precision':>10} {'Recall':>8} {'F1':>8} {'Soporte':>8}",
    ]
    for intent, score in report.per_intent.items():
        lines.append(
            f"{intent.value:22} {score.precision:10.3f} "
            f"{score.recall:8.3f} {score.f1:8.3f} {score.support:8d}"
        )

    if report.failures:
        lines.append("")
        lines.append("Fallos:")
        for failure in report.failures:
            lines.append(
                f"- {failure.message!r}: esperado {failure.expected.value}, "
                f"predicho {failure.predicted.value} "
                f"(confianza {failure.confidence:.2f})"
            )

    return "\n".join(lines)
