"""Ejecución de ``QueryPlan`` sobre los mismos servicios de la API de analítica.

El plan nunca incluye ``organization_id``: el ejecutor lo recibe del contexto
autenticado y lo propaga a marketing y analítica.
"""

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from jev_ai.ai.jev.plans import (
    LOWER_IS_BETTER,
    CampaignPerformancePlan,
    ComparePeriodsPlan,
    QueryPlan,
    TopAdsByMetricPlan,
)
from jev_ai.modules.analytics import service as analytics_service
from jev_ai.modules.marketing import service as marketing_service

TOP_ADS_SCAN_LIMIT = 100


async def _execute_top_ads(
    session: AsyncSession,
    organization_id: UUID,
    plan: TopAdsByMetricPlan,
) -> list[dict[str, Any]]:
    """Ordena anuncios ya agregados y devuelve los mejores según la métrica."""
    ads = await analytics_service.list_ad_performance(
        session,
        organization_id,
        plan.date_from,
        plan.date_to,
        campaign_id=None,
        limit=TOP_ADS_SCAN_LIMIT,
        offset=0,
    )
    ranked = [ad for ad in ads if getattr(ad.metrics, plan.metric.value) is not None]
    ranked.sort(
        key=lambda ad: getattr(ad.metrics, plan.metric.value),
        reverse=plan.metric not in LOWER_IS_BETTER,
    )
    return [ad.model_dump(mode="json") for ad in ranked[: plan.limit]]


async def _execute_campaign(
    session: AsyncSession,
    organization_id: UUID,
    plan: CampaignPerformancePlan,
) -> dict[str, Any]:
    """Resuelve la campaña y devuelve sus métricas agregadas."""
    if plan.campaign_id is not None:
        campaign = await marketing_service.get_campaign(
            session,
            organization_id,
            plan.campaign_id,
        )
    else:
        if plan.campaign_name is None:
            raise ValueError("campaign_id or campaign_name is required")
        campaign = await marketing_service.find_campaign_by_name(
            session,
            organization_id,
            plan.campaign_name,
        )

    performance = await analytics_service.get_campaign_performance(
        session,
        organization_id,
        campaign.id,
        plan.date_from,
        plan.date_to,
    )
    return {
        "campaign": {
            "id": str(campaign.id),
            "name": campaign.name,
            "objective": campaign.objective,
            "status": campaign.status,
        },
        "metrics": None if performance is None else performance.metrics.model_dump(mode="json"),
    }


async def _execute_comparison(
    session: AsyncSession,
    organization_id: UUID,
    plan: ComparePeriodsPlan,
) -> dict[str, Any]:
    """Compara el resumen de dos periodos."""
    first = await analytics_service.get_overview(
        session,
        organization_id,
        plan.date_from,
        plan.date_to,
    )
    second = await analytics_service.get_overview(
        session,
        organization_id,
        plan.comparison_date_from,
        plan.comparison_date_to,
    )
    return {
        "period_a": first.model_dump(mode="json"),
        "period_b": second.model_dump(mode="json"),
    }


async def execute_query_plan(
    session: AsyncSession,
    organization_id: UUID,
    plan: QueryPlan,
) -> Any:
    """Ejecuta el plan con SQLAlchemy a través de los servicios de aplicación."""
    if isinstance(plan, TopAdsByMetricPlan):
        return await _execute_top_ads(session, organization_id, plan)
    if isinstance(plan, CampaignPerformancePlan):
        return await _execute_campaign(session, organization_id, plan)
    return await _execute_comparison(session, organization_id, plan)
