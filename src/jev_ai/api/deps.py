"""Dependencias compartidas de FastAPI: sesión de BD y autenticación."""

import hmac
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from jev_ai.modules.organizations.repository import find_api_key_by_hash
from jev_ai.security import hash_api_key

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


@dataclass(frozen=True)
class OrganizationContext:
    """Organización autenticada que acompaña a una petición.

    Es inmutable y solo contiene el identificador; los servicios de negocio lo usan
    para filtrar datos sin confiar en valores enviados por el cliente.
    """

    organization_id: UUID


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Entrega una sesión async y la cierra al terminar la petición.

    La fábrica vive en ``app.state`` y se crea en el lifespan de la aplicación, de
    modo que los tests pueden construir la app con otra base de datos.
    """
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with session_factory() as session:
        yield session


def _unauthorized() -> HTTPException:
    """Construye la respuesta uniforme para claves ausentes o inválidas."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API key",
        headers={"WWW-Authenticate": "ApiKey"},
    )


async def get_current_organization(
    api_key: Annotated[str | None, Depends(api_key_header)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OrganizationContext:
    """Resuelve la organización dueña de la API key enviada.

    El identificador de organización nunca proviene del cuerpo de la petición: sale
    de la clave autenticada y se inyecta en los endpoints.

    Raises:
        HTTPException: 401 si la cabecera falta o la clave no existe.
    """
    if not api_key:
        raise _unauthorized()

    key_hash = hash_api_key(api_key)
    record = await find_api_key_by_hash(session, key_hash)
    if record is None or not hmac.compare_digest(record.key_hash, key_hash):
        raise _unauthorized()

    return OrganizationContext(organization_id=record.organization_id)
