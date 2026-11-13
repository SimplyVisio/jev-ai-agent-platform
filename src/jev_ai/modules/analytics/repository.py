"""Consultas de agregación sobre ``ad_insights``.

El repositorio solo suma métricas base. Los ratios se calculan después, en el
servicio, para no promediar ratios diarios ni perder precisión.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Date, Select, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from jev_ai.modules.marketing.models import Ad, AdInsight, Campaign


@dataclass(frozen=True)
class BaseAggregate:
    """Sumas de métricas base para un conjunto de filas."""

    impressions: int
    reach: int
    clicks: int
    landing_page_views: int
    spend: Decimal
    leads: int
    sales: int
    revenue: Decimal


@dataclass(frozen=True)
class CampaignAggregate:
    """Sumas base agrupadas por campaña."""

    campaign_id: UUID
    campaign_name: str
    base: BaseAggregate


@dataclass(frozen=True)
class AdAggregate:
    """Sumas base agrupadas por anuncio."""

    ad_id: UUID
    ad_name: str
    campaign_id: UUID
    campaign_name: str
    base: BaseAggregate


@dataclass(frozen=True)
class TrendAggregate:
    """Sumas base agrupadas por periodo."""

    period_start: date
    base: BaseAggregate


def _sum_columns() -> tuple[Any, ...]:
    """Columnas de suma con ceros cuando el rango no tiene filas."""
    return (
        func.coalesce(func.sum(AdInsight.impressions), 0).label("impressions"),
        func.coalesce(func.sum(AdInsight.reach), 0).label("reach"),
        func.coalesce(func.sum(AdInsight.clicks), 0).label("clicks"),
        func.coalesce(func.sum(AdInsight.landing_page_views), 0).label("landing_page_views"),
        func.coalesce(func.sum(AdInsight.spend), 0).label("spend"),
        func.coalesce(func.sum(AdInsight.leads), 0).label("leads"),
        func.coalesce(func.sum(AdInsight.sales), 0).label("sales"),
        func.coalesce(func.sum(AdInsight.revenue), 0).label("revenue"),
    )


def _money(value: Any) -> Decimal:
    """Normaliza importes a dos decimales, el mismo escala que ``NUMERIC(12,2)``."""
    return Decimal(value).quantize(Decimal("0.01"))


def _base_from_row(row: Any) -> BaseAggregate:
    """Convierte una fila agregada en el dataclass de métricas base."""
    return BaseAggregate(
        impressions=int(row.impressions),
        reach=int(row.reach),
        clicks=int(row.clicks),
        landing_page_views=int(row.landing_page_views),
        spend=_money(row.spend),
        leads=int(row.leads),
        sales=int(row.sales),
        revenue=_money(row.revenue),
    )


def _date_filter(
    query: Select[Any],
    organization_id: UUID,
    date_from: date,
    date_to: date,
) -> Select[Any]:
    """Aplica el aislamiento por organización y el rango inclusivo."""
    return query.where(
        AdInsight.organization_id == organization_id,
        AdInsight.date >= date_from,
        AdInsight.date <= date_to,
    )


async def get_overview(
    session: AsyncSession,
    organization_id: UUID,
    date_from: date,
    date_to: date,
) -> BaseAggregate:
    """Suma todas las métricas base de la organización en el rango."""
    query = _date_filter(
        select(*_sum_columns()),
        organization_id,
        date_from,
        date_to,
    )
    row = (await session.execute(query)).one()
    return _base_from_row(row)


async def list_campaigns(
    session: AsyncSession,
    organization_id: UUID,
    date_from: date,
    date_to: date,
    *,
    limit: int,
    offset: int,
) -> list[CampaignAggregate]:
    """Agrupa métricas por campaña, ordenadas por gasto descendente."""
    query = (
        select(
            Campaign.id.label("campaign_id"),
            Campaign.name.label("campaign_name"),
            *_sum_columns(),
        )
        .join(Ad, Ad.campaign_id == Campaign.id)
        .join(AdInsight, AdInsight.ad_id == Ad.id)
        .where(
            Campaign.organization_id == organization_id,
            Ad.organization_id == organization_id,
        )
    )
    query = _date_filter(query, organization_id, date_from, date_to)
    query = (
        query.group_by(Campaign.id, Campaign.name)
        .order_by(func.sum(AdInsight.spend).desc(), Campaign.id)
        .limit(limit)
        .offset(offset)
    )
    rows = (await session.execute(query)).all()
    return [
        CampaignAggregate(
            campaign_id=row.campaign_id,
            campaign_name=row.campaign_name,
            base=_base_from_row(row),
        )
        for row in rows
    ]


async def list_ads(
    session: AsyncSession,
    organization_id: UUID,
    date_from: date,
    date_to: date,
    *,
    campaign_id: UUID | None,
    limit: int,
    offset: int,
) -> list[AdAggregate]:
    """Agrupa métricas por anuncio, con filtro opcional por campaña."""
    query = (
        select(
            Ad.id.label("ad_id"),
            Ad.name.label("ad_name"),
            Campaign.id.label("campaign_id"),
            Campaign.name.label("campaign_name"),
            *_sum_columns(),
        )
        .join(Campaign, Campaign.id == Ad.campaign_id)
        .join(AdInsight, AdInsight.ad_id == Ad.id)
        .where(
            Ad.organization_id == organization_id,
            Campaign.organization_id == organization_id,
        )
    )
    if campaign_id is not None:
        query = query.where(Ad.campaign_id == campaign_id)
    query = _date_filter(query, organization_id, date_from, date_to)
    query = (
        query.group_by(Ad.id, Ad.name, Campaign.id, Campaign.name)
        .order_by(func.sum(AdInsight.spend).desc(), Ad.id)
        .limit(limit)
        .offset(offset)
    )
    rows = (await session.execute(query)).all()
    return [
        AdAggregate(
            ad_id=row.ad_id,
            ad_name=row.ad_name,
            campaign_id=row.campaign_id,
            campaign_name=row.campaign_name,
            base=_base_from_row(row),
        )
        for row in rows
    ]


def _trend_bucket(granularity: str) -> Any:
    """Expresión SQL que agrupa por día, semana o mes."""
    if granularity == "day":
        return AdInsight.date
    return cast(func.date_trunc(granularity, AdInsight.date), Date)


async def list_trends(
    session: AsyncSession,
    organization_id: UUID,
    date_from: date,
    date_to: date,
    *,
    granularity: str,
) -> list[TrendAggregate]:
    """Agrupa métricas base por periodo calendario."""
    bucket = _trend_bucket(granularity)
    query = select(bucket.label("period_start"), *_sum_columns()).group_by(bucket).order_by(bucket)
    query = _date_filter(query, organization_id, date_from, date_to)
    rows = (await session.execute(query)).all()
    return [
        TrendAggregate(
            period_start=row.period_start,
            base=_base_from_row(row),
        )
        for row in rows
    ]
