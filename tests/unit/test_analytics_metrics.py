"""Tests unitarios de las fórmulas de analítica."""

from decimal import Decimal

from jev_ai.modules.analytics.repository import BaseAggregate
from jev_ai.modules.analytics.service import calculate_metrics


def base_metrics() -> BaseAggregate:
    return BaseAggregate(
        impressions=1000,
        reach=500,
        clicks=50,
        landing_page_views=40,
        spend=Decimal("100.00"),
        leads=10,
        sales=2,
        revenue=Decimal("400.00"),
    )


def test_calculates_all_ratios_from_base_metrics() -> None:
    metrics = calculate_metrics(base_metrics(), reach=500)

    assert metrics.frequency == 2.0
    assert metrics.ctr == 5.0
    assert metrics.cpc == 2.0
    assert metrics.cpm == 100.0
    assert metrics.cpl == 10.0
    assert metrics.conversion_rate == 25.0
    assert metrics.roas == 4.0
    assert metrics.spend == Decimal("100.00")
    assert metrics.revenue == Decimal("400.00")


def test_zero_denominators_return_none() -> None:
    zero = BaseAggregate(
        impressions=0,
        reach=0,
        clicks=0,
        landing_page_views=0,
        spend=Decimal("0"),
        leads=0,
        sales=0,
        revenue=Decimal("0"),
    )

    metrics = calculate_metrics(zero, reach=0)

    assert metrics.reach == 0
    assert metrics.frequency is None
    assert metrics.ctr is None
    assert metrics.cpc is None
    assert metrics.cpm is None
    assert metrics.cpl is None
    assert metrics.conversion_rate is None
    assert metrics.roas is None


def test_unavailable_reach_disables_frequency_only() -> None:
    metrics = calculate_metrics(base_metrics(), reach=None)

    assert metrics.reach is None
    assert metrics.frequency is None
    assert metrics.ctr == 5.0
    assert metrics.roas == 4.0


def test_ratios_are_rounded_to_six_decimals() -> None:
    base = BaseAggregate(
        impressions=3,
        reach=2,
        clicks=1,
        landing_page_views=7,
        spend=Decimal("10.00"),
        leads=3,
        sales=0,
        revenue=Decimal("100.00"),
    )

    metrics = calculate_metrics(base, reach=2)

    assert metrics.frequency == 1.5
    assert metrics.ctr == 33.333333
    assert metrics.cpc == 10.0
    assert metrics.cpm == 3333.333333
    assert metrics.cpl == 3.333333
    assert metrics.conversion_rate == 42.857143
    assert metrics.roas == 10.0
