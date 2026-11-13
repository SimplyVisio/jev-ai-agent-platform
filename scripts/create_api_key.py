"""Crea una organización y una API key desde la línea de comandos.

Uso:
    python scripts/create_api_key.py --organization "Demo"

La clave se imprime una sola vez; solo se guarda su hash SHA-256.
"""

import argparse
import asyncio
import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jev_ai.config import get_settings
from jev_ai.infrastructure.database.session import (
    create_database_engine,
    create_session_factory,
)
from jev_ai.modules.organizations.models import ApiKey, Organization
from jev_ai.security import hash_api_key


async def get_or_create_organization(
    session: AsyncSession,
    name: str,
    currency_code: str,
) -> Organization:
    """Busca una organización por nombre o la crea si no existe.

    Args:
        session: Sesión async activa.
        name: Nombre de la organización.
        currency_code: Código ISO 4217 usado si hay que crearla.

    Returns:
        Organización existente o recién creada.
    """
    organization = await session.scalar(select(Organization).where(Organization.name == name))
    if organization is None:
        organization = Organization(name=name, currency_code=currency_code)
        session.add(organization)
        await session.flush()
    return organization


async def create_api_key(
    organization_name: str,
    currency_code: str,
    raw_key: str | None,
) -> None:
    """Crea una API key, guarda su hash e imprime la clave una única vez.

    Args:
        organization_name: Organización a la que pertenecerá la clave.
        currency_code: Moneda de la organización si hay que crearla.
        raw_key: Clave en texto plano. Si es ``None`` se genera aleatoriamente.

    Raises:
        SystemExit: Si la clave es demasiado corta o ya existe.
    """
    if raw_key is not None and len(raw_key) < 16:
        raise SystemExit("La API key debe tener al menos 16 caracteres.")

    key = raw_key or f"jev_{secrets.token_urlsafe(32)}"
    key_hash = hash_api_key(key)

    engine = create_database_engine(get_settings().database_url)
    session_factory = create_session_factory(engine)

    try:
        async with session_factory() as session:
            organization = await get_or_create_organization(
                session,
                organization_name,
                currency_code,
            )
            existing = await session.scalar(select(ApiKey).where(ApiKey.key_hash == key_hash))
            if existing is not None:
                raise SystemExit("Esa API key ya existe.")

            session.add(ApiKey(organization_id=organization.id, key_hash=key_hash))
            await session.commit()

            print(f"Organización: {organization.name} ({organization.id})")
            print("API key (se muestra una sola vez):")
            print(key)
    finally:
        await engine.dispose()


def parse_args() -> argparse.Namespace:
    """Define y parsea los argumentos del script."""
    parser = argparse.ArgumentParser(description="Crea una organización y su API key.")
    parser.add_argument("--organization", default="Demo", help="Nombre de la organización.")
    parser.add_argument("--currency", default="USD", help="Código ISO de la moneda.")
    parser.add_argument(
        "--key",
        default=None,
        help="API key en texto plano. Si se omite, se genera una.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(create_api_key(args.organization, args.currency, args.key))
