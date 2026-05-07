import asyncio
from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Request
from fastapi import status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.deps import get_session
from src.limits import limiter
from src.models import User
from src.schemas import LoginIn
from src.schemas import RegisterIn
from src.schemas import TokenOut
from src.schemas import UserOut
from src.security import create_access_token
from src.security import hash_password
from src.security import verify_password


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def register(
    request: Request,
    payload: RegisterIn,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    password_hash = await asyncio.to_thread(hash_password, payload.password)
    user = User(email=payload.email, password_hash=password_hash)
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        ) from exc
    await session.refresh(user)
    return user


@router.post("/login", response_model=TokenOut)
@limiter.limit("10/minute")
async def login(
    request: Request,
    payload: LoginIn,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TokenOut:
    result = await session.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    password_ok = await asyncio.to_thread(
        verify_password, payload.password, user.password_hash if user else None
    )
    if user is None or not password_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )
    return TokenOut(access_token=create_access_token(user.id))
