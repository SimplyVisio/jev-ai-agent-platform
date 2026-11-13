"""Punto de entrada de la aplicación FastAPI."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import version

from fastapi import FastAPI

from jev_ai.api.v1.endpoints.health import router as health_router
from jev_ai.api.v1.router import api_router
from jev_ai.config import Settings, get_settings
from jev_ai.infrastructure.database.session import (
    create_database_engine,
    create_session_factory,
)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Construye la aplicación y registra su ciclo de vida.

    Args:
        settings: Configuración explícita. Si se omite, se carga desde el entorno.
            Los tests la usan para apuntar a una base de datos temporal.

    Returns:
        Aplicación con routers, OpenAPI y engine async gestionado por el lifespan.
    """
    resolved_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Crea el engine al arrancar y lo libera al apagar la aplicación."""
        engine = create_database_engine(resolved_settings.database_url)
        app.state.session_factory = create_session_factory(engine)
        try:
            yield
        finally:
            await engine.dispose()

    app = FastAPI(
        title=resolved_settings.app_name,
        version=version("jev-ai"),
        lifespan=lifespan,
    )
    app.include_router(health_router)
    app.include_router(api_router, prefix="/api/v1")
    return app
