"""Tests del traductor offline de lenguaje natural a QueryPlan."""

from datetime import date

from jev_ai.ai.jev.plans import parse_query_plan
from jev_ai.ai.llm.base import LLMContext
from jev_ai.ai.llm.plan_builder import build_follow_up_plan, build_plan_from_message

TODAY = date(2026, 11, 13)


def test_builds_top_ads_plan_with_month_and_limit() -> None:
    plan = build_plan_from_message(
        "¿Cuáles son los 3 mejores anuncios por ROAS en octubre de 2026?",
        today=TODAY,
    )

    assert plan == {
        "operation": "top_ads_by_metric",
        "metric": "roas",
        "date_from": "2026-10-01",
        "date_to": "2026-10-31",
        "limit": 3,
    }


def test_builds_top_ads_plan_with_lower_is_better_metric() -> None:
    plan = build_plan_from_message("Top 5 anuncios por CPL este mes", today=TODAY)

    assert plan is not None
    assert plan["metric"] == "cpl"
    assert plan["date_from"] == "2026-11-01"
    assert plan["date_to"] == "2026-11-13"


def test_builds_top_ads_plan_with_last_n_days() -> None:
    plan = build_plan_from_message("Mejores anuncios por CTR en los últimos 7 días", today=TODAY)

    assert plan is not None
    assert plan["metric"] == "ctr"
    assert plan["date_from"] == "2026-11-07"
    assert plan["date_to"] == "2026-11-13"


def test_builds_campaign_plan_with_quoted_name() -> None:
    plan = build_plan_from_message(
        '¿Cómo va la campaña "Demo Prospecting" este mes?',
        today=TODAY,
    )

    assert plan == {
        "operation": "campaign_performance",
        "campaign_name": "Demo Prospecting",
        "date_from": "2026-11-01",
        "date_to": "2026-11-13",
    }


def test_builds_campaign_plan_with_unquoted_name_and_month() -> None:
    plan = build_plan_from_message(
        "Resultados de la campaña Alpha Campaign en septiembre de 2026",
        today=TODAY,
    )

    assert plan is not None
    assert plan["campaign_name"] == "Alpha Campaign"
    assert plan["date_from"] == "2026-09-01"
    assert plan["date_to"] == "2026-09-30"


def test_builds_comparison_with_relative_periods() -> None:
    plan = build_plan_from_message("Compara este mes con el mes pasado", today=TODAY)

    assert plan == {
        "operation": "compare_periods",
        "date_from": "2026-11-01",
        "date_to": "2026-11-13",
        "comparison_date_from": "2026-10-01",
        "comparison_date_to": "2026-10-31",
    }


def test_builds_comparison_with_two_iso_ranges() -> None:
    plan = build_plan_from_message(
        "Compara 2026-10-01 a 2026-10-31 con 2026-09-01 a 2026-09-30",
        today=TODAY,
    )

    assert plan is not None
    assert plan["date_from"] == "2026-10-01"
    assert plan["date_to"] == "2026-10-31"
    assert plan["comparison_date_from"] == "2026-09-01"
    assert plan["comparison_date_to"] == "2026-09-30"


def test_returns_none_for_unknown_or_incomplete_messages() -> None:
    assert build_plan_from_message("Quiero saber algo", today=TODAY) is None
    assert build_plan_from_message("¿Cómo va la campaña?", today=TODAY) is None


def test_follow_up_reuses_period_and_metric() -> None:
    last_plan = parse_query_plan(
        {
            "operation": "top_ads_by_metric",
            "metric": "roas",
            "date_from": "2026-10-01",
            "date_to": "2026-10-31",
            "limit": 5,
        }
    )
    context = LLMContext(last_plan=last_plan)

    plan = build_follow_up_plan("¿Y en septiembre?", context, today=TODAY)

    assert plan is not None
    assert plan["operation"] == "top_ads_by_metric"
    assert plan["metric"] == "roas"
    assert plan["date_from"] == "2026-09-01"
    assert plan["date_to"] == "2026-09-30"

    metric_plan = build_follow_up_plan("¿Y el CTR?", context, today=TODAY)

    assert metric_plan is not None
    assert metric_plan["metric"] == "ctr"
    assert metric_plan["date_from"] == "2026-10-01"


def test_follow_up_reuses_campaign_name() -> None:
    last_plan = parse_query_plan(
        {
            "operation": "campaign_performance",
            "campaign_name": "Demo",
            "date_from": "2026-10-01",
            "date_to": "2026-10-31",
        }
    )

    plan = build_follow_up_plan(
        "¿Y el mes pasado?",
        LLMContext(last_plan=last_plan),
        today=TODAY,
    )

    assert plan is not None
    assert plan["campaign_name"] == "Demo"
    assert plan["date_from"] == "2026-10-01"
    assert plan["date_to"] == "2026-10-31"


def test_follow_up_requires_period_or_metric() -> None:
    last_plan = parse_query_plan(
        {
            "operation": "top_ads_by_metric",
            "metric": "roas",
            "date_from": "2026-10-01",
            "date_to": "2026-10-31",
            "limit": 5,
        }
    )

    assert (
        build_follow_up_plan(
            "Dame un café",
            LLMContext(last_plan=last_plan),
            today=TODAY,
        )
        is None
    )


def test_follow_up_does_not_infer_comparisons() -> None:
    last_plan = parse_query_plan(
        {
            "operation": "compare_periods",
            "date_from": "2026-10-01",
            "date_to": "2026-10-31",
            "comparison_date_from": "2026-09-01",
            "comparison_date_to": "2026-09-30",
        }
    )

    assert (
        build_follow_up_plan(
            "¿Y en agosto?",
            LLMContext(last_plan=last_plan),
            today=TODAY,
        )
        is None
    )
