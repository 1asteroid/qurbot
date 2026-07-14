"""Update all products in the `lak` category to use `kg` as the unit.

Run this against the active database on any server:
    python scripts/update_lak_units_to_kg.py

It is safe to run locally as long as DATABASE_URL points to the target DB.
"""

import asyncio
import logging
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from config import settings
from database.models import Category, Product


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("lak_unit_migration")


def to_async_url(db_url: str) -> str:
    if db_url.startswith("postgres://"):
        return db_url.replace("postgres://", "postgresql+asyncpg://", 1)
    if db_url.startswith("postgresql://") and "+asyncpg" not in db_url:
        return db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return db_url


async def main() -> None:
    db_url = to_async_url(settings.DATABASE_URL)
    logger.info("Connecting to DB: %s", db_url)

    engine = create_async_engine(db_url, echo=False, pool_pre_ping=True)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with session_factory() as session:
        result = await session.execute(
            select(Category.id).where(func.lower(Category.name) == "lak")
        )
        lak_category_id = result.scalar_one_or_none()

        if lak_category_id is None:
            logger.warning("Category 'lak' was not found. Nothing to update.")
            return

        update_result = await session.execute(
            update(Product)
            .where(Product.category_id == lak_category_id)
            .values(unit="kg")
        )
        await session.commit()

        updated_rows = update_result.rowcount or 0
        logger.info("Updated %s products in category 'lak' to unit='kg'.", updated_rows)


if __name__ == "__main__":
    asyncio.run(main())