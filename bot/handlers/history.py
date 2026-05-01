import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards import (
    history_users_list_keyboard, 
    history_user_orders_keyboard,
    history_order_detail_keyboard,
    main_menu_keyboard
)
from services import OrderService
from utils import format_number, build_receipt, generate_receipt_pdf, generate_user_orders_pdf

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.text == "📜 Buyurtmalar tarixi")
async def show_order_history(message: Message, session: AsyncSession):
    """Show order history grouped by users"""
    service = OrderService(session)
    users_data = await service.get_users_with_orders_grouped()
    
    if not users_data:
        await message.answer(
            "📜 Buyurtmalar tarixi bo'sh.",
            reply_markup=main_menu_keyboard()
        )
        return
    
    text = f"📜 <b>Buyurtmalar tarixi</b>\n"
    text += f"Jami foydalanuvchilar: <b>{len(users_data)}</b>\n\n"
    text += "Userlarni tanlang (eng yangi buyurtma bergan user birinchi):"
    
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=history_users_list_keyboard(users_data)
    )


@router.callback_query(F.data == "history_users_list")
async def show_history_users_list(callback: CallbackQuery, session: AsyncSession):
    """Show users list in grouped history view"""
    service = OrderService(session)
    users_data = await service.get_users_with_orders_grouped()
    
    if not users_data:
        await callback.message.edit_text("📜 Buyurtmalar tarixi bo'sh.")
        await callback.answer()
        return
    
    text = f"📜 <b>Buyurtmalar tarixi</b>\n"
    text += f"Jami foydalanuvchilar: <b>{len(users_data)}</b>\n\n"
    text += "Userlarni tanlang (eng yangi buyurtma bergan user birinchi):"
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=history_users_list_keyboard(users_data)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("history_user:"))
async def show_user_orders_history(callback: CallbackQuery, session: AsyncSession):
    """Show specific user's orders history"""
    user_id = int(callback.data.split(":")[1])
    service = OrderService(session)
    
    user_orders = await service.get_user_orders_summary(user_id)
    
    if not user_orders:
        await callback.answer("Ushbu user uchun buyurtma topilmadi.", show_alert=True)
        return
    
    # Get user info from first order
    user = user_orders[0]["order"].user
    total_count = len(user_orders)
    total_sum = sum(order["total_sum"] for order in user_orders)
    
    text = f"👤 <b>{user.full_name}</b>\n"
    text += f"📞 {user.phone}\n"
    text += f"Jami buyurtmalar: <b>{total_count}</b>\n"
    text += f"Umumiy summa: <b>{format_number(total_sum)} UZS</b>\n\n"
    text += "Buyurtmalarni tanlang (eng yangi birinchi):"
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=history_user_orders_keyboard(user_id, user_orders)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("history_order_detail:"))
async def show_order_detail_history(callback: CallbackQuery, session: AsyncSession):
    """Show order details from history"""
    order_id = int(callback.data.split(":")[1])
    service = OrderService(session)
    order = await service.get_order_with_details(order_id)
    
    if not order:
        await callback.answer("Buyurtma topilmadi.", show_alert=True)
        return
    
    text = build_receipt(order)
    text += f"\n\n🔔 <b>Status:</b> {order.status}\n"
    if order.accepted_at:
        text += f"✅ <b>Qabul qilindi:</b> {order.accepted_at.strftime('%d.%m.%Y %H:%M')}\n"
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=history_order_detail_keyboard(order_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("history_order_pdf:"))
async def download_order_pdf_history(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    """Download order PDF from history"""
    order_id = int(callback.data.split(":")[1])
    service = OrderService(session)
    order = await service.get_order_with_details(order_id)
    
    if not order:
        await callback.answer("Buyurtma topilmadi.", show_alert=True)
        return
    
    pdf_buffer = generate_receipt_pdf(order)
    pdf_buffer.seek(0)
    
    file_name = f"buyurtma_{order_id}.pdf"
    await callback.message.answer_document(
        document=pdf_buffer,
        filename=file_name,
        caption=f"📄 Buyurtma #{order_id} PDF"
    )
    await callback.answer("✅ PDF yuklandi!")
