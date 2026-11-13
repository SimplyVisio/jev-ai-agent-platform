"""Endpoints de analítica agregada."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from jev_ai.api.deps import OrganizationDep, SessionDep
from jev_ai.modules.analytics import service
from jev_ai.modules.analytics.schemas import (
    AdPerformance,
    CampaignPerformance,
    DateRange,
    OverviewRead,
    TrendGranularity,
    TrendPoint,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview", response_model=OverviewRead)
async def get_overview(
    date_range: Annotated[DateRange, Query()],
    context: OrganizationDep,
    session: SessionDep,
) -> OverviewRead:
    """Resume las métricas de la organización en el rango solicitado."""
    return await service.get_overview(
        session,
        context.organization_id,
        date_range.date_from,
        date_range.date_to,
    )


@router.get("/campaigns", response_model=list[CampaignPerformance])
async def list_campaign_performance(
    date_range: Annotated[DateRange, Query()],
    context: OrganizationDep,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[CampaignPerformance]:
    """Devuelve el rendimiento agregado por campaña."""
    return await service.list_campaign_performance(
        session,
        context.organization_id,
        date_range.date_from,
        date_range.date_to,
        limit=limit,
        offset=offset,
    )


@router.get("/ads", response_model=list[AdPerformance])
async def list_ad_performance(
    date_range: Annotated[DateRange, Query()],
    context: OrganizationDep,
    session: SessionDep,
    campaign_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[AdPerformance]:
    """Devuelve el rendimiento agregado por anuncio."""
    return await service.list_ad_performance(
        session,
        context.organization_id,
        date_range.date_from,
        date_range.date_to,
        campaign_id=campaign_id,
        limit=limit,
        offset=offset,
    )


@router.get("/trends", response_model=list[TrendPoint])
async def list_trends(
    date_range: Annotated[DateRange, Query()],
    context: OrganizationDep,
    session: SessionDep,
    granularity: TrendGranularity = TrendGranularity.DAY,
) -> list[TrendPoint]:
    """Devuelve la evolución de las métricas por día, semana o mes."""
    return await service.list_trends(
        session,
        context.organization_id,
        date_range.date_from,
        date_range.date_to,
        granularity=granularity,
    )
