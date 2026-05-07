from __future__ import annotations

import asyncio
import json
import logging
from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from fastapi import WebSocket
from fastapi import WebSocketDisconnect

from src.container import AppContainer
from src.deps import ws_authenticate
from src.deps import ws_container
from src.models import Coin


logger = logging.getLogger(__name__)
router = APIRouter(tags=["ws"])


def _parse_coins(payload: object) -> set[Coin]:
    if not isinstance(payload, dict):
        return set()
    raw = payload.get("subscribe", [])
    if not isinstance(raw, list):
        return set()
    coins: set[Coin] = set()
    for item in raw:
        try:
            coins.add(Coin(item))
        except ValueError:
            continue
    return coins


@router.websocket("/ws/prices")
async def ws_prices(
    websocket: WebSocket,
    container: Annotated[AppContainer, Depends(ws_container)],
    token: str | None = None,
) -> None:
    await websocket.accept()
    user = await ws_authenticate(websocket, container, token)
    if user is None:
        return

    async with container.ws_lock:
        if user.id in container.ws_active_users:
            await websocket.close(code=4409, reason="Already connected")
            return
        container.ws_active_users.add(user.id)

    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=100)
    coins: set[Coin] = set()
    container.subscribers.register(queue, coins)

    try:
        try:
            raw = await asyncio.wait_for(websocket.receive_text(), timeout=10)
            coins.update(_parse_coins(json.loads(raw)))
        except (TimeoutError, json.JSONDecodeError):
            pass

        async def reader() -> None:
            while True:
                raw = await websocket.receive_text()
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                new_coins = _parse_coins(msg)
                if new_coins:
                    coins.clear()
                    coins.update(new_coins)

        async def writer() -> None:
            while True:
                msg = await queue.get()
                await websocket.send_text(msg)

        await asyncio.gather(reader(), writer())
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001
        logger.exception("ws_prices error")
    finally:
        container.subscribers.unregister(queue)
        async with container.ws_lock:
            container.ws_active_users.discard(user.id)
