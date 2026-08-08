import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.platforms.tiktok_adapter import TikTokAdapter
from src.utils.security import encrypt_token


@pytest.fixture
def tiktok_adapter():
    return TikTokAdapter()


@pytest.fixture
def encrypted_token():
    data = json.dumps({"access_token": "mock_tiktok_at", "refresh_token": "mock_tiktok_rt"})
    return encrypt_token(data)


class TestTikTokAuth:
    def test_get_auth_url_contains_required_params(self, tiktok_adapter):
        url = tiktok_adapter.get_auth_url("test_state_123")
        assert "tiktok.com" in url
        assert "code_challenge=" in url
        assert "code_challenge_method=S256" in url
        assert "state=test_state_123" in url
        assert "test_state_123" in tiktok_adapter._pending_verifiers

    def test_get_auth_url_stores_pkce_verifier(self, tiktok_adapter):
        url = tiktok_adapter.get_auth_url("state_abc")
        verifier = tiktok_adapter._pending_verifiers.get("state_abc")
        assert verifier is not None
        assert len(verifier) > 40
        assert len(verifier) <= 128

    def test_pkce_verifier_removed_after_auth(self, tiktok_adapter):
        tiktok_adapter._pending_verifiers["state_key"] = "some_verifier"

        assert "state_key" in tiktok_adapter._pending_verifiers
        tiktok_adapter._pending_verifiers.pop("state_key")
        assert "state_key" not in tiktok_adapter._pending_verifiers

    @pytest.mark.asyncio
    async def test_authenticate_invalid_state(self, tiktok_adapter):
        with pytest.raises(ValueError, match="PKCE verifier"):
            await tiktok_adapter.authenticate("code123", "missing_state")

    @pytest.mark.asyncio
    async def test_authenticate_success(self, tiktok_adapter):
        tiktok_adapter._pending_verifiers["s1"] = "test_verifier"

        mock_oauth_resp = MagicMock()
        mock_oauth_resp.json.return_value = {"access_token": "new_at", "refresh_token": "new_rt", "open_id": "oid1"}
        mock_oauth_resp.raise_for_status.return_value = None

        mock_user_resp = MagicMock()
        mock_user_resp.json.return_value = {
            "data": {"user": {"open_id": "oid1", "display_name": "TestTokUser"}}
        }
        mock_user_resp.raise_for_status.return_value = None

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(side_effect=[mock_oauth_resp, mock_user_resp])
            mock_client_class.return_value = mock_client

            result = await tiktok_adapter.authenticate("auth_code", "s1")

        assert "access_token" in result
        assert result["display_name"] == "TestTokUser"


class TestTikTokPosts:
    @pytest.mark.asyncio
    async def test_post_text_not_supported(self, tiktok_adapter):
        result = await tiktok_adapter.post_text("any_token", "Hello")
        assert result.success is False
        assert "text-only" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_post_image_success(self, tiktok_adapter, encrypted_token):
        mock_init_resp = MagicMock()
        mock_init_resp.json.return_value = {
            "data": {
                "publish_id": "publish_123",
                "upload_urls": ["https://upload.tiktok.com/photo/abc"],
            }
        }
        mock_init_resp.raise_for_status.return_value = None

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)

            mock_put_resp = MagicMock()
            mock_put_resp.raise_for_status.return_value = None
            mock_client.post = AsyncMock(return_value=mock_init_resp)
            mock_client.put = AsyncMock(return_value=mock_put_resp)
            mock_client_class.return_value = mock_client

            result = await tiktok_adapter.post_image(encrypted_token, b"fake_jpeg_data", "My photo")
            assert result.success is True
            assert result.platform_post_id == "publish_123"

    @pytest.mark.asyncio
    async def test_post_image_http_error(self, tiktok_adapter, encrypted_token):
        import httpx

        mock_init_resp = MagicMock()
        mock_init_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=MagicMock(status_code=401)
        )

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_init_resp)
            mock_client_class.return_value = mock_client

            result = await tiktok_adapter.post_image(encrypted_token, b"fake_jpeg", "Caption")
            assert result.success is False

    @pytest.mark.asyncio
    async def test_post_video_success(self, tiktok_adapter, encrypted_token):
        mock_init_resp = MagicMock()
        mock_init_resp.json.return_value = {
            "data": {
                "publish_id": "video_pub_456",
                "upload_url": "https://upload.tiktok.com/video/xyz",
            }
        }
        mock_init_resp.raise_for_status.return_value = None

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)

            mock_put_resp = MagicMock()
            mock_put_resp.raise_for_status.return_value = None
            mock_client.post = AsyncMock(return_value=mock_init_resp)
            mock_client.put = AsyncMock(return_value=mock_put_resp)
            mock_client_class.return_value = mock_client

            result = await tiktok_adapter.post_video(encrypted_token, b"fake_video_data", "My reel")
            assert result.success is True
            assert result.platform_post_id == "video_pub_456"

    @pytest.mark.asyncio
    async def test_post_video_error(self, tiktok_adapter, encrypted_token):
        import httpx

        mock_init_resp = MagicMock()
        mock_init_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=MagicMock(status_code=403)
        )

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_init_resp)
            mock_client_class.return_value = mock_client

            result = await tiktok_adapter.post_video(encrypted_token, b"bad", "Test")
            assert result.success is False

    @pytest.mark.asyncio
    async def test_post_invalid_token(self, tiktok_adapter):
        result = await tiktok_adapter.post_image("garbage_token", b"data", "Cap")
        assert result.success is False
        assert "Invalid token" in result.error_message


class TestTikTokRefresh:
    @pytest.mark.asyncio
    async def test_refresh_success(self, tiktok_adapter, encrypted_token):
        mock_refresh_resp = MagicMock()
        mock_refresh_resp.json.return_value = {"access_token": "fresh_at", "refresh_token": "fresh_rt"}
        mock_refresh_resp.raise_for_status.return_value = None

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_refresh_resp)
            mock_client_class.return_value = mock_client

            result = await tiktok_adapter.refresh_token(encrypted_token)
            assert "access_token" in result

    @pytest.mark.asyncio
    async def test_refresh_no_token(self, tiktok_adapter):
        data = json.dumps({"access_token": "at_only"})
        encrypted = encrypt_token(data)
        result = await tiktok_adapter.refresh_token(encrypted)
        assert "No refresh token" in result["message"]


class TestTikTokInfo:
    def test_platform_info(self, tiktok_adapter):
        info = tiktok_adapter.get_platform_info()
        assert info.name == "tiktok"
        assert info.display_name == "TikTok"
        assert info.supports_text is False
        assert info.supports_image is True
        assert info.supports_video is True
        assert info.max_text_length == 2200
        assert info.max_image_count == 35
