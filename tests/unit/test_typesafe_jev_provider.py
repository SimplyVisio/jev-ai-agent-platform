"""Tests del contrato y cliente HTTP de TypeSafe JEV sin llamadas reales."""

import json

import httpx
import pytest
from pydantic import ValidationError

from jev_ai.ai.jev.client import TypeSafeJevProvider
from jev_ai.ai.jev.contracts import (
    BoxAnswer,
    BoxQuestion,
    ChoiceAnswer,
    ChoiceQuestion,
    DecisionRequest,
    NoulAnswer,
    NoulQuestion,
    ScoreQuestion,
)
from jev_ai.ai.jev.errors import (
    JevAPIError,
    JevConnectionError,
    JevRequestError,
    JevResponseError,
    JevTimeoutError,
)
from jev_ai.observability.usage import TokenUsage


def provider(handler, **overrides) -> TypeSafeJevProvider:
    """Construye el cliente con un transporte determinista."""
    return TypeSafeJevProvider(
        api_key="test-key",
        base_url="https://jev.example",
        timeout=5,
        transport=httpx.MockTransport(handler),
        **overrides,
    )


def choice_response() -> dict:
    return {
        "model": "jev-1.13.0",
        "answers": {
            "department": {
                "type": "choice",
                "choice": "technical",
                "probabilities": {"billing": 0.08, "technical": 0.85},
                "confidence": 0.82,
            }
        },
        "usage": {"input_tokens": 312, "output_tokens": 48},
    }


@pytest.mark.asyncio
async def test_sends_choice_request_and_parses_response() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json=choice_response(),
            headers={"x-typesafe-request-id": "req_123"},
        )

    request = DecisionRequest(
        state="Help! My payouts have been failing for 3 days.",
        questions={
            "department": ChoiceQuestion(
                instructions="Which team should handle this?",
                criteria={
                    "billing": "Payments, invoicing, refunds",
                    "technical": "Bugs, outages, integrations",
                },
            )
        },
    )

    result = await provider(handler).decide(request)

    http_request = captured["request"]
    assert str(http_request.url) == "https://jev.example/v1/systemone"
    assert http_request.headers["authorization"] == "Bearer test-key"
    assert http_request.headers["content-type"] == "application/json"
    assert captured["payload"] == {
        "state": "Help! My payouts have been failing for 3 days.",
        "questions": {
            "department": {
                "type": "choice",
                "instructions": "Which team should handle this?",
                "criteria": {
                    "billing": "Payments, invoicing, refunds",
                    "technical": "Bugs, outages, integrations",
                },
            }
        },
        "model": "jev-1.13.0",
    }
    assert result.request_id == "req_123"
    assert result.response.model == "jev-1.13.0"
    answer = result.response.answers["department"]
    assert isinstance(answer, ChoiceAnswer)
    assert answer.choice == "technical"
    assert answer.confidence == 0.82
    assert result.usage == TokenUsage(input_tokens=312, output_tokens=48)


@pytest.mark.asyncio
async def test_sends_noul_and_score_questions_and_resolves_model() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "model": "jev-1.13.0",
                "answers": {
                    "is_frustrated": {"type": "noul", "noul": 0.68},
                    "urgency": {
                        "type": "score",
                        "score": 2,
                        "probabilities": {"0": 0.01, "1": 0.04, "2": 0.95},
                        "confidence": 0.9,
                    },
                },
            },
        )

    request = DecisionRequest(
        model="jev-latest",
        state={"message": "I was double charged"},
        questions={
            "is_frustrated": NoulQuestion(instructions="Is the customer frustrated?"),
            "urgency": ScoreQuestion(
                instructions="How urgent is this?",
                criteria=["can wait", "soon", "today"],
            ),
        },
    )

    result = await provider(handler).decide(request)

    assert captured["payload"]["model"] == "jev-latest"
    assert result.response.model == "jev-1.13.0"
    noul = result.response.answers["is_frustrated"]
    assert isinstance(noul, NoulAnswer)
    assert noul.noul == 0.68
    assert result.response.answers["urgency"].confidence == 0.9
    assert result.response.answers["urgency"].legend is None
    assert result.usage is None


@pytest.mark.asyncio
async def test_supports_box_question_and_legend() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "model": "jev-1.14.0",
                "answers": {
                    "button": {
                        "type": "box",
                        "box": {"top": 0.1, "bottom": 0.2, "left": 0.3, "right": 0.4},
                        "confidence": 0.9,
                    },
                    "severity": {
                        "type": "score",
                        "score": 0.67,
                        "legend": {"0": "safe", "1": "unsafe"},
                    },
                },
            },
        )

    request = DecisionRequest(
        model="jev-1.14.0",
        state={"image": "base64"},
        questions={
            "button": BoxQuestion(instructions="Where is the button?"),
            "severity": ScoreQuestion(instructions="How bad?", criteria=["safe", "unsafe"]),
        },
    )

    result = await provider(handler).decide(request)

    assert captured["payload"]["questions"]["button"] == {
        "type": "box",
        "instructions": "Where is the button?",
    }
    answer = result.response.answers["button"]
    assert isinstance(answer, BoxAnswer)
    assert answer.box.top == 0.1
    assert result.response.answers["severity"].legend == {"0": "safe", "1": "unsafe"}


def test_rejects_invalid_requests() -> None:
    with pytest.raises(ValidationError):
        DecisionRequest(state=None, questions={})

    with pytest.raises(ValidationError):
        DecisionRequest(state="hola", questions={})

    with pytest.raises(ValidationError):
        ChoiceQuestion(
            instructions="Elige",
            criteria={str(index): f"opción {index}" for index in range(256)},
        )

    with pytest.raises(ValidationError):
        ScoreQuestion(instructions="Puntúa", criteria=["solo un nivel"])


@pytest.mark.asyncio
async def test_maps_http_error_with_request_id_and_detail() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            422,
            json={"detail": [{"msg": "state must not be null"}]},
            headers={
                "x-typesafe-request-id": "req_422",
                "retry-after": "2",
            },
        )

    with pytest.raises(JevAPIError) as exc_info:
        await provider(handler).decide(
            DecisionRequest(
                state="hola",
                questions={"category": ChoiceQuestion(instructions="Elige", criteria={"a": "A"})},
            )
        )

    error = exc_info.value
    assert error.status_code == 422
    assert "state must not be null" in error.detail
    assert error.request_id == "req_422"
    assert error.retry_after == "2"


@pytest.mark.asyncio
async def test_maps_timeout_and_connection_errors() -> None:
    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    def connection_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    request = DecisionRequest(
        state="hola",
        questions={"category": ChoiceQuestion(instructions="Elige", criteria={"a": "A"})},
    )

    with pytest.raises(JevTimeoutError):
        await provider(timeout_handler).decide(request)
    with pytest.raises(JevConnectionError):
        await provider(connection_handler).decide(request)


@pytest.mark.asyncio
async def test_rejects_malformed_or_invalid_responses() -> None:
    request = DecisionRequest(
        state="hola",
        questions={"category": ChoiceQuestion(instructions="Elige", criteria={"a": "A"})},
    )

    def invalid_json(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not json")

    def invalid_contract(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "jev-1.13.0",
                "answers": {
                    "category": {
                        "type": "choice",
                        "choice": "a",
                        "probabilities": {"a": 1.5},
                    }
                },
            },
        )

    with pytest.raises(JevResponseError, match="invalid JSON"):
        await provider(invalid_json).decide(request)
    with pytest.raises(JevResponseError, match="contract"):
        await provider(invalid_contract).decide(request)


@pytest.mark.asyncio
async def test_retries_429_and_529_with_retry_after_and_backoff(monkeypatch) -> None:
    delays: list[float] = []
    attempts = 0

    async def fake_sleep(seconds: float) -> None:
        delays.append(seconds)

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(
                429, json={"detail": "slow down"}, headers={"retry-after": "0.25"}
            )
        if attempts == 2:
            return httpx.Response(529, json={"detail": "overloaded"})
        return httpx.Response(200, json=choice_response())

    monkeypatch.setattr("jev_ai.ai.jev.client.asyncio.sleep", fake_sleep)

    request = DecisionRequest(
        state="hola",
        questions={"category": ChoiceQuestion(instructions="Elige", criteria={"a": "A"})},
    )
    result = await provider(handler, max_retries=2).decide(request)

    assert result.response.model == "jev-1.13.0"
    assert attempts == 3
    assert delays == [0.25, 1.0]


@pytest.mark.asyncio
async def test_stops_retrying_and_returns_last_api_error(monkeypatch) -> None:
    attempts = 0

    async def fake_sleep(_seconds: float) -> None:
        return None

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(529, json={"detail": "overloaded"})

    monkeypatch.setattr("jev_ai.ai.jev.client.asyncio.sleep", fake_sleep)

    request = DecisionRequest(
        state="hola",
        questions={"category": ChoiceQuestion(instructions="Elige", criteria={"a": "A"})},
    )
    with pytest.raises(JevAPIError) as exc_info:
        await provider(handler, max_retries=1).decide(request)

    assert exc_info.value.status_code == 529
    assert attempts == 2


@pytest.mark.asyncio
async def test_rejects_non_finite_and_excessive_nesting_before_http(monkeypatch) -> None:
    called = False

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, json=choice_response())

    request = DecisionRequest(
        state={"value": float("nan")},
        questions={"category": ChoiceQuestion(instructions="Elige", criteria={"a": "A"})},
    )
    with pytest.raises(JevRequestError, match="non-finite"):
        await provider(handler).decide(request)

    nested: object = "value"
    for _ in range(65):
        nested = [nested]
    request = DecisionRequest(
        state=nested,
        questions={"category": ChoiceQuestion(instructions="Elige", criteria={"a": "A"})},
    )
    with pytest.raises(JevRequestError, match="nesting"):
        await provider(handler).decide(request)

    monkeypatch.setattr("jev_ai.ai.jev.client.MAX_REQUEST_BYTES", 10)
    request = DecisionRequest(
        state="hola",
        questions={"category": ChoiceQuestion(instructions="Elige", criteria={"a": "A"})},
    )
    with pytest.raises(JevRequestError, match="exceeds"):
        await provider(handler).decide(request)

    assert called is False


def test_rejects_blank_api_key_and_invalid_client_options() -> None:
    with pytest.raises(ValueError, match="TYPESAFE_API_KEY"):
        TypeSafeJevProvider(api_key="  ")
    with pytest.raises(ValueError, match="max_retries"):
        TypeSafeJevProvider(api_key="key", max_retries=-1)
    with pytest.raises(ValueError, match="retry_backoff"):
        TypeSafeJevProvider(api_key="key", retry_backoff=-1)

    instance = provider(lambda _request: httpx.Response(200, json=choice_response()))

    assert instance.provider_name == "typesafe"
    assert instance.model_name == "jev-1.13.0"
