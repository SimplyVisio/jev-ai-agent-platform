"""Tests del traductor offline de lenguaje natural a QueryPlan."""

from datetime import date

from jev_ai.ai.llm.plan_builder import build_plan_from_message

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
