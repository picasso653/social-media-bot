import json
import pytest
from unittest.mock import MagicMock, patch

from src.platforms.x_adapter import XAdapter
from src.utils.security import encrypt_token


@pytest.fixture
def x_adapter():
    return XAdapter()


@pytest.fixture
def encrypted_token():
    data = json.dumps({"access_token": "test_at", "access_token_secret": "test_ats"})
    return encrypt_token(data)


class TestXAdapterAuth:
    def test_get_auth_url_returns_url(self, x_adapter):
        with patch("tweepy.OAuth1UserHandler") as mock_handler_class:
            mock_handler = MagicMock()
            mock_handler.get_authorization_url.return_value = "https://api.x.com/oauth/authorize?oauth_token=abc"
            mock_handler.request_token = {"oauth_token": "abc", "oauth_token_secret": "secret"}
            mock_handler_class.return_value = mock_handler

            url = x_adapter.get_auth_url("state123")
            assert "oauth_token=abc" in url
            assert "abc" in x_adapter._request_tokens
            assert x_adapter._request_tokens["abc"]["oauth_token_secret"] == "secret"

    def test_get_auth_url_stores_request_token(self, x_adapter):
        with patch("tweepy.OAuth1UserHandler") as mock_handler_class:
            mock_handler = MagicMock()
            mock_handler.get_authorization_url.return_value = "https://api.x.com/oauth/authorize?oauth_token=xyz"
            mock_handler.request_token = {"oauth_token": "xyz", "oauth_token_secret": "supersecret"}
            mock_handler_class.return_value = mock_handler

            x_adapter.get_auth_url("state456")
            assert "xyz" in x_adapter._request_tokens

    @pytest.mark.asyncio
    async def test_authenticate_valid_flow(self, x_adapter):
        x_adapter._request_tokens["token123"] = {"oauth_token_secret": "tmp_secret"}

        with patch("tweepy.OAuth1UserHandler") as mock_handler_class:
            mock_handler = MagicMock()
            mock_handler.get_access_token.return_value = ("final_at", "final_ats")
            mock_handler_class.return_value = mock_handler

            with patch.object(x_adapter, "_get_client") as mock_get_client:
                mock_client = MagicMock()
                mock_me = MagicMock()
                mock_me.data.id = "12345"
                mock_me.data.username = "testuser"
                mock_client.get_me.return_value = mock_me
                mock_get_client.return_value = mock_client

                result = await x_adapter.authenticate("verifier123", "token123")

                assert "access_token" in result
                assert result["platform_user_id"] == "12345"
                assert result["display_name"] == "@testuser"
                assert "token123" not in x_adapter._request_tokens

    @pytest.mark.asyncio
    async def test_authenticate_invalid_token(self, x_adapter):
        with pytest.raises(ValueError, match="Invalid or expired request token"):
            await x_adapter.authenticate("code", "nonexistent")


class TestXAdapterPostText:
    @pytest.mark.asyncio
    async def test_post_text_success(self, x_adapter, encrypted_token):
        with patch.object(x_adapter, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.create_tweet.return_value = MagicMock(
                data={"id": "55555", "text": "Hello"}
            )
            mock_get_client.return_value = mock_client

            result = await x_adapter.post_text(encrypted_token, "Hello world")
            assert result.success is True
            assert result.platform_post_id == "55555"
            assert "x.com" in result.platform_post_url

    @pytest.mark.asyncio
    async def test_post_text_truncates_280(self, x_adapter, encrypted_token):
        with patch.object(x_adapter, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.create_tweet.return_value = MagicMock(data={"id": "1"})
            mock_get_client.return_value = mock_client

            long_text = "A" * 300
            await x_adapter.post_text(encrypted_token, long_text)
            call_args = mock_client.create_tweet.call_args
            assert len(call_args.kwargs["text"]) <= 280

    @pytest.mark.asyncio
    async def test_post_text_invalid_token(self, x_adapter):
        result = await x_adapter.post_text("invalid_token", "Hello")
        assert result.success is False
        assert "Invalid token" in result.error_message

    @pytest.mark.asyncio
    async def test_post_text_api_error(self, x_adapter, encrypted_token):
        with patch.object(x_adapter, "_get_client") as mock_get_client:
            from tweepy.errors import TweepyException
            mock_client = MagicMock()
            mock_client.create_tweet.side_effect = TweepyException("Rate limit exceeded")
            mock_get_client.return_value = mock_client

            result = await x_adapter.post_text(encrypted_token, "Hello")
            assert result.success is False
            assert "Rate limit exceeded" in result.error_message


class TestXAdapterPostImage:
    @pytest.mark.asyncio
    async def test_post_image_success(self, x_adapter, encrypted_token):
        with patch.object(x_adapter, "_get_api_v1") as mock_get_api:
            mock_api = MagicMock()
            mock_media = MagicMock()
            mock_media.media_id = 999
            mock_api.media_upload.return_value = mock_media
            mock_get_api.return_value = mock_api

            with patch.object(x_adapter, "_get_client") as mock_get_client:
                mock_client = MagicMock()
                mock_client.create_tweet.return_value = MagicMock(data={"id": "777"})
                mock_get_client.return_value = mock_client

                result = await x_adapter.post_image(encrypted_token, b"fake_jpeg", "My photo")
                assert result.success is True
                assert result.platform_post_id == "777"

    @pytest.mark.asyncio
    async def test_post_image_api_error(self, x_adapter, encrypted_token):
        with patch.object(x_adapter, "_get_api_v1") as mock_get_api:
            from tweepy.errors import TweepyException
            mock_api = MagicMock()
            mock_api.media_upload.side_effect = TweepyException("Media too large")
            mock_get_api.return_value = mock_api

            result = await x_adapter.post_image(encrypted_token, b"fake_jpeg", "Photo")
            assert result.success is False

    @pytest.mark.asyncio
    async def test_post_image_invalid_token(self, x_adapter):
        result = await x_adapter.post_image("bad_token", b"data", "Caption")
        assert result.success is False


class TestXAdapterVideo:
    @pytest.mark.asyncio
    async def test_post_video_not_supported(self, x_adapter):
        result = await x_adapter.post_video("token", b"video", "Caption")
        assert result.success is False
        assert "not supported" in result.error_message.lower()


class TestXAdapterInfo:
    def test_platform_info(self, x_adapter):
        info = x_adapter.get_platform_info()
        assert info.name == "x"
        assert info.display_name == "X (Twitter)"
        assert info.supports_text is True
        assert info.supports_image is True
        assert info.supports_video is False
        assert info.max_text_length == 280
        assert info.max_image_count == 4


class TestXAdapterRefreshToken:
    @pytest.mark.asyncio
    async def test_refresh_noop(self, x_adapter):
        result = await x_adapter.refresh_token("any_token")
        assert "do not expire" in result["message"]
