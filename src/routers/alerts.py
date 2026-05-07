from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from fastapi import Request
from fastapi import status
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.container import ALERT_CACHE_INVALIDATION_CHANNEL
from src.container import AppContainer
from src.deps import current_user
from src.deps import get_container
from src.deps import get_session
from src.limits import limiter
from src.models import Alert
from src.models import AlertStatus
from src.models import User
from src.schemas import AlertIn
from src.schemas import AlertOut


router = APIRouter(prefix="/alerts", tags=["alerts"])


async def _invalidate(container: AppContainer, coin: str) -> None:
    await container.redis.publish(ALERT_CACHE_INVALIDATION_CHANNEL, coin)


@router.post("", response_model=AlertOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("60/minute")
async def create_alert(
    request: Request,
    payload: AlertIn,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    container: Annotated[AppContainer, Depends(get_container)],
) -> Alert:
    limit = container.settings.max_alerts_per_user
    # serialize concurrent inserts per user to keep the limit honest
    await session.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": user.id})
    active_count = await session.scalar(
        select(func.count(Alert.id)).where(
            Alert.user_id == user.id, Alert.status == AlertStatus.active
        )
    )
    if (active_count or 0) >= limit:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Active alerts limit reached ({limit})",
        )

    alert = Alert(
        user_id=user.id,
        coin=payload.coin,
        direction=payload.direction,
        threshold=payload.threshold,
        status=AlertStatus.active,
    )
    session.add(alert)
    await session.commit()
    await session.refresh(alert)
    await _invalidate(container, alert.coin.value)
    return alert


@router.get("", response_model=list[AlertOut])
@limiter.limit("60/minute")
async def list_alerts(
    request: Request,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    status_filter: Annotated[AlertStatus | None, Query(alias="status")] = None,
) -> list[Alert]:
    stmt = select(Alert).where(Alert.user_id == user.id)
    if status_filter is not None:
        stmt = stmt.where(Alert.status == status_filter)
    stmt = stmt.order_by(Alert.created_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.delete("/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("60/minute")
async def cancel_alert(
    request: Request,
    alert_id: int,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    container: Annotated[AppContainer, Depends(get_container)],
) -> None:
    alert = await session.get(Alert, alert_id)
    if alert is None or alert.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if alert.status == AlertStatus.active:
        alert.status = AlertStatus.cancelled
        await session.commit()
        await _invalidate(container, alert.coin.value)
