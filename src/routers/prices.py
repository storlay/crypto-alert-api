from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Query
from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.deps import current_user
from src.deps import get_session
from src.limits import limiter
from src.models import Candle1m
from src.models import Coin
from src.models import User
from src.schemas import CandleOut


router = APIRouter(prefix="/prices", tags=["prices"])


@router.get("/{coin}/history", response_model=list[CandleOut])
@limiter.limit("60/minute")
async def history(
    request: Request,
    coin: Coin,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    hours: Annotated[int, Query(ge=1, le=168)] = 24,
) -> list[CandleOut]:
    since = datetime.now(UTC) - timedelta(hours=hours)
    stmt = (
        select(Candle1m)
        .where(Candle1m.coin == coin, Candle1m.open_time >= since)
        .order_by(Candle1m.open_time.asc())
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [
        CandleOut(time=r.open_time, open=r.open, high=r.high, low=r.low, close=r.close)
        for r in rows
    ]
