"""Add `accepted_at` column to `orders` table for SQLite if missing.

Run on the server where your DATABASE_URL is configured:

    python scripts/add_accepted_at_migration.py

The script is idempotent: it checks for existence and exits if column already present.
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

    sync_url = to_async_url(db_url)

    logger.info(f"Connecting to database: {sync_url}")

    engine = create_async_engine(sync_url, echo=False, pool_pre_ping=True)

    async with engine.begin() as conn:
        # Only handle SQLite automatically. For other DBs, show instructions.
        if sync_url.startswith("sqlite:"):
            logger.info("Detected SQLite. Checking table schema...")
            try:
                rows = (await conn.execute(text("PRAGMA table_info(orders);"))).fetchall()
            except Exception as e:
                logger.error(f"Error reading table info: {e}")
                sys.exit(1)

            cols = [r[1] for r in rows]
            if "accepted_at" in cols:
                logger.info("Column 'accepted_at' already exists. Nothing to do.")
                return

            logger.info("Adding column 'accepted_at' to 'orders' table...")
            try:
                await conn.execute(text("ALTER TABLE orders ADD COLUMN accepted_at DATETIME;"))
                logger.info("Column added successfully.")
            except Exception as e:
                logger.error(f"Failed to add column: {e}")
                sys.exit(1)
        else:
            try:
                result = await conn.execute(text(
                    "SELECT column_name FROM information_schema.columns WHERE table_name='orders' AND column_name='accepted_at';"
                ))
                if result.fetchone():
                    logger.info("Column 'accepted_at' already exists. Nothing to do.")
                    return

                logger.info("Adding column 'accepted_at' to 'orders' table...")
                await conn.execute(text("ALTER TABLE orders ADD COLUMN accepted_at TIMESTAMP;"))
                logger.info("Column added successfully.")
            except Exception as e:
                logger.error(f"Failed to add column on PostgreSQL: {e}")
                sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
