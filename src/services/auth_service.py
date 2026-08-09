import logging
import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.social_account import SocialAccount
from src.models.user import User
from src.platforms.registry import PlatformRegistry

logger = logging.getLogger(__name__)

VALID_PLATFORMS = {"x", "tiktok", "instagram"}


class AuthService:
    def __init__(self, session: AsyncSession | None = None):
        self._session = session
        self._pending_auth: dict[str, dict] = {}

    async def _ensure_user(self, telegram_id: int | str) -> User:
        session = self._session
        if session is None:
            raise RuntimeError("AuthService requires a database session")

        result = await session.execute(select(User).where(User.telegram_id == int(telegram_id)))
        user = result.scalar_one_or_none()

        if user is None:
            user = User(telegram_id=int(telegram_id))
            session.add(user)
            await session.flush()

        return user

    async def start_oauth(self, platform: str, telegram_id: int | str) -> str:
        if platform not in VALID_PLATFORMS:
            raise ValueError(f"Unknown platform: {platform}")

        state = str(uuid.uuid4())
        self._pending_auth[state] = {
            "platform": platform,
            "telegram_id": str(telegram_id),
        }

        try:
            adapter = PlatformRegistry.get(platform)
            return adapter.get_auth_url(state)
        except Exception:
            return f"https://example.com/oauth/{platform}/authorize?state={state}"

    async def complete_oauth(self, platform: str, code: str, state: str) -> dict:
        session = self._session
        if session is None:
            raise RuntimeError("AuthService requires a database session")

        pending = self._pending_auth.pop(state, None)
        if pending is None:
            raise ValueError("Invalid or expired OAuth state")

        telegram_id = pending["telegram_id"]

        adapter = PlatformRegistry.get(platform)
        result = await adapter.authenticate(code, state)

        info = adapter.get_platform_info()

        user = await self._ensure_user(telegram_id)

        existing = await session.execute(
            select(SocialAccount).where(
                SocialAccount.user_id == user.id,
                SocialAccount.platform == platform,
            )
        )
        existing_account = existing.scalar_one_or_none()

        if existing_account:
            existing_account.access_token = result.get("access_token", "")
            existing_account.platform_user_id = result.get("platform_user_id", "")
            existing_account.is_active = True
        else:
            account = SocialAccount(
                user_id=user.id,
                platform=platform,
                platform_user_id=result.get("platform_user_id", "unknown"),
                access_token=result.get("access_token", ""),
                is_active=True,
            )
            session.add(account)

        await session.commit()

        return {
            "platform": platform,
            "display_name": result.get("display_name", info.display_name),
            "status": "connected",
        }

    async def disconnect_platform(self, telegram_id: str, platform: str) -> bool:
        session = self._session
        if session is None:
            raise RuntimeError("AuthService requires a database session")

        user = await self._ensure_user(telegram_id)

        result = await session.execute(
            select(SocialAccount).where(
                SocialAccount.user_id == user.id,
                SocialAccount.platform == platform,
            )
        )
        account = result.scalar_one_or_none()

        if account:
            account.is_active = False
            await session.commit()
            return True

        return False

    async def get_connected_platforms(self, telegram_id: str) -> list[str]:
        session = self._session
        if session is None:
            raise RuntimeError("AuthService requires a database session")

        user = await self._ensure_user(telegram_id)

        result = await session.execute(
            select(SocialAccount).where(
                SocialAccount.user_id == user.id,
                SocialAccount.is_active.is_(True),
            )
        )
        accounts = result.scalars().all()

        display_names = []
        for account in accounts:
            try:
                adapter = PlatformRegistry.get(account.platform)
                info = adapter.get_platform_info()
                display_names.append(info.display_name)
            except ValueError:
                display_names.append(account.platform.upper())

        return display_names

    async def get_token_for_platform(self, telegram_id: str, platform: str) -> str | None:
        session = self._session
        if session is None:
            return None

        try:
            user = await self._ensure_user(telegram_id)
        except RuntimeError:
            return None

        result = await session.execute(
            select(SocialAccount).where(
                SocialAccount.user_id == user.id,
                SocialAccount.platform == platform,
                SocialAccount.is_active.is_(True),
            )
        )
        account = result.scalar_one_or_none()
        return account.access_token if account else None
