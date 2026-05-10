from datetime import datetime
from typing import Optional, List
import pytz
from sqlalchemy import (
    BigInteger, String, Integer, Float, DateTime, Boolean,
    ForeignKey, Enum as SAEnum, Text
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from config import settings

TZ = pytz.timezone(settings.TIMEZONE)


def now_tashkent() -> datetime:
    return datetime.now(TZ).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(30), nullable=False)
    is_manager: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    total_purchase_sum: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    paid_sum: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_tashkent, nullable=False)

    orders: Mapped[List["Order"]] = relationship("Order", back_populates="user", lazy="selectin", foreign_keys="Order.user_id")

    def __repr__(self) -> str:
        return f"<User id={self.id} name={self.full_name} is_manager={self.is_manager}>"


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)  # kg, dona, metr
    category_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("categories.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_tashkent, nullable=False)

    order_items: Mapped[List["OrderItem"]] = relationship("OrderItem", back_populates="product", lazy="selectin")
    category: Mapped[Optional["Category"]] = relationship("Category", back_populates="products", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Product id={self.id} name={self.name}>"


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_tashkent, nullable=False)

    products: Mapped[List[Product]] = relationship("Product", back_populates="category", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Category id={self.id} name={self.name}>"


class Unit(Base):
    __tablename__ = "units"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_tashkent, nullable=False)

    def __repr__(self) -> str:
        return f"<Unit id={self.id} name={self.name}>"


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    manager_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    total_sum: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    receipt_message_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_tashkent, nullable=False)

    # Use string references for foreign_keys to avoid circular reference issues
    user: Mapped["User"] = relationship(
        "User", 
        back_populates="orders", 
        lazy="selectin",
        foreign_keys="Order.user_id"
    )
    manager: Mapped[Optional["User"]] = relationship(
        "User", 
        lazy="selectin", 
        foreign_keys="Order.manager_id"
    )
    items: Mapped[List["OrderItem"]] = relationship("OrderItem", back_populates="order", lazy="selectin", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Order id={self.id} user_id={self.user_id} total={self.total_sum}>"


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id"), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    total_price: Mapped[float] = mapped_column(Float, nullable=False)
    size: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    order: Mapped["Order"] = relationship("Order", back_populates="items", lazy="selectin")
    product: Mapped["Product"] = relationship("Product", back_populates="order_items", lazy="selectin")

    def __repr__(self) -> str:
        return f"<OrderItem order={self.order_id} product={self.product_id}>"
