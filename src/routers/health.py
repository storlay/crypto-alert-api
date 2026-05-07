from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from sqlalchemy import text

from src.container import AppContainer
from src.deps import get_container


router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(
    container: Annotated[AppContainer, Depends(get_container)],
) -> dict[str, str]:
    async with container.engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    await container.redis.ping()  # type: ignore[misc]
    return {"status": "ready"}
