import pytest
from httpx import AsyncClient

from src.config import get_settings


async def _signup(client: AsyncClient, email: str = "a@b.com") -> str:
    await client.post("/auth/register", json={"email": email, "password": "secret123"})
    r = await client.post("/auth/login", json={"email": email, "password": "secret123"})
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_create_list_cancel_alert(client: AsyncClient) -> None:
    token = await _signup(client)
    h = {"Authorization": f"Bearer {token}"}

    r = await client.post(
        "/alerts",
        json={"coin": "BTC", "direction": "above", "threshold": "75000"},
        headers=h,
    )
    assert r.status_code == 201, r.text
    alert_id = r.json()["id"]

    r = await client.get("/alerts?status=active", headers=h)
    assert r.status_code == 200
    assert len(r.json()) == 1

    r = await client.delete(f"/alerts/{alert_id}", headers=h)
    assert r.status_code == 204

    r = await client.get("/alerts?status=active", headers=h)
    assert r.json() == []


@pytest.mark.asyncio
async def test_alert_limit(client: AsyncClient) -> None:
    settings = get_settings()
    settings.max_alerts_per_user = 3
    token = await _signup(client, "limit@x.com")
    h = {"Authorization": f"Bearer {token}"}

    for _ in range(3):
        r = await client.post(
            "/alerts",
            json={"coin": "BTC", "direction": "above", "threshold": "75000"},
            headers=h,
        )
        assert r.status_code == 201

    r = await client.post(
        "/alerts",
        json={"coin": "ETH", "direction": "below", "threshold": "1000"},
        headers=h,
    )
    assert r.status_code == 409
    settings.max_alerts_per_user = 20


@pytest.mark.asyncio
async def test_alert_requires_auth(client: AsyncClient) -> None:
    r = await client.get("/alerts")
    assert r.status_code == 401
