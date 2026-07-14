import logging
from typing import Optional, List
from datetime import datetime, timedelta
from sqlalchemy import select, desc, func, extract
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from database.models import Order, OrderItem, OrderReturnItem, Product, User, now_tashkent
import pytz
from config import settings

logger = logging.getLogger(__name__)
TZ = pytz.timezone(settings.TIMEZONE)


class OrderService:
    def __init__(self, session: AsyncSession):
        self.session = session

    def _order_return_total_expr(self):
        return (
            select(func.coalesce(func.sum(OrderReturnItem.total_price), 0))
            .where(OrderReturnItem.order_id == Order.id)
            .correlate(Order)
            .scalar_subquery()
        )

    def _order_net_total_expr(self):
        return Order.total_sum - self._order_return_total_expr()

    async def create_order(
        self,
        user_id: int,
        items: List[dict],  # [{product_id, quantity, price, total_price, size}]
        manager_id: Optional[int] = None,
    ) -> Order:
        total_sum = sum(item["total_price"] for item in items)
        order = Order(user_id=user_id, manager_id=manager_id, total_sum=total_sum, status="pending")
        self.session.add(order)
        await self.session.flush()  # get order.id

        for item_data in items:
            item = OrderItem(
                order_id=order.id,
                product_id=item_data["product_id"],
                quantity=item_data["quantity"],
                price=item_data["price"],
                total_price=item_data["total_price"],
                size=item_data.get("size"),
            )
            self.session.add(item)

        # Update user's total_purchase_sum
        user = await self._get_user_by_id(user_id)
        if user:
            user.total_purchase_sum += total_sum
            self.session.add(user)

        await self.session.commit()
        await self.session.refresh(order)
        logger.info(f"Created order id={order.id} user_id={user_id} manager_id={manager_id} total={total_sum}")
        return order

    async def update_pending_order(
        self,
        order_id: int,
        items: List[dict],
        manager_id: Optional[int] = None,
    ) -> Order:
        order = await self.get_order_with_details(order_id)
        if not order:
            raise ValueError("Order not found")
        if order.status != "pending":
            raise ValueError("Only pending orders can be edited")

        old_total = order.total_sum or 0.0
        old_returned_total = sum((item.total_price or 0.0) for item in order.return_items or [])
        old_net_total = max(0.0, old_total - old_returned_total)
        new_total = sum(item["total_price"] for item in items)

        order.items.clear()
        order.return_items.clear()
        order.total_sum = new_total
        order.status = "pending"
        order.accepted_at = None
        if manager_id is not None:
            order.manager_id = manager_id

        for item_data in items:
            order.items.append(
                OrderItem(
                    product_id=item_data["product_id"],
                    quantity=item_data["quantity"],
                    price=item_data["price"],
                    total_price=item_data["total_price"],
                    size=item_data.get("size"),
                )
            )

        user = await self._get_user_by_id(order.user_id)
        if user:
            user.total_purchase_sum += new_total - old_net_total
            self.session.add(user)

        self.session.add(order)
        await self.session.commit()
        await self.session.refresh(order)
        logger.info(f"Updated pending order id={order.id} total={new_total}")
        return order

    async def get_order_with_details(self, order_id: int) -> Optional[Order]:
        result = await self.session.execute(
            select(Order)
            .options(
                selectinload(Order.user),
                selectinload(Order.items)
                .selectinload(OrderItem.product)
                .selectinload(Product.category),
                selectinload(Order.items).selectinload(OrderItem.return_items),
                selectinload(Order.return_items)
                .selectinload(OrderReturnItem.product)
                .selectinload(Product.category),
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
                selectinload(Order.items)
                .selectinload(OrderItem.product)
                .selectinload(Product.category),
                selectinload(Order.items).selectinload(OrderItem.return_items),
                selectinload(Order.return_items)
                .selectinload(OrderReturnItem.product)
                .selectinload(Product.category),
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
            select(func.count(Order.id), func.coalesce(func.sum(self._order_net_total_expr()), 0))
            .where(Order.created_at >= today_start)
            .where(Order.status == "accepted")
        )
        row = result.one()
        return {"count": row[0], "total": row[1]}

    async def get_monthly_stats(self, year: int, month: int) -> dict:
        result = await self.session.execute(
            select(func.count(Order.id), func.coalesce(func.sum(self._order_net_total_expr()), 0))
            .where(extract("year", Order.created_at) == year)
            .where(extract("month", Order.created_at) == month)
            .where(Order.status == "accepted")
        )
        row = result.one()
        return {"count": row[0], "total": row[1]}

    async def get_yearly_stats(self, year: int) -> dict:
        result = await self.session.execute(
            select(func.count(Order.id), func.coalesce(func.sum(self._order_net_total_expr()), 0))
            .where(extract("year", Order.created_at) == year)
            .where(Order.status == "accepted")
        )
        row = result.one()
        return {"count": row[0], "total": row[1]}

    async def get_top_products(self, limit: int = 5) -> List[dict]:
        gross_result = await self.session.execute(
            select(
                Product.id,
                Product.name,
                Product.unit,
                func.sum(OrderItem.quantity).label("total_qty"),
                func.sum(OrderItem.total_price).label("total_revenue"),
            )
            .join(OrderItem, OrderItem.product_id == Product.id)
            .join(Order, Order.id == OrderItem.order_id)
            .where(Order.status == "accepted")
            .group_by(Product.id, Product.name, Product.unit)
        )
        gross_rows = gross_result.all()

        returned_result = await self.session.execute(
            select(
                OrderReturnItem.product_id,
                func.coalesce(func.sum(OrderReturnItem.quantity), 0).label("returned_qty"),
                func.coalesce(func.sum(OrderReturnItem.total_price), 0).label("returned_revenue"),
            )
            .join(Order, Order.id == OrderReturnItem.order_id)
            .where(Order.status == "accepted")
            .group_by(OrderReturnItem.product_id)
        )
        returned_map = {
            row.product_id: {"qty": row.returned_qty or 0, "revenue": row.returned_revenue or 0}
            for row in returned_result.all()
        }

        rows = []
        for row in gross_rows:
            returned = returned_map.get(row.id, {"qty": 0, "revenue": 0})
            rows.append(
                {
                    "name": row.name,
                    "unit": row.unit,
                    "total_qty": max(0, (row.total_qty or 0) - returned["qty"]),
                    "total_revenue": max(0, (row.total_revenue or 0) - returned["revenue"]),
                }
            )

        rows.sort(key=lambda item: item["total_revenue"], reverse=True)
        rows = rows[:limit]
        return [
            {
                "name": row.name,
                "unit": row.unit,
                "total_qty": row.total_qty,
                "total_revenue": row.total_revenue,
            }
            for row in rows
        ]

    async def get_orders_by_user(self, user_id: int, limit: int = 10, offset: int = 0) -> tuple[List[Order], int]:
        """Get orders for a specific user with pagination"""
        count_result = await self.session.execute(
            select(func.count(Order.id)).where(Order.user_id == user_id)
        )
        total = count_result.scalar_one()

        result = await self.session.execute(
            select(Order)
            .options(
                selectinload(Order.user),
                selectinload(Order.items).selectinload(OrderItem.product).selectinload(Product.category),
            )
            .where(Order.user_id == user_id)
            .order_by(desc(Order.created_at))
            .offset(offset)
            .limit(limit)
        )
        orders = list(result.scalars().all())
        return orders, total

    async def get_orders_for_period(self, start_date: datetime, end_date: datetime) -> tuple[List[Order], dict]:
        """Get orders for a specific date range and stats"""
        result = await self.session.execute(
            select(Order)
            .options(
                selectinload(Order.user),
                selectinload(Order.items)
                .selectinload(OrderItem.product)
                .selectinload(Product.category),
                selectinload(Order.items).selectinload(OrderItem.return_items),
                selectinload(Order.return_items)
                .selectinload(OrderReturnItem.product)
                .selectinload(Product.category),
            )
            .where(Order.created_at >= start_date)
            .where(Order.created_at <= end_date)
            .where(Order.status == "accepted")
            .order_by(desc(Order.created_at))
        )
        orders = list(result.scalars().all())
        
        total_sum = sum(max(0.0, (o.total_sum or 0.0) - sum((r.total_price or 0.0) for r in o.return_items or [])) for o in orders)
        stats = {
            "count": len(orders),
            "total": total_sum,
        }
        return orders, stats

    async def accept_order(self, order_id: int) -> Optional[Order]:
        """Mark order as accepted"""
        order = await self.get_order_with_details(order_id)
        if order:
            await self.set_order_status(order, "accepted")
        return order

    async def set_order_status(self, order: Order, status: str) -> Order:
        order.status = status
        order.accepted_at = now_tashkent() if status == "accepted" else None
        self.session.add(order)
        await self.session.commit()
        await self.session.refresh(order)
        logger.info(f"Order {order.id} status changed to {status}")
        return order

    async def get_users_with_orders_grouped(self) -> List[dict]:
        """
        Get users with their order counts and total amounts, sorted by last order date (newest first)
        Returns: [{user, order_count, total_amount, last_order_date}, ...]
        """
        result = await self.session.execute(
            select(
                User.id,
                User.full_name,
                User.phone,
                func.count(Order.id).label("order_count"),
                func.coalesce(func.sum(self._order_net_total_expr()), 0).label("total_amount"),
                func.max(Order.created_at).label("last_order_date"),
            )
            .outerjoin(Order, Order.user_id == User.id)
            .group_by(User.id, User.full_name, User.phone)
            .order_by(desc(func.max(Order.created_at)))
        )
        rows = result.all()
        users_data = []
        for row in rows:
            user = await self._get_user_by_id(row.id)
            if user and row.order_count > 0:  # Only users with orders
                users_data.append({
                    "user": user,
                    "order_count": row.order_count,
                    "total_amount": row.total_amount,
                    "last_order_date": row.last_order_date,
                })
        return users_data

    async def _get_user_by_id(self, user_id: int) -> Optional[User]:
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_user_orders_summary(self, user_id: int) -> List[dict]:
        """
        Get summary of user's orders (date, total, count of items)
        Sorted by date (newest first)
        """
        result = await self.session.execute(
            select(
                Order,
                self._order_net_total_expr().label("net_total"),
                self._order_return_total_expr().label("returned_total"),
            )
            .options(
                selectinload(Order.user),
                selectinload(Order.items)
                .selectinload(OrderItem.product)
                .selectinload(Product.category),
                selectinload(Order.items).selectinload(OrderItem.return_items),
                selectinload(Order.return_items)
                .selectinload(OrderReturnItem.product)
                .selectinload(Product.category),
            )
            .where(Order.user_id == user_id)
            .order_by(desc(Order.created_at))
        )
        rows = result.all()
        
        summary = []
        for row in rows:
            order = row[0]
            summary.append({
                "order": order,
                "item_count": len(order.items),
                "created_at": order.created_at,
                "total_sum": row.net_total,
                "gross_total": order.total_sum,
                "returned_total": row.returned_total,
            })
        return summary

    async def add_return_item(self, order_item_id: int, quantity: float) -> Optional[OrderReturnItem]:
        order_item = await self.session.execute(
            select(OrderItem)
            .options(
                selectinload(OrderItem.order).selectinload(Order.user),
                selectinload(OrderItem.product).selectinload(Product.category),
                selectinload(OrderItem.return_items),
            )
            .where(OrderItem.id == order_item_id)
        )
        order_item = order_item.scalar_one_or_none()
        if not order_item:
            return None

        returned_qty = sum((item.quantity or 0.0) for item in order_item.return_items or [])
        remaining_qty = max(0.0, (order_item.quantity or 0.0) - returned_qty)
        if quantity <= 0 or quantity > remaining_qty:
            raise ValueError("Invalid return quantity")

        total_price = quantity * (order_item.price or 0.0)
        return_item = OrderReturnItem(
            order_id=order_item.order_id,
            order_item_id=order_item.id,
            product_id=order_item.product_id,
            quantity=quantity,
            price=order_item.price,
            total_price=total_price,
            size=order_item.size,
        )
        self.session.add(return_item)

        user = order_item.order.user if order_item.order else await self._get_user_by_id(order_item.order.user_id)
        if user:
            user.total_purchase_sum = max(0.0, (user.total_purchase_sum or 0.0) - total_price)
            self.session.add(user)

        await self.session.commit()
        await self.session.refresh(return_item)
        logger.info(
            "Added return item order_item_id=%s quantity=%s total=%s",
            order_item_id,
            quantity,
            total_price,
        )
        return return_item

    async def add_payment(self, user_id: int, amount: float) -> Optional[User]:
        """Add payment amount to user's paid_sum"""
        user = await self._get_user_by_id(user_id)
        if user:
            user.paid_sum += amount
            self.session.add(user)
            await self.session.commit()
            await self.session.refresh(user)
            logger.info(f"Added payment of {amount} UZS to user {user_id}. New paid_sum: {user.paid_sum}")
        return user

    async def delete_order(self, order_id: int) -> bool:
        order = await self.get_order_with_details(order_id)
        if not order:
            return False

        user = await self._get_user_by_id(order.user_id)
        if user:
            returned_total = sum((item.total_price or 0.0) for item in order.return_items or [])
            net_total = max(0.0, (order.total_sum or 0.0) - returned_total)
            user.total_purchase_sum = max(0.0, (user.total_purchase_sum or 0.0) - net_total)
            self.session.add(user)

        await self.session.delete(order)
        await self.session.commit()
        logger.info(f"Deleted order id={order_id}")
        return True
