"""Consistencia del dataset offline con el clasificador y las políticas."""

import json
from datetime import date
from pathlib import Path

from jev_ai.ai.jev.classifier import classify_intent
from jev_ai.ai.jev.intents import Intent
from jev_ai.ai.jev.plans import parse_query_plan
from jev_ai.ai.jev.policies import validate_query_plan
from jev_ai.ai.llm.plan_builder import build_plan_from_message

DATASET = Path(__file__).resolve().parents[2] / "mocks" / "datasets" / "query_plans.json"


def test_dataset_matches_classifier_builder_and_policies() -> None:
    dataset = json.loads(DATASET.read_text(encoding="utf-8"))
    reference_date = date.fromisoformat(dataset["reference_date"])

    for case in dataset["cases"]:
        expected_intent = Intent(case["intent"])
        assert classify_intent(case["message"]).intent is expected_intent

        plan = build_plan_from_message(case["message"], today=reference_date)
        assert plan == case["expected_plan"]

        if plan is None:
            continue
        parsed = parse_query_plan(plan)
        decision = validate_query_plan(parsed, expected_intent=expected_intent)
        assert decision.accepted is (case["expected_policy"] == "accepted")
