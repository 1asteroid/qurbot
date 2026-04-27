import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards import order_history_keyboard, order_detail_keyboard
from services import OrderService, UserService
from utils import format_number, build_receipt

logger = logging.getLogger(__name__)
router = Router()

PER_PAGE = 10


@router.message(F.text == "📜 Buyurtmalar tarixi")
async def show_order_history(message: Message, session: AsyncSession):
    user_service = UserService(session)
    user = await user_service.get_by_telegram_id(message.from_user.id)
    if not user or not user.is_manager:
        await message.answer("❌ Sizda bu bo'limga kirish huquqi yo'q.")
        return
    await _send_history_page(message, session, page=1, edit=False)


@router.callback_query(F.data.startswith("orders_page:"))
async def paginate_orders(callback: CallbackQuery, session: AsyncSession):
    user_service = UserService(session)
    user = await user_service.get_by_telegram_id(callback.from_user.id)
    if not user or not user.is_manager:
        await callback.answer("❌ Sizda huquq yo'q.", show_alert=True)
        return
    page = int(callback.data.split(":")[1])
    await _send_history_page(callback.message, session, page=page, edit=True)
    await callback.answer()


async def _send_history_page(event, session: AsyncSession, page: int, edit: bool):
    service = OrderService(session)
    orders, total = await service.get_all_orders_paginated(page=page, per_page=PER_PAGE)

    if not orders:
        text = "📜 Buyurtmalar tarixi bo'sh."
        if edit:
            await event.edit_text(text)
        else:
            await event.answer(text)
        return

    lines = [f"📜 <b>Buyurtmalar tarixi</b> (Jami: {total} ta)\n"]
    for i, order in enumerate(orders, start=(page - 1) * PER_PAGE + 1):
        lines.append(
            f"{i}. <b>#{order.id}</b> — {order.user.full_name}\n"
            f"   💰 {format_number(order.total_sum)} UZS\n"
            f"   📅 {order.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        )

    text = "\n".join(lines)
    keyboard = order_history_keyboard(page, total, PER_PAGE)

    if edit:
        await event.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await event.answer(text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery):
    await callback.answer()
