import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards import manager_orders_keyboard, manager_order_detail_keyboard, main_menu_keyboard
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
    await _send_orders_page(message, session, page=1, edit=False)


@router.callback_query(F.data == "manager_orders_list")
async def show_manager_orders_inline(callback: CallbackQuery, session: AsyncSession):
    """Show manager orders in inline format"""
    user_service = UserService(session)
    user = await user_service.get_by_telegram_id(callback.from_user.id)
    if not user or not user.is_manager:
        await callback.answer("❌ Sizda huquq yo'q.", show_alert=True)
        return
    await _send_orders_page(callback.message, session, page=1, edit=True)
    await callback.answer()


@router.callback_query(F.data.startswith("manager_orders_page:"))
async def paginate_manager_orders(callback: CallbackQuery, session: AsyncSession):
    user_service = UserService(session)
    user = await user_service.get_by_telegram_id(callback.from_user.id)
    if not user or not user.is_manager:
        await callback.answer("❌ Sizda huquq yo'q.", show_alert=True)
        return
    page = int(callback.data.split(":")[1])
    await _send_orders_page(callback.message, session, page=page, edit=True)
    await callback.answer()


@router.callback_query(F.data.startswith("manager_order_detail:"))
async def show_manager_order_detail(callback: CallbackQuery, session: AsyncSession):
    """Show order details for manager"""
    order_id = int(callback.data.split(":")[1])
    
    order_service = OrderService(session)
    order = await order_service.get_order_with_details(order_id)
    
    if not order:
        await callback.answer("❌ Buyurtma topilmadi.", show_alert=True)
        return
    
    # Build detailed receipt
    text = build_receipt(order)
    text += f"\n\n🔔 <b>Status:</b> {order.status}\n"
    if order.accepted_at:
        text += f"✅ <b>Qabul qilindi:</b> {order.accepted_at.strftime('%d.%m.%Y %H:%M')}\n"
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=manager_order_detail_keyboard(order_id, order.status),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("manager_toggle_accept:"))
async def toggle_manager_order_status(callback: CallbackQuery, session: AsyncSession):
    user_service = UserService(session)
    user = await user_service.get_by_telegram_id(callback.from_user.id)
    if not user or not user.is_manager:
        await callback.answer("❌ Sizda huquq yo'q.", show_alert=True)
        return

    order_id = int(callback.data.split(":")[1])
    order_service = OrderService(session)
    order = await order_service.get_order_with_details(order_id)

    if not order:
        await callback.answer("❌ Buyurtma topilmadi.", show_alert=True)
        return

    new_status = "pending" if order.status == "accepted" else "accepted"
    order = await order_service.set_order_status(order, new_status)

    text = build_receipt(order)
    text += f"\n\n🔔 <b>Status:</b> {order.status}\n"
    if order.accepted_at:
        text += f"✅ <b>Qabul qilindi:</b> {order.accepted_at.strftime('%d.%m.%Y %H:%M')}\n"

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=manager_order_detail_keyboard(order.id, order.status),
    )
    await callback.answer("✅ Holat yangilandi!")


async def _send_orders_page(event, session: AsyncSession, page: int, edit: bool):
    """Send a page of orders with inline buttons"""
    service = OrderService(session)
    orders, total = await service.get_all_orders_paginated(page=page, per_page=PER_PAGE)

    if not orders:
        text = "📜 Buyurtmalar tarixi bo'sh."
        if edit:
            await event.edit_text(text)
        else:
            await event.answer(text)
        return

    # Create text header
    total_pages = (total + PER_PAGE - 1) // PER_PAGE
    text = f"📜 <b>Buyurtmalar tarixi</b>\n<b>Jami:</b> {total} ta | <b>Sahifa:</b> {page}/{total_pages}\n\n"
    text += "<b>Oxirgi 10 buyurtmani birinchi ko'rsat, keyingi 10 likka inline belgi orqali o'ting:</b>\n"
    
    keyboard = manager_orders_keyboard(orders, page, total, PER_PAGE)

    if edit:
        await event.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await event.answer(text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery):
    await callback.answer()
