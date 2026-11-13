"""Respuestas deterministas generadas desde plantillas.

El texto no lo redacta el LLM en esta versión: se construye con los datos ya
validados. Así se evita que un modelo invente cifras o identificadores.
"""

from decimal import Decimal
from typing import Any

from jev_ai.ai.jev.plans import (
    CampaignPerformancePlan,
    ComparePeriodsPlan,
    MetricName,
    QueryPlan,
    TopAdsByMetricPlan,
)

HELP_TEXT = (
    "Puedo consultar tus campañas y anuncios. Prueba con:\n"
    '- "¿Cuáles son los 5 mejores anuncios por ROAS en octubre de 2026?"\n'
    '- "¿Cómo va la campaña "Demo Prospecting" este mes?"\n'
    '- "Compara este mes con el mes pasado"\n'
    'También puedes pedir "top 3 anuncios por CPL" o cambiar el periodo.'
)

_METRIC_LABELS = {
    MetricName.IMPRESSIONS: "impresiones",
    MetricName.REACH: "alcance",
    MetricName.CLICKS: "clics",
    MetricName.LANDING_PAGE_VIEWS: "visitas",
    MetricName.SPEND: "gasto",
    MetricName.LEADS: "leads",
    MetricName.SALES: "ventas",
    MetricName.REVENUE: "ingresos",
    MetricName.FREQUENCY: "frecuencia",
    MetricName.CTR: "CTR",
    MetricName.CPC: "CPC",
    MetricName.CPM: "CPM",
    MetricName.CPL: "CPL",
    MetricName.CONVERSION_RATE: "tasa de conversión",
    MetricName.ROAS: "ROAS",
}

_MONEY_METRICS = {MetricName.SPEND, MetricName.REVENUE}


def _format_metric(metric: MetricName, value: Any) -> str:
    if value is None:
        return "sin datos"
    if metric in _MONEY_METRICS:
        return f"{Decimal(str(value)):.2f}"
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".")
    return str(value)


def _format_change(first: Any, second: Any) -> str:
    if first in (None, 0) or second is None:
        return "sin comparación"
    change = (float(second) - float(first)) / float(first) * 100
    sign = "+" if change >= 0 else ""
    return f"{sign}{change:.2f}%"


def _render_top_ads(plan: TopAdsByMetricPlan, data: list[dict[str, Any]]) -> str:
    metric = _METRIC_LABELS[plan.metric]
    if not data:
        return (
            f"No encontré anuncios con datos de {metric} entre {plan.date_from} y {plan.date_to}."
        )

    lines = [f"Top {len(data)} anuncios por {metric} ({plan.date_from} a {plan.date_to}):"]
    for index, item in enumerate(data, start=1):
        value = item["metrics"][plan.metric.value]
        lines.append(
            f"{index}. {item['ad_name']} ({item['campaign_name']}): "
            f"{_format_metric(plan.metric, value)}"
        )
    return "\n".join(lines)


def _render_campaign(plan: CampaignPerformancePlan, data: dict[str, Any]) -> str:
    campaign = data["campaign"]
    metrics = data["metrics"]
    if metrics is None:
        return (
            f"La campaña {campaign['name']} no tiene métricas entre "
            f"{plan.date_from} y {plan.date_to}."
        )

    return (
        f"Campaña {campaign['name']} ({plan.date_from} a {plan.date_to}): "
        f"{metrics['impressions']} impresiones, {metrics['clicks']} clics, "
        f"gasto {_format_metric(MetricName.SPEND, metrics['spend'])}, "
        f"{metrics['leads']} leads, "
        f"ROAS {_format_metric(MetricName.ROAS, metrics['roas'])}, "
        f"CTR {_format_metric(MetricName.CTR, metrics['ctr'])}%."
    )


def _render_comparison(plan: ComparePeriodsPlan, data: dict[str, Any]) -> str:
    first = data["period_a"]
    second = data["period_b"]
    return (
        f"Periodo A ({plan.date_from} a {plan.date_to}): "
        f"{first['impressions']} impresiones, "
        f"gasto {_format_metric(MetricName.SPEND, first['spend'])}, "
        f"ingresos {_format_metric(MetricName.REVENUE, first['revenue'])}, "
        f"ROAS {_format_metric(MetricName.ROAS, first['roas'])}.\n"
        f"Periodo B ({plan.comparison_date_from} a {plan.comparison_date_to}): "
        f"{second['impressions']} impresiones, "
        f"gasto {_format_metric(MetricName.SPEND, second['spend'])}, "
        f"ingresos {_format_metric(MetricName.REVENUE, second['revenue'])}, "
        f"ROAS {_format_metric(MetricName.ROAS, second['roas'])}.\n"
        f"Variación de ROAS: {_format_change(first['roas'], second['roas'])}."
    )


def render_reply(plan: QueryPlan, data: Any) -> str:
    """Genera una respuesta legible a partir del plan y los datos ejecutados."""
    if isinstance(plan, TopAdsByMetricPlan):
        return _render_top_ads(plan, data)
    if isinstance(plan, CampaignPerformancePlan):
        return _render_campaign(plan, data)
    return _render_comparison(plan, data)
