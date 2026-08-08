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
    assert data["version"] == "0.1.0"


@pytest.mark.asyncio
async def test_telegram_webhook_no_token(async_client):
    response = await async_client.post("/api/v1/telegram/webhook", json={"update_id": 1, "message": {"text": "test"}})
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is False
    assert "bot token" in data["message"].lower()


@pytest.mark.asyncio
async def test_webhook_info(async_client):
    response = await async_client.get("/api/v1/telegram/webhook-info")
    assert response.status_code == 200
    data = response.json()
    assert "bot_configured" in data


@pytest.mark.asyncio
async def test_auth_login(async_client):
    response = await async_client.get("/api/v1/auth/x/login?telegram_id=12345")
    assert response.status_code == 200
    data = response.json()
    assert "auth_url" in data


@pytest.mark.asyncio
async def test_create_post_endpoint(async_client):
    response = await async_client.post("/api/v1/posts/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "created"
