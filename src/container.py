from __future__ import annotations

import asyncio
from contextlib import suppress
from decimal import Decimal

from aiogram import Bot
from redis.asyncio import Redis
from redis.asyncio import from_url
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine

from src.config import Settings
from src.models import Coin


class SubscribersRegistry:
    def __init__(self) -> None:
        self._subs: dict[asyncio.Queue[str], set[Coin]] = {}

    def register(self, queue: asyncio.Queue[str], coins: set[Coin]) -> None:
        self._subs[queue] = coins

    def unregister(self, queue: asyncio.Queue[str]) -> None:
        self._subs.pop(queue, None)

    def fanout(self, message: str, coin: Coin) -> None:
        for queue, coins in list(self._subs.items()):
            if coins and coin not in coins:
                continue
            with suppress(asyncio.QueueFull):
                queue.put_nowait(message)


class AppContainer:
    """Holds long-lived resources. Created in lifespan, no module-level globals."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.engine: AsyncEngine = create_async_engine(
            settings.database_url, pool_pre_ping=True
        )
        self.sessionmaker: async_sessionmaker[AsyncSession] = async_sessionmaker(
            self.engine, expire_on_commit=False
        )
        self.redis: Redis = from_url(settings.redis_url, decode_responses=True)
        self.bot: Bot | None = (
            Bot(token=settings.telegram_bot_token)
            if settings.telegram_bot_token
            else None
        )
        self.subscribers = SubscribersRegistry()
        self.latest_prices: dict[Coin, Decimal] = {}
        self.ws_active_users: set[int] = set()
        self.ws_lock = asyncio.Lock()

    async def aclose(self) -> None:
        if self.bot is not None:
            await self.bot.session.close()
        await self.redis.aclose()
        await self.engine.dispose()


def from_settings(settings: Settings) -> AppContainer:
    return AppContainer(settings)


PRICE_CHANNEL = "prices"
ALERT_CACHE_INVALIDATION_CHANNEL = "alerts:invalidate"


def link_key(code: str) -> str:
    return f"tg:link:{code}"
