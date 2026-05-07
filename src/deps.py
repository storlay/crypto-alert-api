from collections.abc import AsyncIterator
from typing import Annotated

import jwt
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Request
from fastapi import WebSocket
from fastapi import status
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.container import AppContainer
from src.models import User
from src.security import decode_token


bearer = HTTPBearer(auto_error=False)


def get_container(request: Request) -> AppContainer:
    return request.app.state.container


def ws_container(websocket: WebSocket) -> AppContainer:
    return websocket.app.state.container


async def get_session(
    container: Annotated[AppContainer, Depends(get_container)],
) -> AsyncIterator[AsyncSession]:
    async with container.sessionmaker() as session:
        yield session


async def _user_from_token(token: str, session: AsyncSession) -> User:
    try:
        payload = decode_token(token)
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        ) from exc

    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )
    return user


async def current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token"
        )
    user = await _user_from_token(credentials.credentials, session)
    request.state.user_id = user.id
    return user


async def ws_authenticate(
    websocket: WebSocket,
    container: AppContainer,
    token: str | None,
) -> User | None:
    if not token:
        await websocket.close(code=4401)
        return None
    try:
        async with container.sessionmaker() as session:
            return await _user_from_token(token, session)
    except HTTPException:
        await websocket.close(code=4401)
        return None
