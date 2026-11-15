"""Tests del clasificador Jev y del proveedor de decisiones mock."""

import pytest

from jev_ai.ai.jev.classifier import JevIntentClassifier, RuleBasedClassifier
from jev_ai.ai.jev.contracts import (
    BoxQuestion,
    ChoiceAnswer,
    ChoiceQuestion,
    DecisionProvider,
    DecisionRequest,
    DecisionResponse,
    DecisionResult,
    NoulQuestion,
    ScoreQuestion,
)
from jev_ai.ai.jev.errors import JevTimeoutError
from jev_ai.ai.jev.intents import Intent
from jev_ai.ai.jev.mock import MockDecisionProvider


@pytest.mark.asyncio
async def test_mock_answers_all_supported_question_types() -> None:
    provider = MockDecisionProvider.default()
    result = await provider.decide(
        DecisionRequest(
            state="hola",
            questions={
                "yes": NoulQuestion(instructions="¿Sí?"),
                "kind": ChoiceQuestion(instructions="Elige", criteria={"a": "A", "b": "B"}),
                "level": ScoreQuestion(instructions="Puntúa", criteria=["bajo", "alto"]),
                "area": BoxQuestion(instructions="¿Dónde?"),
            },
        )
    )

    assert result.response.model == "deterministic"
    assert result.response.answers["yes"].type == "noul"
    assert result.response.answers["kind"].type == "choice"
    assert result.response.answers["level"].type == "score"
    assert result.response.answers["area"].type == "box"


@pytest.mark.asyncio
async def test_mock_intent_uses_the_rule_based_result() -> None:
    classifier = JevIntentClassifier(MockDecisionProvider.default())

    top_ads = await classifier.classify("Top 3 anuncios por ROAS")
    help_result = await classifier.classify("Hola, ¿qué puedes hacer?")
    unknown = await classifier.classify("Quiero saber algo")

    assert top_ads.intent is Intent.TOP_ADS_BY_METRIC
    assert top_ads.confidence == 0.95
    assert top_ads.reason == "jev:mock:deterministic"
    assert help_result.intent is Intent.HELP
    assert unknown.intent is Intent.UNKNOWN


@pytest.mark.asyncio
async def test_falls_back_to_rules_when_jev_fails() -> None:
    classifier = JevIntentClassifier(
        MockDecisionProvider(error=JevTimeoutError("timeout")),
        fallback=RuleBasedClassifier(),
    )

    result = await classifier.classify("Top 3 anuncios por ROAS")

    assert result.intent is Intent.TOP_ADS_BY_METRIC
    assert result.reason == "jev_fallback:JevTimeoutError:top_ads_keyword"


class InvalidIntentProvider(DecisionProvider):
    """Simula un Jev que devuelve una opción fuera del catálogo."""

    async def decide(self, request: DecisionRequest) -> DecisionResult:
        name = next(iter(request.questions))
        return DecisionResult(
            response=DecisionResponse(
                model="jev-test",
                answers={name: ChoiceAnswer(type="choice", choice="invented")},
            )
        )


@pytest.mark.asyncio
async def test_falls_back_when_jev_returns_an_unknown_choice() -> None:
    classifier = JevIntentClassifier(
        InvalidIntentProvider(),
        fallback=RuleBasedClassifier(),
    )

    result = await classifier.classify("Hola")

    assert result.intent is Intent.HELP
    assert result.reason == "jev_fallback:invalid_intent:help_keyword"


@pytest.mark.asyncio
async def test_raises_without_fallback() -> None:
    classifier = JevIntentClassifier(MockDecisionProvider(error=JevTimeoutError("timeout")))

    with pytest.raises(JevTimeoutError):
        await classifier.classify("Hola")
