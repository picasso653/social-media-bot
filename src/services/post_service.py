import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.post import Post
from src.models.post_platform import PostPlatform
from src.platforms.registry import PlatformRegistry
from src.services.auth_service import AuthService

logger = logging.getLogger(__name__)


class PostService:
    def __init__(self, session: AsyncSession | None = None, auth_service: AuthService | None = None):
        self._session = session
        self.auth_service = auth_service or AuthService(session=session)

    async def create_post(
        self,
        user_id: str,
        content: str,
        media: bytes | None = None,
        platforms: list[str] | None = None,
    ) -> dict:
        if platforms is None:
            platforms = PlatformRegistry.get_names()

        if not platforms:
            return {"status": "no_accounts", "platforms": [], "platform_results": {}}

        content_type = "image" if media else "text"
        platform_results: dict = {}

        for platform_name in platforms:
            try:
                adapter = PlatformRegistry.get(platform_name)
            except ValueError:
                platform_results[platform_name] = {
                    "display_name": platform_name.upper(),
                    "success": False,
                    "error": "Unknown platform",
                }
                continue

            info = adapter.get_platform_info()

            if content_type == "image" and not info.supports_image:
                platform_results[platform_name] = {
                    "display_name": info.display_name,
                    "success": False,
                    "error": f"{info.display_name} does not support image posts",
                }
                continue

            if content_type == "text" and not info.supports_text:
                platform_results[platform_name] = {
                    "display_name": info.display_name,
                    "success": False,
                    "error": f"{info.display_name} does not support text-only posts",
                }
                continue

            token = await self.auth_service.get_token_for_platform(user_id, platform_name)
            if token is None:
                platform_results[platform_name] = {
                    "display_name": info.display_name,
                    "success": False,
                    "error": "Account not connected. Use /connect in Telegram.",
                }
                continue

            try:
                if content_type == "image":
                    result = await adapter.post_image(token, media, content)
                else:
                    result = await adapter.post_text(token, content)
            except NotImplementedError:
                result = None
            except Exception as e:
                logger.error("Post to %s failed: %s", platform_name, e)
                result = None

            if result is not None:
                platform_results[platform_name] = {
                    "display_name": info.display_name,
                    "success": result.success,
                    "error": result.error_message if not result.success else None,
                    "post_url": result.platform_post_url if result.success else None,
                }
            else:
                platform_results[platform_name] = {
                    "display_name": info.display_name,
                    "success": False,
                    "error": "Adapter error — check logs",
                }

        posted_count = sum(1 for r in platform_results.values() if r.get("success"))

        return {
            "status": "posted" if posted_count > 0 else "failed",
            "content_type": content_type,
            "platforms": platforms,
            "platform_results": platform_results,
            "posted_count": posted_count,
        }

    async def get_user_history(self, user_id: str, limit: int = 10) -> list[dict]:
        return []

    async def get_post_status(self, post_id: str) -> dict:
        return {"post_id": post_id, "status": "pending"}
