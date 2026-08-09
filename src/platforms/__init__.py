from src.platforms.registry import PlatformRegistry
from src.platforms.x_adapter import XAdapter
from src.platforms.tiktok_adapter import TikTokAdapter
from src.platforms.instagram_adapter import InstagramAdapter


def register_all_adapters() -> None:
    PlatformRegistry.register("x", XAdapter())
    PlatformRegistry.register("tiktok", TikTokAdapter())
    PlatformRegistry.register("instagram", InstagramAdapter())
