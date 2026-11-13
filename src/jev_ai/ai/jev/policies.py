"""Políticas deterministas que validan un ``QueryPlan`` antes de ejecutarlo.

La confianza del clasificador no sustituye estas reglas: un plan puede ser propuesto
con confianza alta y aun así violar el catálogo o los límites del motor.
"""

from datetime import date

from pydantic import BaseModel, Field

from jev_ai.ai.jev.intents import Intent
from jev_ai.ai.jev.plans import (
    CampaignPerformancePlan,
    ComparePeriodsPlan,
    MetricName,
    QueryPlan,
    TopAdsByMetricPlan,
)

MAX_RANGE_DAYS = 366
_UNRANKABLE_METRICS = frozenset({MetricName.REACH, MetricName.FREQUENCY})


class PolicyViolation(BaseModel):
    """Incumplimiento concreto de una política."""

    code: str
    message: str


class PlanDecision(BaseModel):
    """Resultado de validar un plan."""

    accepted: bool
    violations: list[PolicyViolation] = Field(default_factory=list)


def _range_days(start: date, end: date) -> int:
    return (end - start).days + 1


def validate_query_plan(
    plan: QueryPlan,
    *,
    expected_intent: Intent | None = None,
) -> PlanDecision:
    """Valida el plan contra el catálogo cerrado y los límites del motor."""
    violations: list[PolicyViolation] = []

    if expected_intent is not None and expected_intent.value != plan.operation.value:
        violations.append(
            PolicyViolation(
                code="intent_mismatch",
                message=("La intención detectada no coincide con la operación del plan"),
            )
        )

    if isinstance(plan, TopAdsByMetricPlan):
        if plan.metric in _UNRANKABLE_METRICS:
            violations.append(
                PolicyViolation(
                    code="metric_not_rankable",
                    message=(f"La métrica {plan.metric.value} no se puede ordenar por anuncio"),
                )
            )
        if _range_days(plan.date_from, plan.date_to) > MAX_RANGE_DAYS:
            violations.append(
                PolicyViolation(
                    code="range_too_large",
                    message=f"El rango supera {MAX_RANGE_DAYS} días",
                )
            )

    if isinstance(plan, CampaignPerformancePlan):
        if plan.campaign_name is not None and not plan.campaign_name.strip():
            violations.append(
                PolicyViolation(
                    code="empty_campaign_name",
                    message="El nombre de la campaña no puede estar vacío",
                )
            )
        if _range_days(plan.date_from, plan.date_to) > MAX_RANGE_DAYS:
            violations.append(
                PolicyViolation(
                    code="range_too_large",
                    message=f"El rango supera {MAX_RANGE_DAYS} días",
                )
            )

    if isinstance(plan, ComparePeriodsPlan):
        if _range_days(plan.date_from, plan.date_to) > MAX_RANGE_DAYS:
            violations.append(
                PolicyViolation(
                    code="range_too_large",
                    message=f"El primer rango supera {MAX_RANGE_DAYS} días",
                )
            )
        if _range_days(plan.comparison_date_from, plan.comparison_date_to) > MAX_RANGE_DAYS:
            violations.append(
                PolicyViolation(
                    code="range_too_large",
                    message=f"El rango de comparación supera {MAX_RANGE_DAYS} días",
                )
            )

    return PlanDecision(accepted=not violations, violations=violations)
