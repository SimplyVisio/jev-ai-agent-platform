from uuid import UUID

from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_me_without_api_key_returns_401(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "ApiKey"


def test_me_with_invalid_api_key_returns_401(client: TestClient) -> None:
    response = client.get(
        "/api/v1/auth/me",
        headers={"X-API-Key": "jev_invalid_0123456789"},
    )

    assert response.status_code == 401


def test_me_returns_authenticated_organization(
    client: TestClient,
    organizations: dict[str, UUID],
    api_keys: dict[str, str],
) -> None:
    response = client.get(
        "/api/v1/auth/me",
        headers={"X-API-Key": api_keys["alpha"]},
    )

    assert response.status_code == 200
    assert response.json() == {"organization_id": str(organizations["alpha"])}


def test_each_api_key_resolves_its_own_organization(
    client: TestClient,
    organizations: dict[str, UUID],
    api_keys: dict[str, str],
) -> None:
    alpha_response = client.get(
        "/api/v1/auth/me",
        headers={"X-API-Key": api_keys["alpha"]},
    )
    beta_response = client.get(
        "/api/v1/auth/me",
        headers={"X-API-Key": api_keys["beta"]},
    )

    assert alpha_response.json()["organization_id"] == str(organizations["alpha"])
    assert beta_response.json()["organization_id"] == str(organizations["beta"])
    assert alpha_response.json() != beta_response.json()
