import base64
import hashlib
import json
import logging
import secrets
from urllib.parse import urlencode

import httpx

from src.config import settings
from src.platforms.base import BasePlatformAdapter, PlatformInfo, PostResult
from src.utils.security import decrypt_token, encrypt_token
from src.utils.text_formatter import truncate_text

logger = logging.getLogger(__name__)


class TikTokAdapter(BasePlatformAdapter):
    def __init__(self):
        self.base_url = "https://open.tiktokapis.com/v2"
        self.client_key = settings.tiktok_client_key
        self.client_secret = settings.tiktok_client_secret
        self.redirect_uri = settings.tiktok_callback_url
        self._pending_verifiers: dict[str, str] = {}

    def _generate_pkce(self) -> tuple[str, str]:
        code_verifier = secrets.token_urlsafe(64)[:128]
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode()).digest()
        ).rstrip(b"=").decode()
        return code_verifier, code_challenge

    def _encrypt_tokens(self, tokens: dict) -> str:
        return encrypt_token(json.dumps(tokens))

    def _decrypt_tokens(self, encrypted: str) -> dict:
        return json.loads(decrypt_token(encrypted))

    async def _api_post(self, path: str, access_token: str, body: dict) -> dict:
        url = f"{self.base_url}{path}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            return resp.json()

    async def _api_put_bytes(self, url: str, data: bytes) -> None:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.put(url, content=data)
            resp.raise_for_status()

    def get_auth_url(self, state: str) -> str:
        code_verifier, code_challenge = self._generate_pkce()
        self._pending_verifiers[state] = code_verifier

        params = {
            "client_key": self.client_key,
            "response_type": "code",
            "scope": "user.info.basic,video.publish,video.upload",
            "redirect_uri": self.redirect_uri,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        return f"https://www.tiktok.com/v2/auth/authorize/?{urlencode(params)}"

    async def authenticate(self, code: str, state: str = "") -> dict:
        code_verifier = self._pending_verifiers.pop(state, None)
        if not code_verifier:
            raise ValueError("Invalid or expired PKCE verifier for TikTok OAuth")

        body = {
            "client_key": self.client_key,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "code_verifier": code_verifier,
            "redirect_uri": self.redirect_uri,
        }

        try:
            url = f"{self.base_url}/oauth/token/"
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, data=body)
                resp.raise_for_status()
                token_data = resp.json()
        except httpx.HTTPStatusError as e:
            logger.error("TikTok OAuth token exchange failed: %s", e)
            raise ValueError(f"TikTok OAuth failed: {e}") from e

        encrypted = self._encrypt_tokens(token_data)
        access_token = token_data.get("access_token", "")
        display_name = "TikTok"

        if access_token:
            try:
                user_info = await self._api_post("/user/info/?fields=open_id,display_name", access_token, {})
                user_data = user_info.get("data", {}).get("user", {})
                platform_user_id = user_data.get("open_id", "unknown")
                display_name = user_data.get("display_name", "TikTok")
            except Exception:
                platform_user_id = "unknown"

        return {
            "access_token": encrypted,
            "platform_user_id": platform_user_id,
            "display_name": display_name,
        }

    async def refresh_token(self, refresh_token: str) -> dict:
        tokens = self._decrypt_tokens(refresh_token)
        actual_refresh = tokens.get("refresh_token", "")

        if not actual_refresh:
            return {"access_token": refresh_token, "message": "No refresh token available"}

        body = {
            "client_key": self.client_key,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": actual_refresh,
        }

        try:
            url = f"{self.base_url}/oauth/token/"
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, data=body)
                resp.raise_for_status()
                token_data = resp.json()
        except httpx.HTTPStatusError as e:
            logger.error("TikTok token refresh failed: %s", e)
            return {"access_token": refresh_token, "message": f"Refresh failed: {e}"}

        return {"access_token": self._encrypt_tokens(token_data)}

    async def post_text(self, access_token: str, content: str) -> PostResult:
        return PostResult(
            success=False,
            error_message="TikTok does not support text-only posts. Send a photo or video instead.",
        )

    async def post_image(self, access_token: str, image_data: bytes, caption: str) -> PostResult:
        try:
            tokens = self._decrypt_tokens(access_token)
            access_token = tokens.get("access_token", access_token)
        except Exception as e:
            return PostResult(success=False, error_message=f"Invalid token: {e}")

        truncated_caption = truncate_text(caption.strip() or "New post", 2200)

        init_body = {
            "post_info": {
                "title": truncated_caption,
                "privacy_level": "PUBLIC_TO_EVERYONE",
                "disable_comment": False,
                "disable_duet": False,
                "disable_stitch": False,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "photo_cover_index": 0,
            },
        }

        try:
            init_data = await self._api_post("/post/publish/photo/init/", access_token, init_body)
            data = init_data.get("data", {})
            publish_id = data.get("publish_id", "unknown")

            upload_urls = data.get("upload_urls", [])
            if upload_urls:
                await self._api_put_bytes(upload_urls[0], image_data)

            return PostResult(
                success=True,
                platform_post_id=publish_id,
            )
        except httpx.HTTPStatusError as e:
            logger.error("TikTok photo post failed: %s", e)
            return PostResult(success=False, error_message=str(e))
        except Exception as e:
            logger.error("TikTok photo post failed: %s", e)
            return PostResult(success=False, error_message=str(e))

    async def post_video(self, access_token: str, video_data: bytes, caption: str) -> PostResult:
        try:
            tokens = self._decrypt_tokens(access_token)
            access_token = tokens.get("access_token", access_token)
        except Exception as e:
            return PostResult(success=False, error_message=f"Invalid token: {e}")

        truncated_caption = truncate_text(caption.strip() or "New video", 2200)

        init_body = {
            "post_info": {
                "title": truncated_caption,
                "privacy_level": "PUBLIC_TO_EVERYONE",
                "disable_comment": False,
                "disable_duet": False,
                "disable_stitch": False,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": len(video_data),
            },
        }

        try:
            init_data = await self._api_post("/post/publish/video/init/", access_token, init_body)
            data = init_data.get("data", {})
            publish_id = data.get("publish_id", "unknown")
            upload_url = data.get("upload_url", "")

            if upload_url:
                await self._api_put_bytes(upload_url, video_data)

            return PostResult(
                success=True,
                platform_post_id=publish_id,
            )
        except httpx.HTTPStatusError as e:
            logger.error("TikTok video post failed: %s", e)
            return PostResult(success=False, error_message=str(e))
        except Exception as e:
            logger.error("TikTok video post failed: %s", e)
            return PostResult(success=False, error_message=str(e))

    def get_platform_info(self) -> PlatformInfo:
        return PlatformInfo(
            name="tiktok",
            display_name="TikTok",
            supports_text=False,
            supports_image=True,
            supports_video=True,
            max_text_length=2200,
            max_image_count=35,
        )
