import logging
from typing import Optional, List
from datetime import datetime, timedelta
from sqlalchemy import select, desc, func, extract
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from database.models import Order, OrderItem, Product, User
import pytz
from config import settings

logger = logging.getLogger(__name__)
TZ = pytz.timezone(settings.TIMEZONE)


class OrderService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_order(
        self,
        user_id: int,
        items: List[dict],  # [{product_id, quantity, price, total_price}]
        manager_id: Optional[int] = None,
    ) -> Order:
        total_sum = sum(item["total_price"] for item in items)
        order = Order(user_id=user_id, manager_id=manager_id, total_sum=total_sum, status="confirmed")
        self.session.add(order)
        await self.session.flush()  # get order.id

        for item_data in items:
            item = OrderItem(
                order_id=order.id,
                product_id=item_data["product_id"],
                quantity=item_data["quantity"],
                price=item_data["price"],
                total_price=item_data["total_price"],
            )
            self.session.add(item)

        await self.session.commit()
        await self.session.refresh(order)
        logger.info(f"Created order id={order.id} user_id={user_id} manager_id={manager_id} total={total_sum}")
        return order

    async def get_order_with_details(self, order_id: int) -> Optional[Order]:
        result = await self.session.execute(
            select(Order)
            .options(
                selectinload(Order.user),
                selectinload(Order.items).selectinload(OrderItem.product),
            )
            .where(Order.id == order_id)
        )
        return result.scalar_one_or_none()

    async def get_all_orders_paginated(self, page: int = 1, per_page: int = 10) -> tuple[List[Order], int]:
        count_result = await self.session.execute(select(func.count(Order.id)))
        total = count_result.scalar_one()

        result = await self.session.execute(
            select(Order)
            .options(
                selectinload(Order.user),
                selectinload(Order.items).selectinload(OrderItem.product),
            )
            .order_by(desc(Order.created_at))
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        orders = list(result.scalars().all())
        return orders, total

    async def get_daily_stats(self) -> dict:
        today = datetime.now(TZ).replace(tzinfo=None).date()
        today_start = datetime(today.year, today.month, today.day)

        result = await self.session.execute(
            select(func.count(Order.id), func.coalesce(func.sum(Order.total_sum), 0))
            .where(Order.created_at >= today_start)
            .where(Order.status == "confirmed")
        )
        row = result.one()
        return {"count": row[0], "total": row[1]}

    async def get_monthly_stats(self, year: int, month: int) -> dict:
        result = await self.session.execute(
            select(func.count(Order.id), func.coalesce(func.sum(Order.total_sum), 0))
            .where(extract("year", Order.created_at) == year)
            .where(extract("month", Order.created_at) == month)
            .where(Order.status == "confirmed")
        )
        row = result.one()
        return {"count": row[0], "total": row[1]}

    async def get_yearly_stats(self, year: int) -> dict:
        result = await self.session.execute(
            select(func.count(Order.id), func.coalesce(func.sum(Order.total_sum), 0))
            .where(extract("year", Order.created_at) == year)
            .where(Order.status == "confirmed")
        )
        row = result.one()
        return {"count": row[0], "total": row[1]}

    async def get_top_products(self, limit: int = 5) -> List[dict]:
        result = await self.session.execute(
            select(
                Product.name,
                Product.unit,
                func.sum(OrderItem.quantity).label("total_qty"),
                func.sum(OrderItem.total_price).label("total_revenue"),
            )
            .join(OrderItem, OrderItem.product_id == Product.id)
            .join(Order, Order.id == OrderItem.order_id)
            .where(Order.status == "confirmed")
            .group_by(Product.id, Product.name, Product.unit)
            .order_by(desc("total_revenue"))
            .limit(limit)
        )
        rows = result.all()
        return [
            {
                "name": row.name,
                "unit": row.unit,
                "total_qty": row.total_qty,
                "total_revenue": row.total_revenue,
            }
            for row in rows
        ]
