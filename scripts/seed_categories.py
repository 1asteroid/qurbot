"""Seed base units, categories, and products into the database.

This script is idempotent: it adds missing rows only and does not drop tables.

Run with:
	python scripts/seed_categories.py
"""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from config import settings
from database.models import Category, Product, Unit, now_tashkent

logger = logging.getLogger("seed")
logging.basicConfig(level=logging.INFO)

UNITS = ["chelak", "dona", "kg", "metr"]

DATA = [
	(
		"lak",
		[
			("Nova milano", "chelak"),
			("Nova lak", "kg"),
			("Nova zemshuk", "kg"),
			("Nova otachento", "kg"),
		],
	),
	(
		"tiyaga",
		[
			("Dela", "metr"),
			("Taroq", "metr"),
			("Kapalak", "metr"),
			("Rels", "metr"),
			("Karniz", "metr"),
			("Padagolnik", "metr"),
			("Noshka", "dona"),
			("Karnizga gul", "dona"),
		],
	),
	(
		"travertin",
		[
			("Nova leonarda", "chelak"),
			("Nova travertino", "chelak"),
			("Nova shpaklovka", "chelak"),
			("Nova guruntovka", "chelak"),
		],
	),
]


def to_asyncpg_url(db_url: str) -> str:
	return db_url.replace("postgres://", "postgresql+asyncpg://", 1).replace(
		"postgresql://", "postgresql+asyncpg://", 1
	)


async def main() -> None:
	db_url = settings.DATABASE_URL
	if not db_url:
		logger.error("DATABASE_URL not set")
		sys.exit(1)

	engine = create_async_engine(to_asyncpg_url(db_url), echo=False, pool_pre_ping=True)

	SessionFactory = async_sessionmaker(bind=engine, expire_on_commit=False)

	async with SessionFactory() as session:
		existing_units = set((await session.execute(select(Unit.name))).scalars().all())
		for unit_name in UNITS:
			if unit_name not in existing_units:
				session.add(Unit(name=unit_name, created_at=now_tashkent()))

		existing_categories = {
			row.name: row for row in (await session.execute(select(Category))).scalars().all()
		}
		existing_products = {
			row.name: row for row in (await session.execute(select(Product))).scalars().all()
		}

		for category_name, products in DATA:
			category = existing_categories.get(category_name)
			if category is None:
				category = Category(name=category_name, created_at=now_tashkent())
				session.add(category)
				await session.flush()
				existing_categories[category_name] = category

			for product_name, unit_name in products:
				if product_name in existing_products:
					continue
				session.add(
					Product(
						name=product_name,
						unit=unit_name,
						category_id=category.id,
						created_at=now_tashkent(),
					)
				)

		await session.commit()

	logger.info("Base data seed complete.")


if __name__ == "__main__":
	asyncio.run(main())
