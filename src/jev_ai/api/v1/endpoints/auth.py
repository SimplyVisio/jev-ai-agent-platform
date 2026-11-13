"""Endpoints de identidad."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from jev_ai.api.deps import OrganizationContext, get_current_organization

router = APIRouter()


class OrganizationResponse(BaseModel):
    """Organización autenticada por la API key de la petición."""

    organization_id: UUID


@router.get("/me", response_model=OrganizationResponse)
async def me(
    context: Annotated[OrganizationContext, Depends(get_current_organization)],
) -> OrganizationResponse:
    """Devuelve la organización asociada a la cabecera ``X-API-Key``.

    Es un endpoint de diagnóstico; los recursos de negocio reutilizan la misma
    dependencia de autenticación.
    """
    return OrganizationResponse(organization_id=context.organization_id)
