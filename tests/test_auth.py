import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_and_login(client: AsyncClient) -> None:
    r = await client.post(
        "/auth/register",
        json={"email": "a@b.com", "password": "secret123"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["email"] == "a@b.com"
    assert body["id"] > 0

    r = await client.post(
        "/auth/login",
        json={"email": "a@b.com", "password": "secret123"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["access_token"]


@pytest.mark.asyncio
async def test_register_duplicate(client: AsyncClient) -> None:
    await client.post(
        "/auth/register", json={"email": "x@y.com", "password": "secret123"}
    )
    r = await client.post(
        "/auth/register", json={"email": "x@y.com", "password": "secret123"}
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient) -> None:
    await client.post(
        "/auth/register", json={"email": "u@v.com", "password": "secret123"}
    )
    r = await client.post(
        "/auth/login", json={"email": "u@v.com", "password": "wrongpass"}
    )
    assert r.status_code == 401
