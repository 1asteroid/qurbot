"""Fully reset the database and seed only categories/products.

This script drops all existing tables, recreates the schema from the current models,
and inserts only the requested categories and products.

Use locally or on Heroku with care:
    heroku run python scripts/seed_categories.py
"""
import logging
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
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
        ("Nova lak", "chelak"),
        ("Nova zemshuk", "chelak"),
        ("Nova otochento", "chelak"),
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
    if db_url.startswith("sqlite+aiosqlite://"):
        return db_url.replace("sqlite+aiosqlite://", "sqlite://", 1)
    if db_url.startswith("postgres://"):
        return db_url.replace("postgres://", "postgresql://", 1)
    return db_url


def main() -> None:
    db_url = settings.DATABASE_URL
    if not db_url:
        logger.error("DATABASE_URL not set")
        sys.exit(1)

    sync_url = to_sync_url(db_url)
    logger.info("Connecting to DB: %s", sync_url)

    connect_args = {"check_same_thread": False} if sync_url.startswith("sqlite:") else {}
    engine = create_engine(sync_url, connect_args=connect_args)

    logger.warning("Dropping all tables and recreating schema from models")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    with Session(engine) as session:
        logger.info("Seeding categories and products")
        for category_name, products in CATEGORIES:
            category = Category(name=category_name, created_at=now_tashkent())
            session.add(category)
            session.flush()

            for product_name, unit in products:
                session.add(
                    Product(
                        name=product_name,
                        unit=unit,
                        category_id=category.id,
                        created_at=now_tashkent(),
                    )
                )

        session.commit()

    logger.info("Database reset and seed complete.")


if __name__ == "__main__":
    main()
