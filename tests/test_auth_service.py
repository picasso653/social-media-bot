from unittest.mock import MagicMock, patch

import pytest

from src.platforms import register_all_adapters
from src.platforms.registry import PlatformRegistry
from src.services.auth_service import AuthService


@pytest.fixture(autouse=True)
def _register_adapters():
    register_all_adapters()


@pytest.fixture
def auth_service():
    return AuthService()


@pytest.fixture
def mock_x_adapter():
    mock = MagicMock()
    mock.get_auth_url.return_value = "https://api.x.com/oauth/authorize?oauth_token=mock123"
    mock.get_platform_info.return_value = MagicMock(
        name="x",
        display_name="X (Twitter)",
    )

    async def mock_authenticate(code, state):
        return {"access_token": "encrypted_mock_token", "platform_user_id": "999", "display_name": "X (Twitter)"}

    mock.authenticate = mock_authenticate
    return mock


class TestAuthService:
    @pytest.mark.asyncio
    async def test_start_oauth_valid_platform(self, auth_service, mock_x_adapter):
        with patch.object(PlatformRegistry, "get", return_value=mock_x_adapter):
            url = await auth_service.start_oauth("x", 12345)
        assert url != ""
        assert "oauth" in url

    @pytest.mark.asyncio
    async def test_start_oauth_invalid_platform(self, auth_service):
        with pytest.raises(ValueError):
            await auth_service.start_oauth("linkedin", 12345)

    @pytest.mark.asyncio
    async def test_complete_oauth_invalid_state(self, auth_service, mock_x_adapter):
        with patch.object(PlatformRegistry, "get", return_value=mock_x_adapter):
            with pytest.raises(ValueError, match="Invalid or expired OAuth state"):
                await auth_service.complete_oauth("x", "code123", "bad_state")

    @pytest.mark.asyncio
    async def test_connect_and_status_flow(self, auth_service, mock_x_adapter):
        auth_service._pending_auth["known_state_123"] = {
            "platform": "x",
            "telegram_id": "12345",
        }
        with patch.object(PlatformRegistry, "get", return_value=mock_x_adapter):
            result = await auth_service.complete_oauth("x", "code123", "known_state_123")

        assert result["platform"] == "x"
        assert result["status"] == "connected"

        platforms = await auth_service.get_connected_platforms("12345")
        assert len(platforms) == 1
        assert "X (Twitter)" in platforms

    @pytest.mark.asyncio
    async def test_disconnect(self, auth_service, mock_x_adapter):
        auth_service._pending_auth["known_state_456"] = {
            "platform": "x",
            "telegram_id": "12345",
        }
        with patch.object(PlatformRegistry, "get", return_value=mock_x_adapter):
            await auth_service.complete_oauth("x", "code456", "known_state_456")

        success = await auth_service.disconnect_platform("12345", "x")
        assert success is True
        platforms = await auth_service.get_connected_platforms("12345")
        assert len(platforms) == 0

    @pytest.mark.asyncio
    async def test_multiple_platforms(self, auth_service, mock_x_adapter):
        tiktok_mock = MagicMock()
        tiktok_mock.get_auth_url.return_value = "https://tiktok.com/auth?state=tok123"
        tiktok_mock.get_platform_info.return_value = MagicMock(name="tiktok", display_name="TikTok")

        async def tiktok_auth(code, state):
            return {"access_token": "tok", "platform_user_id": "1", "display_name": "TikTok"}

        tiktok_mock.authenticate = tiktok_auth

        auth_service._pending_auth["x_state"] = {"platform": "x", "telegram_id": "12345"}
        auth_service._pending_auth["tt_state"] = {"platform": "tiktok", "telegram_id": "12345"}

        with patch.object(PlatformRegistry, "get", side_effect=lambda p: mock_x_adapter if p == "x" else tiktok_mock):
            await auth_service.complete_oauth("x", "code1", "x_state")
            await auth_service.complete_oauth("tiktok", "code2", "tt_state")

        platforms = await auth_service.get_connected_platforms("12345")
        assert len(platforms) == 2

    @pytest.mark.asyncio
    async def test_empty_status(self, auth_service):
        platforms = await auth_service.get_connected_platforms("unknown_user")
        assert platforms == []
