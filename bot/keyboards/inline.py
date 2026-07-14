import math
from typing import List, Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.models import User, Product, Order, Category
from utils.formatting import (
    format_quantity,
    get_order_item_remaining_quantity,
    get_order_net_total,
    order_has_returnable_items,
)


# ─── User selection ───────────────────────────────────────────────────────────

def users_keyboard(users: List[User], show_search: bool = True) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for user in users:
        builder.row(
            InlineKeyboardButton(
                text=f"👤 {user.full_name} | {user.phone}",
                callback_data=f"select_user:{user.id}",
            )
        )
    if show_search:
        builder.row(
            InlineKeyboardButton(text="🔍 Qidirish", callback_data="search_user")
        )
    builder.row(
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_order")
    )
    return builder.as_markup()


# ─── Product selection ────────────────────────────────────────────────────────

def category_switch_keyboard(
    categories: List[Category],
    callback_prefix: str,
    active_category_id: Optional[int] = None,
    back_callback: Optional[str] = None,
    back_text: str = "⬅️ Orqaga",
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for category in categories:
        mark = "✅ " if active_category_id == category.id else ""
        builder.button(
            text=f"{mark}{category.name}",
            callback_data=f"{callback_prefix}:{category.id}",
        )
    if categories:
        builder.adjust(2)
    if back_callback:
        builder.row(InlineKeyboardButton(text=back_text, callback_data=back_callback))
    return builder.as_markup()


def products_select_keyboard(
    products: List[Product],
    selected_ids: Optional[List[int]] = None,
    categories: Optional[List[Category]] = None,
    active_category_id: Optional[int] = None,
    category_callback_prefix: str = "select_category",
    back_callback: Optional[str] = None,
) -> InlineKeyboardMarkup:
    selected_ids = selected_ids or []
    builder = InlineKeyboardBuilder()
    if categories:
        for category in categories:
            mark = "✅ " if active_category_id == category.id else ""
            builder.button(
                text=f"📁 {mark}{category.name}",
                callback_data=f"{category_callback_prefix}:{category.id}",
            )
        builder.adjust(2)
    for product in products:
        mark = "✅ " if product.id in selected_ids else ""
        builder.row(
            InlineKeyboardButton(
                text=f"{mark}{product.name}",
                callback_data=f"add_product:{product.id}",
            )
        )
    builder.row(
        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="finish_products"),
        InlineKeyboardButton(text="❌ Bekor", callback_data="cancel_order"),
    )
    if back_callback:
        builder.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data=back_callback))
    return builder.as_markup()


def order_review_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="confirm_order"),
        InlineKeyboardButton(text="✏️ Tahrirlash", callback_data="edit_order"),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_order"),
    )
    return builder.as_markup()


# ─── Product CRUD ─────────────────────────────────────────────────────────────

def products_list_keyboard(
    products: List[Product],
    categories: Optional[List[Category]] = None,
    active_category_id: Optional[int] = None,
    category_callback_prefix: str = "products_category",
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if categories:
        for category in categories:
            mark = "✅ " if active_category_id == category.id else ""
            builder.button(
                text=f"📁 {mark}{category.name}",
                callback_data=f"{category_callback_prefix}:{category.id}",
            )
        builder.adjust(2)
    for product in products:
        builder.row(
            InlineKeyboardButton(
                text=f"📦 {product.name}",
                callback_data=f"product_detail:{product.id}",
            )
        )
    builder.row(
        InlineKeyboardButton(text="➕ Mahsulot qo'shish", callback_data="add_product_start")
    )
    return builder.as_markup()


def product_detail_keyboard(product_id: int, back_callback: Optional[str] = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✏️ Tahrirlash", callback_data=f"edit_product:{product_id}"),
        InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"delete_product:{product_id}"),
    )
    builder.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data=back_callback or "back_to_products"))
    return builder.as_markup()


def order_receipt_keyboard(
    order_id: int,
    can_accept: bool = False,
    back_callback: str = "my_orders",
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if can_accept:
        builder.row(
            InlineKeyboardButton(text="✅ Buyurtmani qabul qildim", callback_data=f"accept_order:{order_id}")
        )
    builder.row(
        InlineKeyboardButton(text="📄 PDF olish", callback_data=f"download_receipt_pdf:{order_id}")
    )
    builder.row(
        InlineKeyboardButton(text="⬅️ Orqaga", callback_data=back_callback)
    )
    return builder.as_markup()


def unit_keyboard(units: Optional[List[str]] = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    available_units = units or ["kg", "chelak", "dona", "metr"]
    for unit in available_units:
        builder.button(text=unit, callback_data=f"unit:{unit}")
    builder.adjust(3)
    builder.row(
        InlineKeyboardButton(text="❌ Bekor", callback_data="cancel_product")
    )
    return builder.as_markup()


# ─── Manager Orders ───────────────────────────────────────────────────────────

def manager_orders_keyboard(orders: List[Order], page: int, total: int, per_page: int = 10) -> InlineKeyboardMarkup:
    """Keyboard for manager's inline orders view with pagination"""
    builder = InlineKeyboardBuilder()
    
    for order in orders:
        # Format: Order #123 - Customer Name - Total UZS
        from utils import format_number
        status_mark = "✅" if order.status == "accepted" else "⏳"
        status_text = "Qabul qilingan" if order.status == "accepted" else "Qabul qilinmagan"
        text = f"{status_mark} #{order.id} - {order.user.full_name} ({format_number(get_order_net_total(order))} UZS) | {status_text}"
        builder.row(
            InlineKeyboardButton(text=text, callback_data=f"manager_order_detail:{order.id}")
        )
    
    # Pagination buttons
    total_pages = math.ceil(total / per_page)
    nav_buttons = []
    
    if page > 1:
        nav_buttons.append(
            InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"manager_orders_page:{page - 1}")
        )
    
    if page < total_pages:
        nav_buttons.append(
            InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"manager_orders_page:{page + 1}")
        )
    
    if nav_buttons:
        builder.row(*nav_buttons)
    
    # Show page info
    builder.row(
        InlineKeyboardButton(text=f"📄 Sahifa {page}/{total_pages}", callback_data="noop")
    )
    
    builder.row(
        InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_main_menu")
    )
    
    return builder.as_markup()


def manager_order_detail_keyboard(order_id: int, status: str, can_delete: bool = False) -> InlineKeyboardMarkup:
    """Keyboard for viewing manager order details"""
    builder = InlineKeyboardBuilder()
    if status == "accepted":
        builder.row(
            InlineKeyboardButton(text="⏳ Qabul qilinmagan qilish", callback_data=f"manager_toggle_accept:{order_id}")
        )
    else:
        builder.row(
            InlineKeyboardButton(text="✅ Qabul qilingan qilish", callback_data=f"manager_toggle_accept:{order_id}")
        )
        builder.row(
            InlineKeyboardButton(text="✏️ Buyurtmani tahrirlash", callback_data=f"edit_pending_order:{order_id}")
        )
    if can_delete:
        builder.row(
            InlineKeyboardButton(text="🗑 Buyurtmani o'chirish", callback_data=f"delete_order:{order_id}")
        )
    builder.row(
        InlineKeyboardButton(text="📋 Buyurtmalarim", callback_data="manager_orders_list")
    )
    builder.row(
        InlineKeyboardButton(text="🏠 Asosiy sahifa", callback_data="back_to_main_menu")
    )
    return builder.as_markup()


def confirm_order_delete_keyboard(order_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Ha, o'chirish", callback_data=f"confirm_delete_order:{order_id}"),
        InlineKeyboardButton(text="❌ Yo'q", callback_data=f"manager_order_detail:{order_id}"),
    )
    return builder.as_markup()


def confirm_delete_keyboard(product_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Ha, o'chirish", callback_data=f"confirm_delete:{product_id}"),
        InlineKeyboardButton(text="❌ Yo'q", callback_data=f"product_detail:{product_id}"),
    )
    return builder.as_markup()


# ─── Order history pagination ─────────────────────────────────────────────────

def order_history_keyboard(page: int, total: int, per_page: int = 10) -> InlineKeyboardMarkup:
    total_pages = max(1, math.ceil(total / per_page))
    builder = InlineKeyboardBuilder()
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"orders_page:{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        nav.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"orders_page:{page + 1}"))
    builder.row(*nav)
    return builder.as_markup()


def order_detail_keyboard(order_id: int, page: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"orders_page:{page}")
    )
    return builder.as_markup()


# ─── Monitoring ───────────────────────────────────────────────────────────────

def monitoring_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📅 Bugungi", callback_data="stats:daily"),
        InlineKeyboardButton(text="📆 Oy", callback_data="stats:monthly"),
    )
    builder.row(
        InlineKeyboardButton(text="📊 Yillik", callback_data="stats:yearly"),
        InlineKeyboardButton(text="🗓 Boshqa oy", callback_data="stats:custom"),
    )
    builder.row(
        InlineKeyboardButton(text="🏆 Top mahsulotlar", callback_data="stats:top_products")
    )
    builder.row(
        InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_main_menu")
    )
    return builder.as_markup()


def monitoring_report_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for monitoring reports with PDF download"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💾 PDF yuklash", callback_data="download_report_pdf")
    )
    builder.row(
        InlineKeyboardButton(text="⬅️ Orqaga", callback_data="stats:menu")
    )
    return builder.as_markup()


# ─── Order History Grouped by Users ──────────────────────────────────────────

def history_users_list_keyboard(users_data: List[dict]) -> InlineKeyboardMarkup:
    """Keyboard for showing users with their order counts and totals"""
    from utils import format_number
    builder = InlineKeyboardBuilder()
    
    for user_info in users_data:
        user = user_info["user"]
        order_count = user_info["order_count"]
        total_amount = user_info["total_amount"]
        text = f"👤 {user.full_name} | {order_count} ta buyurtma | {format_number(total_amount)} UZS"
        builder.row(
            InlineKeyboardButton(text=text, callback_data=f"history_user:{user.id}")
        )
    
    builder.row(
        InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_main_menu")
    )
    return builder.as_markup()


def history_user_orders_keyboard(user_id: int, user_orders: List[dict]) -> InlineKeyboardMarkup:
    """Keyboard for showing specific user's orders"""
    from utils import format_number
    builder = InlineKeyboardBuilder()
    
    for order_info in user_orders:
        order = order_info["order"]
        item_count = order_info["item_count"]
        created_at = order_info["created_at"]
        total_sum = order_info["total_sum"]
        date_str = created_at.strftime('%d.%m.%Y %H:%M')
        text = f"📦 {date_str} | {item_count} ta mahsulot | {format_number(total_sum)} UZS"
        builder.row(
            InlineKeyboardButton(text=text, callback_data=f"history_order_detail:{order.id}:{user_id}")
        )
    
    builder.row(
        InlineKeyboardButton(text="💰 To'lash", callback_data=f"payment_user:{user_id}")
    )
    builder.row(
        InlineKeyboardButton(text="📄 Barcha buyurtmalar PDF", callback_data=f"history_user_pdf:{user_id}")
    )
    builder.row(
        InlineKeyboardButton(text="⬅️ Orqaga", callback_data="history_users_list")
    )
    return builder.as_markup()


def _return_item_button_label(item) -> str:
    from utils import format_number

    item_name = item.product.name[:18]
    category_name = (
        item.product.category.name if item.product and item.product.category else ""
    ).strip().lower()
    if item.size:
        if category_name == "travertin":
            item_name = f"{item_name} | Rang: {item.size}"
        elif category_name == "tiya":
            item_name = f"{item_name} | Razmer: {item.size}"
        else:
            item_name = f"{item_name} | {item.size}"
    return item_name


def history_return_items_keyboard(order: Order, user_id: int = None) -> InlineKeyboardMarkup:
    """Keyboard for selecting order items to return."""
    builder = InlineKeyboardBuilder()

    for item in order.items:
        remaining_qty = get_order_item_remaining_quantity(item)
        item_name = _return_item_button_label(item)
        if remaining_qty > 0:
            button_text = f"📦 {item_name} ({format_quantity(remaining_qty)}/{format_quantity(item.quantity)})"
            callback_data = f"return_item:{order.id}:{item.id}"
        else:
            button_text = f"✅ {item_name} (qaytarildi)"
            callback_data = "noop"
        builder.row(
            InlineKeyboardButton(text=button_text, callback_data=callback_data)
        )

    back_callback = (
        f"history_order_detail:{order.id}:{user_id}"
        if user_id
        else f"history_order_detail:{order.id}"
    )
    builder.row(
        InlineKeyboardButton(text="⬅️ Buyurtmaga qaytish", callback_data=back_callback)
    )
    return builder.as_markup()


def history_order_detail_keyboard(
    order: Order,
    user_id: int = None,
    can_edit: bool = False,
    can_return: bool = False,
) -> InlineKeyboardMarkup:
    """Keyboard for showing order details in history with return actions."""
    builder = InlineKeyboardBuilder()
    if can_edit:
        builder.row(
            InlineKeyboardButton(text="✏️ Buyurtmani tahrirlash", callback_data=f"edit_pending_order:{order.id}")
        )

    if can_return and order_has_returnable_items(order):
        return_callback = (
            f"return_menu:{order.id}:{user_id}"
            if user_id
            else f"return_menu:{order.id}"
        )
        builder.row(
            InlineKeyboardButton(text="↩️ Qaytgan maxsulotlar", callback_data=return_callback)
        )

    builder.row(
        InlineKeyboardButton(text="📄 PDF olish", callback_data=f"history_order_pdf:{order.id}")
    )
    back_callback = f"history_user:{user_id}" if user_id else "history_users_list"
    builder.row(
        InlineKeyboardButton(text="⬅️ Orqaga", callback_data=back_callback)
    )
    return builder.as_markup()
