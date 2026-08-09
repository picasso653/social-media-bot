from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.post import Post
from src.models.post_platform import PostPlatform
from src.repositories.base import BaseRepository


class PostRepository(BaseRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_by_id(self, post_id: UUID) -> Post | None:
        result = await self.session.execute(select(Post).where(Post.id == post_id))
        return result.scalar_one_or_none()

    async def get_user_posts(self, user_id: UUID, limit: int = 20, offset: int = 0) -> list[Post]:
        result = await self.session.execute(
            select(Post)
            .where(Post.user_id == user_id)
            .order_by(Post.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_post_platforms(self, post_id: UUID) -> list[PostPlatform]:
        result = await self.session.execute(select(PostPlatform).where(PostPlatform.post_id == post_id))
        return list(result.scalars().all())
