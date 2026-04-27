import math
from typing import List, Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.models import User, Product, Order


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

def products_select_keyboard(
    products: List[Product],
    selected_ids: Optional[List[int]] = None,
) -> InlineKeyboardMarkup:
    selected_ids = selected_ids or []
    builder = InlineKeyboardBuilder()
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

def products_list_keyboard(products: List[Product]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
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


def product_detail_keyboard(product_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✏️ Tahrirlash", callback_data=f"edit_product:{product_id}"),
        InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"delete_product:{product_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_products")
    )
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
    return builder.as_markup()
