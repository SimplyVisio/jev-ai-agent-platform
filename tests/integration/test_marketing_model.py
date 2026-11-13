"""Tests de integración del modelo de marketing."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from jev_ai.modules.marketing.models import (
    Ad,
    AdInsight,
    Campaign,
    CampaignObjective,
)
from jev_ai.modules.organizations.models import Organization

INSIGHT_DATE = date(2026, 10, 1)


async def create_campaign_and_ad(
    session: AsyncSession,
    organization_name: str = "Marketing",
) -> tuple[Campaign, Ad]:
    """Crea una organización, una campaña y un anuncio listos para métricas."""
    organization = Organization(
        name=f"{organization_name} {uuid4()}",
        currency_code="USD",
    )
    session.add(organization)
    await session.flush()

    campaign = Campaign(
        organization_id=organization.id,
        name="Launch",
        objective=CampaignObjective.TRAFFIC,
    )
    session.add(campaign)
    await session.flush()

    ad = Ad(
        campaign_id=campaign.id,
        organization_id=organization.id,
        name="Ad 1",
    )
    session.add(ad)
    await session.flush()

    return campaign, ad


async def test_ad_insight_is_unique_per_ad_and_date(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        campaign, ad = await create_campaign_and_ad(session)
        session.add(
            AdInsight(
                ad_id=ad.id,
                organization_id=campaign.organization_id,
                date=INSIGHT_DATE,
            )
        )
        await session.commit()
        ad_id = ad.id
        organization_id = campaign.organization_id

    async with session_factory() as session:
        session.add(
            AdInsight(
                ad_id=ad_id,
                organization_id=organization_id,
                date=INSIGHT_DATE,
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()


async def test_deleting_campaign_cascades_to_ads_and_insights(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        campaign, ad = await create_campaign_and_ad(session)
        session.add(
            AdInsight(
                ad_id=ad.id,
                organization_id=campaign.organization_id,
                date=INSIGHT_DATE,
            )
        )
        await session.commit()
        campaign_id = campaign.id
        ad_id = ad.id

    async with session_factory() as session:
        campaign = await session.get(Campaign, campaign_id)
        assert campaign is not None
        await session.delete(campaign)
        await session.commit()

    async with session_factory() as session:
        assert await session.get(Ad, ad_id) is None
        remaining = await session.scalar(
            select(func.count()).select_from(AdInsight).where(AdInsight.ad_id == ad_id)
        )
        assert remaining == 0


async def test_insights_are_isolated_by_organization(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        campaign_a, ad_a = await create_campaign_and_ad(session, "Org A")
        campaign_b, ad_b = await create_campaign_and_ad(session, "Org B")
        session.add(
            AdInsight(
                ad_id=ad_a.id,
                organization_id=campaign_a.organization_id,
                date=INSIGHT_DATE,
                spend=Decimal("10.50"),
                revenue=Decimal("20.25"),
            )
        )
        session.add(
            AdInsight(
                ad_id=ad_b.id,
                organization_id=campaign_b.organization_id,
                date=INSIGHT_DATE,
                spend=Decimal("99.99"),
            )
        )
        await session.commit()
        organization_a = campaign_a.organization_id
        organization_b = campaign_b.organization_id

    async with session_factory() as session:
        rows = (
            await session.scalars(
                select(AdInsight).where(AdInsight.organization_id == organization_a)
            )
        ).all()
        assert len(rows) == 1
        assert rows[0].spend == Decimal("10.50")
        assert rows[0].revenue == Decimal("20.25")

        other_organization = await session.scalar(
            select(func.count())
            .select_from(AdInsight)
            .where(AdInsight.organization_id == organization_b)
        )
        assert other_organization == 1


async def test_negative_metrics_are_rejected(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        campaign, ad = await create_campaign_and_ad(session)
        session.add(
            AdInsight(
                ad_id=ad.id,
                organization_id=campaign.organization_id,
                date=INSIGHT_DATE,
                clicks=-1,
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()
