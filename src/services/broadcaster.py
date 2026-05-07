from __future__ import annotations

import asyncio
import json
import logging

from src.container import PRICE_CHANNEL
from src.container import AppContainer
from src.models import Coin


logger = logging.getLogger(__name__)


async def _broadcast_once(container: AppContainer) -> None:
    pubsub = container.redis.pubsub()
    await pubsub.subscribe(PRICE_CHANNEL)
    logger.info("broadcaster: subscribed to %s", PRICE_CHANNEL)
    try:
        async for raw in pubsub.listen():
            if raw.get("type") != "message":
                continue
            try:
                payload = json.loads(raw["data"])
                coin = Coin(payload["coin"])
            except (KeyError, ValueError, json.JSONDecodeError):
                continue
            container.subscribers.fanout(raw["data"], coin)
    finally:
        await pubsub.unsubscribe(PRICE_CHANNEL)
        await pubsub.aclose()


async def run_broadcaster(container: AppContainer) -> None:
    backoff = 1.0
    while True:
        try:
            await _broadcast_once(container)
            backoff = 1.0
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            logger.exception("broadcaster crashed; reconnect in %.1fs", backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60.0)
