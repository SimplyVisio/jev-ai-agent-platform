"""Consultas de persistencia del módulo de organizaciones."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jev_ai.modules.organizations.models import ApiKey


async def find_api_key_by_hash(session: AsyncSession, key_hash: str) -> ApiKey | None:
    """Busca una API key por su hash SHA-256.

    Args:
        session: Sesión async activa.
        key_hash: Digest hexadecimal calculado a partir de la clave recibida.

    Returns:
        La entidad ``ApiKey`` o ``None`` si no existe. La comparación en tiempo
        constante del hash se realiza en la dependencia de autenticación.
    """
    result = await session.execute(select(ApiKey).where(ApiKey.key_hash == key_hash))
    return result.scalar_one_or_none()
