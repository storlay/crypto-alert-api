from __future__ import annotations

import asyncio
import logging
import secrets

from aiogram import Bot
from aiogram import Dispatcher
from aiogram import F
from aiogram.filters import CommandStart
from aiogram.types import Message
from redis.asyncio import Redis
from redis.asyncio import from_url

from src.config import get_settings
from src.container import link_key


logger = logging.getLogger(__name__)


def _new_code() -> str:
    return secrets.token_urlsafe(8)


async def _on_start(message: Message, redis: Redis, ttl: int) -> None:
    if message.from_user is None:
        return
    chat_id = message.chat.id
    code = _new_code()
    await redis.set(link_key(code), str(chat_id), ex=ttl)
    await message.answer(
        "Привет! Чтобы привязать аккаунт, отправьте этот код в PATCH /me:\n\n"
        f"<code>{code}</code>\n\n"
        f"Код действителен {ttl // 60} минут.",
        parse_mode="HTML",
    )


async def _on_help(message: Message) -> None:
    await message.answer("Доступно: /start — получить код привязки.")


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.message.register(_on_start, CommandStart())
    dp.message.register(_on_help, F.text == "/help")
    return dp


async def run() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")

    redis = from_url(settings.redis_url, decode_responses=True)
    bot = Bot(token=settings.telegram_bot_token)
    dp = build_dispatcher()
    try:
        await dp.start_polling(bot, redis=redis, ttl=settings.telegram_link_ttl_sec)
    finally:
        await bot.session.close()
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(run())
