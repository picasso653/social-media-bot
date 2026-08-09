from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db_session
from src.services.auth_service import AuthService

router = APIRouter()


@router.get("/{platform}/login")
async def start_oauth(
    platform: str,
    telegram_id: int = Query(..., description="Telegram user ID"),
    session: AsyncSession = Depends(get_db_session),
):
    if platform not in ("x", "tiktok", "instagram"):
        raise HTTPException(status_code=400, detail=f"Unknown platform: {platform}")

    auth_service = AuthService(session=session)
    try:
        auth_url = await auth_service.start_oauth(platform, telegram_id)
        return {
            "platform": platform,
            "auth_url": auth_url,
            "message": f"Visit this URL to authorize {platform.upper()}",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{platform}/callback")
async def oauth_callback(
    platform: str,
    code: str = Query(default=""),
    state: str = Query(default=""),
    oauth_token: str = Query(default=""),
    oauth_verifier: str = Query(default=""),
    session: AsyncSession = Depends(get_db_session),
):
    if platform not in ("x", "tiktok", "instagram"):
        raise HTTPException(status_code=400, detail=f"Unknown platform: {platform}")

    effective_code = oauth_verifier or code
    effective_state = oauth_token or state

    if not effective_code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    auth_service = AuthService(session=session)
    try:
        result = await auth_service.complete_oauth(platform, effective_code, effective_state)
        return {
            "platform": platform,
            "status": "connected",
            "display_name": result["display_name"],
            "message": f"Successfully connected to {result['display_name']}. You can close this window.",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
