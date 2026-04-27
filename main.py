import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import settings
from database import init_db
from bot.handlers import setup_routers
from bot.middlewares import DbSessionMiddleware, ManagerCheckMiddleware

# ─── Logging setup ────────────────────────────────────────────────────────────

_log_handlers: list = [logging.StreamHandler(sys.stdout)]
if not any(v in ("1", "true", "yes") for v in [os.environ.get("DYNO", "")]):
    # Add file handler only when not running on Heroku (no persistent filesystem)
    _log_handlers.append(logging.FileHandler("bot.log", encoding="utf-8"))

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=_log_handlers,
)
logger = logging.getLogger(__name__)


async def main() -> None:
    logger.info("Starting Construction Bot...")

    # Initialize DB
    await init_db()

    # Bot instance
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # Dispatcher with FSM storage
    dp = Dispatcher(storage=MemoryStorage())

    # ── Middlewares ──────────────────────────────────────────────────────────
    dp.update.middleware(DbSessionMiddleware())
    dp.update.middleware(ManagerCheckMiddleware())

    # ── Routers ──────────────────────────────────────────────────────────────
    dp.include_router(setup_routers())

    # ── Start polling ────────────────────────────────────────────────────────
    logger.info(f"Bot started. Manager IDs: {settings.manager_ids_list}")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        logger.info("Bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())
