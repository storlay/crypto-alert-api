import pytest
from httpx import AsyncClient

from src.container import AppContainer
from src.container import link_key


async def _signup(client: AsyncClient) -> str:
    await client.post(
        "/auth/register", json={"email": "m@m.com", "password": "secret123"}
    )
    r = await client.post(
        "/auth/login", json={"email": "m@m.com", "password": "secret123"}
    )
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_link_telegram_via_code(
    client: AsyncClient, container: AppContainer
) -> None:
    token = await _signup(client)
    await container.redis.set(link_key("CODE-1"), "12345", ex=600)

    r = await client.patch(
        "/me",
        json={"link_code": "CODE-1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    assert await container.redis.get(link_key("CODE-1")) is None


@pytest.mark.asyncio
async def test_link_invalid_code(client: AsyncClient) -> None:
    token = await _signup(client)
    r = await client.patch(
        "/me",
        json={"link_code": "BOGUS"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 400
