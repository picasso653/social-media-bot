import json
import logging
import uuid

from src.platforms.registry import PlatformRegistry

logger = logging.getLogger(__name__)

VALID_PLATFORMS = {"x", "tiktok", "instagram"}


class AuthService:
    def __init__(self):
        self._pending_auth: dict[str, dict] = {}
        self._connected_accounts: dict[str, list[dict]] = {}

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
            auth_url = adapter.get_auth_url(state)
            return auth_url
        except Exception:
            return f"https://example.com/oauth/{platform}/authorize?state={state}"

    async def complete_oauth(self, platform: str, code: str, state: str) -> dict:
        pending = self._pending_auth.pop(state, None)
        if pending is None:
            raise ValueError("Invalid or expired OAuth state")

        telegram_id = pending["telegram_id"]

        adapter = PlatformRegistry.get(platform)
        result = await adapter.authenticate(code, state)

        info = adapter.get_platform_info()

        self._connected_accounts.setdefault(telegram_id, [])
        existing = [a for a in self._connected_accounts[telegram_id] if a["platform"] == platform]
        for acc in existing:
            self._connected_accounts[telegram_id].remove(acc)

        self._connected_accounts[telegram_id].append({
            "platform": platform,
            "display_name": result.get("display_name", info.display_name),
            "platform_user_id": result.get("platform_user_id", "unknown"),
            "access_token": result.get("access_token", ""),
            "connected_at": "now",
        })

        return {
            "platform": platform,
            "display_name": result.get("display_name", info.display_name),
            "status": "connected",
        }

    async def disconnect_platform(self, telegram_id: str, platform: str) -> bool:
        accounts = self._connected_accounts.get(telegram_id, [])
        self._connected_accounts[telegram_id] = [a for a in accounts if a["platform"] != platform]
        return True

    async def get_connected_platforms(self, telegram_id: str) -> list[str]:
        accounts = self._connected_accounts.get(telegram_id, [])
        return [a["display_name"] for a in accounts]
