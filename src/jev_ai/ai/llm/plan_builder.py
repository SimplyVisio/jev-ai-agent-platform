"""Traductor determinista de lenguaje natural a borradores de ``QueryPlan``.

Cumple el papel del LLM cuando no hay API key ni túnel: reconoce un vocabulario
cerrado de métricas, periodos y operaciones. No ejecuta SQL ni decide permisos; solo
propone un plan que JEV AI valida después.
"""

import re
import unicodedata
from datetime import date, timedelta
from typing import Any

from jev_ai.ai.jev.classifier import classify_intent
from jev_ai.ai.jev.intents import Intent
from jev_ai.ai.jev.plans import MetricName

_MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}

_MONTH_PATTERN = "|".join(_MONTHS)
_METRIC_TERMS: tuple[tuple[str, MetricName], ...] = (
    ("tasa de conversion", MetricName.CONVERSION_RATE),
    ("landing page views", MetricName.LANDING_PAGE_VIEWS),
    ("conversion", MetricName.CONVERSION_RATE),
    ("visitas", MetricName.LANDING_PAGE_VIEWS),
    ("impresiones", MetricName.IMPRESSIONS),
    ("impressions", MetricName.IMPRESSIONS),
    ("frecuencia", MetricName.FREQUENCY),
    ("alcance", MetricName.REACH),
    ("reach", MetricName.REACH),
    ("ingresos", MetricName.REVENUE),
    ("revenue", MetricName.REVENUE),
    ("gasto", MetricName.SPEND),
    ("spend", MetricName.SPEND),
    ("ventas", MetricName.SALES),
    ("sales", MetricName.SALES),
    ("clics", MetricName.CLICKS),
    ("clicks", MetricName.CLICKS),
    ("leads", MetricName.LEADS),
    ("roas", MetricName.ROAS),
    ("ctr", MetricName.CTR),
    ("cpc", MetricName.CPC),
    ("cpm", MetricName.CPM),
    ("cpl", MetricName.CPL),
)


def _normalize(text: str) -> str:
    """Quita acentos y pasa a minúsculas para comparar términos."""
    decomposed = unicodedata.normalize("NFKD", text)
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    return without_accents.lower()


def _month_range(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    next_month = date(year + (month == 12), month % 12 + 1, 1)
    return start, next_month - timedelta(days=1)


def _last_n_days(today: date, days: int) -> tuple[date, date]:
    return today - timedelta(days=days - 1), today


def _parse_period(text: str, today: date) -> tuple[date, date] | None:
    """Interpreta un periodo en español o ISO; devuelve ``None`` si no lo reconoce."""
    normalized = _normalize(text)

    iso_range = re.search(
        r"(\d{4}-\d{2}-\d{2})\s*(?:a|hasta|-)\s*(\d{4}-\d{2}-\d{2})",
        normalized,
    )
    if iso_range:
        return date.fromisoformat(iso_range.group(1)), date.fromisoformat(iso_range.group(2))

    last_days = re.search(r"ultimos?\s+(\d+)\s+dias", normalized)
    if last_days:
        return _last_n_days(today, max(1, int(last_days.group(1))))

    if "mes pasado" in normalized or "mes anterior" in normalized:
        last_day = today.replace(day=1) - timedelta(days=1)
        return last_day.replace(day=1), last_day

    if "este mes" in normalized or "mes actual" in normalized:
        return today.replace(day=1), today

    if "este ano" in normalized or "ano actual" in normalized:
        return date(today.year, 1, 1), today

    month_year = re.search(
        rf"\b({_MONTH_PATTERN})\b(?:\s+de)?\s+(\d{{4}})\b",
        normalized,
    )
    if month_year:
        return _month_range(int(month_year.group(2)), _MONTHS[month_year.group(1)])

    iso_single = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", normalized)
    if iso_single:
        day = date.fromisoformat(iso_single.group(1))
        return day, day

    month_only = re.search(rf"\b({_MONTH_PATTERN})\b", normalized)
    if month_only:
        return _month_range(today.year, _MONTHS[month_only.group(1)])

    return None


def _extract_range(message: str, today: date) -> tuple[date, date]:
    """Devuelve el periodo mencionado o los últimos 30 días por defecto."""
    return _parse_period(message, today) or _last_n_days(today, 30)


def _extract_comparison_periods(
    message: str,
    today: date,
) -> tuple[tuple[date, date], tuple[date, date]]:
    """Obtiene los dos periodos de una comparación."""
    iso_ranges = re.findall(
        r"(\d{4}-\d{2}-\d{2})\s*(?:a|hasta|-)\s*(\d{4}-\d{2}-\d{2})",
        _normalize(message),
    )
    if len(iso_ranges) >= 2:
        return (
            (date.fromisoformat(iso_ranges[0][0]), date.fromisoformat(iso_ranges[0][1])),
            (date.fromisoformat(iso_ranges[1][0]), date.fromisoformat(iso_ranges[1][1])),
        )

    parts = re.split(
        r"\b(?:con|vs\.?|frente a)\b",
        message,
        maxsplit=1,
        flags=re.IGNORECASE,
    )
    if len(parts) == 2:
        first = _parse_period(parts[0], today)
        second = _parse_period(parts[1], today)
        if first is not None and second is not None:
            return first, second

    month_mentions = re.findall(
        rf"\b(?:{_MONTH_PATTERN})\b(?:\s+de)?\s+\d{{4}}\b",
        _normalize(message),
    )
    if len(month_mentions) >= 2:
        first = _parse_period(month_mentions[0], today)
        second = _parse_period(month_mentions[1], today)
        if first is not None and second is not None:
            return first, second

    current_start = today.replace(day=1)
    previous_end = current_start - timedelta(days=1)
    return (current_start, today), (previous_end.replace(day=1), previous_end)


def _extract_metric(message: str) -> MetricName:
    """Reconoce la métrica mencionada; ROAS es el valor por defecto."""
    normalized = _normalize(message)
    for term, metric in _METRIC_TERMS:
        if re.search(rf"\b{re.escape(term)}\b", normalized):
            return metric
    return MetricName.ROAS


def _extract_limit(message: str, *, default: int = 5) -> int:
    """Extrae un límite razonable entre 1 y 20."""
    normalized = _normalize(message)
    for pattern in (
        r"\btop\s+(\d+)\b",
        r"\b(\d+)\s+(?:mejores|anuncios|ads)\b",
        r"\blimite\s+(\d+)\b",
    ):
        match = re.search(pattern, normalized)
        if match:
            return min(20, max(1, int(match.group(1))))
    return default


def _extract_campaign_name(message: str) -> str | None:
    """Extrae el nombre de campaña, priorizando comillas."""
    quoted = re.search(
        r"campa[nñ]a\s+[\"“']([^\"”']+)[\"”']",
        message,
        re.IGNORECASE,
    )
    if quoted:
        return quoted.group(1).strip()

    target = re.search(r"campa[nñ]a\s+(.+)$", message, re.IGNORECASE)
    if target is None:
        return None

    period_marker = re.compile(
        rf"\s+(?:en|durante|para)\s+"
        rf"|\s+del\s+(?:mes|a[nñ]o)\b"
        rf"|\s+(?:este|el)\s+(?:mes|a[nñ]o)\b"
        rf"|\s+(?:los\s+)?[uú]ltimos?\s+\d+\s+d[ií]as\b"
        rf"|\s+de\s+(?=(?:{_MONTH_PATTERN}|\d{{4}}|este\s+mes|el\s+mes))",
        re.IGNORECASE,
    )
    candidate = period_marker.split(target.group(1), maxsplit=1)[0]
    candidate = re.split(r"[,.;]", candidate, maxsplit=1)[0]
    name = candidate.strip(" \"'“”")
    return name or None


def build_plan_from_message(message: str, *, today: date | None = None) -> dict[str, Any] | None:
    """Propone un plan para el mensaje; ``None`` si no puede construirlo.

    Es determinista y no accede a la base de datos. El plan se valida y ejecuta
    después con el ``organization_id`` del contexto autenticado.
    """
    current_day = today or date.today()
    intent = classify_intent(message).intent

    if intent is Intent.TOP_ADS_BY_METRIC:
        date_from, date_to = _extract_range(message, current_day)
        return {
            "operation": "top_ads_by_metric",
            "metric": _extract_metric(message).value,
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "limit": _extract_limit(message),
        }

    if intent is Intent.CAMPAIGN_PERFORMANCE:
        campaign_name = _extract_campaign_name(message)
        if campaign_name is None:
            return None
        date_from, date_to = _extract_range(message, current_day)
        return {
            "operation": "campaign_performance",
            "campaign_name": campaign_name,
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
        }

    if intent is Intent.COMPARE_PERIODS:
        (date_from, date_to), (comparison_from, comparison_to) = _extract_comparison_periods(
            message, current_day
        )
        return {
            "operation": "compare_periods",
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "comparison_date_from": comparison_from.isoformat(),
            "comparison_date_to": comparison_to.isoformat(),
        }

    return None
