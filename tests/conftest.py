from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.community.postgres import PostgresContainer

from jev_ai.config import Settings
from jev_ai.main import create_app
from jev_ai.modules.organizations.models import ApiKey, Organization
from jev_ai.security import hash_api_key

PROJECT_ROOT = Path(__file__).resolve().parents[1]

ALPHA_KEY = "jev_test_alpha_0123456789"
BETA_KEY = "jev_test_beta_0123456789"


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    with PostgresContainer("postgres:17-alpine", driver="asyncpg") as postgres:
        yield postgres.get_connection_url()


@pytest.fixture(scope="session")
def migrated_database_url(database_url: str) -> str:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")
    return database_url


@pytest.fixture(scope="session")
def api_keys() -> dict[str, str]:
    return {"alpha": ALPHA_KEY, "beta": BETA_KEY}


@pytest.fixture(scope="session")
async def organizations(migrated_database_url: str) -> dict[str, UUID]:
    engine = create_async_engine(migrated_database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    organization_ids: dict[str, UUID] = {}

    try:
        async with session_factory() as session:
            for name, key in (("alpha", ALPHA_KEY), ("beta", BETA_KEY)):
                organization = Organization(name=f"Test {name}", currency_code="USD")
                session.add(organization)
                await session.flush()
                session.add(
                    ApiKey(
                        organization_id=organization.id,
                        key_hash=hash_api_key(key),
                    )
                )
                organization_ids[name] = organization.id
            await session.commit()
    finally:
        await engine.dispose()

    return organization_ids


@pytest.fixture
async def session_factory(
    migrated_database_url: str,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(migrated_database_url)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()


@pytest.fixture
def client(migrated_database_url: str) -> Iterator[TestClient]:
    app = create_app(Settings(database_url=migrated_database_url))
    with TestClient(app) as test_client:
        yield test_client
