"""Tests de integración del chat offline."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from jev_ai.modules.marketing.models import Ad, AdInsight, Campaign
from jev_ai.modules.organizations.models import ApiKey, Organization
from jev_ai.security import hash_api_key


@dataclass(frozen=True)
class ChatSeed:
    organization_id: UUID
    key: str
    campaign_id: UUID
    ad_winner_id: UUID
    ad_runner_id: UUID


def headers(key: str) -> dict[str, str]:
    return {"X-API-Key": key}


async def _seed_chat(
    session_factory: async_sessionmaker[AsyncSession],
) -> tuple[ChatSeed, ChatSeed]:
    alpha_key = f"jev_test_{uuid4().hex}"
    beta_key = f"jev_test_{uuid4().hex}"

    async with session_factory() as session:
        alpha = Organization(name=f"Chat Alpha {uuid4()}", currency_code="USD")
        beta = Organization(name=f"Chat Beta {uuid4()}", currency_code="USD")
        session.add_all([alpha, beta])
        await session.flush()
        session.add_all(
            [
                ApiKey(organization_id=alpha.id, key_hash=hash_api_key(alpha_key)),
                ApiKey(organization_id=beta.id, key_hash=hash_api_key(beta_key)),
            ]
        )

        alpha_campaign = Campaign(
            organization_id=alpha.id,
            name="Chat Campaign",
            objective="sales",
        )
        beta_campaign = Campaign(
            organization_id=beta.id,
            name="Beta Hidden",
            objective="sales",
        )
        session.add_all([alpha_campaign, beta_campaign])
        await session.flush()

        winner = Ad(
            campaign_id=alpha_campaign.id,
            organization_id=alpha.id,
            name="Chat Winner",
        )
        runner = Ad(
            campaign_id=alpha_campaign.id,
            organization_id=alpha.id,
            name="Chat Runner",
        )
        hidden_ad = Ad(
            campaign_id=beta_campaign.id,
            organization_id=beta.id,
            name="Hidden Ad",
        )
        session.add_all([winner, runner, hidden_ad])
        await session.flush()

        session.add_all(
            [
                AdInsight(
                    ad_id=winner.id,
                    organization_id=alpha.id,
                    date=date(2026, 10, 1),
                    impressions=1000,
                    reach=400,
                    clicks=50,
                    landing_page_views=40,
                    spend=Decimal("100.00"),
                    leads=10,
                    sales=2,
                    revenue=Decimal("500.00"),
                ),
                AdInsight(
                    ad_id=runner.id,
                    organization_id=alpha.id,
                    date=date(2026, 10, 1),
                    impressions=500,
                    reach=200,
                    clicks=20,
                    landing_page_views=20,
                    spend=Decimal("100.00"),
                    leads=5,
                    sales=1,
                    revenue=Decimal("100.00"),
                ),
                AdInsight(
                    ad_id=hidden_ad.id,
                    organization_id=beta.id,
                    date=date(2026, 10, 1),
                    impressions=99999,
                    reach=99999,
                    clicks=99999,
                    landing_page_views=99999,
                    spend=Decimal("999.99"),
                    leads=999,
                    sales=99,
                    revenue=Decimal("9999.99"),
                ),
            ]
        )
        await session.commit()

        return (
            ChatSeed(
                organization_id=alpha.id,
                key=alpha_key,
                campaign_id=alpha_campaign.id,
                ad_winner_id=winner.id,
                ad_runner_id=runner.id,
            ),
            ChatSeed(
                organization_id=beta.id,
                key=beta_key,
                campaign_id=beta_campaign.id,
                ad_winner_id=hidden_ad.id,
                ad_runner_id=hidden_ad.id,
            ),
        )


@pytest.fixture
async def chat_seed(
    session_factory: async_sessionmaker[AsyncSession],
) -> tuple[ChatSeed, ChatSeed]:
    return await _seed_chat(session_factory)


def post_chat(client: TestClient, key: str, message: str, **extra: object) -> dict:
    response = client.post(
        "/api/v1/chat",
        json={"message": message, **extra},
        headers=headers(key),
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_chat_top_ads_returns_ranked_data(
    client: TestClient,
    chat_seed: tuple[ChatSeed, ChatSeed],
) -> None:
    alpha, _beta = chat_seed

    body = post_chat(
        client,
        alpha.key,
        "¿Cuáles son los 2 mejores anuncios por ROAS en octubre de 2026?",
    )

    assert body["status"] == "ok"
    assert body["intent"] == "top_ads_by_metric"
    assert body["query_plan"]["operation"] == "top_ads_by_metric"
    assert body["query_plan"]["limit"] == 2
    assert [item["ad_name"] for item in body["data"]] == ["Chat Winner", "Chat Runner"]
    assert body["data"][0]["metrics"]["roas"] == pytest.approx(5.0)
    assert "Top 2 anuncios por ROAS" in body["reply"]


def test_chat_debug_returns_real_graph_trace(
    client: TestClient,
    chat_seed: tuple[ChatSeed, ChatSeed],
) -> None:
    alpha, _beta = chat_seed

    body = post_chat(
        client,
        alpha.key,
        "¿Cuáles son los 2 mejores anuncios por ROAS en octubre de 2026?",
        debug=True,
    )

    trace = body["trace"]
    assert [step["node"] for step in trace] == [
        "classify_intent",
        "propose_plan",
        "validate_plan",
        "execute_service",
        "generate_response",
    ]
    assert "rule=top_ads_keyword" in trace[0]["detail"]
    assert "top_ads_by_metric" in trace[1]["detail"]
    assert "plan aceptado" in trace[2]["detail"]
    assert "consultando PostgreSQL" in trace[3]["detail"]
    assert "filas=2" in trace[3]["detail"]
    assert "generando respuesta" in trace[4]["detail"]
    assert all(step["duration_ms"] >= 0 for step in trace)


def test_chat_without_debug_does_not_expose_trace(
    client: TestClient,
    chat_seed: tuple[ChatSeed, ChatSeed],
) -> None:
    alpha, _beta = chat_seed

    body = post_chat(
        client,
        alpha.key,
        "¿Cuáles son los 2 mejores anuncios por ROAS en octubre de 2026?",
    )

    assert body["trace"] is None


def test_chat_campaign_performance_uses_org_context(
    client: TestClient,
    chat_seed: tuple[ChatSeed, ChatSeed],
) -> None:
    alpha, _beta = chat_seed

    body = post_chat(
        client,
        alpha.key,
        '¿Cómo va la campaña "Chat Campaign" en octubre de 2026?',
    )

    assert body["status"] == "ok"
    assert body["intent"] == "campaign_performance"
    assert body["data"]["campaign"]["name"] == "Chat Campaign"
    assert body["data"]["metrics"]["impressions"] == 1500
    assert body["data"]["metrics"]["spend"] == "200.00"
    assert body["data"]["metrics"]["roas"] == pytest.approx(3.0)
    assert "Chat Campaign" in body["reply"]


def test_chat_compare_returns_both_periods(
    client: TestClient,
    chat_seed: tuple[ChatSeed, ChatSeed],
) -> None:
    alpha, _beta = chat_seed

    body = post_chat(
        client,
        alpha.key,
        "Compara 2026-10-01 a 2026-10-02 con 2026-09-01 a 2026-09-02",
    )

    assert body["status"] == "ok"
    assert body["intent"] == "compare_periods"
    assert body["query_plan"]["comparison_date_from"] == "2026-09-01"
    assert body["data"]["period_a"]["impressions"] == 1500
    assert body["data"]["period_a"]["spend"] == "200.00"
    assert body["data"]["period_b"]["impressions"] == 0
    assert body["data"]["period_b"]["spend"] == "0.00"
    assert "Periodo A" in body["reply"]
    assert "Periodo B" in body["reply"]


def test_chat_dry_run_validates_without_executing(
    client: TestClient,
    chat_seed: tuple[ChatSeed, ChatSeed],
) -> None:
    alpha, _beta = chat_seed

    body = post_chat(
        client,
        alpha.key,
        "Top 2 anuncios por ROAS en octubre de 2026",
        dry_run=True,
    )

    assert body["status"] == "ok"
    assert body["query_plan"]["operation"] == "top_ads_by_metric"
    assert body["data"] is None
    assert "Plan validado" in body["reply"]


def test_chat_rejects_non_rankable_metric(
    client: TestClient,
    chat_seed: tuple[ChatSeed, ChatSeed],
) -> None:
    alpha, _beta = chat_seed

    body = post_chat(
        client,
        alpha.key,
        "Top 2 anuncios por alcance en octubre de 2026",
    )

    assert body["status"] == "needs_clarification"
    assert body["query_plan"]["metric"] == "reach"
    assert body["data"] is None
    assert "no se puede ordenar" in body["reply"]


def test_chat_does_not_leak_other_organization_data(
    client: TestClient,
    chat_seed: tuple[ChatSeed, ChatSeed],
) -> None:
    _alpha, beta = chat_seed

    body = post_chat(
        client,
        beta.key,
        '¿Cómo va la campaña "Chat Campaign" en octubre de 2026?',
    )

    assert body["status"] == "needs_clarification"
    assert body["data"] is None
    assert "No encontré esa campaña" in body["reply"]


def test_chat_rejects_unsupported_actions(
    client: TestClient,
    chat_seed: tuple[ChatSeed, ChatSeed],
) -> None:
    alpha, _beta = chat_seed

    body = post_chat(
        client,
        alpha.key,
        'Elimina la campaña "Chat Campaign"',
    )

    assert body["status"] == "needs_clarification"
    assert body["intent"] == "unknown"
    assert body["query_plan"] is None
    assert body["data"] is None


def test_chat_help_and_unknown_intents(
    client: TestClient,
    chat_seed: tuple[ChatSeed, ChatSeed],
) -> None:
    alpha, _beta = chat_seed

    help_body = post_chat(client, alpha.key, "¿Qué puedes hacer?")
    assert help_body["intent"] == "help"
    assert help_body["query_plan"] is None
    assert "Prueba con" in help_body["reply"]

    unknown_body = post_chat(client, alpha.key, "Quiero saber algo")
    assert unknown_body["intent"] == "unknown"
    assert unknown_body["status"] == "needs_clarification"
    assert unknown_body["confidence"] == pytest.approx(0.2)


def test_chat_requires_api_key(client: TestClient) -> None:
    response = client.post("/api/v1/chat", json={"message": "Hola"})

    assert response.status_code == 401


def test_chat_validates_message(
    client: TestClient,
    chat_seed: tuple[ChatSeed, ChatSeed],
) -> None:
    alpha, _beta = chat_seed

    response = client.post(
        "/api/v1/chat",
        json={"message": "   "},
        headers=headers(alpha.key),
    )

    assert response.status_code == 422
