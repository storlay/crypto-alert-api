from datetime import UTC
from datetime import datetime
from datetime import timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient

from src.container import AppContainer
from src.models import Candle1m
from src.models import Coin


async def _signup(client: AsyncClient) -> str:
    await client.post(
        "/auth/register", json={"email": "p@p.com", "password": "secret123"}
    )
    r = await client.post(
        "/auth/login", json={"email": "p@p.com", "password": "secret123"}
    )
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_history_returns_recent_candles(
    client: AsyncClient, container: AppContainer
) -> None:
    token = await _signup(client)
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    async with container.sessionmaker() as s:
        for i in range(5):
            s.add(
                Candle1m(
                    coin=Coin.BTC,
                    open_time=now - timedelta(minutes=i),
                    open=Decimal("100"),
                    high=Decimal("110"),
                    low=Decimal("95"),
                    close=Decimal("105"),
                    volume=Decimal("1"),
                )
            )
        await s.commit()

    r = await client.get(
        "/prices/BTC/history?hours=1", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200, r.text
    assert len(r.json()) == 5


@pytest.mark.asyncio
async def test_history_hours_validation(client: AsyncClient) -> None:
    token = await _signup(client)
    r = await client.get(
        "/prices/BTC/history?hours=0",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422
    r = await client.get(
        "/prices/BTC/history?hours=200",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422
