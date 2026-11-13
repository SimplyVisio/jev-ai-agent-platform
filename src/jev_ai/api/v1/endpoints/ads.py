"""Endpoints de anuncios, anidados bajo su campaña."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from jev_ai.api.deps import OrganizationDep, SessionDep
from jev_ai.modules.marketing import service
from jev_ai.modules.marketing.models import Ad, AdStatus
from jev_ai.modules.marketing.schemas import AdCreate, AdRead, AdUpdate

router = APIRouter(prefix="/campaigns", tags=["ads"])


@router.get("/{campaign_id}/ads", response_model=list[AdRead])
async def list_ads(
    campaign_id: UUID,
    context: OrganizationDep,
    session: SessionDep,
    status: Annotated[AdStatus | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Ad]:
    """Lista anuncios de una campaña de la organización autenticada."""
    return await service.list_ads(
        session,
        context.organization_id,
        campaign_id,
        status=status,
        limit=limit,
        offset=offset,
    )


@router.post("/{campaign_id}/ads", response_model=AdRead, status_code=201)
async def create_ad(
    campaign_id: UUID,
    payload: AdCreate,
    context: OrganizationDep,
    session: SessionDep,
) -> Ad:
    """Crea un anuncio dentro de una campaña."""
    return await service.create_ad(
        session,
        context.organization_id,
        campaign_id,
        payload,
    )


@router.get("/{campaign_id}/ads/{ad_id}", response_model=AdRead)
async def get_ad(
    campaign_id: UUID,
    ad_id: UUID,
    context: OrganizationDep,
    session: SessionDep,
) -> Ad:
    """Devuelve un anuncio por id."""
    return await service.get_ad(
        session,
        context.organization_id,
        campaign_id,
        ad_id,
    )


@router.patch("/{campaign_id}/ads/{ad_id}", response_model=AdRead)
async def update_ad(
    campaign_id: UUID,
    ad_id: UUID,
    payload: AdUpdate,
    context: OrganizationDep,
    session: SessionDep,
) -> Ad:
    """Actualiza parcialmente un anuncio."""
    return await service.update_ad(
        session,
        context.organization_id,
        campaign_id,
        ad_id,
        payload,
    )


@router.delete("/{campaign_id}/ads/{ad_id}", status_code=204)
async def archive_ad(
    campaign_id: UUID,
    ad_id: UUID,
    context: OrganizationDep,
    session: SessionDep,
) -> None:
    """Archiva un anuncio sin borrar sus métricas."""
    await service.archive_ad(
        session,
        context.organization_id,
        campaign_id,
        ad_id,
    )
