"""Tests de integración de la API de analítica."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from jev_ai.modules.marketing.models import Ad, AdInsight, Campaign
from jev_ai.modules.organizations.models import ApiKey, Organization
from jev_ai.security import hash_api_key

RANGE = "date_from=2026-10-01&date_to=2026-10-02"


@dataclass(frozen=True)
class AnalyticsSeed:
    organization_id: UUID
    key: str
    campaign_id: UUID
    empty_campaign_id: UUID
    ad_one_id: UUID
    ad_two_id: UUID


def headers(key: str) -> dict[str, str]:
    return {"X-API-Key": key}


async def _seed_organizations(
    session_factory: async_sessionmaker[AsyncSession],
) -> tuple[AnalyticsSeed, AnalyticsSeed]:
    alpha_key = f"jev_test_{uuid4().hex}"
    beta_key = f"jev_test_{uuid4().hex}"

    async with session_factory() as session:
        alpha = Organization(name=f"Alpha {uuid4()}", currency_code="USD")
        beta = Organization(name=f"Beta {uuid4()}", currency_code="USD")
        session.add_all([alpha, beta])
        await session.flush()
        session.add_all(
            [
                ApiKey(organization_id=alpha.id, key_hash=hash_api_key(alpha_key)),
                ApiKey(organization_id=beta.id, key_hash=hash_api_key(beta_key)),
            ]
        )

        alpha_campaign = Campaign(
            organization_id=alpha.id,
            name="Alpha Campaign",
            objective="sales",
        )
        empty_campaign = Campaign(
            organization_id=alpha.id,
            name="Alpha Empty",
            objective="traffic",
        )
        beta_campaign = Campaign(
            organization_id=beta.id,
            name="Beta Campaign",
            objective="sales",
        )
        session.add_all([alpha_campaign, empty_campaign, beta_campaign])
        await session.flush()

        ad_one = Ad(
            campaign_id=alpha_campaign.id,
            organization_id=alpha.id,
            name="Ad One",
        )
        ad_two = Ad(
            campaign_id=alpha_campaign.id,
            organization_id=alpha.id,
            name="Ad Two",
        )
        empty_ad = Ad(
            campaign_id=empty_campaign.id,
            organization_id=alpha.id,
            name="Empty Ad",
        )
        beta_ad = Ad(
            campaign_id=beta_campaign.id,
            organization_id=beta.id,
            name="Beta Ad",
        )
        session.add_all([ad_one, ad_two, empty_ad, beta_ad])
        await session.flush()

        session.add_all(
            [
                AdInsight(
                    ad_id=ad_one.id,
                    organization_id=alpha.id,
                    date=date(2026, 10, 1),
                    impressions=1000,
                    reach=400,
                    clicks=50,
                    landing_page_views=40,
                    spend=Decimal("100.00"),
                    leads=10,
                    sales=2,
                    revenue=Decimal("400.00"),
                ),
                AdInsight(
                    ad_id=ad_one.id,
                    organization_id=alpha.id,
                    date=date(2026, 10, 2),
                    impressions=200,
                    reach=100,
                    clicks=50,
                    landing_page_views=20,
                    spend=Decimal("20.00"),
                    leads=2,
                    sales=0,
                    revenue=Decimal("0.00"),
                ),
                AdInsight(
                    ad_id=ad_two.id,
                    organization_id=alpha.id,
                    date=date(2026, 10, 1),
                    impressions=500,
                    reach=200,
                    clicks=25,
                    landing_page_views=20,
                    spend=Decimal("50.00"),
                    leads=5,
                    sales=1,
                    revenue=Decimal("100.00"),
                ),
                AdInsight(
                    ad_id=ad_two.id,
                    organization_id=alpha.id,
                    date=date(2026, 10, 2),
                    impressions=100,
                    reach=50,
                    clicks=5,
                    landing_page_views=10,
                    spend=Decimal("10.00"),
                    leads=1,
                    sales=0,
                    revenue=Decimal("0.00"),
                ),
                AdInsight(
                    ad_id=beta_ad.id,
                    organization_id=beta.id,
                    date=date(2026, 10, 1),
                    impressions=99999,
                    reach=99999,
                    clicks=99999,
                    landing_page_views=99999,
                    spend=Decimal("999.99"),
                    leads=999,
                    sales=99,
                    revenue=Decimal("9999.99"),
                ),
            ]
        )
        await session.commit()

        return (
            AnalyticsSeed(
                organization_id=alpha.id,
                key=alpha_key,
                campaign_id=alpha_campaign.id,
                empty_campaign_id=empty_campaign.id,
                ad_one_id=ad_one.id,
                ad_two_id=ad_two.id,
            ),
            AnalyticsSeed(
                organization_id=beta.id,
                key=beta_key,
                campaign_id=beta_campaign.id,
                empty_campaign_id=beta_campaign.id,
                ad_one_id=beta_ad.id,
                ad_two_id=beta_ad.id,
            ),
        )


@pytest.fixture
async def analytics_seed(
    session_factory: async_sessionmaker[AsyncSession],
) -> tuple[AnalyticsSeed, AnalyticsSeed]:
    return await _seed_organizations(session_factory)


def test_overview_sums_base_metrics_before_ratios(
    client: TestClient,
    analytics_seed: tuple[AnalyticsSeed, AnalyticsSeed],
) -> None:
    alpha, _beta = analytics_seed

    response = client.get(f"/api/v1/analytics/overview?{RANGE}", headers=headers(alpha.key))

    assert response.status_code == 200
    body = response.json()
    assert body["date_from"] == "2026-10-01"
    assert body["date_to"] == "2026-10-02"
    assert body["impressions"] == 1800
    assert body["clicks"] == 130
    assert body["landing_page_views"] == 90
    assert body["leads"] == 18
    assert body["sales"] == 3
    assert body["spend"] == "180.00"
    assert body["revenue"] == "500.00"
    assert isinstance(body["spend"], str)
    assert body["reach"] is None
    assert body["frequency"] is None
    assert body["ctr"] == pytest.approx(7.222222)
    assert body["cpc"] == pytest.approx(1.384615)
    assert body["cpm"] == pytest.approx(100.0)
    assert body["cpl"] == pytest.approx(10.0)
    assert body["conversion_rate"] == pytest.approx(20.0)
    assert body["roas"] == pytest.approx(2.777778)


def test_overview_respects_date_range(
    client: TestClient,
    analytics_seed: tuple[AnalyticsSeed, AnalyticsSeed],
) -> None:
    alpha, _beta = analytics_seed

    response = client.get(
        "/api/v1/analytics/overview?date_from=2026-10-01&date_to=2026-10-01",
        headers=headers(alpha.key),
    )

    body = response.json()
    assert body["impressions"] == 1500
    assert body["clicks"] == 75
    assert Decimal(body["spend"]) == Decimal("150.00")
    assert body["reach"] is None
    assert body["frequency"] is None
    assert body["ctr"] == pytest.approx(5.0)
    assert body["conversion_rate"] == pytest.approx(25.0)
    assert body["roas"] == pytest.approx(3.333333)


def test_campaign_performance_excludes_campaigns_without_insights(
    client: TestClient,
    analytics_seed: tuple[AnalyticsSeed, AnalyticsSeed],
) -> None:
    alpha, _beta = analytics_seed

    response = client.get(
        f"/api/v1/analytics/campaigns?{RANGE}",
        headers=headers(alpha.key),
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["campaign_id"] == str(alpha.campaign_id)
    assert body[0]["campaign_name"] == "Alpha Campaign"
    assert body[0]["metrics"]["impressions"] == 1800
    assert body[0]["metrics"]["reach"] is None
    assert body[0]["metrics"]["ctr"] == pytest.approx(7.222222)


def test_ad_performance_hides_reach_for_multi_day_range(
    client: TestClient,
    analytics_seed: tuple[AnalyticsSeed, AnalyticsSeed],
) -> None:
    alpha, _beta = analytics_seed

    response = client.get(f"/api/v1/analytics/ads?{RANGE}", headers=headers(alpha.key))

    body = response.json()
    assert [item["ad_id"] for item in body] == [
        str(alpha.ad_one_id),
        str(alpha.ad_two_id),
    ]
    first = body[0]["metrics"]
    assert first["impressions"] == 1200
    assert first["clicks"] == 100
    assert Decimal(first["spend"]) == Decimal("120.00")
    assert first["reach"] is None
    assert first["frequency"] is None


def test_ad_performance_reports_reach_for_single_day(
    client: TestClient,
    analytics_seed: tuple[AnalyticsSeed, AnalyticsSeed],
) -> None:
    alpha, _beta = analytics_seed

    response = client.get(
        "/api/v1/analytics/ads?date_from=2026-10-01&date_to=2026-10-01",
        headers=headers(alpha.key),
    )

    body = response.json()
    assert body[0]["metrics"]["reach"] == 400
    assert body[0]["metrics"]["frequency"] == 2.5
    assert body[1]["metrics"]["reach"] == 200
    assert body[1]["metrics"]["frequency"] == 2.5


def test_ad_performance_filters_and_paginates(
    client: TestClient,
    analytics_seed: tuple[AnalyticsSeed, AnalyticsSeed],
) -> None:
    alpha, _beta = analytics_seed

    by_campaign = client.get(
        f"/api/v1/analytics/ads?{RANGE}&campaign_id={alpha.campaign_id}",
        headers=headers(alpha.key),
    )
    empty = client.get(
        f"/api/v1/analytics/ads?{RANGE}&campaign_id={alpha.empty_campaign_id}",
        headers=headers(alpha.key),
    )
    page = client.get(f"/api/v1/analytics/ads?{RANGE}&limit=1&offset=1", headers=headers(alpha.key))

    assert len(by_campaign.json()) == 2
    assert empty.json() == []
    assert [item["ad_id"] for item in page.json()] == [str(alpha.ad_two_id)]


def test_daily_trends_aggregate_each_period(
    client: TestClient,
    analytics_seed: tuple[AnalyticsSeed, AnalyticsSeed],
) -> None:
    alpha, _beta = analytics_seed

    response = client.get(
        f"/api/v1/analytics/trends?{RANGE}&granularity=day",
        headers=headers(alpha.key),
    )

    body = response.json()
    assert len(body) == 2
    first, second = body
    assert first["period_start"] == "2026-10-01"
    assert first["period_end"] == "2026-10-01"
    assert first["metrics"]["impressions"] == 1500
    assert first["metrics"]["ctr"] == pytest.approx(5.0)
    assert first["metrics"]["reach"] is None
    assert second["period_start"] == "2026-10-02"
    assert second["metrics"]["impressions"] == 300
    assert second["metrics"]["ctr"] == pytest.approx(18.333333)


def test_weekly_trends_are_clipped_to_requested_range(
    client: TestClient,
    analytics_seed: tuple[AnalyticsSeed, AnalyticsSeed],
) -> None:
    alpha, _beta = analytics_seed

    response = client.get(
        f"/api/v1/analytics/trends?{RANGE}&granularity=week",
        headers=headers(alpha.key),
    )

    body = response.json()
    assert len(body) == 1
    assert body[0]["period_start"] == "2026-10-01"
    assert body[0]["period_end"] == "2026-10-02"
    assert body[0]["metrics"]["impressions"] == 1800


def test_monthly_trends_use_calendar_periods(
    client: TestClient,
    analytics_seed: tuple[AnalyticsSeed, AnalyticsSeed],
) -> None:
    alpha, _beta = analytics_seed

    response = client.get(
        "/api/v1/analytics/trends?date_from=2026-10-01&date_to=2026-10-31&granularity=month",
        headers=headers(alpha.key),
    )

    body = response.json()
    assert len(body) == 1
    assert body[0]["period_start"] == "2026-10-01"
    assert body[0]["period_end"] == "2026-10-31"
    assert body[0]["metrics"]["impressions"] == 1800


def test_analytics_includes_archived_entities(
    client: TestClient,
    analytics_seed: tuple[AnalyticsSeed, AnalyticsSeed],
) -> None:
    alpha, _beta = analytics_seed

    archived = client.delete(
        f"/api/v1/campaigns/{alpha.campaign_id}",
        headers=headers(alpha.key),
    )
    response = client.get(f"/api/v1/analytics/campaigns?{RANGE}", headers=headers(alpha.key))

    assert archived.status_code == 204
    assert [item["campaign_id"] for item in response.json()] == [str(alpha.campaign_id)]


def test_analytics_is_isolated_by_organization(
    client: TestClient,
    analytics_seed: tuple[AnalyticsSeed, AnalyticsSeed],
) -> None:
    _alpha, beta = analytics_seed

    response = client.get(f"/api/v1/analytics/overview?{RANGE}", headers=headers(beta.key))

    body = response.json()
    assert body["impressions"] == 99999
    assert Decimal(body["spend"]) == Decimal("999.99")
    assert body["ctr"] == pytest.approx(100.0)


def test_empty_range_returns_zeroes_and_empty_lists(
    client: TestClient,
    analytics_seed: tuple[AnalyticsSeed, AnalyticsSeed],
) -> None:
    alpha, _beta = analytics_seed
    empty_range = "date_from=2027-01-01&date_to=2027-01-31"

    overview = client.get(
        f"/api/v1/analytics/overview?{empty_range}",
        headers=headers(alpha.key),
    ).json()
    assert overview["impressions"] == 0
    assert overview["spend"] == "0.00"
    assert overview["ctr"] is None
    assert overview["roas"] is None

    for endpoint in ("campaigns", "ads", "trends"):
        response = client.get(
            f"/api/v1/analytics/{endpoint}?{empty_range}",
            headers=headers(alpha.key),
        )
        assert response.json() == []


def test_analytics_validates_input(
    client: TestClient,
    analytics_seed: tuple[AnalyticsSeed, AnalyticsSeed],
) -> None:
    alpha, _beta = analytics_seed

    reversed_range = client.get(
        "/api/v1/analytics/overview?date_from=2026-10-02&date_to=2026-10-01",
        headers=headers(alpha.key),
    )
    missing_date = client.get(
        "/api/v1/analytics/overview?date_from=2026-10-01",
        headers=headers(alpha.key),
    )
    bad_granularity = client.get(
        f"/api/v1/analytics/trends?{RANGE}&granularity=hour",
        headers=headers(alpha.key),
    )
    bad_limit = client.get(
        f"/api/v1/analytics/campaigns?{RANGE}&limit=0",
        headers=headers(alpha.key),
    )
    unauthorized = client.get(f"/api/v1/analytics/overview?{RANGE}")

    assert reversed_range.status_code == 422
    assert missing_date.status_code == 422
    assert bad_granularity.status_code == 422
    assert bad_limit.status_code == 422
    assert unauthorized.status_code == 401
