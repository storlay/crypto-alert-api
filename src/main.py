from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.config import get_settings
from src.container import AppContainer
from src.limits import limiter
from src.routers import main_router
from src.services.alerts import run_alert_checker
from src.services.binance import run_binance_consumer
from src.services.broadcaster import run_broadcaster


logger = logging.getLogger(__name__)


def _rate_limit_handler(_request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429, content={"detail": f"Rate limit exceeded: {exc.detail}"}
    )


def _log_task_exit(task: asyncio.Task) -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.exception(
            "background task %s exited with error", task.get_name(), exc_info=exc
        )


def _make_lifespan(container: AppContainer | None = None):
    @asynccontextmanager
    async def lifespan(app_: FastAPI) -> AsyncIterator[None]:
        owns_container = container is None
        ctx = container or AppContainer(get_settings())
        app_.state.container = ctx  # type: ignore[attr-defined]

        tasks = [
            asyncio.create_task(run_binance_consumer(ctx), name="binance_consumer"),
            asyncio.create_task(run_alert_checker(ctx), name="alert_checker"),
            asyncio.create_task(run_broadcaster(ctx), name="ws_broadcaster"),
        ]
        for task in tasks:
            task.add_done_callback(_log_task_exit)
        try:
            yield
        finally:
            for task in tasks:
                task.cancel()
            for task in tasks:
                try:
                    await task
                except (asyncio.CancelledError, Exception):  # noqa: BLE001
                    pass
            if owns_container:
                await ctx.aclose()

    return lifespan


def create_app(container: AppContainer | None = None) -> FastAPI:
    application = FastAPI(title="CryptoAlert API", lifespan=_make_lifespan(container))
    application.state.limiter = limiter  # type: ignore[attr-defined]
    application.add_exception_handler(RateLimitExceeded, _rate_limit_handler)  # type: ignore[arg-type]
    application.add_middleware(SlowAPIMiddleware)

    application.include_router(main_router)
    return application


app = create_app()
