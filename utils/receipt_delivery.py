import logging

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Order

logger = logging.getLogger(__name__)


async def sync_order_receipt_message(
    bot: Bot,
    session: AsyncSession,
    order: Order,
    text: str,
    reply_markup: InlineKeyboardMarkup,
) -> int:
    chat_id = order.user.telegram_id
    message_id = order.receipt_message_id

    if message_id:
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                parse_mode="HTML",
                reply_markup=reply_markup,
            )
            return message_id
        except Exception as exc:
            logger.info("Could not edit receipt message for order %s: %s", order.id, exc)
            try:
                await bot.delete_message(chat_id=chat_id, message_id=message_id)
            except Exception:
                pass

    sent_message = await bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode="HTML",
        reply_markup=reply_markup,
    )
    order.receipt_message_id = sent_message.message_id
    session.add(order)
    await session.commit()
    return sent_message.message_id
