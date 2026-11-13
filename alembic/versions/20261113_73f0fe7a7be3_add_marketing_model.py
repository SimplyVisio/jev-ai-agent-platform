"""add marketing model

Revision ID: 73f0fe7a7be3
Revises: 773a708e0e81
Create Date: 2026-11-13 05:42:31.876252

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "73f0fe7a7be3"
down_revision: str | Sequence[str] | None = "773a708e0e81"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "campaigns",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("objective", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_campaigns_organization_id", "campaigns", ["organization_id"])
    op.create_table(
        "ads",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ads_campaign_id", "ads", ["campaign_id"])
    op.create_index("ix_ads_organization_id", "ads", ["organization_id"])
    op.create_table(
        "ad_insights",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ad_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("impressions", sa.BigInteger(), nullable=False),
        sa.Column("reach", sa.BigInteger(), nullable=False),
        sa.Column("clicks", sa.BigInteger(), nullable=False),
        sa.Column("landing_page_views", sa.BigInteger(), nullable=False),
        sa.Column("spend", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("leads", sa.BigInteger(), nullable=False),
        sa.Column("sales", sa.BigInteger(), nullable=False),
        sa.Column("revenue", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.CheckConstraint("impressions >= 0", name="ck_ad_insights_impressions"),
        sa.CheckConstraint("reach >= 0", name="ck_ad_insights_reach"),
        sa.CheckConstraint("clicks >= 0", name="ck_ad_insights_clicks"),
        sa.CheckConstraint("landing_page_views >= 0", name="ck_ad_insights_lpv"),
        sa.CheckConstraint("spend >= 0", name="ck_ad_insights_spend"),
        sa.CheckConstraint("leads >= 0", name="ck_ad_insights_leads"),
        sa.CheckConstraint("sales >= 0", name="ck_ad_insights_sales"),
        sa.CheckConstraint("revenue >= 0", name="ck_ad_insights_revenue"),
        sa.ForeignKeyConstraint(["ad_id"], ["ads.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ad_id", "date", name="uq_ad_insights_ad_id_date"),
    )
    op.create_index("ix_ad_insights_ad_id", "ad_insights", ["ad_id"])
    op.create_index(
        "ix_ad_insights_organization_id_date",
        "ad_insights",
        ["organization_id", "date"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ad_insights_organization_id_date",
        table_name="ad_insights",
    )
    op.drop_index("ix_ad_insights_ad_id", table_name="ad_insights")
    op.drop_table("ad_insights")
    op.drop_index("ix_ads_organization_id", table_name="ads")
    op.drop_index("ix_ads_campaign_id", table_name="ads")
    op.drop_table("ads")
    op.drop_index("ix_campaigns_organization_id", table_name="campaigns")
    op.drop_table("campaigns")
