from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field(
        default="postgresql+asyncpg://crypto:crypto@localhost:5432/crypto"
    )
    redis_url: str = Field(default="redis://localhost:6379/0")

    jwt_secret: str = Field(default="dev-secret-change-me-please-32bytes-min")
    jwt_alg: str = "HS256"
    jwt_ttl_min: int = 60 * 24

    telegram_bot_token: str | None = None
    telegram_link_ttl_sec: int = 600

    binance_ws_url: str = (
        "wss://stream.binance.com:9443/stream?streams="
        "btcusdt@kline_1m/ethusdt@kline_1m/solusdt@kline_1m/"
        "bnbusdt@kline_1m/xrpusdt@kline_1m"
    )

    max_alerts_per_user: int = 20


@lru_cache
def get_settings() -> Settings:
    return Settings()
