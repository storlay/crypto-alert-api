from fastapi import APIRouter

from src.routers.alerts import router as alerts_router
from src.routers.auth import router as auth_router
from src.routers.health import router as health_router
from src.routers.me import router as me_router
from src.routers.prices import router as prices_router
from src.routers.ws import router as ws_router


routers = (
    alerts_router,
    auth_router,
    health_router,
    me_router,
    prices_router,
    ws_router,
)

main_router = APIRouter()

for router in routers:
    main_router.include_router(router)
