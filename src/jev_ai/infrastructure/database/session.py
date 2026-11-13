"""Construcción del engine async y de las fábricas de sesiones."""

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def create_database_engine(database_url: str) -> AsyncEngine:
    """Crea un engine async con validación de conexiones reutilizadas.

    Args:
        database_url: DSN compatible con asyncpg.

    Returns:
        Engine que no abre conexiones hasta la primera consulta.
    """
    return create_async_engine(database_url, pool_pre_ping=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Crea la fábrica de sesiones usada por los endpoints.

    ``expire_on_commit=False`` permite devolver entidades ya cargadas después de un
    commit sin provocar consultas implícitas al serializarlas.
    """
    return async_sessionmaker(engine, expire_on_commit=False)
