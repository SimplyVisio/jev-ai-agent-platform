"""Router de la versión 1 de la API."""

from fastapi import APIRouter

from jev_ai.api.v1.endpoints import ads, analytics, auth, campaigns, chat

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(campaigns.router, prefix="/campaigns")
api_router.include_router(ads.router)
api_router.include_router(analytics.router)
api_router.include_router(chat.router, prefix="/chat")
