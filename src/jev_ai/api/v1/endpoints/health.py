"""Endpoint de liveness del servicio."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Estado básico del proceso HTTP.

    No comprueba la base de datos: sirve para saber si el servidor está vivo.
    """

    status: Literal["ok"] = "ok"


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Devuelve ``ok`` cuando el proceso puede atender peticiones."""
    return HealthResponse()
