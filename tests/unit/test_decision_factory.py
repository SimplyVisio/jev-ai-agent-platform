"""Tests de selección del proveedor Jev."""

import pytest

from jev_ai.ai.jev.client import TypeSafeJevProvider
from jev_ai.ai.jev.factory import build_decision_provider
from jev_ai.ai.jev.mock import MockDecisionProvider
from jev_ai.config import Settings


def settings(**overrides) -> Settings:
    return Settings(
        database_url="postgresql+asyncpg://user:password@localhost:5432/jev",
        **overrides,
    )


def test_returns_mock_by_default() -> None:
    assert isinstance(build_decision_provider(settings()), MockDecisionProvider)


def test_builds_typesafe_when_configured() -> None:
    provider = build_decision_provider(
        settings(
            jev_provider="typesafe",
            typesafe_api_key="test-key",
            jev_model="jev-1.14.0",
            jev_timeout_seconds=60,
            jev_max_retries=1,
        )
    )

    assert isinstance(provider, TypeSafeJevProvider)
    assert provider.model_name == "jev-1.14.0"


def test_requires_api_key_for_typesafe() -> None:
    with pytest.raises(ValueError, match="TYPESAFE_API_KEY"):
        build_decision_provider(settings(jev_provider="typesafe"))
