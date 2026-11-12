from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jev_ai.modules.organizations.models import ApiKey


async def find_api_key_by_hash(session: AsyncSession, key_hash: str) -> ApiKey | None:
    result = await session.execute(select(ApiKey).where(ApiKey.key_hash == key_hash))
    return result.scalar_one_or_none()
