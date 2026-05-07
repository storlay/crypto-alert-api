from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from datetime import UTC
from datetime import datetime
from decimal import Decimal

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.container import ALERT_CACHE_INVALIDATION_CHANNEL
from src.container import PRICE_CHANNEL
from src.container import AppContainer
from src.models import Alert
from src.models import AlertStatus
from src.models import Coin
from src.models import Direction
from src.models import User


logger = logging.getLogger(__name__)


class AlertCache:
    def __init__(self, container: AppContainer) -> None:
        self._container = container
        self._lock = asyncio.Lock()
        self._loaded: set[Coin] = set()
        self._cache: dict[Coin, list[Alert]] = defaultdict(list)

    async def _load(self, coin: Coin) -> list[Alert]:
        async with self._container.sessionmaker() as session:
            stmt = (
                select(Alert)
                .where(Alert.coin == coin, Alert.status == AlertStatus.active)
                .options(selectinload(Alert.user))
            )
            return list((await session.execute(stmt)).scalars().all())

    async def get(self, coin: Coin) -> list[Alert]:
        async with self._lock:
            if coin not in self._loaded:
                self._cache[coin] = await self._load(coin)
                self._loaded.add(coin)
            return list(self._cache[coin])

    async def invalidate(self, coin: Coin) -> None:
        async with self._lock:
            self._loaded.discard(coin)
            self._cache.pop(coin, None)


def _format_message(alert: Alert, price: Decimal) -> str:
    op = ">" if alert.direction == Direction.above else "<"
    created = alert.created_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")
    return (
        f"{alert.coin.value} достиг {price} USDT\n"
        f"Условие: {alert.coin.value} {op} {alert.threshold}\n"
        f"Создан: {created}"
    )


async def _send_telegram(bot: Bot | None, chat_id: int, text: str) -> None:
    if bot is None:
        logger.warning("telegram bot not configured; skipping send to %s", chat_id)
        return
    try:
        await bot.send_message(chat_id, text)
    except TelegramAPIError:
        logger.exception("telegram send failed for %s", chat_id)


async def _trigger(container: AppContainer, alert_id: int, price: Decimal) -> None:
    async with container.sessionmaker() as session:
        alert = await session.get(Alert, alert_id, options=[selectinload(Alert.user)])
        if alert is None or alert.status != AlertStatus.active:
            return
        alert.status = AlertStatus.triggered
        alert.triggered_at = datetime.now(UTC)
        alert.triggered_price = price
        await session.commit()
        user: User = alert.user
        message = _format_message(alert, price)

    if user.telegram_chat_id:
        await _send_telegram(container.bot, user.telegram_chat_id, message)


def _matched(alert: Alert, price: Decimal) -> bool:
    if alert.direction == Direction.above:
        return price >= alert.threshold
    return price <= alert.threshold


async def _process_price(
    container: AppContainer, cache: AlertCache, coin: Coin, price: Decimal
) -> None:
    alerts = await cache.get(coin)
    triggered_ids = [a.id for a in alerts if _matched(a, price)]
    if not triggered_ids:
        return
    await cache.invalidate(coin)
    for alert_id in triggered_ids:
        try:
            await _trigger(container, alert_id, price)
        except Exception:  # noqa: BLE001
            logger.exception("trigger failed for alert %s", alert_id)


async def _check_once(container: AppContainer, cache: AlertCache) -> None:
    pubsub = container.redis.pubsub()
    await pubsub.subscribe(PRICE_CHANNEL, ALERT_CACHE_INVALIDATION_CHANNEL)
    logger.info("alert_checker: subscribed")
    try:
        async for raw in pubsub.listen():
            if raw.get("type") != "message":
                continue
            channel = raw["channel"]
            data = raw["data"]
            if channel == ALERT_CACHE_INVALIDATION_CHANNEL:
                try:
                    await cache.invalidate(Coin(data))
                except ValueError:
                    pass
                continue
            try:
                payload = json.loads(data)
                coin = Coin(payload["coin"])
                price = Decimal(payload["price"])
            except (KeyError, ValueError, json.JSONDecodeError):
                continue
            try:
                await _process_price(container, cache, coin, price)
            except Exception:  # noqa: BLE001
                logger.exception("alert checker failure")
    finally:
        await pubsub.unsubscribe()
        await pubsub.aclose()


async def run_alert_checker(container: AppContainer) -> None:
    cache = AlertCache(container)
    backoff = 1.0
    while True:
        try:
            await _check_once(container, cache)
            backoff = 1.0
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            logger.exception("alert_checker crashed; reconnect in %.1fs", backoff)
            # cache may be stale after disconnect; clear it
            for coin in list(Coin):
                await cache.invalidate(coin)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60.0)
