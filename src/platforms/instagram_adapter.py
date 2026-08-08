import json
import logging
from urllib.parse import urlencode

import httpx

from src.config import settings
from src.platforms.base import BasePlatformAdapter, PlatformInfo, PostResult
from src.utils.security import decrypt_token, encrypt_token
from src.utils.text_formatter import truncate_text

logger = logging.getLogger(__name__)

FACEBOOK_GRAPH_URL = "https://graph.facebook.com/v21.0"


class InstagramAdapter(BasePlatformAdapter):
    def __init__(self):
        self.app_id = settings.instagram_app_id
        self.app_secret = settings.instagram_app_secret
        self.redirect_uri = settings.instagram_callback_url

    def _encrypt_tokens(self, tokens: dict) -> str:
        return encrypt_token(json.dumps(tokens))

    def _decrypt_tokens(self, encrypted: str) -> dict:
        return json.loads(decrypt_token(encrypted))

    async def _fb_get(self, path: str, access_token: str, params: dict | None = None) -> dict:
        url = f"{FACEBOOK_GRAPH_URL}/{path}"
        req_params = params or {}
        req_params["access_token"] = access_token
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params=req_params)
            resp.raise_for_status()
            return resp.json()

    async def _fb_post(self, path: str, access_token: str, data: dict) -> dict:
        url = f"{FACEBOOK_GRAPH_URL}/{path}"
        data["access_token"] = access_token
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, data=data)
            resp.raise_for_status()
            return resp.json()

    async def _get_long_lived_token(self, short_lived_token: str) -> dict:
        url = f"{FACEBOOK_GRAPH_URL}/oauth/access_token"
        params = {
            "grant_type": "fb_exchange_token",
            "client_id": self.app_id,
            "client_secret": self.app_secret,
            "fb_exchange_token": short_lived_token,
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()

    async def _get_instagram_business_account(self, page_id: str, access_token: str) -> str | None:
        url = f"{FACEBOOK_GRAPH_URL}/{page_id}"
        params = {"fields": "instagram_business_account", "access_token": access_token}
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
                ig_account = data.get("instagram_business_account", {})
                return ig_account.get("id") if ig_account else None
        except Exception:
            return None

    def get_auth_url(self, state: str) -> str:
        params = {
            "client_id": self.app_id,
            "redirect_uri": self.redirect_uri,
            "scope": "instagram_basic,instagram_content_publish,pages_show_list,pages_read_engagement",
            "response_type": "code",
            "state": state,
        }
        return f"https://www.facebook.com/v21.0/dialog/oauth?{urlencode(params)}"

    async def authenticate(self, code: str, state: str = "") -> dict:
        url = f"{FACEBOOK_GRAPH_URL}/oauth/access_token"
        params = {
            "client_id": self.app_id,
            "client_secret": self.app_secret,
            "redirect_uri": self.redirect_uri,
            "code": code,
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                token_data = resp.json()
            short_token = token_data.get("access_token", "")

            long_lived = await self._get_long_lived_token(short_token)
            long_token = long_lived.get("access_token", short_token)

            pages_data = await self._fb_get("me/accounts", long_token)
            pages = pages_data.get("data", [])

            ig_business_id = None
            for page in pages:
                ig_id = await self._get_instagram_business_account(page["id"], long_token)
                if ig_id:
                    ig_business_id = ig_id
                    break

            token_bundle = {
                "access_token": long_token,
                "ig_business_id": ig_business_id,
            }

            display_name = "Instagram"
            platform_user_id = ig_business_id or "pending_ig_setup"

            if ig_business_id:
                try:
                    info = await self._fb_get(
                        f"{ig_business_id}",
                        long_token,
                        {"fields": "username,name"},
                    )
                    display_name = f"@{info.get('username', 'unknown')}"
                    platform_user_id = ig_business_id
                except Exception:
                    pass

            return {
                "access_token": self._encrypt_tokens(token_bundle),
                "platform_user_id": platform_user_id,
                "display_name": display_name,
            }
        except httpx.HTTPStatusError as e:
            logger.error("Instagram OAuth failed: %s", e)
            raise ValueError(f"Instagram OAuth failed: {e}") from e

    async def refresh_token(self, refresh_token: str) -> dict:
        tokens = self._decrypt_tokens(refresh_token)
        access_token = tokens.get("access_token", "")

        try:
            refreshed = await self._get_long_lived_token(access_token)
            long_token = refreshed.get("access_token", access_token)
            tokens["access_token"] = long_token
            return {"access_token": self._encrypt_tokens(tokens)}
        except Exception as e:
            logger.error("Instagram token refresh failed: %s", e)
            return {"access_token": refresh_token, "message": f"Refresh failed: {e}"}

    async def post_text(self, access_token: str, content: str) -> PostResult:
        return PostResult(
            success=False,
            error_message="Instagram does not support text-only posts. Send a photo or video.",
        )

    async def post_image(self, access_token: str, image_data: bytes, caption: str) -> PostResult:
        try:
            tokens = self._decrypt_tokens(access_token)
            fb_token = tokens.get("access_token", access_token)
            ig_business_id = tokens.get("ig_business_id")
        except Exception as e:
            return PostResult(success=False, error_message=f"Invalid token: {e}")

        if not ig_business_id:
            return PostResult(
                success=False,
                error_message="No Instagram Business Account found. Ensure your Facebook Page has an Instagram Business account linked.",
            )

        truncated_caption = truncate_text(caption.strip() or "New post", 2200)

        image_url = "https://placeholder-image.example.com/uploaded_image.jpg"

        try:
            container_data = await self._fb_post(
                f"{ig_business_id}/media",
                fb_token,
                {
                    "image_url": image_url,
                    "caption": truncated_caption,
                },
            )
            creation_id = container_data.get("id", "")

            publish_data = await self._fb_post(
                f"{ig_business_id}/media_publish",
                fb_token,
                {"creation_id": creation_id},
            )
            return PostResult(
                success=True,
                platform_post_id=publish_data.get("id", creation_id),
            )
        except httpx.HTTPStatusError as e:
            logger.error("Instagram post failed: %s", e)
            return PostResult(success=False, error_message=str(e))
        except Exception as e:
            logger.error("Instagram post failed: %s", e)
            return PostResult(success=False, error_message=str(e))

    async def post_video(self, access_token: str, video_data: bytes, caption: str) -> PostResult:
        try:
            tokens = self._decrypt_tokens(access_token)
            fb_token = tokens.get("access_token", access_token)
            ig_business_id = tokens.get("ig_business_id")
        except Exception as e:
            return PostResult(success=False, error_message=f"Invalid token: {e}")

        if not ig_business_id:
            return PostResult(
                success=False,
                error_message="No Instagram Business Account found.",
            )

        truncated_caption = truncate_text(caption.strip() or "New reel", 2200)

        video_url = "https://placeholder-video.example.com/uploaded_video.mp4"

        try:
            container_data = await self._fb_post(
                f"{ig_business_id}/media",
                fb_token,
                {
                    "media_type": "REELS",
                    "video_url": video_url,
                    "caption": truncated_caption,
                },
            )
            creation_id = container_data.get("id", "")

            publish_data = await self._fb_post(
                f"{ig_business_id}/media_publish",
                fb_token,
                {"creation_id": creation_id},
            )
            return PostResult(
                success=True,
                platform_post_id=publish_data.get("id", creation_id),
            )
        except httpx.HTTPStatusError as e:
            logger.error("Instagram reel post failed: %s", e)
            return PostResult(success=False, error_message=str(e))
        except Exception as e:
            logger.error("Instagram reel post failed: %s", e)
            return PostResult(success=False, error_message=str(e))

    def get_platform_info(self) -> PlatformInfo:
        return PlatformInfo(
            name="instagram",
            display_name="Instagram",
            supports_text=False,
            supports_image=True,
            supports_video=True,
            max_text_length=2200,
            max_image_count=10,
        )
