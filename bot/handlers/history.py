import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards import (
    history_users_list_keyboard, 
    history_user_orders_keyboard,
    history_order_detail_keyboard,
    order_receipt_keyboard,
    main_menu_keyboard,
    cancel_keyboard,
)
from bot.states import PaymentStates, ReturnStates
from services import OrderService, UserService
from utils import (
    format_number,
    build_receipt,
    build_receipt_with_status,
    generate_receipt_pdf,
    generate_user_orders_pdf,
)
from utils.formatting import get_order_item_remaining_quantity
from utils.receipt_delivery import sync_order_receipt_message

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
    text += f"To'lanishi kerak: <b>{format_number(total_sum - user.paid_sum)} UZS</b>\n"
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
    parts = callback.data.split(":")
    order_id = int(parts[1])
    user_id = int(parts[2]) if len(parts) > 2 else None
    
    service = OrderService(session)
    order = await service.get_order_with_details(order_id)
    
    if not order:
        await callback.answer("Buyurtma topilmadi.", show_alert=True)
        return

    user_service = UserService(session)
    viewer = await user_service.get_by_telegram_id(callback.from_user.id)
    can_edit = bool(viewer and viewer.is_manager and order.status == "pending")
    
    text = build_receipt(order)
    text += f"\n\n🔔 <b>Status:</b> {order.status}\n"
    if order.accepted_at:
        text += f"✅ <b>Qabul qilindi:</b> {order.accepted_at.strftime('%d.%m.%Y %H:%M')}\n"
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=history_order_detail_keyboard(order, user_id or order.user_id, can_edit=can_edit)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("return_item:"))
async def prompt_return_item_quantity(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    user_service = UserService(session)
    viewer = await user_service.get_by_telegram_id(callback.from_user.id)
    if not viewer or not viewer.is_manager:
        await callback.answer("❌ Sizda bu bo'limga kirish huquqi yo'q.", show_alert=True)
        return

    parts = callback.data.split(":")
    order_id = int(parts[1])
    order_item_id = int(parts[2])

    service = OrderService(session)
    order = await service.get_order_with_details(order_id)
    if not order:
        await callback.answer("Buyurtma topilmadi.", show_alert=True)
        return

    order_item = next((item for item in order.items if item.id == order_item_id), None)
    if not order_item:
        await callback.answer("Mahsulot topilmadi.", show_alert=True)
        return

    remaining_qty = get_order_item_remaining_quantity(order_item)
    if remaining_qty <= 0:
        await callback.answer("Bu mahsulot allaqachon to'liq qaytarilgan.", show_alert=True)
        return

    await state.set_state(ReturnStates.entering_quantity)
    await state.update_data(
        order_id=order_id,
        order_item_id=order_item_id,
        history_user_id=order.user_id,
    )

    item_name = order_item.product.name
    if order_item.size:
        item_name = f"{item_name} ({order_item.size})"

    await callback.message.answer(
        f"↩️ <b>Qaytgan mahsulot</b>\n\n"
        f"📦 Mahsulot: <b>{item_name}</b>\n"
        f"📥 Qolgan miqdor: <b>{remaining_qty:.2f}</b>\n\n"
        f"Qaytariladigan miqdorni kiriting:",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
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
    pdf_file = BufferedInputFile(
        pdf_buffer.getvalue(),
        filename=f"buyurtma_{order_id}.pdf",
    )

    await callback.message.answer_document(
        document=pdf_file,
        caption=f"📄 Buyurtma #{order_id} PDF",
    )
    await callback.answer("✅ PDF yuklandi!")


@router.message(ReturnStates.entering_quantity)
async def process_return_quantity(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=main_menu_keyboard())
        return

    try:
        quantity = float(message.text.strip())
        if quantity <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Noto'g'ri format. Miqdorni raqam bilan kiriting.")
        return

    data = await state.get_data()
    order_id = data.get("order_id")
    order_item_id = data.get("order_item_id")
    history_user_id = data.get("history_user_id")
    if not order_id or not order_item_id:
        await state.clear()
        await message.answer("❌ Qaytarish holati topilmadi.")
        return

    service = OrderService(session)
    order = await service.get_order_with_details(order_id)
    if not order:
        await state.clear()
        await message.answer("❌ Buyurtma topilmadi.")
        return

    order_item = next((item for item in order.items if item.id == order_item_id), None)
    if not order_item:
        await state.clear()
        await message.answer("❌ Mahsulot topilmadi.")
        return

    remaining_qty = get_order_item_remaining_quantity(order_item)
    if quantity > remaining_qty:
        await message.answer(f"❌ Maksimal qaytarish miqdori: {remaining_qty:.2f}")
        return

    try:
        return_item = await service.add_return_item(order_item_id=order_item_id, quantity=quantity)
    except ValueError:
        await message.answer("❌ Qaytarish miqdori noto'g'ri.")
        return

    if not return_item:
        await state.clear()
        await message.answer("❌ Qaytarish saqlanmadi.")
        return

    updated_order = await service.get_order_with_details(order_id)
    if updated_order:
        receipt_text = build_receipt_with_status(updated_order)
        try:
            await sync_order_receipt_message(
                bot=bot,
                session=session,
                order=updated_order,
                text=f"<pre>{receipt_text}</pre>",
                reply_markup=order_receipt_keyboard(
                    updated_order.id,
                    can_accept=updated_order.status == "pending",
                    back_callback="my_orders",
                ),
            )
        except Exception as exc:
            logger.warning("Could not sync returned receipt for order %s: %s", updated_order.id, exc)

        await message.answer(
            f"✅ Qaytarish saqlandi.\n\n<pre>{receipt_text}</pre>",
            parse_mode="HTML",
            reply_markup=history_order_detail_keyboard(updated_order, history_user_id or updated_order.user_id, can_edit=updated_order.status == "pending"),
        )

    await state.clear()


@router.callback_query(F.data.startswith("history_user_pdf:"))
async def download_user_orders_pdf_history(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    """Download all orders PDF for a specific user"""
    user_id = int(callback.data.split(":")[1])
    service = OrderService(session)

    user_orders = await service.get_user_orders_summary(user_id)
    if not user_orders:
        await callback.answer("Ushbu user uchun buyurtma topilmadi.", show_alert=True)
        return

    user = user_orders[0]["order"].user
    pdf_buffer = generate_user_orders_pdf(user, user_orders)
    pdf_file = BufferedInputFile(
        pdf_buffer.getvalue(),
        filename=f"{user.full_name}_buyurtmalar.pdf",
    )

    await callback.message.answer_document(
        document=pdf_file,
        caption=f"📄 {user.full_name} buyurtmalari PDF",
    )
    await callback.answer("✅ PDF yuklandi!")


@router.callback_query(F.data.startswith("payment_user:"))
async def prompt_user_payment(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Prompt for payment amount for user"""
    user_id = int(callback.data.split(":")[1])
    
    # Get user info
    service = OrderService(session)
    user_orders = await service.get_user_orders_summary(user_id)
    
    if not user_orders:
        await callback.answer("Ushbu user uchun buyurtma topilmadi.", show_alert=True)
        return
    
    user = user_orders[0]["order"].user
    total_sum = sum(order["total_sum"] for order in user_orders)
    to_pay = total_sum - user.paid_sum
    
    await state.set_state(PaymentStates.entering_amount)
    await state.update_data(user_id=user_id, payment_from="user_list")
    
    await callback.message.answer(
        f"💰 <b>To'lash</b>\n\n"
        f"👤 {user.full_name}\n"
        f"To'lanishi kerak: <b>{format_number(to_pay)} UZS</b>\n\n"
        f"Miqdorni kiriting (UZS):",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("payment_amount:"))
async def prompt_payment_amount(callback: CallbackQuery, state: FSMContext):
    """Prompt for payment amount from order detail"""
    parts = callback.data.split(":")
    order_id = int(parts[1])
    user_id = int(parts[2])
    
    await state.set_state(PaymentStates.entering_amount)
    await state.update_data(order_id=order_id, user_id=user_id, payment_from="order_detail")
    
    await callback.message.answer(
        "💰 <b>To'lash summasi</b>\n\nUZS miqdorini kiriting:",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )
    await callback.answer()


@router.message(PaymentStates.entering_amount)
async def process_payment(message: Message, state: FSMContext, session: AsyncSession):
    """Process payment"""
    if message.text == "❌ Bekor qilish":
        data = await state.get_data()
        user_id = data.get("user_id")
        await state.clear()
        await message.answer("Bekor qilindi.")
        
        # Go back to user orders list
        if user_id:
            service = OrderService(session)
            user_orders = await service.get_user_orders_summary(user_id)
            if user_orders:
                await message.answer(
                    "👤 Buyurtmalarga qaytish uchun qayta /start ni bosing yoki tarixni tanlang.",
                    reply_markup=None,
                )
        return
    
    # Parse amount
    try:
        amount = float(message.text.strip())
        if amount <= 0:
            await message.answer("❌ Summasi musbat son bo'lishi kerak!")
            return
    except ValueError:
        await message.answer("❌ Noto'g'ri format! Raqam kiriting.")
        return
    
    data = await state.get_data()
    user_id = data["user_id"]
    payment_from = data.get("payment_from", "user_list")
    
    service = OrderService(session)
    
    # Add payment
    user = await service.add_payment(user_id, amount)
    
    if not user:
        await message.answer("❌ Foydalanuvchi topilmadi.", reply_markup=main_menu_keyboard())
        await state.clear()
        return
    
    # Get user's orders to show updated info
    user_orders = await service.get_user_orders_summary(user_id)
    total_sum = sum(order["total_sum"] for order in user_orders)
    
    await state.clear()
    await message.answer(
        f"✅ <b>To'lov muvaffaqiyatli saqlandi!</b>\n\n"
        f"👤 {user.full_name}\n"
        f"💰 To'langan summa: <b>{format_number(amount)} UZS</b>\n"
        f"Jami to'langan: <b>{format_number(user.paid_sum)} UZS</b>\n"
        f"To'lanishi kerak: <b>{format_number(total_sum - user.paid_sum)} UZS</b>",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard()
    )
