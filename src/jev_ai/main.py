"""Punto de entrada de la aplicación FastAPI."""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from importlib.metadata import version
from time import perf_counter
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from structlog.contextvars import bind_contextvars, clear_contextvars

from jev_ai.ai.chat import ChatService, PersistentChatService
from jev_ai.ai.jev.classifier import RuleBasedClassifier
from jev_ai.ai.llm.factory import build_llm_provider
from jev_ai.ai.llm.instrumented import InstrumentedLLMProvider
from jev_ai.api.v1.endpoints.health import router as health_router
from jev_ai.api.v1.router import api_router
from jev_ai.config import Settings, get_settings
from jev_ai.infrastructure.database.session import (
    create_database_engine,
    create_session_factory,
)
from jev_ai.modules.conversations.service import ConversationNotFoundError
from jev_ai.modules.marketing.service import MarketingNotFoundError
from jev_ai.observability.context import (
    current_trace_id,
    reset_trace_id,
    set_trace_id,
)
from jev_ai.observability.logging import configure_logging

logger = structlog.get_logger(__name__)


async def _marketing_not_found_handler(
    _request: Request,
    exc: MarketingNotFoundError,
) -> JSONResponse:
    """Convierte un recurso ausente en una respuesta 404 uniforme."""
    return JSONResponse(status_code=404, content={"detail": str(exc)})


async def _conversation_not_found_handler(
    _request: Request,
    exc: ConversationNotFoundError,
) -> JSONResponse:
    """Convierte una conversación ausente en una respuesta 404 uniforme."""
    return JSONResponse(status_code=404, content={"detail": str(exc)})


async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Registra el error con su traza y evita filtrar detalles internos."""
    logger.exception(
        "unhandled_exception",
        method=request.method,
        path=request.url.path,
        error_type=type(exc).__name__,
    )
    trace_id = current_trace_id()
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "trace_id": None if trace_id is None else str(trace_id),
        },
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
    configure_logging(resolved_settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Crea el engine al arrancar y lo libera al apagar la aplicación."""
        engine = create_database_engine(resolved_settings.database_url)
        app.state.session_factory = create_session_factory(engine)
        app.state.chat_service = ChatService(
            RuleBasedClassifier(),
            InstrumentedLLMProvider(build_llm_provider(resolved_settings)),
            session_factory=app.state.session_factory,
        )
        app.state.persistent_chat_service = PersistentChatService(
            app.state.chat_service,
        )
        try:
            yield
        finally:
            await engine.dispose()

    app = FastAPI(
        title=resolved_settings.app_name,
        version=version("jev-ai"),
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def trace_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Asigna una traza opaca y la devuelve en la cabecera de la respuesta."""
        trace_id = uuid4()
        token = set_trace_id(trace_id)
        clear_contextvars()
        bind_contextvars(trace_id=str(trace_id))
        started = perf_counter()
        try:
            response = await call_next(request)
            logger.info(
                "http_request",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=round((perf_counter() - started) * 1000, 2),
            )
            response.headers["X-Trace-ID"] = str(trace_id)
            return response
        finally:
            clear_contextvars()
            reset_trace_id(token)

    app.include_router(health_router)
    app.include_router(api_router, prefix="/api/v1")
    app.add_exception_handler(
        MarketingNotFoundError,
        _marketing_not_found_handler,
    )
    app.add_exception_handler(
        ConversationNotFoundError,
        _conversation_not_found_handler,
    )
    app.add_exception_handler(Exception, _unhandled_exception_handler)
    return app
