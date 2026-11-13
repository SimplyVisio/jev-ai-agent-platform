"""Tests de integración del CRUD de marketing."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from jev_ai.modules.organizations.models import ApiKey, Organization
from jev_ai.security import hash_api_key


async def create_api_organization(
    session_factory: async_sessionmaker[AsyncSession],
) -> tuple[UUID, str]:
    key = f"jev_test_{uuid4().hex}"
    async with session_factory() as session:
        organization = Organization(
            name=f"API {uuid4()}",
            currency_code="USD",
        )
        session.add(organization)
        await session.flush()
        session.add(
            ApiKey(
                organization_id=organization.id,
                key_hash=hash_api_key(key),
            )
        )
        await session.commit()
        return organization.id, key


@pytest.fixture
async def api_organization(
    session_factory: async_sessionmaker[AsyncSession],
) -> tuple[UUID, str]:
    return await create_api_organization(session_factory)


@pytest.fixture
async def two_api_organizations(
    session_factory: async_sessionmaker[AsyncSession],
) -> tuple[tuple[UUID, str], tuple[UUID, str]]:
    return (
        await create_api_organization(session_factory),
        await create_api_organization(session_factory),
    )


def headers(key: str) -> dict[str, str]:
    return {"X-API-Key": key}


def create_campaign(
    client: TestClient,
    key: str,
    *,
    name: str = "Launch",
    objective: str = "traffic",
) -> dict[str, object]:
    response = client.post(
        "/api/v1/campaigns",
        json={"name": name, "objective": objective},
        headers=headers(key),
    )
    assert response.status_code == 201
    return response.json()


def test_campaign_crud(
    client: TestClient,
    api_organization: tuple[UUID, str],
) -> None:
    organization_id, key = api_organization
    campaign = create_campaign(client, key, name="  Launch  ")
    campaign_id = campaign["id"]

    assert campaign["name"] == "Launch"
    assert campaign["objective"] == "traffic"
    assert campaign["status"] == "active"
    assert campaign["organization_id"] == str(organization_id)

    listed = client.get("/api/v1/campaigns", headers=headers(key))
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [campaign_id]

    traffic = client.get("/api/v1/campaigns?objective=traffic", headers=headers(key))
    sales = client.get("/api/v1/campaigns?objective=sales", headers=headers(key))
    assert [item["id"] for item in traffic.json()] == [campaign_id]
    assert sales.json() == []

    fetched = client.get(f"/api/v1/campaigns/{campaign_id}", headers=headers(key))
    assert fetched.status_code == 200
    assert fetched.json()["id"] == campaign_id

    patched = client.patch(
        f"/api/v1/campaigns/{campaign_id}",
        json={"name": "Renamed", "objective": "sales"},
        headers=headers(key),
    )
    assert patched.status_code == 200
    assert patched.json()["name"] == "Renamed"
    assert patched.json()["objective"] == "sales"
    assert patched.json()["status"] == "active"

    archived = client.delete(
        f"/api/v1/campaigns/{campaign_id}",
        headers=headers(key),
    )
    assert archived.status_code == 204
    assert archived.content == b""

    after_archive = client.get(
        f"/api/v1/campaigns/{campaign_id}",
        headers=headers(key),
    )
    assert after_archive.json()["status"] == "archived"

    active = client.get("/api/v1/campaigns?status=active", headers=headers(key))
    assert active.json() == []

    all_campaigns = client.get("/api/v1/campaigns", headers=headers(key))
    assert [item["id"] for item in all_campaigns.json()] == [campaign_id]

    archived_list = client.get(
        "/api/v1/campaigns?status=archived",
        headers=headers(key),
    )
    assert [item["id"] for item in archived_list.json()] == [campaign_id]


def test_campaign_pagination(
    client: TestClient,
    api_organization: tuple[UUID, str],
) -> None:
    _, key = api_organization
    for index in range(3):
        create_campaign(client, key, name=f"Campaign {index}")

    first_page = client.get("/api/v1/campaigns?limit=2", headers=headers(key))
    second_page = client.get(
        "/api/v1/campaigns?limit=2&offset=2",
        headers=headers(key),
    )

    assert len(first_page.json()) == 2
    assert len(second_page.json()) == 1


def test_campaign_validation(
    client: TestClient,
    api_organization: tuple[UUID, str],
) -> None:
    _, key = api_organization

    invalid_objective = client.post(
        "/api/v1/campaigns",
        json={"name": "Launch", "objective": "invalid"},
        headers=headers(key),
    )
    blank_name = client.post(
        "/api/v1/campaigns",
        json={"name": "   ", "objective": "traffic"},
        headers=headers(key),
    )
    invalid_limit = client.get(
        "/api/v1/campaigns?limit=101",
        headers=headers(key),
    )
    invalid_offset = client.get(
        "/api/v1/campaigns?offset=-1",
        headers=headers(key),
    )

    assert invalid_objective.status_code == 422
    assert blank_name.status_code == 422
    assert invalid_limit.status_code == 422
    assert invalid_offset.status_code == 422


def test_ad_crud_nested(
    client: TestClient,
    api_organization: tuple[UUID, str],
) -> None:
    organization_id, key = api_organization
    campaign = create_campaign(client, key)
    campaign_id = campaign["id"]

    created = client.post(
        f"/api/v1/campaigns/{campaign_id}/ads",
        json={"name": "Ad 1"},
        headers=headers(key),
    )
    assert created.status_code == 201
    ad = created.json()
    ad_id = ad["id"]
    assert ad["campaign_id"] == campaign_id
    assert ad["organization_id"] == str(organization_id)
    assert ad["status"] == "active"

    listed = client.get(
        f"/api/v1/campaigns/{campaign_id}/ads",
        headers=headers(key),
    )
    assert [item["id"] for item in listed.json()] == [ad_id]

    fetched = client.get(
        f"/api/v1/campaigns/{campaign_id}/ads/{ad_id}",
        headers=headers(key),
    )
    assert fetched.status_code == 200

    patched = client.patch(
        f"/api/v1/campaigns/{campaign_id}/ads/{ad_id}",
        json={"name": "Ad 1 renamed", "status": "paused"},
        headers=headers(key),
    )
    assert patched.status_code == 200
    assert patched.json()["name"] == "Ad 1 renamed"
    assert patched.json()["status"] == "paused"

    paused = client.get(
        f"/api/v1/campaigns/{campaign_id}/ads?status=paused",
        headers=headers(key),
    )
    assert [item["id"] for item in paused.json()] == [ad_id]

    archived = client.delete(
        f"/api/v1/campaigns/{campaign_id}/ads/{ad_id}",
        headers=headers(key),
    )
    assert archived.status_code == 204

    archived_list = client.get(
        f"/api/v1/campaigns/{campaign_id}/ads?status=archived",
        headers=headers(key),
    )
    assert [item["id"] for item in archived_list.json()] == [ad_id]

    after_archive = client.get(
        f"/api/v1/campaigns/{campaign_id}/ads/{ad_id}",
        headers=headers(key),
    )
    assert after_archive.json()["status"] == "archived"


def test_ad_under_unknown_campaign_returns_404(
    client: TestClient,
    api_organization: tuple[UUID, str],
) -> None:
    _, key = api_organization
    unknown_campaign_id = uuid4()

    listed = client.get(
        f"/api/v1/campaigns/{unknown_campaign_id}/ads",
        headers=headers(key),
    )
    created = client.post(
        f"/api/v1/campaigns/{unknown_campaign_id}/ads",
        json={"name": "Ad 1"},
        headers=headers(key),
    )

    assert listed.status_code == 404
    assert created.status_code == 404
    assert created.json() == {"detail": "Campaign not found"}


def test_organizations_cannot_access_each_other(
    client: TestClient,
    two_api_organizations: tuple[tuple[UUID, str], tuple[UUID, str]],
) -> None:
    (_, key_a), (_, key_b) = two_api_organizations
    campaign = create_campaign(client, key_a)
    campaign_id = campaign["id"]
    ad = client.post(
        f"/api/v1/campaigns/{campaign_id}/ads",
        json={"name": "Private ad"},
        headers=headers(key_a),
    ).json()
    ad_id = ad["id"]

    assert client.get("/api/v1/campaigns", headers=headers(key_b)).json() == []
    assert client.get(f"/api/v1/campaigns/{campaign_id}", headers=headers(key_b)).status_code == 404
    assert (
        client.patch(
            f"/api/v1/campaigns/{campaign_id}",
            json={"name": "Stolen"},
            headers=headers(key_b),
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/api/v1/campaigns/{campaign_id}",
            headers=headers(key_b),
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/v1/campaigns/{campaign_id}/ads",
            headers=headers(key_b),
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/v1/campaigns/{campaign_id}/ads",
            json={"name": "Intruder"},
            headers=headers(key_b),
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/v1/campaigns/{campaign_id}/ads/{ad_id}",
            headers=headers(key_b),
        ).status_code
        == 404
    )

    assert client.get(f"/api/v1/campaigns/{campaign_id}", headers=headers(key_a)).status_code == 200


def test_campaigns_require_api_key(client: TestClient) -> None:
    response = client.get("/api/v1/campaigns")

    assert response.status_code == 401
