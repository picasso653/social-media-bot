from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PostResult:
    success: bool
    platform_post_id: Optional[str] = None
    platform_post_url: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class PlatformInfo:
    name: str
    display_name: str
    supports_text: bool = True
    supports_image: bool = True
    supports_video: bool = False
    max_text_length: int = 5000
    max_image_count: int = 1


class BasePlatformAdapter(ABC):
    @abstractmethod
    async def authenticate(self, code: str, state: str = "") -> dict:
        ...

    @abstractmethod
    async def refresh_token(self, refresh_token: str) -> dict:
        ...

    @abstractmethod
    async def post_text(self, access_token: str, content: str) -> PostResult:
        ...

    @abstractmethod
    async def post_image(self, access_token: str, image_data: bytes, caption: str) -> PostResult:
        ...

    @abstractmethod
    async def post_video(self, access_token: str, video_data: bytes, caption: str) -> PostResult:
        ...

    @abstractmethod
    def get_platform_info(self) -> PlatformInfo:
        ...

    @abstractmethod
    def get_auth_url(self, state: str) -> str:
        ...
