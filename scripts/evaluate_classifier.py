"""Evalúa el clasificador de intenciones y falla si baja de los umbrales.

Uso:
    python scripts/evaluate_classifier.py
    python scripts/evaluate_classifier.py --min-accuracy 0.95 --min-macro-f1 0.90
"""

import argparse
import asyncio
import sys
from pathlib import Path

from jev_ai.ai.jev.classifier import RuleBasedClassifier
from jev_ai.ai.jev.evaluation import (
    evaluate_classifier,
    format_report,
    load_cases,
)

DATASET = Path(__file__).resolve().parents[1] / "mocks" / "datasets" / "intents.json"


async def evaluate(min_accuracy: float, min_macro_f1: float, dataset: Path) -> int:
    """Ejecuta la evaluación y devuelve un código de salida para CI."""
    cases = load_cases(dataset)
    report = await evaluate_classifier(cases, RuleBasedClassifier())
    print(format_report(report))

    failed = False
    if report.accuracy < min_accuracy:
        print(
            f"\nERROR: accuracy {report.accuracy:.2%} < {min_accuracy:.2%}",
            file=sys.stderr,
        )
        failed = True
    if report.macro_f1 < min_macro_f1:
        print(
            f"ERROR: macro F1 {report.macro_f1:.2%} < {min_macro_f1:.2%}",
            file=sys.stderr,
        )
        failed = True
    return 1 if failed else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evalúa el clasificador JEV AI.")
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument("--min-accuracy", type=float, default=0.90)
    parser.add_argument("--min-macro-f1", type=float, default=0.85)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    raise SystemExit(asyncio.run(evaluate(args.min_accuracy, args.min_macro_f1, args.dataset)))
