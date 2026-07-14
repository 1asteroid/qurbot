import logging
from typing import List, Optional

from sqlalchemy import select, desc, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..database.models import Unit, Product

logger = logging.getLogger(__name__)


class UnitService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(self) -> List[Unit]:
        result = await self.session.execute(select(Unit).order_by(Unit.name))
        return list(result.scalars().all())

    async def get_all_names(self) -> List[str]:
        units = await self.get_all()
        return [unit.name for unit in units]

    async def get_by_id(self, unit_id: int) -> Optional[Unit]:
        result = await self.session.execute(select(Unit).where(Unit.id == unit_id))
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Optional[Unit]:
        result = await self.session.execute(select(Unit).where(func.lower(Unit.name) == name.strip().lower()))
        return result.scalar_one_or_none()

    async def create(self, name: str) -> Unit:
        name = name.strip()
        existing = await self.get_by_name(name)
        if existing:
            raise ValueError("Bunday birlik allaqachon mavjud")

        unit = Unit(name=name)
        self.session.add(unit)
        await self.session.commit()
        await self.session.refresh(unit)
        logger.info(f"Created unit name={name}")
        return unit

    async def count_products(self, unit_name: str) -> int:
        result = await self.session.execute(select(func.count(Product.id)).where(func.lower(Product.unit) == unit_name.strip().lower()))
        return int(result.scalar_one())

    async def update(self, unit_id: int, new_name: str) -> Optional[Unit]:
        unit = await self.get_by_id(unit_id)
        if not unit:
            return None

        new_name = new_name.strip()
        old_name = unit.name
        if old_name.lower() == new_name.lower():
            return unit

        duplicate = await self.get_by_name(new_name)
        if duplicate and duplicate.id != unit_id:
            raise ValueError("Bunday birlik allaqachon mavjud")

        unit.name = new_name
        await self.session.execute(
            update(Product)
            .where(func.lower(Product.unit) == old_name.lower())
            .values(unit=new_name)
        )
        self.session.add(unit)
        await self.session.commit()
        await self.session.refresh(unit)
        logger.info(f"Updated unit id={unit_id} old_name={old_name} new_name={new_name}")
        return unit

    async def delete_with_reassign(self, unit_id: int, replacement_unit_id: Optional[int] = None) -> bool:
        unit = await self.get_by_id(unit_id)
        if not unit:
            return False

        products_count = await self.count_products(unit.name)
        if products_count > 0:
            if not replacement_unit_id:
                raise ValueError("Bu birlik mahsulotlarga biriktirilgan")

            replacement = await self.get_by_id(replacement_unit_id)
            if not replacement:
                raise ValueError("O'rnini bosuvchi birlik topilmadi")

            if replacement.id == unit.id:
                raise ValueError("Bir xil birlikni tanlab bo'lmaydi")

            await self.session.execute(
                update(Product)
                .where(func.lower(Product.unit) == unit.name.lower())
                .values(unit=replacement.name)
            )

        await self.session.delete(unit)
        await self.session.commit()
        logger.info(f"Deleted unit id={unit_id} name={unit.name}")
        return True