import pytest

from src.platforms import register_all_adapters
from src.services.post_service import PostService


@pytest.fixture(autouse=True)
def _register_adapters():
    register_all_adapters()


class TestPostService:
    @pytest.fixture
    def post_service(self):
        return PostService()

    @pytest.mark.asyncio
    async def test_create_text_post(self, post_service):
        result = await post_service.create_post(
            user_id="12345",
            content="Hello world",
            media=None,
            platforms=["x"],
        )
        assert result["status"] == "failed"
        assert result["content_type"] == "text"
        assert "x" in result["platforms"]
        assert result["platform_results"]["x"]["display_name"] == "X (Twitter)"

    @pytest.mark.asyncio
    async def test_create_image_post(self, post_service):
        result = await post_service.create_post(
            user_id="12345",
            content="My photo",
            media=b"fake_image_bytes",
            platforms=["instagram"],
        )
        assert result["content_type"] == "image"
        assert "instagram" in result["platform_results"]

    @pytest.mark.asyncio
    async def test_unsupported_text_on_tiktok(self, post_service):
        result = await post_service.create_post(
            user_id="12345",
            content="Text only post",
            media=None,
            platforms=["tiktok"],
        )
        pr = result["platform_results"]["tiktok"]
        assert pr["success"] is False
        assert "text" in pr["error"].lower()

    @pytest.mark.asyncio
    async def test_unknown_platform_excluded(self, post_service):
        result = await post_service.create_post(
            user_id="12345",
            content="Test",
            platforms=["x", "unknown_platform"],
        )
        assert "unknown_platform" in result["platform_results"]
        assert result["platform_results"]["unknown_platform"]["success"] is False

    @pytest.mark.asyncio
    async def test_no_platforms(self, post_service):
        result = await post_service.create_post(
            user_id="12345",
            content="Test",
            platforms=[],
        )
        assert result["status"] == "no_accounts"

    @pytest.mark.asyncio
    async def test_default_platforms_all(self, post_service):
        result = await post_service.create_post(
            user_id="12345",
            content="Test",
        )
        assert len(result["platforms"]) == 3
        assert "x" in result["platforms"]
        assert "tiktok" in result["platforms"]
        assert "instagram" in result["platforms"]

    @pytest.mark.asyncio
    async def test_get_user_history_empty(self, post_service):
        history = await post_service.get_user_history("12345")
        assert history == []
