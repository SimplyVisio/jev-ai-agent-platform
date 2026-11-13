"""Genera datos sintéticos reproducibles para demos, Bruno y tests manuales.

Uso:
    python scripts/seed.py --organization "Demo"
    python scripts/seed.py --organization "Demo" --reset

No crea API keys: si la organización no tiene ninguna, el script indica cómo crearla.
Los datos cubren del 1 de septiembre al 13 de noviembre de 2026 y usan una semilla
fija para que campañas, anuncios y métricas sean siempre los mismos.
"""

import argparse
import asyncio
import math
import random
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from jev_ai.config import get_settings
from jev_ai.infrastructure.database.session import (
    create_database_engine,
    create_session_factory,
)
from jev_ai.modules.marketing.models import (
    Ad,
    AdInsight,
    Campaign,
    CampaignObjective,
    CampaignStatus,
)
from jev_ai.modules.organizations.models import ApiKey, Organization

START_DATE = date(2026, 9, 1)
END_DATE = date(2026, 11, 13)
SEED = 42
CENT = Decimal("0.01")


@dataclass(frozen=True)
class AdProfile:
    """Parámetros base de un anuncio sintético."""

    name: str
    impressions: int
    ctr: float
    landing_page_rate: float
    lead_rate: float
    sale_rate: float
    cpc: float
    cpm: float
    average_order_value: float
    trend: float
    frequency: float


@dataclass(frozen=True)
class CampaignProfile:
    """Campaña con sus anuncios."""

    name: str
    objective: CampaignObjective
    ads: tuple[AdProfile, ...]


DEMO_CAMPAIGNS: tuple[CampaignProfile, ...] = (
    CampaignProfile(
        name="Demo Prospecting",
        objective=CampaignObjective.LEADS,
        ads=(
            AdProfile(
                name="Prospecting Winner",
                impressions=900,
                ctr=0.065,
                landing_page_rate=0.78,
                lead_rate=0.18,
                sale_rate=0.20,
                cpc=0.55,
                cpm=8.0,
                average_order_value=95.0,
                trend=0.45,
                frequency=1.6,
            ),
            AdProfile(
                name="Prospecting Broad",
                impressions=1400,
                ctr=0.032,
                landing_page_rate=0.65,
                lead_rate=0.08,
                sale_rate=0.12,
                cpc=0.45,
                cpm=6.0,
                average_order_value=80.0,
                trend=0.05,
                frequency=2.1,
            ),
            AdProfile(
                name="Prospecting Clickbait",
                impressions=1800,
                ctr=0.090,
                landing_page_rate=0.28,
                lead_rate=0.03,
                sale_rate=0.04,
                cpc=0.35,
                cpm=5.0,
                average_order_value=70.0,
                trend=-0.20,
                frequency=2.4,
            ),
        ),
    ),
    CampaignProfile(
        name="Demo Retargeting",
        objective=CampaignObjective.SALES,
        ads=(
            AdProfile(
                name="Retargeting Video",
                impressions=500,
                ctr=0.050,
                landing_page_rate=0.82,
                lead_rate=0.12,
                sale_rate=0.30,
                cpc=0.60,
                cpm=10.0,
                average_order_value=120.0,
                trend=0.30,
                frequency=1.5,
            ),
            AdProfile(
                name="Retargeting Static",
                impressions=700,
                ctr=0.030,
                landing_page_rate=0.70,
                lead_rate=0.09,
                sale_rate=0.18,
                cpc=0.50,
                cpm=7.0,
                average_order_value=100.0,
                trend=0.00,
                frequency=1.9,
            ),
        ),
    ),
    CampaignProfile(
        name="Demo Awareness",
        objective=CampaignObjective.AWARENESS,
        ads=(
            AdProfile(
                name="Awareness Reach",
                impressions=4000,
                ctr=0.012,
                landing_page_rate=0.40,
                lead_rate=0.020,
                sale_rate=0.01,
                cpc=0.25,
                cpm=3.0,
                average_order_value=60.0,
                trend=0.15,
                frequency=3.0,
            ),
            AdProfile(
                name="Awareness Video",
                impressions=2500,
                ctr=0.020,
                landing_page_rate=0.35,
                lead_rate=0.015,
                sale_rate=0.01,
                cpc=0.20,
                cpm=2.5,
                average_order_value=60.0,
                trend=-0.15,
                frequency=3.4,
            ),
        ),
    ),
)


def _money(value: float) -> Decimal:
    return Decimal(str(round(max(0.0, value), 2))).quantize(CENT)


def _daily_insight(
    profile: AdProfile,
    *,
    ad_id: object,
    organization_id: object,
    day: date,
    day_index: int,
    total_days: int,
    rng: random.Random,
) -> AdInsight:
    """Construye una fila diaria con tendencia, estacionalidad y ruido."""
    weekday_factor = 1.12 if day.weekday() < 5 else 0.78
    trend_factor = 1 + profile.trend * (day_index / max(1, total_days - 1))
    season_factor = 1 + 0.18 * math.sin(2 * math.pi * day_index / 45)
    noise = rng.uniform(0.88, 1.12)

    impressions = max(
        1,
        int(profile.impressions * weekday_factor * trend_factor * season_factor * noise),
    )
    reach = min(
        impressions,
        int(impressions / rng.uniform(profile.frequency, profile.frequency + 0.8)),
    )
    clicks = min(
        impressions,
        int(impressions * profile.ctr * rng.uniform(0.90, 1.10)),
    )
    landing_page_views = min(
        clicks,
        int(clicks * profile.landing_page_rate * rng.uniform(0.90, 1.10)),
    )
    leads = min(
        landing_page_views,
        int(landing_page_views * profile.lead_rate * rng.uniform(0.90, 1.10)),
    )
    sales = min(
        leads,
        int(leads * profile.sale_rate * rng.uniform(0.90, 1.10)),
    )

    spend = _money(clicks * profile.cpc + impressions * profile.cpm / 1000)
    revenue = _money(sales * profile.average_order_value)

    return AdInsight(
        ad_id=ad_id,
        organization_id=organization_id,
        date=day,
        impressions=impressions,
        reach=max(0, reach),
        clicks=clicks,
        landing_page_views=landing_page_views,
        spend=spend,
        leads=leads,
        sales=sales,
        revenue=revenue,
    )


async def _get_or_create_organization(session: AsyncSession, name: str) -> Organization:
    organization = await session.scalar(select(Organization).where(Organization.name == name))
    if organization is None:
        organization = Organization(name=name, currency_code="USD")
        session.add(organization)
        await session.flush()
    return organization


async def seed(organization_name: str, *, reset: bool) -> None:
    """Siembra o reemplaza los datos de demo de una organización."""
    engine = create_database_engine(get_settings().database_url)
    session_factory = create_session_factory(engine)
    total_days = (END_DATE - START_DATE).days + 1

    try:
        async with session_factory() as session:
            organization = await _get_or_create_organization(session, organization_name)
            demo_names = [campaign.name for campaign in DEMO_CAMPAIGNS]
            existing = (
                await session.scalars(
                    select(Campaign.name).where(
                        Campaign.organization_id == organization.id,
                        Campaign.name.in_(demo_names),
                    )
                )
            ).all()

            if existing and not reset:
                print(
                    f"La organización {organization.name} ya tiene datos de demo. "
                    "Usa --reset para reemplazarlos."
                )
                return

            if existing:
                await session.execute(
                    delete(Campaign).where(
                        Campaign.organization_id == organization.id,
                        Campaign.name.in_(demo_names),
                    )
                )
                await session.flush()

            rng = random.Random(SEED)
            insight_count = 0
            for campaign_profile in DEMO_CAMPAIGNS:
                campaign = Campaign(
                    organization_id=organization.id,
                    name=campaign_profile.name,
                    objective=campaign_profile.objective,
                    status=CampaignStatus.ACTIVE,
                )
                session.add(campaign)
                await session.flush()

                for ad_profile in campaign_profile.ads:
                    ad = Ad(
                        campaign_id=campaign.id,
                        organization_id=organization.id,
                        name=ad_profile.name,
                    )
                    session.add(ad)
                    await session.flush()

                    for offset in range(total_days):
                        day = START_DATE + timedelta(days=offset)
                        session.add(
                            _daily_insight(
                                ad_profile,
                                ad_id=ad.id,
                                organization_id=organization.id,
                                day=day,
                                day_index=offset,
                                total_days=total_days,
                                rng=rng,
                            )
                        )
                        insight_count += 1

            await session.commit()

            key_count = await session.scalar(
                select(func.count())
                .select_from(ApiKey)
                .where(ApiKey.organization_id == organization.id)
            )
            print(f"Organización: {organization.name} ({organization.id})")
            print(f"Campañas: {len(DEMO_CAMPAIGNS)}")
            print(f"Anuncios: {sum(len(campaign.ads) for campaign in DEMO_CAMPAIGNS)}")
            print(f"Filas de ad_insights: {insight_count}")
            print(f"Periodo: {START_DATE} a {END_DATE}")
            if not key_count:
                print(
                    "Esta organización no tiene API key. Crea una con:\n"
                    f'  python scripts/create_api_key.py --organization "{organization.name}"'
                )
    finally:
        await engine.dispose()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Siembra datos sintéticos de demo.")
    parser.add_argument("--organization", default="Demo", help="Organización destino.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Borra y recrea solo las campañas de demo de esa organización.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(seed(args.organization, reset=args.reset))
