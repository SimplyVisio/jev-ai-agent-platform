"""Tests de integración de conversaciones persistentes."""

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
class ConversationSeed:
    organization_id: UUID
    key: str
    campaign_id: UUID


def headers(key: str) -> dict[str, str]:
    return {"X-API-Key": key}


async def _seed(
    session_factory: async_sessionmaker[AsyncSession],
) -> tuple[ConversationSeed, ConversationSeed]:
    alpha_key = f"jev_test_{uuid4().hex}"
    beta_key = f"jev_test_{uuid4().hex}"

    async with session_factory() as session:
        alpha = Organization(name=f"Conversation Alpha {uuid4()}", currency_code="USD")
        beta = Organization(name=f"Conversation Beta {uuid4()}", currency_code="USD")
        session.add_all([alpha, beta])
        await session.flush()
        session.add_all(
            [
                ApiKey(organization_id=alpha.id, key_hash=hash_api_key(alpha_key)),
                ApiKey(organization_id=beta.id, key_hash=hash_api_key(beta_key)),
            ]
        )

        campaign = Campaign(
            organization_id=alpha.id,
            name="Memory Campaign",
            objective="sales",
        )
        session.add(campaign)
        await session.flush()
        ad = Ad(
            campaign_id=campaign.id,
            organization_id=alpha.id,
            name="Memory Winner",
        )
        session.add(ad)
        await session.flush()
        session.add(
            AdInsight(
                ad_id=ad.id,
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
            )
        )
        await session.commit()

        return (
            ConversationSeed(alpha.id, alpha_key, campaign.id),
            ConversationSeed(beta.id, beta_key, uuid4()),
        )


@pytest.fixture
async def conversation_seed(
    session_factory: async_sessionmaker[AsyncSession],
) -> tuple[ConversationSeed, ConversationSeed]:
    return await _seed(session_factory)


def create_conversation(
    client: TestClient,
    key: str,
    *,
    title: str | None = None,
) -> dict:
    response = client.post(
        "/api/v1/conversations",
        json={} if title is None else {"title": title},
        headers=headers(key),
    )
    assert response.status_code == 201, response.text
    return response.json()


def send_message(
    client: TestClient,
    key: str,
    conversation_id: str,
    message: str,
    *,
    debug: bool = False,
) -> dict:
    response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"message": message, "debug": debug},
        headers=headers(key),
    )
    assert response.status_code == 201, response.text
    return response.json()


def messages(client: TestClient, key: str, conversation_id: str) -> list[dict]:
    response = client.get(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers=headers(key),
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_create_and_send_persists_both_messages(
    client: TestClient,
    conversation_seed: tuple[ConversationSeed, ConversationSeed],
) -> None:
    alpha, _beta = conversation_seed
    conversation = create_conversation(client, alpha.key)

    assert conversation["title"] is None
    body = send_message(client, alpha.key, conversation["id"], "Hola")
    assert body["status"] == "ok"
    assert body["intent"] == "help"
    assert body["query_plan"] is None

    detail = client.get(
        f"/api/v1/conversations/{conversation['id']}",
        headers=headers(alpha.key),
    )
    assert detail.status_code == 200
    assert detail.json()["title"] == "Hola"

    transcript = messages(client, alpha.key, conversation["id"])
    assert [item["role"] for item in transcript] == ["user", "assistant"]
    assert [item["sequence"] for item in transcript] == [1, 2]
    assert transcript[0]["content"] == "Hola"
    assert transcript[1]["status"] == "ok"
    assert transcript[0]["id"] == body["user_message_id"]
    assert transcript[1]["id"] == body["assistant_message_id"]


def test_top_ads_message_persists_the_plan(
    client: TestClient,
    conversation_seed: tuple[ConversationSeed, ConversationSeed],
) -> None:
    alpha, _beta = conversation_seed
    conversation = create_conversation(client, alpha.key)

    body = send_message(
        client,
        alpha.key,
        conversation["id"],
        "Top 2 anuncios por ROAS en octubre de 2026",
    )

    assert body["status"] == "ok"
    assert body["query_plan"]["operation"] == "top_ads_by_metric"
    assert body["data"][0]["ad_name"] == "Memory Winner"

    assistant = messages(client, alpha.key, conversation["id"])[1]
    assert assistant["query_plan"]["operation"] == "top_ads_by_metric"
    assert assistant["query_plan"]["metric"] == "roas"
    assert "data" not in assistant


def test_send_message_debug_returns_graph_trace(
    client: TestClient,
    conversation_seed: tuple[ConversationSeed, ConversationSeed],
) -> None:
    alpha, _beta = conversation_seed
    conversation = create_conversation(client, alpha.key)

    body = send_message(
        client,
        alpha.key,
        conversation["id"],
        "Top 2 anuncios por ROAS en octubre de 2026",
        debug=True,
    )

    assert [step["node"] for step in body["trace"]] == [
        "classify_intent",
        "propose_plan",
        "validate_plan",
        "execute_service",
        "generate_response",
    ]
    assert body["data"][0]["ad_name"] == "Memory Winner"
    assert messages(client, alpha.key, conversation["id"])[1]["query_plan"] is not None


def test_send_message_without_debug_has_no_trace(
    client: TestClient,
    conversation_seed: tuple[ConversationSeed, ConversationSeed],
) -> None:
    alpha, _beta = conversation_seed
    conversation = create_conversation(client, alpha.key)

    body = send_message(client, alpha.key, conversation["id"], "Hola")

    assert body["trace"] is None


def test_follow_up_uses_persisted_memory(
    client: TestClient,
    conversation_seed: tuple[ConversationSeed, ConversationSeed],
) -> None:
    alpha, _beta = conversation_seed
    conversation = create_conversation(client, alpha.key)

    send_message(
        client,
        alpha.key,
        conversation["id"],
        "Top 2 anuncios por ROAS en octubre de 2026",
    )
    body = send_message(client, alpha.key, conversation["id"], "¿Y en septiembre de 2026?")

    assert body["status"] == "ok"
    assert body["intent"] == "top_ads_by_metric"
    assert body["query_plan"]["metric"] == "roas"
    assert body["query_plan"]["date_from"] == "2026-09-01"
    assert body["query_plan"]["date_to"] == "2026-09-30"
    assert body["data"] == []

    transcript = messages(client, alpha.key, conversation["id"])
    assert len(transcript) == 4
    assert transcript[3]["query_plan"]["date_from"] == "2026-09-01"


def test_memory_window_excludes_old_plans(
    client: TestClient,
    conversation_seed: tuple[ConversationSeed, ConversationSeed],
) -> None:
    alpha, _beta = conversation_seed
    conversation = create_conversation(client, alpha.key)

    send_message(
        client,
        alpha.key,
        conversation["id"],
        "Top 2 anuncios por ROAS en octubre de 2026",
    )
    for _ in range(5):
        send_message(client, alpha.key, conversation["id"], "Hola")

    body = send_message(
        client,
        alpha.key,
        conversation["id"],
        "¿Y en septiembre de 2026?",
    )

    assert body["status"] == "needs_clarification"
    assert body["query_plan"] is None


def test_campaign_follow_up_reuses_campaign_name(
    client: TestClient,
    conversation_seed: tuple[ConversationSeed, ConversationSeed],
) -> None:
    alpha, _beta = conversation_seed
    conversation = create_conversation(client, alpha.key)

    send_message(
        client,
        alpha.key,
        conversation["id"],
        '¿Cómo va la campaña "Memory Campaign"?',
    )
    body = send_message(
        client,
        alpha.key,
        conversation["id"],
        "¿Y en octubre de 2026?",
    )

    assert body["status"] == "ok"
    assert body["intent"] == "campaign_performance"
    assert body["query_plan"]["campaign_name"] == "Memory Campaign"
    assert body["query_plan"]["date_from"] == "2026-10-01"
    assert body["query_plan"]["date_to"] == "2026-10-31"
    assert body["data"]["campaign"]["name"] == "Memory Campaign"


def test_other_organization_cannot_read_or_append(
    client: TestClient,
    conversation_seed: tuple[ConversationSeed, ConversationSeed],
) -> None:
    alpha, beta = conversation_seed
    conversation = create_conversation(client, alpha.key)

    detail = client.get(
        f"/api/v1/conversations/{conversation['id']}",
        headers=headers(beta.key),
    )
    transcript = client.get(
        f"/api/v1/conversations/{conversation['id']}/messages",
        headers=headers(beta.key),
    )
    append = client.post(
        f"/api/v1/conversations/{conversation['id']}/messages",
        json={"message": "Hola"},
        headers=headers(beta.key),
    )
    listing = client.get("/api/v1/conversations", headers=headers(beta.key))

    assert detail.status_code == 404
    assert transcript.status_code == 404
    assert append.status_code == 404
    assert listing.status_code == 200
    assert listing.json() == []


def test_stateless_chat_does_not_persist(
    client: TestClient,
    conversation_seed: tuple[ConversationSeed, ConversationSeed],
) -> None:
    alpha, _beta = conversation_seed

    response = client.post(
        "/api/v1/chat",
        json={"message": "Hola"},
        headers=headers(alpha.key),
    )
    assert response.status_code == 200

    listing = client.get("/api/v1/conversations", headers=headers(alpha.key))
    assert listing.status_code == 200
    assert listing.json() == []


def test_message_validation_and_unknown_conversation(
    client: TestClient,
    conversation_seed: tuple[ConversationSeed, ConversationSeed],
) -> None:
    alpha, _beta = conversation_seed

    empty = client.post(
        "/api/v1/conversations",
        json={"title": "   "},
        headers=headers(alpha.key),
    )
    missing = client.post(
        f"/api/v1/conversations/{uuid4()}/messages",
        json={"message": "Hola"},
        headers=headers(alpha.key),
    )

    assert empty.status_code == 422
    assert missing.status_code == 404
