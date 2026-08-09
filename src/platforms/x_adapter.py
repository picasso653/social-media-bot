import io
import json
import logging
from typing import Optional

import tweepy
from tweepy.errors import TweepyException

from src.config import settings
from src.platforms.base import BasePlatformAdapter, PlatformInfo, PostResult
from src.utils.security import decrypt_token, encrypt_token
from src.utils.text_formatter import truncate_text

logger = logging.getLogger(__name__)


class XAdapter(BasePlatformAdapter):
    def __init__(self):
        self._request_tokens: dict[str, dict] = {}

    def _build_oauth_handler(self, callback_url: str = "") -> tweepy.OAuth1UserHandler:
        handler = tweepy.OAuth1UserHandler(
            settings.x_api_key,
            settings.x_api_key_secret,
            callback=callback_url or settings.x_callback_url,
        )
        return handler

    def _get_client(self, access_token: str, access_token_secret: str) -> tweepy.Client:
        return tweepy.Client(
            consumer_key=settings.x_api_key,
            consumer_secret=settings.x_api_key_secret,
            access_token=access_token,
            access_token_secret=access_token_secret,
        )

    def _get_api_v1(self, access_token: str, access_token_secret: str) -> tweepy.API:
        auth = tweepy.OAuth1UserHandler(
            settings.x_api_key,
            settings.x_api_key_secret,
        )
        auth.set_access_token(access_token, access_token_secret)
        return tweepy.API(auth)

    def _decrypt_tokens(self, encrypted: str) -> tuple[str, str]:
        data = json.loads(decrypt_token(encrypted))
        return data["access_token"], data["access_token_secret"]

    def _encrypt_tokens(self, access_token: str, access_token_secret: str) -> str:
        data = json.dumps({
            "access_token": access_token,
            "access_token_secret": access_token_secret,
        })
        return encrypt_token(data)

    def get_auth_url(self, state: str) -> str:
        handler = self._build_oauth_handler()
        try:
            auth_url = handler.get_authorization_url(signin_with_twitter=True)
        except TweepyException as e:
            logger.error("Failed to get X authorization URL: %s", e)
            raise

        self._request_tokens[handler.request_token["oauth_token"]] = {
            "oauth_token_secret": handler.request_token["oauth_token_secret"],
        }
        return auth_url

    async def authenticate(self, code: str, state: str = "") -> dict:
        request_token_data = self._request_tokens.get(state)
        if not request_token_data:
            raise ValueError("Invalid or expired request token")

        oauth_token_secret = request_token_data["oauth_token_secret"]
        del self._request_tokens[state]

        handler = self._build_oauth_handler()
        handler.request_token = {
            "oauth_token": state,
            "oauth_token_secret": oauth_token_secret,
            "oauth_callback_confirmed": "true",
        }

        try:
            access_token, access_token_secret = handler.get_access_token(code)
        except TweepyException as e:
            logger.error("Failed to get X access token: %s", e)
            raise ValueError(f"Failed to get X access token: {e}") from e

        encrypted = self._encrypt_tokens(access_token, access_token_secret)
        client = self._get_client(access_token, access_token_secret)
        try:
            me = client.get_me()
            platform_user_id = str(me.data.id)
            display_name = f"@{me.data.username}"
        except TweepyException:
            platform_user_id = "unknown"
            display_name = "X (Twitter)"

        return {
            "access_token": encrypted,
            "platform_user_id": platform_user_id,
            "display_name": display_name,
        }

    async def refresh_token(self, refresh_token: str) -> dict:
        return {"access_token": refresh_token, "message": "X OAuth 1.0a tokens do not expire"}

    async def post_text(self, access_token: str, content: str) -> PostResult:
        try:
            at, ats = self._decrypt_tokens(access_token)
        except Exception as e:
            return PostResult(success=False, error_message=f"Invalid token: {e}")

        truncated = truncate_text(content.strip(), 280)

        try:
            client = self._get_client(at, ats)
            response = client.create_tweet(text=truncated)
            tweet_id = str(response.data["id"])
            return PostResult(
                success=True,
                platform_post_id=tweet_id,
                platform_post_url=f"https://x.com/i/status/{tweet_id}",
            )
        except TweepyException as e:
            logger.error("X post_text failed: %s", e)
            return PostResult(success=False, error_message=str(e))

    async def post_image(self, access_token: str, image_data: bytes, caption: str) -> PostResult:
        try:
            at, ats = self._decrypt_tokens(access_token)
        except Exception as e:
            return PostResult(success=False, error_message=f"Invalid token: {e}")

        truncated = truncate_text(caption.strip(), 280) if caption else ""

        try:
            api = self._get_api_v1(at, ats)
            media = api.media_upload(filename="image.jpg", file=io.BytesIO(image_data))
            client = self._get_client(at, ats)
            response = client.create_tweet(text=truncated, media_ids=[media.media_id])
            tweet_id = str(response.data["id"])
            return PostResult(
                success=True,
                platform_post_id=tweet_id,
                platform_post_url=f"https://x.com/i/status/{tweet_id}",
            )
        except TweepyException as e:
            logger.error("X post_image failed: %s", e)
            return PostResult(success=False, error_message=str(e))

    async def post_video(self, access_token: str, video_data: bytes, caption: str) -> PostResult:
        return PostResult(success=False, error_message="Video posting is not supported on X free tier API")

    def get_platform_info(self) -> PlatformInfo:
        return PlatformInfo(
            name="x",
            display_name="X (Twitter)",
            supports_text=True,
            supports_image=True,
            supports_video=False,
            max_text_length=280,
            max_image_count=4,
        )
