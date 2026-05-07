from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Request
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from src.container import AppContainer
from src.container import link_key
from src.deps import current_user
from src.deps import get_container
from src.deps import get_session
from src.limits import limiter
from src.models import User
from src.schemas import MePatch
from src.schemas import UserOut


router = APIRouter(tags=["me"])


@router.patch("/me", response_model=UserOut)
@limiter.limit("60/minute")
async def patch_me(
    request: Request,
    payload: MePatch,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    container: Annotated[AppContainer, Depends(get_container)],
) -> User:
    chat_id_raw = await container.redis.getdel(link_key(payload.link_code))
    if chat_id_raw is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired link code",
        )
    user.telegram_chat_id = int(chat_id_raw)
    await session.commit()
    await session.refresh(user)
    return user
