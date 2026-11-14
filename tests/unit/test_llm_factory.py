"""Tests de selección del proveedor LLM."""

import pytest

from jev_ai.ai.llm.factory import build_llm_provider
from jev_ai.ai.llm.mock import MockLLMProvider
from jev_ai.ai.llm.openai_compatible import OpenAICompatibleProvider
from jev_ai.config import Settings

_DATABASE_URL = "postgresql+asyncpg://user:password@localhost:5432/jev_ai"


def test_defaults_to_mock() -> None:
    provider = build_llm_provider(Settings(database_url=_DATABASE_URL))

    assert isinstance(provider, MockLLMProvider)


def test_openai_requires_api_key() -> None:
    with pytest.raises(ValueError, match="LLM_API_KEY"):
        build_llm_provider(
            Settings(
                database_url=_DATABASE_URL,
                llm_provider="openai",
                llm_api_key="  ",
            )
        )


def test_builds_openai_provider_with_settings() -> None:
    provider = build_llm_provider(
        Settings(
            database_url=_DATABASE_URL,
            llm_provider="openai",
            llm_api_key="test-key",
            llm_model="test-model",
            llm_base_url="https://llm.example/v1",
            llm_timeout_seconds=10,
        )
    )

    assert isinstance(provider, OpenAICompatibleProvider)
