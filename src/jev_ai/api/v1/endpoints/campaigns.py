"""Endpoints de campañas."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from jev_ai.api.deps import OrganizationDep, SessionDep
from jev_ai.modules.marketing import service
from jev_ai.modules.marketing.models import (
    Campaign,
    CampaignObjective,
    CampaignStatus,
)
from jev_ai.modules.marketing.schemas import (
    CampaignCreate,
    CampaignRead,
    CampaignUpdate,
)

router = APIRouter(tags=["campaigns"])


@router.get("", response_model=list[CampaignRead])
async def list_campaigns(
    context: OrganizationDep,
    session: SessionDep,
    status: Annotated[CampaignStatus | None, Query()] = None,
    objective: Annotated[CampaignObjective | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Campaign]:
    """Lista campañas de la organización autenticada."""
    return await service.list_campaigns(
        session,
        context.organization_id,
        status=status,
        objective=objective,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=CampaignRead, status_code=201)
async def create_campaign(
    payload: CampaignCreate,
    context: OrganizationDep,
    session: SessionDep,
) -> Campaign:
    """Crea una campaña en la organización autenticada."""
    return await service.create_campaign(session, context.organization_id, payload)


@router.get("/{campaign_id}", response_model=CampaignRead)
async def get_campaign(
    campaign_id: UUID,
    context: OrganizationDep,
    session: SessionDep,
) -> Campaign:
    """Devuelve una campaña por id."""
    return await service.get_campaign(session, context.organization_id, campaign_id)


@router.patch("/{campaign_id}", response_model=CampaignRead)
async def update_campaign(
    campaign_id: UUID,
    payload: CampaignUpdate,
    context: OrganizationDep,
    session: SessionDep,
) -> Campaign:
    """Actualiza parcialmente una campaña."""
    return await service.update_campaign(
        session,
        context.organization_id,
        campaign_id,
        payload,
    )


@router.delete("/{campaign_id}", status_code=204)
async def archive_campaign(
    campaign_id: UUID,
    context: OrganizationDep,
    session: SessionDep,
) -> None:
    """Archiva una campaña sin borrar sus anuncios ni métricas."""
    await service.archive_campaign(session, context.organization_id, campaign_id)
