"""Router de la versión 1 de la API."""

from fastapi import APIRouter

from jev_ai.api.v1.endpoints import auth

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
