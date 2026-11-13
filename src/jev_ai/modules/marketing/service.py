"""Casos de uso del módulo de marketing.

La capa de servicio aplica reglas de negocio y delimita transacciones. Los endpoints
no construyen consultas SQL ni deciden permisos.
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from jev_ai.modules.marketing import repository
from jev_ai.modules.marketing.models import (
    Ad,
    AdStatus,
    Campaign,
    CampaignObjective,
    CampaignStatus,
)
from jev_ai.modules.marketing.schemas import (
    AdCreate,
    AdUpdate,
    CampaignCreate,
    CampaignUpdate,
)


class MarketingNotFoundError(Exception):
    """Recurso inexistente dentro de la organización autenticada."""

    def __init__(self, resource: str) -> None:
        super().__init__(f"{resource} not found")


async def list_campaigns(
    session: AsyncSession,
    organization_id: UUID,
    *,
    status: CampaignStatus | None,
    objective: CampaignObjective | None,
    limit: int,
    offset: int,
) -> list[Campaign]:
    """Lista campañas de la organización."""
    return await repository.list_campaigns(
        session,
        organization_id,
        status=status,
        objective=objective,
        limit=limit,
        offset=offset,
    )


async def get_campaign(
    session: AsyncSession,
    organization_id: UUID,
    campaign_id: UUID,
) -> Campaign:
    """Devuelve una campaña o lanza ``MarketingNotFoundError``."""
    campaign = await repository.get_campaign(session, organization_id, campaign_id)
    if campaign is None:
        raise MarketingNotFoundError("Campaign")
    return campaign


async def create_campaign(
    session: AsyncSession,
    organization_id: UUID,
    data: CampaignCreate,
) -> Campaign:
    """Crea una campaña en la organización autenticada."""
    campaign = Campaign(
        organization_id=organization_id,
        name=data.name,
        objective=data.objective,
        status=data.status,
    )
    session.add(campaign)
    await session.commit()
    await session.refresh(campaign)
    return campaign


async def update_campaign(
    session: AsyncSession,
    organization_id: UUID,
    campaign_id: UUID,
    data: CampaignUpdate,
) -> Campaign:
    """Aplica un PATCH parcial a una campaña."""
    campaign = await get_campaign(session, organization_id, campaign_id)
    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    for field, value in changes.items():
        setattr(campaign, field, value)
    await session.commit()
    return campaign


async def archive_campaign(
    session: AsyncSession,
    organization_id: UUID,
    campaign_id: UUID,
) -> None:
    """Archiva una campaña de forma idempotente."""
    campaign = await get_campaign(session, organization_id, campaign_id)
    campaign.status = CampaignStatus.ARCHIVED
    await session.commit()


async def list_ads(
    session: AsyncSession,
    organization_id: UUID,
    campaign_id: UUID,
    *,
    status: AdStatus | None,
    limit: int,
    offset: int,
) -> list[Ad]:
    """Lista anuncios de una campaña de la organización."""
    await get_campaign(session, organization_id, campaign_id)
    return await repository.list_ads(
        session,
        organization_id,
        campaign_id,
        status=status,
        limit=limit,
        offset=offset,
    )


async def get_ad(
    session: AsyncSession,
    organization_id: UUID,
    campaign_id: UUID,
    ad_id: UUID,
) -> Ad:
    """Devuelve un anuncio o lanza ``MarketingNotFoundError``."""
    await get_campaign(session, organization_id, campaign_id)
    ad = await repository.get_ad(session, organization_id, campaign_id, ad_id)
    if ad is None:
        raise MarketingNotFoundError("Ad")
    return ad


async def create_ad(
    session: AsyncSession,
    organization_id: UUID,
    campaign_id: UUID,
    data: AdCreate,
) -> Ad:
    """Crea un anuncio dentro de una campaña de la organización."""
    campaign = await get_campaign(session, organization_id, campaign_id)
    ad = Ad(
        campaign_id=campaign.id,
        organization_id=organization_id,
        name=data.name,
        status=data.status,
    )
    session.add(ad)
    await session.commit()
    await session.refresh(ad)
    return ad


async def update_ad(
    session: AsyncSession,
    organization_id: UUID,
    campaign_id: UUID,
    ad_id: UUID,
    data: AdUpdate,
) -> Ad:
    """Aplica un PATCH parcial a un anuncio."""
    ad = await get_ad(session, organization_id, campaign_id, ad_id)
    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    for field, value in changes.items():
        setattr(ad, field, value)
    await session.commit()
    return ad


async def archive_ad(
    session: AsyncSession,
    organization_id: UUID,
    campaign_id: UUID,
    ad_id: UUID,
) -> None:
    """Archiva un anuncio de forma idempotente."""
    ad = await get_ad(session, organization_id, campaign_id, ad_id)
    ad.status = AdStatus.ARCHIVED
    await session.commit()
