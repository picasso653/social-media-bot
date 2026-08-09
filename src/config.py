from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SocialMediaBot"
    app_env: str = "development"
    app_debug: bool = True
    secret_key: str = "dev-secret-key-change-in-production"

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/socialmedia"
    redis_url: str = "redis://localhost:6379/0"

    telegram_bot_token: str = ""
    telegram_webhook_url: str = ""

    x_api_key: str = ""
    x_api_key_secret: str = ""
    x_callback_url: str = ""

    tiktok_client_key: str = ""
    tiktok_client_secret: str = ""
    tiktok_callback_url: str = ""

    instagram_app_id: str = ""
    instagram_app_secret: str = ""
    instagram_callback_url: str = ""

    token_encryption_key: str = "xcycI9L5ddn1IHJ91C3AW1ePVrKbOstPZwjH8WCk-yg="

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
