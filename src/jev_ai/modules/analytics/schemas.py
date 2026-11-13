"""Contratos de entrada y salida de la API de analítica.

Los importes viajan como ``Decimal`` y se serializan como cadena para no perder
precisión. Los ratios son números adimensionales redondeados a seis decimales.
"""

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class DateRange(BaseModel):
    """Rango de fechas inclusivo y validado."""

    date_from: date = Field(description="Primer día incluido, en UTC.")
    date_to: date = Field(description="Último día incluido, en UTC.")

    @model_validator(mode="after")
    def _validate_order(self) -> Self:
        """Impide rangos invertidos antes de ejecutar cualquier consulta."""
        if self.date_from > self.date_to:
            raise ValueError("date_from must be before or equal to date_to")
        return self


class TrendGranularity(StrEnum):
    """Agrupación temporal admitida por el endpoint de tendencias."""

    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class BaseMetrics(BaseModel):
    """Métricas base sumadas en el periodo consultado."""

    impressions: int = Field(description="Impresiones totales.")
    reach: int | None = Field(
        default=None,
        description="Personas únicas; solo se informa cuando es un dato exacto.",
    )
    clicks: int = Field(description="Clics totales.")
    landing_page_views: int = Field(description="Visitas a la landing atribuidas.")
    spend: Decimal = Field(description="Gasto en la moneda de la organización.")
    leads: int = Field(description="Contactos generados.")
    sales: int = Field(description="Ventas atribuidas.")
    revenue: Decimal = Field(description="Ingresos atribuidos.")


class Metrics(BaseMetrics):
    """Métricas base más ratios derivados; ``None`` si falta el denominador."""

    frequency: float | None = Field(
        default=None,
        description="Impresiones por persona alcanzada.",
    )
    ctr: float | None = Field(default=None, description="Clics / impresiones × 100.")
    cpc: float | None = Field(default=None, description="Gasto / clics.")
    cpm: float | None = Field(default=None, description="Gasto / impresiones × 1000.")
    cpl: float | None = Field(default=None, description="Gasto / leads.")
    conversion_rate: float | None = Field(
        default=None,
        description="Leads / visitas a la landing × 100.",
    )
    roas: float | None = Field(default=None, description="Ingresos / gasto.")


class OverviewRead(Metrics):
    """Resumen de la organización en el rango solicitado."""

    date_from: date
    date_to: date


class CampaignPerformance(BaseModel):
    """Métricas agregadas de una campaña."""

    campaign_id: UUID
    campaign_name: str
    metrics: Metrics


class AdPerformance(BaseModel):
    """Métricas agregadas de un anuncio."""

    ad_id: UUID
    ad_name: str
    campaign_id: UUID
    campaign_name: str
    metrics: Metrics


class TrendPoint(BaseModel):
    """Métricas de un periodo dentro de una serie temporal."""

    period_start: date
    period_end: date
    metrics: Metrics
