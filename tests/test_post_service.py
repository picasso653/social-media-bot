from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.platforms import register_all_adapters
from src.services.auth_service import AuthService
from src.services.post_service import PostService


@pytest.fixture(autouse=True)
def _register_adapters():
    register_all_adapters()


class TestPostService:
    @pytest.fixture
    def post_service(self):
        auth_svc = MagicMock(spec=AuthService)
        auth_svc.get_token_for_platform = AsyncMock(return_value=None)
        return PostService(auth_service=auth_svc)

    @pytest.mark.asyncio
    async def test_create_text_post_no_token(self, post_service):
        result = await post_service.create_post(user_id="12345", content="Hello", platforms=["x"])
        assert result["status"] == "failed"
        assert "x" in result["platform_results"]
        assert not result["platform_results"]["x"]["success"]
        assert "not connected" in result["platform_results"]["x"]["error"].lower()

    @pytest.mark.asyncio
    async def test_create_image_post(self, post_service):
        result = await post_service.create_post(user_id="12345", content="Test", media=b"fake", platforms=["instagram"])
        assert result["content_type"] == "image"
        assert "instagram" in result["platform_results"]

    @pytest.mark.asyncio
    async def test_unsupported_text_on_tiktok(self, post_service):
        result = await post_service.create_post(user_id="12345", content="Text only", platforms=["tiktok"])
        pr = result["platform_results"]["tiktok"]
        assert pr["success"] is False

    @pytest.mark.asyncio
    async def test_unknown_platform(self, post_service):
        result = await post_service.create_post(user_id="12345", content="Test", platforms=["unknown_platform"])
        assert "unknown_platform" in result["platform_results"]
        assert not result["platform_results"]["unknown_platform"]["success"]

    @pytest.mark.asyncio
    async def test_no_platforms(self, post_service):
        result = await post_service.create_post(user_id="12345", content="Test", platforms=[])
        assert result["status"] == "no_accounts"

    @pytest.mark.asyncio
    async def test_default_to_all_platforms(self, post_service):
        result = await post_service.create_post(user_id="12345", content="Test")
        assert len(result["platforms"]) == 3

    @pytest.mark.asyncio
    async def test_get_user_history_empty(self, post_service):
        history = await post_service.get_user_history("12345")
        assert history == []
