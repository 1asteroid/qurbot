import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from config import settings

logger = logging.getLogger(__name__)


class ManagerCheckMiddleware(BaseMiddleware):
    """Marks whether the current user is a manager."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user_id = None
        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery) and event.from_user:
            user_id = event.from_user.id

        is_admin = settings.is_admin(user_id) if user_id else False
        is_manager = user_id in settings.manager_ids_list if user_id else False
        if is_admin:
            is_manager = True
        if user_id and settings.is_permanent_manager(user_id):
            is_manager = True
        
        # Debug logging
        logger.debug(f"User {user_id}: is_manager={is_manager}, is_admin={is_admin}, manager_ids={settings.manager_ids_list}, admin_ids={settings.admin_ids_list}")
        
        data["is_manager"] = is_manager
        data["is_admin"] = is_admin
        return await handler(event, data)
