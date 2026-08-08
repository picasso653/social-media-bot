from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import telegram, auth, posts
from src.config import settings
from src.platforms import register_all_adapters
from src.services.telegram_service import telegram_service


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    register_all_adapters()

    if settings.telegram_bot_token and settings.app_env == "development":
        try:
            await telegram_service.set_webhook()
        except Exception:
            pass

    yield

    if telegram_service.application:
        await telegram_service.application.shutdown()


app = FastAPI(
    title="Social Media Bot",
    description="Multi-platform social media posting bot controlled via Telegram",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(telegram.router, prefix="/api/v1/telegram", tags=["Telegram"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(posts.router, prefix="/api/v1/posts", tags=["Posts"])


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "0.1.0"}
