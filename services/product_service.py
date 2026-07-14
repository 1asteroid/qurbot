import logging
from typing import Optional, List
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from ..database.models import Product, Category

logger = logging.getLogger(__name__)


class ProductService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(self) -> List[Product]:
        result = await self.session.execute(
            select(Product).options(selectinload(Product.category)).order_by(desc(Product.created_at))
        )
        return list(result.scalars().all())

    async def get_all_categories(self) -> List[Category]:
        result = await self.session.execute(select(Category).order_by(Category.name))
        return list(result.scalars().all())

    async def get_by_category(self, category_id: int) -> List[Product]:
        result = await self.session.execute(
            select(Product)
            .options(selectinload(Product.category))
            .where(Product.category_id == category_id)
            .order_by(desc(Product.created_at))
        )
        return list(result.scalars().all())

    async def get_by_id(self, product_id: int) -> Optional[Product]:
        result = await self.session.execute(
            select(Product).options(selectinload(Product.category)).where(Product.id == product_id)
        )
        return result.scalar_one_or_none()

    async def create(self, name: str, unit: str, category_id: Optional[int] = None) -> Product:
        product = Product(name=name, unit=unit, category_id=category_id)
        self.session.add(product)
        await self.session.commit()
        await self.session.refresh(product)
        logger.info(f"Created product name={name} unit={unit} category_id={category_id}")
        return product

    async def update(self, product_id: int, name: str, unit: str) -> Optional[Product]:
        product = await self.get_by_id(product_id)
        if not product:
            return None
        product.name = name
        product.unit = unit
        await self.session.commit()
        await self.session.refresh(product)
        logger.info(f"Updated product id={product_id}")
        return product

    async def delete(self, product_id: int) -> bool:
        product = await self.get_by_id(product_id)
        if not product:
            return False
        await self.session.delete(product)
        await self.session.commit()
        logger.info(f"Deleted product id={product_id}")
        return True
