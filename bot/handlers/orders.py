import logging
from typing import List
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from bot.states import OrderStates
from bot.keyboards import (
    users_keyboard,
    category_switch_keyboard,
    products_select_keyboard,
    order_review_keyboard,
    order_receipt_keyboard,
    main_menu_keyboard,
    cancel_keyboard,
)
from services import UserService, ProductService, OrderService
from utils import build_receipt, build_order_preview, generate_receipt_pdf, format_number

logger = logging.getLogger(__name__)
router = Router()


# ─── Helper ───────────────────────────────────────────────────────────────────

async def _get_products_map(session: AsyncSession) -> dict:
    service = ProductService(session)
    products = await service.get_all()
    return {p.id: p for p in products}


def _build_selection_summary(order_items: List[dict], products_map: dict) -> str:
    if not order_items:
        return ""

    lines = ["🧾 <b>Tanlangan mahsulotlar:</b>"]
    total_sum = 0.0
    for item in order_items:
        product = products_map.get(item["product_id"])
        name = product.name if product else "Noma'lum"
        line_total = item["total_price"]
        total_sum += line_total
        size = item.get("size")
        size_text = f" | 📏 {size}" if size else ""
        lines.append(
            f"• {name}{size_text}: {item['quantity']:.0f} × {format_number(item['price'])} = {format_number(line_total)} UZS"
        )
    lines.append(f"💰 <b>Jami: {format_number(total_sum)} UZS</b>")
    return "\n".join(lines)


# ─── Step 1: Select user ──────────────────────────────────────────────────────

@router.message(F.text == "🧾 Buyurtma yaratish")
async def start_order(message: Message, state: FSMContext, session: AsyncSession, is_manager: bool):
    # Database'dan manager tekshiruvi
    user_service = UserService(session)
    user = await user_service.get_by_telegram_id(message.from_user.id)
    
    if not user or not user.is_manager:
        await message.answer("❌ Sizda bu buyruqqa kirish huquqi yo'q.")
        return

    await state.clear()
    users = await user_service.get_all_latest(limit=20)

    if not users:
        await message.answer("❌ Tizimda hech qanday foydalanuvchi yo'q.")
        return

    await state.set_state(OrderStates.selecting_user)
    await message.answer(
        "👥 <b>Mijozni tanlang</b>\n\nSo'nggi ro'yxatdan o'tganlar:",
        parse_mode="HTML",
        reply_markup=users_keyboard(users),
    )


@router.callback_query(OrderStates.selecting_user, F.data.startswith("select_user:"))
async def select_user(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    user_id = int(callback.data.split(":")[1])
    service = UserService(session)
    user = await service.get_by_id(user_id)

    if not user:
        await callback.answer("❌ Foydalanuvchi topilmadi.", show_alert=True)
        return

    await state.update_data(selected_user_id=user_id, order_items=[])
    # Show categories first for manager to pick
    await state.set_state(OrderStates.selecting_category)
    prod_service = ProductService(session)
    categories = await prod_service.get_all_categories()

    if not categories:
        await callback.message.edit_text("❌ Mahsulotlar kategoriyalari mavjud emas. Avval kategoriya va mahsulot qo'shing.")
        return

    await callback.message.edit_text(
        f"👤 Mijoz: <b>{user.full_name}</b>\n\n"
        f"📂 <b>Mahsulot kategoriyasini tanlang</b>:",
        parse_mode="HTML",
        reply_markup=category_switch_keyboard(categories, callback_prefix="select_category", back_callback="cancel_order"),
    )
    await callback.answer()


# ─── User search ──────────────────────────────────────────────────────────────

@router.callback_query(OrderStates.selecting_user, F.data == "search_user")
async def prompt_user_search(callback: CallbackQuery, state: FSMContext):
    await state.set_state(OrderStates.searching_user)
    await callback.message.answer(
        "🔍 Ism yoki telefon raqamni kiriting:",
        reply_markup=cancel_keyboard(),
    )
    await callback.answer()


@router.message(OrderStates.searching_user)
async def search_user(message: Message, state: FSMContext, session: AsyncSession):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=main_menu_keyboard())
        return

    query = message.text.strip()
    service = UserService(session)
    users = await service.search(query)

    await state.set_state(OrderStates.selecting_user)

    if not users:
        await message.answer(
            f"🔍 '<b>{query}</b>' bo'yicha hech kim topilmadi.\n\nBoshqatdan urinib ko'ring:",
            parse_mode="HTML",
            reply_markup=users_keyboard([], show_search=True),
        )
        return

    await message.answer(
        f"🔍 <b>{len(users)} ta natija topildi:</b>",
        parse_mode="HTML",
        reply_markup=users_keyboard(users),
    )


# ─── Step 2: Add products ─────────────────────────────────────────────────────

@router.callback_query(OrderStates.selecting_product, F.data.startswith("add_product:"))
async def add_product_to_order(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    product_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    order_items: List[dict] = data.get("order_items", [])

    # Check if product is already being edited (pending)
    pending = data.get("pending_product_id")
    if pending:
        await callback.answer("❗ Avval joriy mahsulot miqdorini kiriting!", show_alert=True)
        return

    prod_service = ProductService(session)
    product = await prod_service.get_by_id(product_id)
    if not product:
        await callback.answer("❌ Mahsulot topilmadi.", show_alert=True)
        return

    category_name = (product.category.name if product.category else "").strip().lower()

    # Allow adding same product multiple times with different sizes/quantities
    await state.update_data(
        pending_product_id=product_id,
        pending_product_category=category_name,
    )
    await state.set_state(OrderStates.entering_quantity)

    await callback.message.answer(
        f"📦 <b>{product.name}</b>\n\n"
        f"Miqdorni kiriting ({product.unit}):",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )
    
    await callback.answer()


@router.callback_query(OrderStates.selecting_category, F.data.startswith("select_category:"))
async def select_category(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    category_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    selected_user_id = data.get("selected_user_id")
    if not selected_user_id:
        await callback.answer("❌ Mijoz tanlanmagan.", show_alert=True)
        return

    user_service = UserService(session)
    user = await user_service.get_by_id(selected_user_id)
    if not user:
        await callback.answer("❌ Foydalanuvchi topilmadi.", show_alert=True)
        return

    order_items: List[dict] = data.get("order_items", [])

    await state.update_data(selected_category_id=category_id)
    await state.set_state(OrderStates.selecting_product)
    prod_service = ProductService(session)
    categories = await prod_service.get_all_categories()
    products = await prod_service.get_by_category(category_id)
    products_map = await _get_products_map(session)
    summary_text = _build_selection_summary(order_items, products_map)

    if not products:
        await callback.message.edit_text("❌ Ushbu kategoriyada mahsulot topilmadi.")
        return

    await callback.message.edit_text(
        f"👤 Mijoz: <b>{user.full_name}</b>\n\n"
        f"{summary_text}\n\n"
        f"📦 <b>Mahsulotlarni tanlang</b> (bir nechta tanlash mumkin):",
        parse_mode="HTML",
        reply_markup=products_select_keyboard(
            products,
            [item["product_id"] for item in order_items],
            categories=categories,
            active_category_id=category_id,
            category_callback_prefix="select_category",
            back_callback="back_to_category_select",
        ),
    )
    await callback.answer()


@router.callback_query(OrderStates.selecting_product, F.data.startswith("select_category:"))
async def switch_order_category(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    category_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    selected_user_id = data.get("selected_user_id")
    if not selected_user_id:
        await callback.answer("❌ Mijoz tanlanmagan.", show_alert=True)
        return

    user_service = UserService(session)
    user = await user_service.get_by_id(selected_user_id)
    if not user:
        await callback.answer("❌ Foydalanuvchi topilmadi.", show_alert=True)
        return

    prod_service = ProductService(session)
    categories = await prod_service.get_all_categories()
    products = await prod_service.get_by_category(category_id)
    order_items: List[dict] = data.get("order_items", [])
    products_map = await _get_products_map(session)
    summary_text = _build_selection_summary(order_items, products_map)

    await state.update_data(selected_category_id=category_id)
    await callback.message.edit_text(
        f"👤 Mijoz: <b>{user.full_name}</b>\n\n"
        f"{summary_text}\n\n"
        f"📦 <b>Mahsulotlarni tanlang</b> (bir nechta tanlash mumkin):",
        parse_mode="HTML",
        reply_markup=products_select_keyboard(
            products,
            [item["product_id"] for item in order_items],
            categories=categories,
            active_category_id=category_id,
            category_callback_prefix="select_category",
            back_callback="back_to_category_select",
        ),
    )
    await callback.answer()


@router.callback_query(F.data == "back_to_category_select")
async def back_to_category_select(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    selected_user_id = data.get("selected_user_id")
    if not selected_user_id:
        await callback.answer("❌ Mijoz tanlanmagan.", show_alert=True)
        return

    user_service = UserService(session)
    user = await user_service.get_by_id(selected_user_id)
    prod_service = ProductService(session)
    categories = await prod_service.get_all_categories()
    await state.set_state(OrderStates.selecting_category)

    await callback.message.edit_text(
        f"👤 Mijoz: <b>{user.full_name}</b>\n\n📂 <b>Mahsulot kategoriyasini tanlang</b>:",
        parse_mode="HTML",
        reply_markup=category_switch_keyboard(categories, callback_prefix="select_category", active_category_id=data.get("selected_category_id"), back_callback="cancel_order"),
    )
    await callback.answer()


@router.message(OrderStates.entering_quantity)
async def process_quantity(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.update_data(pending_product_id=None, pending_product_category=None, pending_item_index=None)
        await state.set_state(OrderStates.selecting_product)
        await message.answer("Mahsulot bekor qilindi.", reply_markup=main_menu_keyboard())
        return

    try:
        qty = float(message.text.replace(",", ".").strip())
        if qty <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❗ Iltimos, to'g'ri miqdor kiriting (masalan: 5 yoki 2.5).")
        return

    data = await state.get_data()
    category_name = (data.get("pending_product_category") or "").strip().lower()

    await state.update_data(pending_quantity=qty)

    if category_name == "lak":
        await state.update_data(pending_size=None)
        await state.set_state(OrderStates.entering_price)
        await message.answer(
            "💰 Narxni kiriting (UZS, 1 birlik uchun):",
            reply_markup=cancel_keyboard(),
        )
        return

    await state.set_state(OrderStates.entering_size)
    if category_name == "travertin":
        prompt_text = "🎨 Rangni kiriting (majburiy):"
    else:
        prompt_text = "📏 Razmerni kiriting (majburiy, masalan: 10x20, M, katta):"

    await message.answer(
        prompt_text,
        reply_markup=cancel_keyboard(),
    )


@router.message(OrderStates.entering_size)
async def process_size(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.update_data(pending_product_id=None, pending_quantity=None, pending_product_category=None)
        await state.set_state(OrderStates.selecting_product)
        await message.answer("Bekor qilindi.", reply_markup=main_menu_keyboard())
        return

    size = (message.text or "").strip()
    if not size:
        await message.answer("❗ Iltimos, qiymat kiriting. Bu maydon bo'sh bo'lishi mumkin emas.")
        return

    await state.update_data(pending_size=size)
    await state.set_state(OrderStates.entering_price)
    await message.answer(
        "💰 Narxni kiriting (UZS, 1 birlik uchun):",
        reply_markup=cancel_keyboard(),
    )


@router.message(OrderStates.entering_price)
async def process_price(message: Message, state: FSMContext, session: AsyncSession):
    if message.text == "❌ Bekor qilish":
        await state.update_data(pending_product_id=None, pending_quantity=None, pending_size=None, pending_product_category=None, pending_item_index=None)
        await state.set_state(OrderStates.selecting_product)
        await message.answer("Bekor qilindi.", reply_markup=main_menu_keyboard())
        return

    try:
        price = float(message.text.replace(",", ".").replace(" ", "").strip())
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❗ Iltimos, to'g'ri narx kiriting (masalan: 50000).")
        return

    data = await state.get_data()
    product_id = data["pending_product_id"]
    quantity = data["pending_quantity"]
    size = data.get("pending_size")
    category_name = (data.get("pending_product_category") or "").strip().lower()
    item_index = data.get("pending_item_index")  # Agar mavjud bo'lsa - o'zgartirilayapti
    total_price = quantity * price

    order_items: List[dict] = data.get("order_items", [])
    
    if item_index is not None:
        # O'zgartirilayapti
        order_items[item_index] = {
            "product_id": product_id,
            "quantity": quantity,
            "price": price,
            "total_price": total_price,
            "size": None if category_name == "lak" else size,
        }
        action_text = "✅ Mahsulot o'zgartirildi!"
    else:
        # Yangi qo'shilayapti - same product can be added multiple times with different sizes
        order_items.append({
            "product_id": product_id,
            "quantity": quantity,
            "price": price,
            "total_price": total_price,
            "size": None if category_name == "lak" else size,
        })
        action_text = "✅ Mahsulot qo'shildi!"

    await state.update_data(
        order_items=order_items,
        pending_product_id=None,
        pending_quantity=None,
        pending_size=None,
        pending_product_category=None,
        pending_item_index=None,
    )
    await state.set_state(OrderStates.selecting_product)

    prod_service = ProductService(session)
    categories = await prod_service.get_all_categories()
    selected_category_id = data.get("selected_category_id")
    if selected_category_id:
        products = await prod_service.get_by_category(selected_category_id)
    else:
        products = await prod_service.get_all()
    selected_ids = [item["product_id"] for item in order_items]
    products_map = await _get_products_map(session)
    summary_text = _build_selection_summary(order_items, products_map)
    user = await UserService(session).get_by_id(data["selected_user_id"])
    customer_name = user.full_name if user else "Noma'lum"
    
    if category_name == "travertin" and size:
        size_text = f" | Rang: {size}"
    elif category_name == "tiya" and size:
        size_text = f" | Razmer: {size}"
    else:
        size_text = ""

    await message.answer(
        f"👤 Mijoz: <b>{customer_name}</b>\n\n"
        f"{action_text}\n"
        f"💰 {quantity:.0f} × {format_number(price)} = {format_number(total_price)} UZS{size_text}\n\n"
        f"{summary_text}\n\n"
        f"📦 <b>Mahsulotlarni tanlang</b> (bir nechta tanlash mumkin):",
        parse_mode="HTML",
        reply_markup=products_select_keyboard(
            products,
            selected_ids,
            categories=categories,
            active_category_id=selected_category_id,
            category_callback_prefix="select_category",
            back_callback="back_to_category_select",
        ),
    )


# ─── Step 3: Review and confirm ───────────────────────────────────────────────

@router.callback_query(OrderStates.selecting_product, F.data == "finish_products")
async def finish_product_selection(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    order_items: List[dict] = data.get("order_items", [])

    if not order_items:
        await callback.answer("❗ Kamida bitta mahsulot tanlang!", show_alert=True)
        return

    products_map = await _get_products_map(session)
    preview_text = build_order_preview(order_items, products_map)

    await state.set_state(OrderStates.reviewing_order)
    await callback.message.edit_text(
        preview_text,
        parse_mode="HTML",
        reply_markup=order_review_keyboard(),
    )
    await callback.answer()


@router.callback_query(OrderStates.reviewing_order, F.data == "confirm_order")
async def confirm_order(callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot):
    data = await state.get_data()
    user_id = data["selected_user_id"]
    order_items: List[dict] = data.get("order_items", [])
    
    # Manager ID olinadi
    manager_user = await UserService(session).get_by_telegram_id(callback.from_user.id)
    manager_id = manager_user.id if manager_user else None

    order_service = OrderService(session)
    order = await order_service.create_order(user_id=user_id, items=order_items, manager_id=manager_id)

    # Load full order with relations
    full_order = await order_service.get_order_with_details(order.id)
    receipt_text = build_receipt(full_order)

    # Send receipt to client (text)
    try:
        await bot.send_message(
            chat_id=full_order.user.telegram_id,
            text=f"<pre>{receipt_text}</pre>",
            parse_mode="HTML",
            reply_markup=order_receipt_keyboard(
                full_order.id,
                can_accept=full_order.status == "pending",
                back_callback="my_orders",
            ),
        )
        
        # Send PDF receipt
        from aiogram.types import FSInputFile, BufferedInputFile
        pdf_buffer = generate_receipt_pdf(full_order)
        pdf_data = pdf_buffer.getvalue()
        
        await bot.send_document(
            chat_id=full_order.user.telegram_id,
            document=BufferedInputFile(pdf_data, filename=f"chek_{full_order.id}.pdf"),
            caption=f"📄 Chek #{full_order.id}"
        )
        client_notified = True
    except Exception as e:
        logger.warning(f"Could not notify client {full_order.user.telegram_id}: {e}")
        client_notified = False

    await state.clear()

    # Notify manager
    status_text = "✅ Chek mijozga yuborildi." if client_notified else "⚠️ Mijozga yuborib bo'lmadi."
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🏠 Asosiy menyuga qaytish", callback_data="back_to_main_menu")
    )
    
    await callback.message.edit_text(
        f"✅ <b>Buyurtma #{full_order.id} tasdiqlandi!</b>\n\n"
        f"<pre>{receipt_text}</pre>\n\n"
        f"{status_text}",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await callback.answer("✅ Buyurtma saqlandi!")


@router.callback_query(OrderStates.reviewing_order, F.data == "edit_order")
async def edit_order(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    await state.set_state(OrderStates.selecting_product)
    data = await state.get_data()
    order_items: List[dict] = data.get("order_items", [])
    selected_ids = [item["product_id"] for item in order_items]

    prod_service = ProductService(session)
    categories = await prod_service.get_all_categories()
    selected_category_id = data.get("selected_category_id")
    if selected_category_id:
        products = await prod_service.get_by_category(selected_category_id)
    else:
        products = await prod_service.get_all()

    await callback.message.edit_text(
        "✏️ <b>Mahsulotlarni tahrirlash</b>\n\nMahsulotni qayta tanlang:",
        parse_mode="HTML",
        reply_markup=products_select_keyboard(
            products,
            selected_ids,
            categories=categories,
            active_category_id=selected_category_id,
            category_callback_prefix="select_category",
            back_callback="back_to_category_select",
        ),
    )
    await callback.answer()


@router.message(OrderStates.reviewing_order, F.text == "❌ Bekor qilish")
async def cancel_order_from_message(message: Message, state: FSMContext):
    """Buyurtmani text button orqali bekor qilish"""
    await state.clear()
    await message.answer(
        "❌ <b>Buyurtma bekor qilindi</b>",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard()
    )


@router.callback_query(F.data == "cancel_order")
async def cancel_order(callback: CallbackQuery, state: FSMContext):
    """Buyurtmani bekor qilish - barcha states'dan (inline orqali)"""
    await state.clear()
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🏠 Asosiy menyuga qaytish", callback_data="back_to_main_menu")
    )
    
    await callback.message.edit_text(
        "❌ <b>Buyurtma bekor qilindi</b>\n\nAsosiy menyuga qaytish:",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await callback.answer("Bekor qilindi.")


@router.callback_query(F.data == "back_to_main_menu")
async def back_to_main_menu(callback: CallbackQuery, state: FSMContext):
    """Asosiy menyuga qaytish"""
    await state.clear()
    await callback.message.delete()
    await callback.message.bot.send_message(
        chat_id=callback.from_user.id,
        text="👋 <b>Asosiy menyu</b>",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard()
    )
    await callback.answer()
