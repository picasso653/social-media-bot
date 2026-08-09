from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.platforms import register_all_adapters
from src.platforms.registry import PlatformRegistry
from src.services.auth_service import AuthService


@pytest.fixture(autouse=True)
def _register_adapters():
    register_all_adapters()


@pytest.fixture
def mock_session():
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.close = AsyncMock()
    return session


@pytest.fixture
def auth_service(mock_session):
    return AuthService(session=mock_session)


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


def _mock_user_result(mock_session, telegram_id="12345", user=None):
    mock_result = MagicMock()
    if user:
        mock_result.scalar_one_or_none.return_value = user
    else:

        class FakeResult:
            @staticmethod
            def scalar_one_or_none():
                return None

        mock_result = FakeResult()
    mock_session.execute.return_value = mock_result
    return mock_result


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
    async def test_connect_and_status_flow(self, auth_service, mock_session, mock_x_adapter):
        auth_service._pending_auth["kn_state"] = {"platform": "x", "telegram_id": "12345"}

        fake_user = MagicMock()
        fake_user.id = "user-uuid-1"
        fake_user.telegram_id = 12345

        result_user = MagicMock()
        result_user.scalar_one_or_none.return_value = fake_user

        result_no_existing = MagicMock()
        result_no_existing.scalar_one_or_none.return_value = None

        result_accounts = MagicMock()
        fake_account = MagicMock()
        fake_account.platform = "x"
        fake_account.access_token = "token123"
        result_accounts.scalars.return_value.all.return_value = [fake_account]

        mock_session.execute = AsyncMock(side_effect=[
            result_user,
            result_no_existing,
            result_user,
            result_accounts,
        ])

        with patch.object(PlatformRegistry, "get", return_value=mock_x_adapter):
            result = await auth_service.complete_oauth("x", "code123", "kn_state")
            assert result["platform"] == "x"
            assert result["status"] == "connected"

            platforms = await auth_service.get_connected_platforms("12345")
            assert len(platforms) == 1

    @pytest.mark.asyncio
    async def test_connect_and_disconnect(self, auth_service, mock_session, mock_x_adapter):
        auth_service._pending_auth["kn_state2"] = {"platform": "x", "telegram_id": "12345"}

        fake_user = MagicMock()
        fake_user.id = "user-uuid-2"
        fake_user.telegram_id = 12345

        result_user = MagicMock()
        result_user.scalar_one_or_none.return_value = fake_user

        result_no_existing = MagicMock()
        result_no_existing.scalar_one_or_none.return_value = None

        result_existing = MagicMock()
        fake_account = MagicMock()
        fake_account.platform = "x"
        result_existing.scalar_one_or_none.return_value = fake_account

        mock_session.execute = AsyncMock(side_effect=[
            result_user,
            result_no_existing,
            result_user,
            result_existing,
        ])

        with patch.object(PlatformRegistry, "get", return_value=mock_x_adapter):
            await auth_service.complete_oauth("x", "code456", "kn_state2")
            success = await auth_service.disconnect_platform("12345", "x")
            assert success is True

    @pytest.mark.asyncio
    async def test_empty_status(self, auth_service, mock_session):
        fake_user = MagicMock()
        fake_user.id = "user-uuid-x"
        fake_user.telegram_id = 999

        result_user = MagicMock()
        result_user.scalar_one_or_none.return_value = fake_user

        result_accounts = MagicMock()
        result_accounts.scalars.return_value.all.return_value = []

        mock_session.execute = AsyncMock(side_effect=[result_user, result_accounts])

        platforms = await auth_service.get_connected_platforms("999")
        assert platforms == []
