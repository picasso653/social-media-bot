import pytest

from src.platforms import register_all_adapters
from src.platforms.registry import PlatformRegistry
from src.services.telegram_service import extract_platforms_from_text, remove_platform_tags, PLATFORM_TAGS


@pytest.fixture(autouse=True)
def _register_adapters():
    register_all_adapters()


class TestPlatformTagExtraction:
    def test_extract_x_tag(self):
        text = "Hello world #x"
        result = extract_platforms_from_text(text)
        assert "x" in result

    def test_extract_twitter_tag(self):
        text = "Check this out #twitter"
        result = extract_platforms_from_text(text)
        assert "x" in result

    def test_extract_tiktok_tag(self):
        text = "New video #tiktok"
        result = extract_platforms_from_text(text)
        assert "tiktok" in result

    def test_extract_tt_tag(self):
        text = "Dance #tt"
        result = extract_platforms_from_text(text)
        assert "tiktok" in result

    def test_extract_instagram_tag(self):
        text = "Photo #instagram"
        result = extract_platforms_from_text(text)
        assert "instagram" in result

    def test_extract_ig_tag(self):
        text = "Selfie #ig"
        result = extract_platforms_from_text(text)
        assert "instagram" in result

    def test_extract_multiple_tags(self):
        text = "Epic #x #tiktok #ig"
        result = extract_platforms_from_text(text)
        assert sorted(result) == sorted(["x", "tiktok", "instagram"])

    def test_no_tags(self):
        text = "Just a normal post"
        result = extract_platforms_from_text(text)
        assert result == []

    def test_case_insensitive(self):
        text = "Check #X #TikTok #IG"
        result = extract_platforms_from_text(text)
        assert sorted(result) == sorted(["x", "tiktok", "instagram"])

    def test_tag_in_middle_of_word(self):
        result = extract_platforms_from_text("prefix#x")
        assert "x" in result


class TestRemovePlatformTags:
    def test_removes_tags(self):
        text = "Hello #x #ig world"
        result = remove_platform_tags(text)
        assert "#x" not in result
        assert "#ig" not in result
        assert "Hello world" in result

    def test_keeps_regular_text(self):
        text = "Just a caption"
        result = remove_platform_tags(text)
        assert result == "Just a caption"

    def test_removes_case_insensitive(self):
        text = "Hello #X #TT"
        result = remove_platform_tags(text)
        assert "#X" not in result
        assert "#TT" not in result


class TestPlatformRegistry:
    def test_x_is_registered(self):
        assert PlatformRegistry.is_registered("x")

    def test_tiktok_is_registered(self):
        assert PlatformRegistry.is_registered("tiktok")

    def test_instagram_is_registered(self):
        assert PlatformRegistry.is_registered("instagram")

    def test_unknown_platform_raises(self):
        with pytest.raises(ValueError):
            PlatformRegistry.get("linkedin")

    def test_get_names_returns_all(self):
        names = PlatformRegistry.get_names()
        assert "x" in names
        assert "tiktok" in names
        assert "instagram" in names

    def test_get_platform_info(self):
        adapter = PlatformRegistry.get("x")
        info = adapter.get_platform_info()
        assert info.name == "x"
        assert info.display_name == "X (Twitter)"
        assert info.supports_text is True
        assert info.supports_image is True
        assert info.max_text_length == 280

    def test_tiktok_info(self):
        adapter = PlatformRegistry.get("tiktok")
        info = adapter.get_platform_info()
        assert info.supports_text is False
        assert info.supports_video is True

    def test_instagram_info(self):
        adapter = PlatformRegistry.get("instagram")
        info = adapter.get_platform_info()
        assert info.name == "instagram"
        assert info.supports_image is True
