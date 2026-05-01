"""Add `size` column to `order_items` table if missing.

Run on the server where your DATABASE_URL is configured (Heroku):

    heroku run python scripts/add_orderitem_size_migration.py

The script is idempotent: it checks for existence and exits if column already present.
"""
import sys
import logging
import asyncio
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
        # Check on SQLite vs Postgres
        if async_url.startswith("sqlite:"):
            logger.info("Detected SQLite. Checking table schema...")
            try:
                rows = (await conn.execute(text("PRAGMA table_info(order_items);"))).fetchall()
            except Exception as e:
                logger.error(f"Error reading table info: {e}")
                sys.exit(1)

            cols = [r[1] for r in rows]
            if "size" in cols:
                logger.info("Column 'size' already exists on 'order_items'. Nothing to do.")
                return

            logger.info("Adding column 'size' to 'order_items' table...")
            try:
                await conn.execute(text("ALTER TABLE order_items ADD COLUMN size TEXT;"))
                logger.info("Column added successfully.")
            except Exception as e:
                logger.error(f"Failed to add column: {e}")
                sys.exit(1)
        else:
            try:
                result = await conn.execute(text(
                    "SELECT column_name FROM information_schema.columns WHERE table_name='order_items' AND column_name='size';"
                ))
                if result.fetchone():
                    logger.info("Column 'size' already exists on 'order_items'. Nothing to do.")
                    return

                logger.info("Adding column 'size' to 'order_items' table on PostgreSQL...")
                await conn.execute(text("ALTER TABLE order_items ADD COLUMN size VARCHAR(100);"))
                logger.info("Column added successfully.")
            except Exception as e:
                logger.error(f"Failed to add column on PostgreSQL: {e}")
                sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
