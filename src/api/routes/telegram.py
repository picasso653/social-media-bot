import json

from fastapi import APIRouter, BackgroundTasks, Request

from src.config import settings
from src.services.telegram_service import telegram_service

router = APIRouter()


@router.get("/webhook-info")
async def webhook_info():
    return {
        "webhook_url": settings.telegram_webhook_url,
        "bot_configured": bool(settings.telegram_bot_token),
    }


@router.post("/webhook")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    if not settings.telegram_bot_token:
        return {"ok": False, "message": "Bot token not configured"}

    update_data = await request.json()
    background_tasks.add_task(telegram_service.process_update, update_data)
    return {"ok": True}
