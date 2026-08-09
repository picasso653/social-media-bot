import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_health_check(async_client):
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_telegram_webhook_no_token(async_client):
    response = await async_client.post("/api/v1/telegram/webhook", json={"update_id": 1})
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is False


@pytest.mark.asyncio
async def test_webhook_info(async_client):
    response = await async_client.get("/api/v1/telegram/webhook-info")
    assert response.status_code == 200
    data = response.json()
    assert "bot_configured" in data
