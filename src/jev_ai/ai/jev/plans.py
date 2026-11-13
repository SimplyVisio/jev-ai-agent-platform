"""Catálogo cerrado de operaciones y esquema validado de ``QueryPlan``.

El LLM solo puede proponer estas operaciones. ``organization_id`` no forma parte del
plan: siempre sale del contexto autenticado del servidor.
"""

import json
from datetime import date
from enum import StrEnum
from typing import Annotated, Any, Literal, Self
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
    model_validator,
)


class QueryOperation(StrEnum):
    """Operaciones que el motor puede ejecutar."""

    TOP_ADS_BY_METRIC = "top_ads_by_metric"
    CAMPAIGN_PERFORMANCE = "campaign_performance"
    COMPARE_PERIODS = "compare_periods"


class MetricName(StrEnum):
    """Métricas permitidas en un plan."""

    IMPRESSIONS = "impressions"
    REACH = "reach"
    CLICKS = "clicks"
    LANDING_PAGE_VIEWS = "landing_page_views"
    SPEND = "spend"
    LEADS = "leads"
    SALES = "sales"
    REVENUE = "revenue"
    FREQUENCY = "frequency"
    CTR = "ctr"
    CPC = "cpc"
    CPM = "cpm"
    CPL = "cpl"
    CONVERSION_RATE = "conversion_rate"
    ROAS = "roas"


LOWER_IS_BETTER = frozenset(
    {
        MetricName.CPC,
        MetricName.CPM,
        MetricName.CPL,
    }
)


class PlanParseError(ValueError):
    """El texto del LLM no contiene un QueryPlan válido."""


class _PlanBase(BaseModel):
    """Rechaza campos desconocidos como defensa contra inyección de parámetros."""

    model_config = ConfigDict(extra="forbid")


class TopAdsByMetricPlan(_PlanBase):
    """Mejores anuncios según una métrica en un periodo."""

    operation: Literal[QueryOperation.TOP_ADS_BY_METRIC]
    metric: MetricName
    date_from: date
    date_to: date
    limit: int = Field(default=5, ge=1, le=20)

    @model_validator(mode="after")
    def _validate_dates(self) -> Self:
        if self.date_from > self.date_to:
            raise ValueError("date_from must be before or equal to date_to")
        return self


class CampaignPerformancePlan(_PlanBase):
    """Resultados de una campaña identificada por id o por nombre exacto."""

    operation: Literal[QueryOperation.CAMPAIGN_PERFORMANCE]
    campaign_id: UUID | None = None
    campaign_name: str | None = Field(default=None, min_length=1, max_length=120)
    date_from: date
    date_to: date

    @model_validator(mode="after")
    def _validate_target_and_dates(self) -> Self:
        if (self.campaign_id is None) == (self.campaign_name is None):
            raise ValueError("Provide exactly one of campaign_id or campaign_name")
        if self.date_from > self.date_to:
            raise ValueError("date_from must be before or equal to date_to")
        return self


class ComparePeriodsPlan(_PlanBase):
    """Comparación del resumen de dos periodos."""

    operation: Literal[QueryOperation.COMPARE_PERIODS]
    date_from: date
    date_to: date
    comparison_date_from: date
    comparison_date_to: date

    @model_validator(mode="after")
    def _validate_dates(self) -> Self:
        if self.date_from > self.date_to:
            raise ValueError("date_from must be before or equal to date_to")
        if self.comparison_date_from > self.comparison_date_to:
            raise ValueError("comparison_date_from must be before or equal to comparison_date_to")
        return self


QueryPlan = Annotated[
    TopAdsByMetricPlan | CampaignPerformancePlan | ComparePeriodsPlan,
    Field(discriminator="operation"),
]

_QUERY_PLAN_ADAPTER = TypeAdapter(QueryPlan)


def parse_query_plan(raw: str | bytes | dict[str, Any]) -> QueryPlan:
    """Convierte la salida del LLM en un plan tipado.

    Raises:
        PlanParseError: Si el JSON es inválido o no cumple el esquema.
    """
    try:
        data = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise PlanParseError("The LLM response is not valid JSON") from exc

    try:
        return _QUERY_PLAN_ADAPTER.validate_python(data)
    except ValidationError as exc:
        raise PlanParseError("The LLM response does not match a QueryPlan") from exc


def plan_to_dict(plan: QueryPlan) -> dict[str, Any]:
    """Serializa un plan a un diccionario JSON-safe."""
    return plan.model_dump(mode="json")
