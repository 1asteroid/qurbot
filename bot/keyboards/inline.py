import math
from typing import List, Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.models import User, Product, Order, Category


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
                text=f"{mark}{category.name}",
                callback_data=f"{category_callback_prefix}:{category.id}",
            )
        builder.adjust(2)
    for product in products:
        mark = "✅ " if product.id in selected_ids else ""
        builder.row(
            InlineKeyboardButton(
                text=f"{mark}{product.name} ({product.unit})",
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
                text=f"{mark}{category.name}",
                callback_data=f"{category_callback_prefix}:{category.id}",
            )
        builder.adjust(2)
    for product in products:
        builder.row(
            InlineKeyboardButton(
                text=f"📦 {product.name} ({product.unit})",
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


def unit_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for unit in ["kg", "dona", "metr", "litr", "qop"]:
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
        text = f"🧾 #{order.id} - {order.user.full_name} ({format_number(order.total_sum)} UZS)"
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


def manager_order_detail_keyboard(order_id: int) -> InlineKeyboardMarkup:
    """Keyboard for viewing manager order details"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📋 Buyurtmalarim", callback_data="manager_orders_list")
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
