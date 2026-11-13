"""Tests del catálogo cerrado de QueryPlan."""

from datetime import date

import pytest
from pydantic import ValidationError

from jev_ai.ai.jev.plans import (
    CampaignPerformancePlan,
    ComparePeriodsPlan,
    PlanParseError,
    TopAdsByMetricPlan,
    parse_query_plan,
    plan_to_dict,
)


def test_parse_top_ads_plan_from_json() -> None:
    plan = parse_query_plan(
        """
        {
          "operation": "top_ads_by_metric",
          "metric": "roas",
          "date_from": "2026-10-01",
          "date_to": "2026-10-31",
          "limit": 5
        }
        """
    )

    assert isinstance(plan, TopAdsByMetricPlan)
    assert plan.limit == 5
    assert plan.date_from == date(2026, 10, 1)
    assert plan.metric.value == "roas"


def test_plan_rejects_organization_id_from_llm() -> None:
    with pytest.raises(PlanParseError):
        parse_query_plan(
            {
                "operation": "top_ads_by_metric",
                "metric": "roas",
                "date_from": "2026-10-01",
                "date_to": "2026-10-31",
                "organization_id": "00000000-0000-0000-0000-000000000000",
            }
        )


def test_plan_rejects_unknown_metric() -> None:
    with pytest.raises(PlanParseError):
        parse_query_plan(
            {
                "operation": "top_ads_by_metric",
                "metric": "profit",
                "date_from": "2026-10-01",
                "date_to": "2026-10-31",
            }
        )


def test_plan_rejects_reversed_dates() -> None:
    with pytest.raises(ValidationError):
        TopAdsByMetricPlan(
            operation="top_ads_by_metric",
            metric="roas",
            date_from=date(2026, 10, 31),
            date_to=date(2026, 10, 1),
        )


def test_campaign_plan_requires_exactly_one_target() -> None:
    with pytest.raises(ValidationError):
        CampaignPerformancePlan(
            operation="campaign_performance",
            date_from=date(2026, 10, 1),
            date_to=date(2026, 10, 31),
        )

    with pytest.raises(ValidationError):
        CampaignPerformancePlan(
            operation="campaign_performance",
            campaign_id="00000000-0000-0000-0000-000000000000",
            campaign_name="Demo",
            date_from=date(2026, 10, 1),
            date_to=date(2026, 10, 31),
        )


def test_compare_plan_rejects_reversed_comparison_dates() -> None:
    with pytest.raises(ValidationError):
        ComparePeriodsPlan(
            operation="compare_periods",
            date_from=date(2026, 10, 1),
            date_to=date(2026, 10, 31),
            comparison_date_from=date(2026, 9, 30),
            comparison_date_to=date(2026, 9, 1),
        )


def test_plan_to_dict_is_json_safe() -> None:
    plan = parse_query_plan(
        {
            "operation": "compare_periods",
            "date_from": "2026-10-01",
            "date_to": "2026-10-31",
            "comparison_date_from": "2026-09-01",
            "comparison_date_to": "2026-09-30",
        }
    )

    assert plan_to_dict(plan) == {
        "operation": "compare_periods",
        "date_from": "2026-10-01",
        "date_to": "2026-10-31",
        "comparison_date_from": "2026-09-01",
        "comparison_date_to": "2026-09-30",
    }
