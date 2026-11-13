"""Tests del presupuesto de contexto conversacional."""

from jev_ai.ai.memory import trim_context
from jev_ai.modules.conversations.models import Message, MessageRole


def _message(sequence: int, content: str) -> Message:
    return Message(
        conversation_id=None,
        organization_id=None,
        sequence=sequence,
        role=MessageRole.USER,
        content=content,
    )


def test_keeps_newest_messages_within_budget() -> None:
    messages = [_message(1, "a" * 10), _message(2, "b" * 10), _message(3, "c" * 10)]

    context = trim_context(messages, max_chars=25)

    assert [item.content for item in context] == ["b" * 10, "c" * 10]
    assert [item.role for item in context] == ["user", "user"]


def test_truncates_newest_message_when_it_does_not_fit() -> None:
    context = trim_context([_message(1, "x" * 20)], max_chars=5)

    assert len(context) == 1
    assert context[0].content == "xxxxx"


def test_zero_budget_returns_empty_context() -> None:
    assert trim_context([_message(1, "hola")], max_chars=0) == ()
