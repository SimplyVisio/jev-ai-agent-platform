"""Schemas HTTP del módulo de marketing."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints

from jev_ai.modules.marketing.models import (
    AdStatus,
    CampaignObjective,
    CampaignStatus,
)

Name = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=120),
]


class CampaignCreate(BaseModel):
    """Datos para crear una campaña."""

    name: Name
    objective: CampaignObjective
    status: CampaignStatus = CampaignStatus.ACTIVE


class CampaignUpdate(BaseModel):
    """Campos editables de una campaña; los omitidos no cambian."""

    name: Name | None = None
    objective: CampaignObjective | None = None
    status: CampaignStatus | None = None


class CampaignRead(BaseModel):
    """Campaña expuesta por la API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    name: str
    objective: CampaignObjective
    status: CampaignStatus
    created_at: datetime


class AdCreate(BaseModel):
    """Datos para crear un anuncio dentro de una campaña."""

    name: Name
    status: AdStatus = AdStatus.ACTIVE


class AdUpdate(BaseModel):
    """Campos editables de un anuncio; los omitidos no cambian."""

    name: Name | None = None
    status: AdStatus | None = None


class AdRead(BaseModel):
    """Anuncio expuesto por la API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    campaign_id: UUID
    organization_id: UUID
    name: str
    status: AdStatus
    created_at: datetime
