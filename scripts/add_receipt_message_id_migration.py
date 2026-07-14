"""Add `receipt_message_id` column to `orders` table if missing.

Run on any server where DATABASE_URL points to the target database:

    python scripts/add_receipt_message_id_migration.py

The script is idempotent and safe to run multiple times.
"""
import sys
import logging
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from config import settings

logger = logging.getLogger("migration")
logging.basicConfig(level=logging.INFO)


def to_async_url(db_url: str) -> str:
    return db_url.replace("postgres://", "postgresql+asyncpg://", 1).replace(
        "postgresql://", "postgresql+asyncpg://", 1
    )


async def main():
    db_url = settings.DATABASE_URL
    if not db_url:
        logger.error("DATABASE_URL is not set in config.settings")
        sys.exit(1)

    async_url = to_async_url(db_url)
    logger.info(f"Connecting to database: {async_url}")

    engine = create_async_engine(async_url, echo=False, pool_pre_ping=True)

    async with engine.begin() as conn:
        if async_url.startswith("sqlite"):
            rows = (await conn.execute(text("PRAGMA table_info(orders);"))).fetchall()
            cols = [r[1] for r in rows]
            if "receipt_message_id" in cols:
                logger.info("Column 'receipt_message_id' already exists. Nothing to do.")
                return

            logger.info("Adding column 'receipt_message_id' to 'orders' table...")
            await conn.execute(text("ALTER TABLE orders ADD COLUMN receipt_message_id INTEGER;"))
            logger.info("Column added successfully.")
        else:
            result = await conn.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='orders' AND column_name='receipt_message_id';"
            ))
            if result.fetchone():
                logger.info("Column 'receipt_message_id' already exists. Nothing to do.")
                return

            logger.info("Adding column 'receipt_message_id' to 'orders' table on PostgreSQL...")
            await conn.execute(text("ALTER TABLE orders ADD COLUMN receipt_message_id INTEGER;"))
            logger.info("Column added successfully.")


if __name__ == "__main__":
    asyncio.run(main())