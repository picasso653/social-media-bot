import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.platforms.instagram_adapter import InstagramAdapter
from src.utils.security import encrypt_token


@pytest.fixture
def instagram_adapter():
    return InstagramAdapter()


@pytest.fixture
def encrypted_token():
    data = json.dumps({
        "access_token": "mock_fb_token",
        "ig_business_id": "123456789",
    })
    return encrypt_token(data)


@pytest.fixture
def encrypted_token_no_ig():
    data = json.dumps({
        "access_token": "mock_fb_token",
        "ig_business_id": None,
    })
    return encrypt_token(data)


class TestInstagramAuth:
    def test_get_auth_url(self, instagram_adapter):
        url = instagram_adapter.get_auth_url("state_ig_1")
        assert "facebook.com" in url
        assert "state=state_ig_1" in url
        assert "instagram_content_publish" in url
        assert "instagram_basic" in url

    @pytest.mark.asyncio
    async def test_authenticate_success(self, instagram_adapter):
        mock_short_token_resp = MagicMock()
        mock_short_token_resp.json.return_value = {"access_token": "short_token"}
        mock_short_token_resp.raise_for_status.return_value = None

        mock_long_token_resp = MagicMock()
        mock_long_token_resp.json.return_value = {"access_token": "long_token_123"}
        mock_long_token_resp.raise_for_status.return_value = None

        mock_pages_resp = MagicMock()
        mock_pages_resp.json.return_value = {"data": [{"id": "page_1", "name": "MyPage"}]}
        mock_pages_resp.raise_for_status.return_value = None

        mock_ig_resp = MagicMock()
        mock_ig_resp.json.return_value = {"instagram_business_account": {"id": "ig_456"}}
        mock_ig_resp.raise_for_status.return_value = None

        mock_profile_resp = MagicMock()
        mock_profile_resp.json.return_value = {"username": "mygram", "name": "My Gram"}
        mock_profile_resp.raise_for_status.return_value = None

        responses = [
            mock_short_token_resp,
            mock_long_token_resp,
            mock_pages_resp,
            mock_ig_resp,
            mock_profile_resp,
        ]

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(side_effect=responses)
            mock_client_class.return_value = mock_client

            result = await instagram_adapter.authenticate("auth_code", "state_1")

        assert "access_token" in result
        assert result["display_name"] == "@mygram"
        assert result["platform_user_id"] == "ig_456"


class TestInstagramPosts:
    @pytest.mark.asyncio
    async def test_post_text_not_supported(self, instagram_adapter):
        result = await instagram_adapter.post_text("any_token", "Hello")
        assert result.success is False
        assert "text-only" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_post_image_success(self, instagram_adapter, encrypted_token):
        mock_container_resp = MagicMock()
        mock_container_resp.json.return_value = {"id": "container_789"}
        mock_container_resp.raise_for_status.return_value = None

        mock_publish_resp = MagicMock()
        mock_publish_resp.json.return_value = {"id": "media_999"}
        mock_publish_resp.raise_for_status.return_value = None

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(side_effect=[mock_container_resp, mock_publish_resp])
            mock_client_class.return_value = mock_client

            result = await instagram_adapter.post_image(encrypted_token, b"fake_jpg", "My insta pic")
            assert result.success is True
            assert result.platform_post_id == "media_999"

    @pytest.mark.asyncio
    async def test_post_image_no_ig_business(self, instagram_adapter, encrypted_token_no_ig):
        result = await instagram_adapter.post_image(encrypted_token_no_ig, b"data", "Cap")
        assert result.success is False
        assert "Instagram Business" in result.error_message

    @pytest.mark.asyncio
    async def test_post_image_invalid_token(self, instagram_adapter):
        result = await instagram_adapter.post_image("bad", b"data", "Cap")
        assert result.success is False
        assert "Invalid token" in result.error_message

    @pytest.mark.asyncio
    async def test_post_image_api_error(self, instagram_adapter, encrypted_token):
        import httpx

        mock_err = MagicMock()
        mock_err.raise_for_status.side_effect = httpx.HTTPStatusError(
            "err", request=MagicMock(), response=MagicMock(status_code=400)
        )

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_err)
            mock_client_class.return_value = mock_client

            result = await instagram_adapter.post_image(encrypted_token, b"data", "Cap")
            assert result.success is False

    @pytest.mark.asyncio
    async def test_post_video_success(self, instagram_adapter, encrypted_token):
        mock_container_resp = MagicMock()
        mock_container_resp.json.return_value = {"id": "reel_container_1"}
        mock_container_resp.raise_for_status.return_value = None

        mock_publish_resp = MagicMock()
        mock_publish_resp.json.return_value = {"id": "reel_123"}
        mock_publish_resp.raise_for_status.return_value = None

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(side_effect=[mock_container_resp, mock_publish_resp])
            mock_client_class.return_value = mock_client

            result = await instagram_adapter.post_video(encrypted_token, b"fake_mp4", "My reel")
            assert result.success is True
            assert result.platform_post_id == "reel_123"

    @pytest.mark.asyncio
    async def test_post_video_no_ig_business(self, instagram_adapter, encrypted_token_no_ig):
        result = await instagram_adapter.post_video(encrypted_token_no_ig, b"data", "Cap")
        assert result.success is False
        assert "Instagram Business" in result.error_message


class TestInstagramRefresh:
    @pytest.mark.asyncio
    async def test_refresh_success(self, instagram_adapter, encrypted_token):
        mock_refresh_resp = MagicMock()
        mock_refresh_resp.json.return_value = {"access_token": "new_long_token"}
        mock_refresh_resp.raise_for_status.return_value = None

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_refresh_resp)
            mock_client_class.return_value = mock_client

            result = await instagram_adapter.refresh_token(encrypted_token)
            assert "access_token" in result


class TestInstagramInfo:
    def test_platform_info(self, instagram_adapter):
        info = instagram_adapter.get_platform_info()
        assert info.name == "instagram"
        assert info.display_name == "Instagram"
        assert info.supports_text is False
        assert info.supports_image is True
        assert info.supports_video is True
        assert info.max_text_length == 2200
        assert info.max_image_count == 10
