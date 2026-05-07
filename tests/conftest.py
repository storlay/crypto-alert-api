from __future__ import annotations

from collections.abc import AsyncIterator
from collections.abc import Iterator

import pytest
import pytest_asyncio
from httpx import ASGITransport
from httpx import AsyncClient
from sqlalchemy import text
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

from src.config import get_settings
from src.container import AppContainer
from src.db import Base


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg.get_connection_url().replace(
            "postgresql+psycopg2", "postgresql+asyncpg"
        )


@pytest.fixture(scope="session")
def redis_url() -> Iterator[str]:
    with RedisContainer("redis:7-alpine") as r:
        host = r.get_container_host_ip()
        port = r.get_exposed_port(6379)
        yield f"redis://{host}:{port}/0"


@pytest_asyncio.fixture(scope="session")
async def container(postgres_url: str, redis_url: str) -> AsyncIterator[AppContainer]:
    settings = get_settings()
    settings.database_url = postgres_url
    settings.redis_url = redis_url
    settings.telegram_bot_token = None
    ctx = AppContainer(settings)
    async with ctx.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield ctx
    await ctx.aclose()


@pytest_asyncio.fixture
async def clean_state(container: AppContainer) -> AsyncIterator[None]:
    async with container.engine.begin() as conn:
        await conn.execute(
            text("TRUNCATE alerts, users, candles_1m RESTART IDENTITY CASCADE")
        )
    await container.redis.flushdb()
    yield


@pytest_asyncio.fixture
async def client(
    container: AppContainer, clean_state: None
) -> AsyncIterator[AsyncClient]:
    from fastapi import FastAPI

    from src.limits import limiter
    from src.routers import alerts
    from src.routers import auth
    from src.routers import me
    from src.routers import prices

    app = FastAPI()
    app.state.limiter = limiter  # type: ignore[attr-defined]
    app.state.container = container  # type: ignore[attr-defined]
    app.include_router(auth.router)
    app.include_router(me.router)
    app.include_router(alerts.router)
    app.include_router(prices.router)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
