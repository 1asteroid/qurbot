import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from bot.states import ProfileEditStates
from bot.keyboards import (
    main_menu_keyboard,
    remove_keyboard,
    phone_keyboard,
    order_receipt_keyboard,
)
from services import UserService, OrderService
from utils import build_receipt_with_status, format_number, format_quantity
from utils.formatting import get_order_net_total, get_order_returned_total
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

logger = logging.getLogger(__name__)
router = Router()


async def _get_or_bootstrap_profile_user(message_or_callback, session: AsyncSession):
    user_service = UserService(session)
    telegram_user = message_or_callback.from_user
    user = await user_service.get_by_telegram_id(telegram_user.id)
    if user:
        return user

    full_name = telegram_user.full_name or telegram_user.first_name or "User"
    user = await user_service.create(
        telegram_id=telegram_user.id,
        full_name=full_name,
        phone="unknown",
    )
    logger.info("Bootstrapped profile for missing user telegram_id=%s", telegram_user.id)
    return user


def _profile_keyboard(user):
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✏️ Ism/Familiya", callback_data="update_full_name")
    )
    builder.row(
        InlineKeyboardButton(text="✏️ Telefon raqam", callback_data="update_phone")
    )
    if user.is_admin:
        builder.row(
            InlineKeyboardButton(text="⚙️ Admin panel", callback_data="admin_panel")
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
    return builder.as_markup()


# ─── User Profile ─────────────────────────────────────────────────────────────

@router.message(F.text == "👤 Profil")
async def show_profile(message: Message, session: AsyncSession):
    """Foydalanuvchi profilini ko'rish"""
    user = await _get_or_bootstrap_profile_user(message, session)
    
    status_text = "👑 Admin" if user.is_admin else ("👨‍💼 Menejer" if user.is_manager else "👤 Mijoz")
    if user.is_admin:
        status_text = "👑 Admin"
    
    text = (
        f"<b>👤 Mening Profilim</b>\n\n"
        f"👤 <b>Ism:</b> {user.full_name}\n"
        f"📱 <b>Telefon:</b> {user.phone}\n"
        f"🏷 <b>Status:</b> {status_text}\n"
        f"📅 <b>Ro'yxat sana:</b> {user.created_at.strftime('%d.%m.%Y')}\n"
    )
    
    await message.answer(text, parse_mode="HTML", reply_markup=_profile_keyboard(user))


# ─── Update Full Name ─────────────────────────────────────────────────────────

@router.callback_query(F.data == "update_full_name")
async def start_update_full_name(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Ism/Familiya o'zgartirish boshlash"""
    user_service = UserService(session)
    user = await user_service.get_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.answer("❌ Foydalanuvchi topilmadi.", show_alert=True)
        return

    await state.set_state(ProfileEditStates.editing_full_name)
    await callback.message.answer("✏️ Yangi ism/familiyangizni kiriting:")
    await callback.answer()


@router.message(ProfileEditStates.editing_full_name)
async def update_full_name(message: Message, state: FSMContext, session: AsyncSession):
    """Ism/Familiya yangilash"""
    full_name = message.text.strip()
    
    if len(full_name) < 2:
        await message.answer("❗ Ism/Familiya juda qisqa. Iltimos, qayta kiriting.")
        return
    
    if len(full_name) > 100:
        await message.answer("❗ Ism/Familiya juda uzun. Iltimos, qayta kiriting.")
        return
    
    user_service = UserService(session)
    user = await user_service.get_by_telegram_id(message.from_user.id)
    
    if user:
        user.full_name = full_name
        session.add(user)
        await session.commit()
        
        await state.clear()
        
        # Profile ni qayta ko'rsatish
        await show_profile(message, session)
        await message.answer("✅ Ism/Familiya o'zgartirildi!")
        logger.info(f"User {user.telegram_id} updated full_name to {full_name}")
    else:
        await message.answer("❌ Foydalanuvchi topilmadi.")
        await state.clear()

@router.callback_query(F.data == "update_phone")
async def start_update_phone(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Telefon raqam o'zgartirish boshlash"""
    user_service = UserService(session)
    user = await user_service.get_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.answer("❌ Foydalanuvchi topilmadi.", show_alert=True)
        return

    await state.set_state(ProfileEditStates.editing_phone)
    await callback.message.answer("📱 Yangi telefon raqamingizni yuboring:", reply_markup=phone_keyboard())
    await callback.answer()


@router.message(ProfileEditStates.editing_phone)
async def update_phone(message: Message, state: FSMContext, session: AsyncSession):
    """Telefon raqamini yangilash"""
    if message.contact:
        phone = message.contact.phone_number
    else:
        phone = message.text.strip()
    
    if not phone.startswith("+"):
        phone = "+" + phone
    
    if len(phone) < 9:
        await message.answer("❗ Telefon raqam noto'g'ri. Iltimos, qayta kiriting.")
        return
    
    user_service = UserService(session)
    user = await user_service.get_by_telegram_id(message.from_user.id)
    
    if user:
        user.phone = phone
        session.add(user)
        await session.commit()
        
        await state.clear()
        await message.answer(
            f"✅ Telefon raqam o'zgartirildi!\n\n"
            f"📱 Yangi telefon: {phone}"
        )
        logger.info(f"User {user.telegram_id} updated phone to {phone}")
        
        # Profile ni qayta ko'rsatish
        await show_profile(message, session)
    else:
        await message.answer("❌ Foydalanuvchi topilmadi.")
        await state.clear()


# ─── My Orders ────────────────────────────────────────────────────────────────

@router.message((F.text == "📋 Mening buyurtmalarim") | (F.text == "🧾 Mening buyurtmalarim"))
async def show_my_orders_message(message: Message, session: AsyncSession):
    """Foydalanuvchining o'z buyurtmalarini ko'rish (reply keyboard orqali)"""
    service = OrderService(session)
    user_service = UserService(session)
    user = await user_service.get_by_telegram_id(message.from_user.id)

    if not user or user.is_manager:
        await message.answer("❌ Sizda bu bo'limga kirish huquqi yo'q.")
        return

    user_orders = await service.get_user_orders_summary(user.id)

    if not user_orders:
        await message.answer(
            "📋 <b>Mening Buyurtmalarim</b>\n\n"
            "Siz hali buyurtma bermagansiz.",
            parse_mode="HTML"
        )
        return
    
    builder = InlineKeyboardBuilder()
    
    text = "📋 <b>Mening Buyurtmalarim</b>\n\n"
    for order_info in user_orders:
        order = order_info["order"]
        total = format_number(order_info["total_sum"])
        builder.row(
            InlineKeyboardButton(
                text=f"🧾 #{order.id} - {total} UZS",
                callback_data=f"order_receipt:{order.id}"
            )
        )
        text += f"📦 Buyurtma #{order.id}: {total} UZS ({order.created_at.strftime('%d.%m.%Y')})\n"
    
    builder.row(
        InlineKeyboardButton(text="⬅️ Profil", callback_data="back_to_profile_from_orders")
    )
    
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data == "my_orders")
async def show_my_orders(callback: CallbackQuery, session: AsyncSession):
    """Foydalanuvchining o'z buyurtmalarini ko'rish (inline orqali)"""
    service = OrderService(session)
    user_service = UserService(session)
    user = await user_service.get_by_telegram_id(callback.from_user.id)

    if not user or user.is_manager:
        await callback.answer("❌ Sizda bu bo'limga kirish huquqi yo'q.", show_alert=True)
        return

    user_orders = await service.get_user_orders_summary(user.id)

    if not user_orders:
        await callback.message.edit_text(
            "📋 <b>Mening Buyurtmalarim</b>\n\n"
            "Siz hali buyurtma bermagansiz.",
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    builder = InlineKeyboardBuilder()
    
    text = "📋 <b>Mening Buyurtmalarim</b>\n\n"
    for order_info in user_orders:
        order = order_info["order"]
        total = format_number(order_info["total_sum"])
        builder.row(
            InlineKeyboardButton(
                text=f"🧾 #{order.id} - {total} UZS",
                callback_data=f"order_receipt:{order.id}"
            )
        )
        text += f"📦 Buyurtma #{order.id}: {total} UZS ({order.created_at.strftime('%d.%m.%Y')})\n"
    
    builder.row(
        InlineKeyboardButton(text="⬅️ Profil", callback_data="back_to_profile_from_orders")
    )
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "back_to_profile_from_orders")
async def back_to_profile_from_orders(callback: CallbackQuery, session: AsyncSession):
    """Mening buyurtmalardan profilga qaytish"""
    user = await _get_or_bootstrap_profile_user(callback, session)
    
    status_text = "👨‍💼 Menejer" if user.is_manager else "👤 Mijoz"
    if user.is_admin:
        status_text = "👑 Admin"
    
    text = (
        f"<b>👤 Mening Profilim</b>\n\n"
        f"👤 <b>Ism:</b> {user.full_name}\n"
        f"📱 <b>Telefon:</b> {user.phone}\n"
        f"🏷 <b>Status:</b> {status_text}\n"
        f"📅 <b>Ro'yxat sana:</b> {user.created_at.strftime('%d.%m.%Y')}\n"
    )
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=_profile_keyboard(user))
    await callback.answer()


@router.callback_query(F.data.startswith("order_receipt:"))
async def show_order_receipt(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    """Buyurtma chekini qayta ko'rish va olish"""
    order_id = int(callback.data.split(":")[1])
    
    order_service = OrderService(session)
    order = await order_service.get_order_with_details(order_id)
    
    if not order:
        await callback.answer("❌ Buyurtma topilmadi.", show_alert=True)
        return
    
    # Tekshirish: Buyurtma foydalanuvchining bo'lsa
    if order.user.telegram_id != callback.from_user.id:
        await callback.answer("❌ Bu buyurtma sizning emas.", show_alert=True)
        return

    receipt_text = build_receipt_with_status(order)
    
    await callback.message.edit_text(
        f"<pre>{receipt_text}</pre>",
        parse_mode="HTML",
        reply_markup=order_receipt_keyboard(
            order.id,
            can_accept=order.status == "pending",
            back_callback="my_orders",
        )
    )
    await callback.answer()


@router.callback_query(F.data.startswith("accept_order:"))
async def accept_order_handler(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    """Order qabul qilish"""
    order_id = int(callback.data.split(":")[1])
    
    order_service = OrderService(session)
    order = await order_service.get_order_with_details(order_id)
    
    if not order:
        await callback.answer("❌ Buyurtma topilmadi.", show_alert=True)
        return
    
    # Tekshirish: Buyurtma foydalanuvchining bo'lsa
    if order.user.telegram_id != callback.from_user.id:
        await callback.answer("❌ Bu buyurtma sizning emas.", show_alert=True)
        return
    
    # Accept the order
    order = await order_service.accept_order(order_id)
    
    # Notify manager
    if order.manager:
        try:
            manager_text = (
                f"✅ <b>Buyurtma qabul qilindi!</b>\n\n"
                f"📦 Buyurtma #: {order.id}\n"
                f"👤 Mijoz: {order.user.full_name}\n"
                f"📱 Tel: {order.user.phone}\n"
                f"💰 Summa: {format_number(get_order_net_total(order))} UZS\n"
                f"✅ Qabul vaqti: {order.accepted_at.strftime('%d.%m.%Y %H:%M')}\n"
            )
            returned_total = get_order_returned_total(order)
            if returned_total > 0:
                manager_text += f"↩️ Qaytarilgan: {format_number(returned_total)} UZS\n"
            
            # Add items info
            manager_text += "\n📋 <b>Buyurtma tarkibi:</b>\n"
            for item in order.items:
                manager_text += f"  • {item.product.name}: {format_quantity(item.quantity)} {item.product.unit} × {format_number(item.price)} = {format_number(item.total_price)} UZS\n"
            
            await bot.send_message(
                chat_id=order.manager.telegram_id,
                text=manager_text,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Could not notify manager: {e}")
    
    # Show updated receipt
    receipt_text = build_receipt_with_status(order)

    try:
        from utils.receipt_delivery import sync_order_receipt_message

        await sync_order_receipt_message(
            bot=bot,
            session=session,
            order=order,
            text=f"<pre>{receipt_text}</pre>",
            reply_markup=order_receipt_keyboard(order.id, can_accept=False, back_callback="my_orders"),
        )
    except Exception as e:
        logger.warning(f"Could not sync original receipt message: {e}")
    
    await callback.message.edit_text(
        f"<pre>{receipt_text}</pre>",
        parse_mode="HTML",
        reply_markup=order_receipt_keyboard(order.id, can_accept=False, back_callback="my_orders")
    )
    await callback.answer("✅ Buyurtma qabul qilindi!")



@router.callback_query(F.data.startswith("download_receipt_pdf:"))
async def download_receipt_pdf(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    """PDF chekni yuborish"""
    order_id = int(callback.data.split(":")[1])
    
    order_service = OrderService(session)
    order = await order_service.get_order_with_details(order_id)
    
    if not order:
        await callback.answer("❌ Buyurtma topilmadi.", show_alert=True)
        return
    
    # Tekshirish: Buyurtma foydalanuvchining bo'lsa
    if order.user.telegram_id != callback.from_user.id:
        await callback.answer("❌ Bu buyurtma sizning emas.", show_alert=True)
        return
    
    # PDF yuklash mavjud bo'lib qoladi: foydalanuvchi uni buyurtmalar bo'limidan olishi mumkin.
    from aiogram.types import BufferedInputFile
    from utils import generate_receipt_pdf

    try:
        pdf_buffer = generate_receipt_pdf(order)
        pdf_data = pdf_buffer.getvalue()

        await bot.send_document(
            chat_id=callback.from_user.id,
            document=BufferedInputFile(pdf_data, filename=f"chek_{order.id}.pdf"),
            caption=f"📄 Chek #{order.id}\nMijoz: {order.user.full_name}"
        )
        await callback.answer("✅ PDF yuborildi!")
    except Exception as e:
        logger.error(f"PDF generation error: {e}")
        await callback.answer("❌ PDF yaratishda xatolik.", show_alert=True)


# ─── Contact Developer ────────────────────────────────────────────────────────

@router.callback_query(F.data == "contact_dev_from_profile")
async def contact_developer_from_profile(callback: CallbackQuery):
    """Dasturchi bilan aloqa (profildan)"""
    DEVELOPER_CONTACT = "@your_developer_username"  # O'zgartiring
    
    await callback.message.edit_text(
        f"👨‍💻 <b>Dasturchi bilan bog'lanish</b>\n\n"
        f"Muammo yoki taklif bo'lsa, quyidagi manzilga murojaat qiling:\n\n"
        f"Telegram: <b>{DEVELOPER_CONTACT}</b>",
        parse_mode="HTML"
    )
    await callback.answer()
