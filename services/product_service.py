import logging
from typing import Optional, List
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import Product

logger = logging.getLogger(__name__)


class ProductService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(self) -> List[Product]:
        result = await self.session.execute(
            select(Product).order_by(desc(Product.created_at))
        )
        return list(result.scalars().all())

    async def get_by_id(self, product_id: int) -> Optional[Product]:
        result = await self.session.execute(
            select(Product).where(Product.id == product_id)
        )
        return result.scalar_one_or_none()

    async def create(self, name: str, unit: str) -> Product:
        product = Product(name=name, unit=unit)
        self.session.add(product)
        await self.session.commit()
        await self.session.refresh(product)
        logger.info(f"Created product name={name} unit={unit}")
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
