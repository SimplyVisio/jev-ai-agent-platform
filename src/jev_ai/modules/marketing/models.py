"""Entidades de campañas, anuncios y métricas diarias.

Las métricas se guardan solo en su forma base; los ratios se calculan en
``analytics/service.py``. ``ad_insights`` registra una fila por anuncio y día.
"""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from jev_ai.infrastructure.database.base import Base

MONEY = Numeric(12, 2)


class CampaignObjective(StrEnum):
    """Objetivo declarado de una campaña (vocabulario cerrado)."""

    AWARENESS = "awareness"
    TRAFFIC = "traffic"
    ENGAGEMENT = "engagement"
    LEADS = "leads"
    SALES = "sales"
    APP_PROMOTION = "app_promotion"


class CampaignStatus(StrEnum):
    """Estado operativo de una campaña."""

    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class AdStatus(StrEnum):
    """Estado operativo de un anuncio."""

    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class Campaign(Base):
    """Campaña publicitaria de una organización.

    Attributes:
        id: Identificador UUID.
        organization_id: Organización propietaria; filtra todos los datos.
        name: Nombre visible de la campaña.
        objective: Objetivo del catálogo ``CampaignObjective``.
        status: Estado del catálogo ``CampaignStatus``.
        created_at: Fecha de alta asignada por PostgreSQL.
        ads: Anuncios de la campaña, eliminados en cascada.
    """

    __tablename__ = "campaigns"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120))
    objective: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(
        String(20),
        default=CampaignStatus.ACTIVE,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    ads: Mapped[list["Ad"]] = relationship(
        back_populates="campaign",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Ad(Base):
    """Anuncio perteneciente a una campaña.

    ``organization_id`` se desnormaliza para filtrar por organización sin joins.

    Attributes:
        id: Identificador UUID.
        campaign_id: Campaña a la que pertenece.
        organization_id: Organización propietaria.
        name: Nombre visible del anuncio.
        status: Estado del catálogo ``AdStatus``.
        created_at: Fecha de alta asignada por PostgreSQL.
        campaign: Campaña padre.
        insights: Métricas diarias del anuncio, eliminadas en cascada.
    """

    __tablename__ = "ads"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    campaign_id: Mapped[UUID] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        index=True,
    )
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), default=AdStatus.ACTIVE)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    campaign: Mapped[Campaign] = relationship(back_populates="ads")
    insights: Mapped[list["AdInsight"]] = relationship(
        back_populates="ad",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class AdInsight(Base):
    """Métricas base de un anuncio para un día concreto.

    Attributes:
        id: Identificador UUID.
        ad_id: Anuncio medido.
        organization_id: Organización propietaria, desnormalizada para filtrar.
        date: Día de la medición.
        impressions: Impresiones del día.
        reach: Personas únicas alcanzadas (no sumable entre días).
        clicks: Clics del día.
        landing_page_views: Visitas a la landing atribuidas por la plataforma.
        spend: Gasto en la moneda de la organización.
        leads: Contactos generados.
        sales: Ventas atribuidas.
        revenue: Ingresos atribuidos.
        ad: Anuncio padre.
    """

    __tablename__ = "ad_insights"
    __table_args__ = (
        UniqueConstraint("ad_id", "date", name="uq_ad_insights_ad_id_date"),
        Index("ix_ad_insights_organization_id_date", "organization_id", "date"),
        CheckConstraint("impressions >= 0", name="ck_ad_insights_impressions"),
        CheckConstraint("reach >= 0", name="ck_ad_insights_reach"),
        CheckConstraint("clicks >= 0", name="ck_ad_insights_clicks"),
        CheckConstraint("landing_page_views >= 0", name="ck_ad_insights_lpv"),
        CheckConstraint("spend >= 0", name="ck_ad_insights_spend"),
        CheckConstraint("leads >= 0", name="ck_ad_insights_leads"),
        CheckConstraint("sales >= 0", name="ck_ad_insights_sales"),
        CheckConstraint("revenue >= 0", name="ck_ad_insights_revenue"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    ad_id: Mapped[UUID] = mapped_column(
        ForeignKey("ads.id", ondelete="CASCADE"),
        index=True,
    )
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
    )
    date: Mapped[date] = mapped_column(Date)

    impressions: Mapped[int] = mapped_column(BigInteger, default=0)
    reach: Mapped[int] = mapped_column(BigInteger, default=0)
    clicks: Mapped[int] = mapped_column(BigInteger, default=0)
    landing_page_views: Mapped[int] = mapped_column(BigInteger, default=0)
    spend: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    leads: Mapped[int] = mapped_column(BigInteger, default=0)
    sales: Mapped[int] = mapped_column(BigInteger, default=0)
    revenue: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))

    ad: Mapped[Ad] = relationship(back_populates="insights")
