"""Cálculo determinista de métricas y casos de uso de analítica.

Los ratios se derivan siempre de métricas base ya sumadas. Nunca se promedian
ratios diarios, porque eso produce resultados distintos del ratio del periodo.
"""

from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from jev_ai.modules.analytics import repository
from jev_ai.modules.analytics.repository import BaseAggregate
from jev_ai.modules.analytics.schemas import (
    AdPerformance,
    CampaignPerformance,
    Metrics,
    OverviewRead,
    TrendGranularity,
    TrendPoint,
)


def _ratio(
    numerator: int | Decimal,
    denominator: int | Decimal,
    *,
    factor: int = 1,
) -> float | None:
    """Divide dos métricas y devuelve ``None`` si el denominador es cero."""
    if denominator == 0:
        return None
    value = Decimal(numerator) * factor / Decimal(denominator)
    return round(float(value), 6)


def calculate_metrics(base: BaseAggregate, *, reach: int | None) -> Metrics:
    """Deriva ratios a partir de métricas base agregadas.

    Args:
        base: Sumas base del periodo.
        reach: Personas únicas cuando el dato es exacto; ``None`` si agregar
            filas diarias o varios anuncios lo volvería una sobreestimación.
    """
    return Metrics(
        impressions=base.impressions,
        reach=reach,
        clicks=base.clicks,
        landing_page_views=base.landing_page_views,
        spend=base.spend,
        leads=base.leads,
        sales=base.sales,
        revenue=base.revenue,
        frequency=None if reach is None else _ratio(base.impressions, reach),
        ctr=_ratio(base.clicks, base.impressions, factor=100),
        cpc=_ratio(base.spend, base.clicks),
        cpm=_ratio(base.spend, base.impressions, factor=1000),
        cpl=_ratio(base.spend, base.leads),
        conversion_rate=_ratio(base.leads, base.landing_page_views, factor=100),
        roas=_ratio(base.revenue, base.spend),
    )


def _period_end(start: date, granularity: TrendGranularity) -> date:
    """Calcula el último día del periodo calendario que empieza en ``start``."""
    if granularity is TrendGranularity.DAY:
        return start
    if granularity is TrendGranularity.WEEK:
        return start + timedelta(days=6)
    next_month = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
    return next_month - timedelta(days=1)


async def get_overview(
    session: AsyncSession,
    organization_id: UUID,
    date_from: date,
    date_to: date,
) -> OverviewRead:
    """Resume las métricas de la organización en el rango consultado."""
    base = await repository.get_overview(
        session,
        organization_id,
        date_from,
        date_to,
    )
    metrics = calculate_metrics(base, reach=None)
    return OverviewRead(
        date_from=date_from,
        date_to=date_to,
        **metrics.model_dump(),
    )


async def list_campaign_performance(
    session: AsyncSession,
    organization_id: UUID,
    date_from: date,
    date_to: date,
    *,
    limit: int,
    offset: int,
) -> list[CampaignPerformance]:
    """Devuelve métricas agregadas por campaña."""
    rows = await repository.list_campaigns(
        session,
        organization_id,
        date_from,
        date_to,
        limit=limit,
        offset=offset,
    )
    return [
        CampaignPerformance(
            campaign_id=row.campaign_id,
            campaign_name=row.campaign_name,
            metrics=calculate_metrics(row.base, reach=None),
        )
        for row in rows
    ]


async def list_ad_performance(
    session: AsyncSession,
    organization_id: UUID,
    date_from: date,
    date_to: date,
    *,
    campaign_id: UUID | None,
    limit: int,
    offset: int,
) -> list[AdPerformance]:
    """Devuelve métricas agregadas por anuncio.

    ``reach`` solo se informa para un único día: hay una fila por anuncio y día,
    pero sumar varios días sobrecontaría personas únicas.
    """
    rows = await repository.list_ads(
        session,
        organization_id,
        date_from,
        date_to,
        campaign_id=campaign_id,
        limit=limit,
        offset=offset,
    )
    single_day = date_from == date_to
    return [
        AdPerformance(
            ad_id=row.ad_id,
            ad_name=row.ad_name,
            campaign_id=row.campaign_id,
            campaign_name=row.campaign_name,
            metrics=calculate_metrics(
                row.base,
                reach=row.base.reach if single_day else None,
            ),
        )
        for row in rows
    ]


async def list_trends(
    session: AsyncSession,
    organization_id: UUID,
    date_from: date,
    date_to: date,
    *,
    granularity: TrendGranularity,
) -> list[TrendPoint]:
    """Devuelve una serie temporal de métricas agregadas por periodo.

    Los periodos se recortan al rango solicitado para que las etiquetas no
    sugieran datos fuera de la consulta.
    """
    rows = await repository.list_trends(
        session,
        organization_id,
        date_from,
        date_to,
        granularity=granularity.value,
    )
    return [
        TrendPoint(
            period_start=max(row.period_start, date_from),
            period_end=min(_period_end(row.period_start, granularity), date_to),
            metrics=calculate_metrics(row.base, reach=None),
        )
        for row in rows
    ]
