from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.social_account import SocialAccount
from src.repositories.base import BaseRepository


class AccountRepository(BaseRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_by_user_and_platform(self, user_id: str, platform: str) -> SocialAccount | None:
        result = await self.session.execute(
            select(SocialAccount).where(SocialAccount.user_id == user_id, SocialAccount.platform == platform)
        )
        return result.scalar_one_or_none()

    async def get_active_for_user(self, user_id: str) -> list[SocialAccount]:
        result = await self.session.execute(
            select(SocialAccount).where(SocialAccount.user_id == user_id, SocialAccount.is_active.is_(True))
        )
        return list(result.scalars().all())
