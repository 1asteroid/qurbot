import logging
from typing import List
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from bot.keyboards import main_menu_keyboard, category_switch_keyboard, manager_orders_keyboard, manager_order_detail_keyboard, confirm_order_delete_keyboard
from bot.states import OrderStates
from services import UserService, OrderService
from services import ProductService
from utils import format_number, generate_manager_report_pdf, build_receipt_with_status
from utils.receipt_delivery import sync_order_receipt_message
import pytz
from config import settings

logger = logging.getLogger(__name__)
router = Router()


# ─── Manager Panel - User Management ──────────────────────────────────────────

@router.callback_query(F.data == "manage_users")
async def manage_users(callback: CallbackQuery, session: AsyncSession):
    """Userlarni boshqarish (manager panel)"""
    user_service = UserService(session)
    user = await user_service.get_by_telegram_id(callback.from_user.id)
    
    # Tekshirish: faqat adminlar
    if not user or not user.is_admin:
        await callback.answer("❌ Sizda bu bo'limga kirish huquqi yo'q.", show_alert=True)
        return
    
    # Barcha userlarni olish
    all_users = await user_service.get_all_latest(limit=100)
    
    builder = InlineKeyboardBuilder()
    
    text = "👥 <b>Userlarni Boshqarish</b>\n\n"
    
    admins = [u for u in all_users if u.is_admin]
    managers = [u for u in all_users if u.is_manager and not u.is_admin]
    regular_users = [u for u in all_users if not u.is_manager and not u.is_admin]
    
    text += f"👑 <b>Adminlar ({len(admins)} ta)</b>\n"
    for u in admins:
        builder.row(
            InlineKeyboardButton(
                text=f"👑 {u.full_name} - ADMIN",
                callback_data=f"user_detail:{u.id}"
            )
        )

    text += f"\n👨‍💼 <b>Menegerlar ({len(managers)} ta)</b>\n"
    for u in managers:
        builder.row(
            InlineKeyboardButton(
                text=f"👨‍💼 {u.full_name} - MENEJER",
                callback_data=f"user_detail:{u.id}"
            )
        )
    
    text += f"\n👤 <b>Oddiy Userlar ({len(regular_users)} ta)</b>\n"
    for u in regular_users:
        builder.row(
            InlineKeyboardButton(
                text=f"👤 {u.full_name}",
                callback_data=f"user_detail:{u.id}"
            )
        )
    
    builder.row(
        InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_profile")
    )
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("user_detail:"))
async def user_detail(callback: CallbackQuery, session: AsyncSession):
    """User tafsilotlarini ko'rish va manager qilish"""
    user_id = int(callback.data.split(":")[1])
    
    user_service = UserService(session)
    user = await user_service.get_by_id(user_id)
    
    if not user:
        await callback.answer("❌ User topilmadi.", show_alert=True)
        return
    
    # Tekshirish: faqat adminlar
    requestor = await user_service.get_by_telegram_id(callback.from_user.id)
    if not requestor or not requestor.is_admin:
        await callback.answer("❌ Sizda huquq yo'q.", show_alert=True)
        return
    
    status = "👑 ADMIN" if user.is_admin else ("👨‍💼 MENEJER" if user.is_manager else "👤 Oddiy Mijoz")
    
    text = (
        f"👤 <b>User Tafsilotlari</b>\n\n"
        f"👤 <b>Ism:</b> {user.full_name}\n"
        f"📱 <b>Telefon:</b> {user.phone}\n"
        f"🏷 <b>Status:</b> {status}\n"
        f"📅 <b>Ro'yxat sana:</b> {user.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        f"🆔 <b>Telegram ID:</b> {user.telegram_id}\n"
    )
    
    # Buyurtmalar statistikasi
    if user.orders:
        total_sum = sum(o.total_sum for o in user.orders)
        text += f"\n📦 <b>Buyurtmalar:</b> {len(user.orders)} ta\n"
        text += f"💰 <b>Jami summa:</b> {format_number(total_sum)} UZS\n"
    
    builder = InlineKeyboardBuilder()
    
    if user.is_admin:
        if settings.is_admin(user.telegram_id):
            builder.row(
                InlineKeyboardButton(
                    text="🔒 Doimiy admin",
                    callback_data="noop"
                )
            )
        else:
            builder.row(
                InlineKeyboardButton(
                    text="❌ Admin Huquqini Olib Olish",
                    callback_data=f"revoke_admin:{user.id}"
                )
            )
    elif user.is_manager:
        if settings.is_permanent_manager(user.telegram_id):
            builder.row(
                InlineKeyboardButton(
                    text="🔒 Doimiy menejer",
                    callback_data="noop"
                )
            )
        else:
            builder.row(
                InlineKeyboardButton(
                    text="✅ Admin Qilish",
                    callback_data=f"make_admin:{user.id}"
                ),
                InlineKeyboardButton(
                    text="❌ Menejer Huquqini Olib Olish",
                    callback_data=f"revoke_manager:{user.id}"
                )
            )
    else:
        builder.row(
            InlineKeyboardButton(
                text="✅ Admin Qilish",
                callback_data=f"make_admin:{user.id}"
            ),
            InlineKeyboardButton(
                text="✅ Menejer Qilish",
                callback_data=f"make_manager:{user.id}"
            )
        )
    
    builder.row(
        InlineKeyboardButton(text="⬅️ Orqaga", callback_data="manage_users")
    )
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("make_manager:"))
async def make_manager(callback: CallbackQuery, session: AsyncSession):
    """Userni manager qilish"""
    user_id = int(callback.data.split(":")[1])
    
    user_service = UserService(session)
    user = await user_service.get_by_id(user_id)
    
    if not user:
        await callback.answer("❌ User topilmadi.", show_alert=True)
        return
    
    # Tekshirish: faqat adminlar
    requestor = await user_service.get_by_telegram_id(callback.from_user.id)
    if not requestor or not requestor.is_admin:
        await callback.answer("❌ Sizda huquq yo'q.", show_alert=True)
        return

    if user.is_manager:
        await callback.answer("ℹ️ User allaqachon menejer.", show_alert=True)
        return
    
    # Menejer qilish
    user.is_manager = True
    session.add(user)
    await session.commit()
    
    await callback.answer(f"✅ {user.full_name} menejer bo'ldi!", show_alert=True)
    logger.info(f"User {user.id} ({user.full_name}) made manager by {requestor.id}")
    
    # Userga xabar yuborish
    await callback.message.bot.send_message(
        chat_id=user.telegram_id,
        text=f"🎉 <b>Tabriklaymiz!</b>\n\n"
        f"Siz menejer sifatida tayinlandingiz!\n"
        f"Endi buyurtma, mahsulot va statistika bilan ishlaya olasiz.",
        parse_mode="HTML"
    )
    
    # Yangilangan holatni ko'rsatish
    await user_detail(callback, session)


@router.callback_query(F.data.startswith("revoke_manager:"))
async def revoke_manager(callback: CallbackQuery, session: AsyncSession):
    """Menejer huquqini olib olish"""
    user_id = int(callback.data.split(":")[1])
    
    user_service = UserService(session)
    user = await user_service.get_by_id(user_id)
    
    if not user:
        await callback.answer("❌ User topilmadi.", show_alert=True)
        return
    
    # Tekshirish: faqat adminlar
    requestor = await user_service.get_by_telegram_id(callback.from_user.id)
    if not requestor or not requestor.is_admin:
        await callback.answer("❌ Sizda huquq yo'q.", show_alert=True)
        return

    if settings.is_permanent_manager(user.telegram_id):
        await callback.answer("🔒 Bu akkaunt doimiy menejer va uni olib bo'lmaydi.", show_alert=True)
        return

    if user.is_admin and settings.is_admin(user.telegram_id):
        await callback.answer("🔒 Bu akkaunt doimiy admin va uni olib bo'lmaydi.", show_alert=True)
        return
    
    user.is_manager = False
    session.add(user)
    await session.commit()
    
    await callback.answer(f"✅ {user.full_name} menejer huquqi olib olindi!", show_alert=True)
    logger.info(f"User {user.id} ({user.full_name}) revoked manager by {requestor.id}")
    
    # Userga xabar yuborish
    await callback.message.bot.send_message(
        chat_id=user.telegram_id,
        text=f"ℹ️ <b>Birinchi xabar</b>\n\n"
        f"Sizning menejer huquqingiz olib olindi.\n"
        f"Endi faqat oddiy mijoz sifatida ishlasiz.",
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("make_admin:"))
async def make_admin(callback: CallbackQuery, session: AsyncSession):
    """Userni admin qilish"""
    user_id = int(callback.data.split(":")[1])

    user_service = UserService(session)
    user = await user_service.get_by_id(user_id)

    if not user:
        await callback.answer("❌ User topilmadi.", show_alert=True)
        return

    requestor = await user_service.get_by_telegram_id(callback.from_user.id)
    if not requestor or not requestor.is_admin:
        await callback.answer("❌ Sizda huquq yo'q.", show_alert=True)
        return

    if user.is_admin:
        await callback.answer("ℹ️ User allaqachon admin.", show_alert=True)
        return

    user.is_admin = True
    user.is_manager = True
    session.add(user)
    await session.commit()

    await callback.answer(f"✅ {user.full_name} admin bo'ldi!", show_alert=True)
    logger.info(f"User {user.id} ({user.full_name}) made admin by {requestor.id}")

    await callback.message.bot.send_message(
        chat_id=user.telegram_id,
        text=f"🎉 <b>Tabriklaymiz!</b>\n\n"
        f"Siz admin sifatida tayinlandingiz!\n"
        f"Endi admin panel va boshqaruv imkoniyatlariga egasiz.",
        parse_mode="HTML"
    )

    await user_detail(callback, session)


@router.callback_query(F.data.startswith("revoke_admin:"))
async def revoke_admin(callback: CallbackQuery, session: AsyncSession):
    """Admin huquqini olib olish"""
    user_id = int(callback.data.split(":")[1])

    user_service = UserService(session)
    user = await user_service.get_by_id(user_id)

    if not user:
        await callback.answer("❌ User topilmadi.", show_alert=True)
        return

    requestor = await user_service.get_by_telegram_id(callback.from_user.id)
    if not requestor or not requestor.is_admin:
        await callback.answer("❌ Sizda huquq yo'q.", show_alert=True)
        return

    if user.is_admin and settings.is_admin(user.telegram_id):
        await callback.answer("🔒 Bu akkaunt doimiy admin va uni olib bo'lmaydi.", show_alert=True)
        return

    user.is_admin = False
    session.add(user)
    await session.commit()

    await callback.answer(f"✅ {user.full_name} admin huquqi olib olindi!", show_alert=True)
    logger.info(f"User {user.id} ({user.full_name}) revoked admin by {requestor.id}")

    await callback.message.bot.send_message(
        chat_id=user.telegram_id,
        text=f"ℹ️ <b>Birinchi xabar</b>\n\n"
        f"Sizning admin huquqingiz olib olindi.",
        parse_mode="HTML"
    )

    await user_detail(callback, session)
    
    # Yangilangan holatni ko'rsatish
    await user_detail(callback, session)


@router.callback_query(F.data == "back_to_profile")
async def back_to_profile(callback: CallbackQuery, session: AsyncSession):
    """Profilga orqaga qaytish"""
    user_service = UserService(session)
    user = await user_service.get_by_telegram_id(callback.from_user.id)
    
    if not user:
        await callback.answer("❌ Profil topilmadi.")
        return
    
    status_text = "👨‍💼 Menejer" if user.is_manager else "👤 Mijoz"
    
    text = (
        f"<b>👤 Mening Profilim</b>\n\n"
        f"👤 <b>Ism:</b> {user.full_name}\n"
        f"📱 <b>Telefon:</b> {user.phone}\n"
        f"🏷 <b>Status:</b> {status_text}\n"
        f"📅 <b>Ro'yxat sana:</b> {user.created_at.strftime('%d.%m.%Y')}\n"
    )
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✏️ Ism/Familiya", callback_data="update_full_name")
    )
    builder.row(
        InlineKeyboardButton(text="✏️ Telefon raqam", callback_data="update_phone")
    )
    if user.is_admin:
        builder.row(
            InlineKeyboardButton(text=" Hisobot", callback_data="manager_report")
        )
        builder.row(
            InlineKeyboardButton(text="📋 Buyurtmalar", callback_data="manager_orders_list")
        )
    elif user.is_manager:
        builder.row(
            InlineKeyboardButton(text="📊 Hisobot", callback_data="manager_report")
        )
        builder.row(
            InlineKeyboardButton(text="📋 Buyurtmalar", callback_data="manager_orders_list")
        )
    else:
        builder.row(
            InlineKeyboardButton(text="📋 Mening buyurtmalarim", callback_data="my_orders")
        )
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()


# ─── Manager Report ───────────────────────────────────────────────────────────

@router.callback_query(F.data == "manager_report")
async def manager_report(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    """Manager hisobot - PDF shaklida bugungi/oylik buyurtmalar"""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from database.models import Order, OrderItem
    
    user_service = UserService(session)
    manager = await user_service.get_by_telegram_id(callback.from_user.id)
    
    if not manager or not manager.is_manager:
        await callback.answer("❌ Sizda huquq yo'q.", show_alert=True)
        return
    
    # Bugungi buyurtmalar (manager tomonidan shakllantirgan)
    tz = pytz.timezone(settings.TIMEZONE)
    today = datetime.now(tz).replace(tzinfo=None).date()
    today_start = datetime(today.year, today.month, today.day)
    today_end = datetime(today.year, today.month, today.day, 23, 59, 59)
    
    # Manager tomonidan shakllantirgan buyurtmalarni olish
    result = await session.execute(
        select(Order)
        .where(Order.manager_id == manager.id)
        .where(Order.created_at >= today_start)
        .where(Order.created_at <= today_end)
        .options(
            selectinload(Order.user),
            selectinload(Order.items).selectinload(OrderItem.product)
        )
    )
    period_orders = list(result.scalars().all())
    
    if not period_orders:
        await callback.answer("📊 Bugun hali buyurtma yo'q.", show_alert=True)
        return
    
    # PDF yaratish
    try:
        pdf_buffer = generate_manager_report_pdf(manager, period_orders)
        pdf_data = pdf_buffer.getvalue()
        
        await bot.send_document(
            chat_id=callback.from_user.id,
            document=BufferedInputFile(pdf_data, filename=f"hisobot_{today}.pdf"),
            caption=f"📊 Hisobot - {today.strftime('%d.%m.%Y')}\nJami: {len(period_orders)} buyurtma"
        )
        await callback.answer("✅ PDF yuborildi!")
    except Exception as e:
        logger.error(f"Report generation error: {e}")
        await callback.answer("❌ Hisobot yaratishda xatolik.", show_alert=True)


@router.callback_query(F.data == "manager_orders_list")
async def manager_orders_list(callback: CallbackQuery, session: AsyncSession):
    """Manager uchun buyurtmalar ro'yxati."""
    user_service = UserService(session)
    manager = await user_service.get_by_telegram_id(callback.from_user.id)

    if not manager or not manager.is_manager:
        await callback.answer("❌ Sizda huquq yo'q.", show_alert=True)
        return

    service = OrderService(session)
    orders, total = await service.get_all_orders_paginated(page=1, per_page=10)

    if not orders:
        await callback.message.edit_text("📋 Buyurtmalar yo'q.")
        await callback.answer()
        return

    await callback.message.edit_text(
        "📋 <b>Buyurtmalar</b>",
        parse_mode="HTML",
        reply_markup=manager_orders_keyboard(orders, page=1, total=total),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("manager_orders_page:"))
async def manager_orders_page(callback: CallbackQuery, session: AsyncSession):
    """Manager buyurtmalarini sahifalash."""
    page = int(callback.data.split(":")[1])
    user_service = UserService(session)
    manager = await user_service.get_by_telegram_id(callback.from_user.id)

    if not manager or not manager.is_manager:
        await callback.answer("❌ Sizda huquq yo'q.", show_alert=True)
        return

    service = OrderService(session)
    orders, total = await service.get_all_orders_paginated(page=page, per_page=10)

    if not orders:
        await callback.answer("Buyurtmalar topilmadi.", show_alert=True)
        return

    await callback.message.edit_text(
        "📋 <b>Buyurtmalar</b>",
        parse_mode="HTML",
        reply_markup=manager_orders_keyboard(orders, page=page, total=total),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("manager_order_detail:"))
async def manager_order_detail(callback: CallbackQuery, session: AsyncSession):
    """Manager buyurtma tafsilotlari."""
    order_id = int(callback.data.split(":")[1])
    user_service = UserService(session)
    manager = await user_service.get_by_telegram_id(callback.from_user.id)

    if not manager or not manager.is_manager:
        await callback.answer("❌ Sizda huquq yo'q.", show_alert=True)
        return

    service = OrderService(session)
    order = await service.get_order_with_details(order_id)

    if not order:
        await callback.answer("❌ Buyurtma topilmadi.", show_alert=True)
        return

    text = build_receipt_with_status(order)
    await callback.message.edit_text(
        f"<pre>{text}</pre>",
        parse_mode="HTML",
        reply_markup=manager_order_detail_keyboard(order.id, order.status, can_delete=manager.is_admin),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("delete_order:"))
async def delete_order_prompt(callback: CallbackQuery, session: AsyncSession):
    order_id = int(callback.data.split(":")[1])
    user_service = UserService(session)
    manager = await user_service.get_by_telegram_id(callback.from_user.id)

    if not manager or not manager.is_admin:
        await callback.answer("❌ Sizda huquq yo'q.", show_alert=True)
        return

    service = OrderService(session)
    order = await service.get_order_with_details(order_id)

    if not order:
        await callback.answer("❌ Buyurtma topilmadi.", show_alert=True)
        return

    await callback.message.edit_text(
        f"🗑 <b>Buyurtma #{order.id}</b> ni o'chirishni tasdiqlaysizmi?\n\n"
        f"{build_receipt_with_status(order)}",
        parse_mode="HTML",
        reply_markup=confirm_order_delete_keyboard(order.id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_delete_order:"))
async def confirm_delete_order(callback: CallbackQuery, session: AsyncSession):
    order_id = int(callback.data.split(":")[1])
    user_service = UserService(session)
    manager = await user_service.get_by_telegram_id(callback.from_user.id)

    if not manager or not manager.is_admin:
        await callback.answer("❌ Sizda huquq yo'q.", show_alert=True)
        return

    service = OrderService(session)
    deleted = await service.delete_order(order_id)

    if not deleted:
        await callback.answer("❌ Buyurtma topilmadi.", show_alert=True)
        return

    await callback.answer("✅ Buyurtma o'chirildi!", show_alert=True)
    await manager_orders_list(callback, session)


@router.callback_query(F.data.startswith("manager_toggle_accept:"))
async def manager_toggle_accept(callback: CallbackQuery, session: AsyncSession):
    """Manager buyurtma statusini o'zgartiradi."""
    order_id = int(callback.data.split(":")[1])
    user_service = UserService(session)
    manager = await user_service.get_by_telegram_id(callback.from_user.id)

    if not manager or not manager.is_manager:
        await callback.answer("❌ Sizda huquq yo'q.", show_alert=True)
        return

    service = OrderService(session)
    order = await service.get_order_with_details(order_id)

    if not order:
        await callback.answer("❌ Buyurtma topilmadi.", show_alert=True)
        return

    new_status = "pending" if order.status == "accepted" else "accepted"
    order = await service.set_order_status(order, new_status)

    text = build_receipt_with_status(order)
    await callback.message.edit_text(
        f"<pre>{text}</pre>",
        parse_mode="HTML",
        reply_markup=manager_order_detail_keyboard(order.id, order.status),
    )
    await callback.answer("✅ Holat o'zgartirildi!")


@router.callback_query(F.data.startswith("edit_pending_order:"))
async def edit_pending_order(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Manager buyurtmani tahrirlash oqimiga kiradi."""
    order_id = int(callback.data.split(":")[1])
    user_service = UserService(session)
    manager = await user_service.get_by_telegram_id(callback.from_user.id)

    if not manager or not manager.is_manager:
        await callback.answer("❌ Sizda huquq yo'q.", show_alert=True)
        return

    service = OrderService(session)
    order = await service.get_order_with_details(order_id)

    if not order:
        await callback.answer("❌ Buyurtma topilmadi.", show_alert=True)
        return

    if order.status != "pending":
        await callback.answer("ℹ️ Faqat tasdiqlanmagan buyurtma tahrirlanadi.", show_alert=True)
        return

    prod_service = ProductService(session)
    categories = await prod_service.get_all_categories()
    if not categories:
        await callback.answer("❌ Kategoriyalar topilmadi.", show_alert=True)
        return

    await state.clear()
    await state.set_state(OrderStates.selecting_category)
    await state.update_data(
        editing_order_id=order.id,
        selected_user_id=order.user_id,
        order_items=[],
        selected_category_id=None,
    )

    await callback.message.answer(
        f"✏️ <b>Buyurtma #{order.id} tahrirlanmoqda</b>\n\n"
        f"Mahsulotlarni qayta tanlang. Saqlanganda mijozning eski cheki yangilanadi.",
        parse_mode="HTML",
        reply_markup=category_switch_keyboard(
            categories,
            callback_prefix="select_category",
            back_callback="cancel_order",
        ),
    )
    await callback.answer()
