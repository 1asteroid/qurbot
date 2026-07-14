from datetime import datetime
from typing import List
from database.models import Order, OrderItem, OrderReturnItem


def format_number(value: float) -> str:
    """Format number with thousand separators."""
    return f"{value:,.0f}".replace(",", " ")


def format_quantity(value: float) -> str:
    """Format quantity without hiding decimal precision."""
    return f"{value:.2f}".rstrip("0").rstrip(".")


def format_phone(phone: str) -> str:
    """Normalize phone number display."""
    return phone.strip()


def _item_suffix(category_name: str, size: str) -> str:
    if not size:
        return ""
    if category_name == "travertin":
        return f" | Rang: {size}"
    if category_name == "tiya":
        return f" | Razmer: {size}"
    return f" | {size}"


def _item_extra_label(item: OrderItem) -> str:
    category_name = (item.product.category.name if item.product and item.product.category else "").strip().lower()
    return _item_suffix(category_name, item.size or "")


def _return_item_label(item: OrderReturnItem) -> str:
    category_name = (item.product.category.name if item.product and item.product.category else "").strip().lower()
    return _item_suffix(category_name, item.size or "")


def get_order_returned_total(order: Order) -> float:
    return sum((item.total_price or 0.0) for item in getattr(order, "return_items", []) or [])


def get_order_net_total(order: Order) -> float:
    return max(0.0, (order.total_sum or 0.0) - get_order_returned_total(order))


def get_order_item_returned_quantity(item: OrderItem) -> float:
    return sum((return_item.quantity or 0.0) for return_item in getattr(item, "return_items", []) or [])


def get_order_item_remaining_quantity(item: OrderItem) -> float:
    return max(0.0, (item.quantity or 0.0) - get_order_item_returned_quantity(item))


def order_has_returnable_items(order: Order) -> bool:
    return any(get_order_item_remaining_quantity(item) > 0 for item in order.items)


def build_return_items_text(order: Order) -> str:
    return_items = getattr(order, "return_items", []) or []
    if not return_items:
        return ""

    lines = []
    lines.append("↩️ <b>Qaytgan mahsulotlar</b>")
    lines.append("─" * 40)
    for item in return_items:
        name = item.product.name[:17]
        qty = format_quantity(item.quantity)
        price = format_number(item.price)
        total = format_number(item.total_price)
        lines.append(f"{name:<18} {qty:<8} {price:<10} {total}{_return_item_label(item)}")
    lines.append("─" * 40)
    lines.append(f"↩️ QAYTARILDI: {format_number(get_order_returned_total(order))} UZS")
    lines.append(f"💰 SOF JAMI: {format_number(get_order_net_total(order))} UZS")
    return "\n".join(lines)


def build_receipt(order: Order) -> str:
    """Build a clean text receipt from an Order object."""
    lines = []
    lines.append("═" * 40)
    lines.append(f"🧾 CHEK #{order.id}")
    lines.append(f"👤 Mijoz: {order.user.full_name}")
    lines.append(f"📱 Tel: {order.user.phone}")
    lines.append(f"📅 Sana: {order.created_at.strftime('%d.%m.%Y %H:%M')}")
    lines.append("─" * 40)
    lines.append(f"{'Mahsulot':<18} {'Miqdor':<8} {'Narx':<10} {'Jami'}")
    lines.append("─" * 40)

    for item in order.items:
        name = item.product.name[:17]
        qty = format_quantity(item.quantity)
        price = format_number(item.price)
        total = format_number(item.total_price)
        lines.append(f"{name:<18} {qty:<8} {price:<10} {total}{_item_extra_label(item)}")

    lines.append("═" * 40)
    lines.append(f"💰 JAMI: {format_number(order.total_sum)} UZS")
    return_text = build_return_items_text(order)
    if return_text:
        lines.append(return_text)
    lines.append("═" * 40)
    lines.append("✅ Buyurtma tasdiqlandi")
    return "\n".join(lines)


def build_receipt_with_status(order: Order) -> str:
    receipt_text = build_receipt(order)
    receipt_text += f"\n\n🔔 <b>Status:</b> {order.status}\n"
    if order.accepted_at:
        receipt_text += f"✅ <b>Qabul qilindi:</b> {order.accepted_at.strftime('%d.%m.%Y %H:%M')}\n"
    return receipt_text


def build_order_preview(items: List[dict], products_map: dict) -> str:
    """Build order preview text from FSM items."""
    lines = []
    lines.append("📋 <b>BUYURTMA KO'RIB CHIQISH</b>")
    lines.append("─" * 35)

    total = 0
    for i, item in enumerate(items, 1):
        product = products_map.get(item["product_id"])
        name = product.name if product else "Noma'lum"
        qty = item["quantity"]
        price = item["price"]
        t = item["total_price"]
        size = item.get("size")
        product_category = (product.category.name if product and getattr(product, "category", None) else "").strip().lower()
        total += t
        
        if size:
            if product_category == "travertin":
                size_text = f" | 🎨 {size}"
            elif product_category == "tiya":
                size_text = f" | 📏 {size}"
            else:
                size_text = f" | {size}"
        else:
            size_text = ""
        lines.append(
            f"{i}. <b>{name}</b>{size_text}\n"
            f"   {format_quantity(qty)} × {format_number(price)} = {format_number(t)} UZS"
        )

    lines.append("─" * 35)
    lines.append(f"💰 <b>JAMI: {format_number(total)} UZS</b>")
    return "\n".join(lines)


def format_order_list_item(order: Order, index: int) -> str:
    return (
        f"{index}. 👤 {order.user.full_name}\n"
        f"   💰 {format_number(get_order_net_total(order))} UZS\n"
        f"   📅 {order.created_at.strftime('%d.%m.%Y %H:%M')}"
    )
