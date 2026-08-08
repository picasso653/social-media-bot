from src.platforms.base import BasePlatformAdapter


class PlatformRegistry:
    _adapters: dict[str, BasePlatformAdapter] = {}

    @classmethod
    def register(cls, name: str, adapter: BasePlatformAdapter) -> None:
        cls._adapters[name] = adapter

    @classmethod
    def get(cls, name: str) -> BasePlatformAdapter:
        if name not in cls._adapters:
            raise ValueError(f"Unknown platform: {name}")
        return cls._adapters[name]

    @classmethod
    def get_all(cls) -> dict[str, BasePlatformAdapter]:
        return dict(cls._adapters)

    @classmethod
    def get_names(cls) -> list[str]:
        return list(cls._adapters.keys())

    @classmethod
    def is_registered(cls, name: str) -> bool:
        return name in cls._adapters
