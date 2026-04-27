import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from database.db import AsyncSessionFactory

logger = logging.getLogger(__name__)


class DbSessionMiddleware(BaseMiddleware):
    """Injects an AsyncSession into handler data for every update."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        async with AsyncSessionFactory() as session:
            data["session"] = session
            try:
                result = await handler(event, data)
                return result
            except Exception as exc:
                await session.rollback()
                logger.exception(f"Exception in handler, session rolled back: {exc}")
                raise
