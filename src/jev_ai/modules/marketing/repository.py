"""Consultas de persistencia del módulo de marketing."""

from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from jev_ai.modules.marketing.models import (
    Ad,
    AdStatus,
    Campaign,
    CampaignObjective,
    CampaignStatus,
)


def _campaign_filters(
    query: Select[tuple[Campaign]],
    organization_id: UUID,
    status: CampaignStatus | None,
    objective: CampaignObjective | None,
) -> Select[tuple[Campaign]]:
    query = query.where(Campaign.organization_id == organization_id)
    if status is not None:
        query = query.where(Campaign.status == status)
    if objective is not None:
        query = query.where(Campaign.objective == objective)
    return query


async def list_campaigns(
    session: AsyncSession,
    organization_id: UUID,
    *,
    status: CampaignStatus | None,
    objective: CampaignObjective | None,
    limit: int,
    offset: int,
) -> list[Campaign]:
    """Lista campañas de la organización con filtros y paginación."""
    query = _campaign_filters(
        select(Campaign),
        organization_id,
        status,
        objective,
    )
    query = query.order_by(Campaign.created_at.desc(), Campaign.id).limit(limit).offset(offset)
    return list((await session.scalars(query)).all())


async def get_campaign(
    session: AsyncSession,
    organization_id: UUID,
    campaign_id: UUID,
) -> Campaign | None:
    """Busca una campaña por id dentro de la organización."""
    return await session.scalar(
        select(Campaign).where(
            Campaign.id == campaign_id,
            Campaign.organization_id == organization_id,
        )
    )


async def find_campaign_by_name(
    session: AsyncSession,
    organization_id: UUID,
    name: str,
) -> Campaign | None:
    """Busca una campaña por nombre exacto sin distinguir mayúsculas."""
    return await session.scalar(
        select(Campaign)
        .where(
            Campaign.organization_id == organization_id,
            func.lower(Campaign.name) == name.lower(),
        )
        .order_by(Campaign.created_at.desc())
        .limit(1)
    )


async def list_ads(
    session: AsyncSession,
    organization_id: UUID,
    campaign_id: UUID,
    *,
    status: AdStatus | None,
    limit: int,
    offset: int,
) -> list[Ad]:
    """Lista anuncios de una campaña con filtro de estado y paginación."""
    query = select(Ad).where(
        Ad.organization_id == organization_id,
        Ad.campaign_id == campaign_id,
    )
    if status is not None:
        query = query.where(Ad.status == status)
    query = query.order_by(Ad.created_at.desc(), Ad.id).limit(limit).offset(offset)
    return list((await session.scalars(query)).all())


async def get_ad(
    session: AsyncSession,
    organization_id: UUID,
    campaign_id: UUID,
    ad_id: UUID,
) -> Ad | None:
    """Busca un anuncio por id dentro de la campaña y organización."""
    return await session.scalar(
        select(Ad).where(
            Ad.id == ad_id,
            Ad.campaign_id == campaign_id,
            Ad.organization_id == organization_id,
        )
    )
