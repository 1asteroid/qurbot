"""Fully reset the database and seed only categories/products.

This script drops all existing tables, recreates the schema from the current models,
and inserts only the requested categories and products.

Use locally or on a server with care:
    python scripts/seed_categories.py
"""
import logging
import sys
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from config import settings
from database.models import Base, Category, Product, now_tashkent

logger = logging.getLogger("seed")
logging.basicConfig(level=logging.INFO)

CATEGORIES = [
    ("travertin", [
        ("Nova milano", "chelak"),
        ("Nova leonardo", "chelak"),
        ("Nova travertino", "chelak"),
        ("Nova shpaklovka", "chelak"),
        ("Nova guruntovka", "chelak"),
    ]),
    ("lak", [
        ("Nova lak", "kg"),
        ("Nova zemshuk", "kg"),
        ("Nova otochento", "kg"),
    ]),
    ("tiyaga", [
        ("Dela", "metr"),
        ("Taroq", "metr"),
        ("Kapalak", "metr"),
        ("Rels", "metr"),
        ("Karniz", "metr"),
        ("Padagonik", "metr"),
        ("Noshka", "dona"),
        ("Karnizga gul", "dona"),
    ]),
]


def to_sync_url(db_url: str) -> str:
    return db_url.replace("postgres://", "postgresql+asyncpg://", 1).replace(
        "postgresql://", "postgresql+asyncpg://", 1
    )


async def main() -> None:
    db_url = settings.DATABASE_URL
    if not db_url:
        logger.error("DATABASE_URL not set")
        sys.exit(1)

    sync_url = to_sync_url(db_url)
    logger.info("Connecting to DB: %s", sync_url)

    engine = create_async_engine(sync_url, echo=False, pool_pre_ping=True)

    logger.warning("Dropping all tables and recreating schema from models")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    SessionFactory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with SessionFactory() as session:
        logger.info("Seeding categories and products")
        for category_name, products in CATEGORIES:
            category = Category(name=category_name, created_at=now_tashkent())
            session.add(category)
            await session.flush()

            for product_name, unit in products:
                session.add(
                    Product(
                        name=product_name,
                        unit=unit,
                        category_id=category.id,
                        created_at=now_tashkent(),
                    )
                )

        await session.commit()

    logger.info("Database reset and seed complete.")


if __name__ == "__main__":
    asyncio.run(main())
