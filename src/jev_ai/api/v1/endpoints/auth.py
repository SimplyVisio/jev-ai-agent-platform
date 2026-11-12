from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from jev_ai.api.deps import OrganizationContext, get_current_organization

router = APIRouter()


class OrganizationResponse(BaseModel):
    organization_id: UUID


@router.get("/me", response_model=OrganizationResponse)
async def me(
    context: Annotated[OrganizationContext, Depends(get_current_organization)],
) -> OrganizationResponse:
    return OrganizationResponse(organization_id=context.organization_id)
