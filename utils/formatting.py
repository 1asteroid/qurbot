from datetime import datetime
from typing import List
from database.models import Order, OrderItem


def format_number(value: float) -> str:
    """Format number with thousand separators."""
    return f"{value:,.0f}".replace(",", " ")


def format_phone(phone: str) -> str:
    """Normalize phone number display."""
    return phone.strip()


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
        qty = f"{item.quantity:.0f}"
        price = format_number(item.price)
        total = format_number(item.total_price)
        lines.append(f"{name:<18} {qty:<8} {price:<10} {total}")
        if item.size:
            lines.append(f"{'📏 Razmer:':<18} {item.size}")

    lines.append("═" * 40)
    lines.append(f"💰 JAMI: {format_number(order.total_sum)} UZS")
    lines.append("═" * 40)
    lines.append("✅ Buyurtma tasdiqlandi")
    return "\n".join(lines)


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
        total += t
        
        size_text = f" | 📏 {size}" if size else ""
        lines.append(
            f"{i}. <b>{name}</b>{size_text}\n"
            f"   {qty:.0f} × {format_number(price)} = {format_number(t)} UZS"
        )

    lines.append("─" * 35)
    lines.append(f"💰 <b>JAMI: {format_number(total)} UZS</b>")
    return "\n".join(lines)


def format_order_list_item(order: Order, index: int) -> str:
    return (
        f"{index}. 👤 {order.user.full_name}\n"
        f"   💰 {format_number(order.total_sum)} UZS\n"
        f"   📅 {order.created_at.strftime('%d.%m.%Y %H:%M')}"
    )
