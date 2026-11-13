"""Tests de las políticas deterministas que validan planes."""

from datetime import date

from jev_ai.ai.jev.intents import Intent
from jev_ai.ai.jev.plans import (
    CampaignPerformancePlan,
    ComparePeriodsPlan,
    TopAdsByMetricPlan,
)
from jev_ai.ai.jev.policies import MAX_RANGE_DAYS, validate_query_plan


def _top_ads(metric: str = "roas", days: int = 30) -> TopAdsByMetricPlan:
    return TopAdsByMetricPlan(
        operation="top_ads_by_metric",
        metric=metric,
        date_from=date(2026, 1, 1),
        date_to=date.fromordinal(date(2026, 1, 1).toordinal() + days - 1),
        limit=5,
    )


def test_accepts_valid_plan_and_matching_intent() -> None:
    decision = validate_query_plan(_top_ads(), expected_intent=Intent.TOP_ADS_BY_METRIC)

    assert decision.accepted is True
    assert decision.violations == []


def test_rejects_intent_mismatch() -> None:
    decision = validate_query_plan(
        _top_ads(),
        expected_intent=Intent.CAMPAIGN_PERFORMANCE,
    )

    assert decision.accepted is False
    assert [violation.code for violation in decision.violations] == ["intent_mismatch"]


def test_rejects_non_rankable_metrics() -> None:
    decision = validate_query_plan(_top_ads(metric="reach"))

    assert decision.accepted is False
    assert [violation.code for violation in decision.violations] == ["metric_not_rankable"]


def test_rejects_ranges_over_the_limit() -> None:
    decision = validate_query_plan(_top_ads(days=MAX_RANGE_DAYS + 1))

    assert decision.accepted is False
    assert [violation.code for violation in decision.violations] == ["range_too_large"]


def test_rejects_blank_campaign_name() -> None:
    plan = CampaignPerformancePlan(
        operation="campaign_performance",
        campaign_name="   ",
        date_from=date(2026, 10, 1),
        date_to=date(2026, 10, 31),
    )

    decision = validate_query_plan(plan)

    assert decision.accepted is False
    assert [violation.code for violation in decision.violations] == ["empty_campaign_name"]


def test_rejects_comparison_range_over_the_limit() -> None:
    plan = ComparePeriodsPlan(
        operation="compare_periods",
        date_from=date(2026, 1, 1),
        date_to=date(2026, 12, 31),
        comparison_date_from=date(2020, 1, 1),
        comparison_date_to=date(2021, 12, 31),
    )

    decision = validate_query_plan(plan)

    assert decision.accepted is False
    assert [violation.code for violation in decision.violations] == ["range_too_large"]
