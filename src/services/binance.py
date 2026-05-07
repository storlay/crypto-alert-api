from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import UTC
from datetime import datetime
from decimal import Decimal

import websockets
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.container import PRICE_CHANNEL
from src.container import AppContainer
from src.models import Candle1m
from src.models import Coin


logger = logging.getLogger(__name__)

_SYMBOL_TO_COIN = {
    "BTCUSDT": Coin.BTC,
    "ETHUSDT": Coin.ETH,
    "SOLUSDT": Coin.SOL,
    "BNBUSDT": Coin.BNB,
    "XRPUSDT": Coin.XRP,
}


async def _save_candle(container: AppContainer, coin: Coin, k: dict) -> None:
    async with container.sessionmaker() as session:
        stmt = pg_insert(Candle1m).values(
            coin=coin,
            open_time=datetime.fromtimestamp(k["t"] / 1000, tz=UTC),
            open=Decimal(k["o"]),
            high=Decimal(k["h"]),
            low=Decimal(k["l"]),
            close=Decimal(k["c"]),
            volume=Decimal(k["v"]),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["coin", "open_time"],
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
            },
        )
        await session.execute(stmt)
        await session.commit()


async def _handle_kline(container: AppContainer, symbol: str, k: dict) -> None:
    coin = _SYMBOL_TO_COIN.get(symbol.upper())
    if coin is None:
        return
    close = Decimal(k["c"])
    container.latest_prices[coin] = close

    payload = json.dumps(
        {"coin": coin.value, "price": str(close), "ts": int(time.time())}
    )
    await container.redis.publish(PRICE_CHANNEL, payload)

    if k.get("x"):
        try:
            await _save_candle(container, coin, k)
        except Exception:  # noqa: BLE001
            logger.exception("failed to persist candle for %s", coin)


async def run_binance_consumer(container: AppContainer) -> None:
    url = container.settings.binance_ws_url
    backoff = 1.0
    while True:
        try:
            logger.info("binance: connecting %s", url)
            async with websockets.connect(url, ping_interval=20) as ws:
                backoff = 1.0
                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    data = msg.get("data") or msg
                    if data.get("e") != "kline":
                        continue
                    await _handle_kline(container, data["s"], data["k"])
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            logger.exception("binance ws error; reconnect in %.1fs", backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60.0)
