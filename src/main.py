import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from src.api.dependencies import engine
from src.api.routes import telegram, auth, posts
from src.config import settings
from src.models import Base
from src.platforms import register_all_adapters
from src.services.telegram_service import telegram_service

# ── Logging setup ──────────────────────────────────────────

LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"

logging.basicConfig(
    level=logging.DEBUG if settings.app_debug else logging.INFO,
    format=LOG_FORMAT,
    datefmt=LOG_DATE_FORMAT,
    stream=sys.stdout,
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.INFO)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

logger = logging.getLogger("social-media-bot")

# ── App lifecycle ───────────────────────────────────────────

@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    logger.info("Starting up — registering platform adapters")
    register_all_adapters()

    logger.info("Connecting to database")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables verified")
    except Exception as e:
        logger.critical("Database connection failed: %s", e)
        raise

    if settings.telegram_bot_token and settings.telegram_webhook_url:
        try:
            await telegram_service.set_webhook()
            logger.info("Telegram webhook set to %s", settings.telegram_webhook_url)
        except Exception as e:
            logger.error("Failed to set Telegram webhook: %s", e)

    logger.info("Ready to receive requests")
    yield

    logger.info("Shutting down")
    if telegram_service.application:
        await telegram_service.application.shutdown()
    await engine.dispose()


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


@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.debug("→ %s %s", request.method, request.url.path)
    response = await call_next(request)
    logger.debug("← %s %s → %s", request.method, request.url.path, response.status_code)
    return response


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "0.1.0"}
