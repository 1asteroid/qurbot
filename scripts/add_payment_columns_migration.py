"""Add payment tracking columns to users table.

This migration:
1. Adds `total_purchase_sum` column (default 0.0)
2. Adds `paid_sum` column (default 0.0)
3. Populates `total_purchase_sum` from existing orders for each user
4. Sets `paid_sum` to 0 for all users

Run on the server where your DATABASE_URL is configured:

    python scripts/add_payment_columns_migration.py

The script is idempotent: it checks for existence and exits if columns already present.
"""
import sys
import logging
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
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
        # Check table schema
        try:
            if async_url.startswith("sqlite:"):
                rows = (await conn.execute(text("PRAGMA table_info(users);"))).fetchall()
                cols = [r[1] for r in rows]
            else:
                # PostgreSQL
                rows = (await conn.execute(
                    text("""SELECT column_name FROM information_schema.columns 
                            WHERE table_name='users';""")
                )).fetchall()
                cols = [r[0] for r in rows]
        except Exception as e:
            logger.error(f"Error reading table info: {e}")
            sys.exit(1)

        # Check if columns already exist
        has_total = "total_purchase_sum" in cols
        has_paid = "paid_sum" in cols

        if has_total and has_paid:
            logger.info("Columns 'total_purchase_sum' and 'paid_sum' already exist. Nothing to do.")
            await engine.dispose()
            sys.exit(0)

        # Add missing columns
        if not has_total:
            logger.info("Adding 'total_purchase_sum' column...")
            try:
                await conn.execute(text(
                    "ALTER TABLE users ADD COLUMN total_purchase_sum FLOAT NOT NULL DEFAULT 0.0;"
                ))
                await conn.commit()
                logger.info("✅ Column 'total_purchase_sum' added.")
            except Exception as e:
                logger.error(f"Error adding 'total_purchase_sum': {e}")
                await conn.rollback()
                sys.exit(1)

        if not has_paid:
            logger.info("Adding 'paid_sum' column...")
            try:
                await conn.execute(text(
                    "ALTER TABLE users ADD COLUMN paid_sum FLOAT NOT NULL DEFAULT 0.0;"
                ))
                await conn.commit()
                logger.info("✅ Column 'paid_sum' added.")
            except Exception as e:
                logger.error(f"Error adding 'paid_sum': {e}")
                await conn.rollback()
                sys.exit(1)

    # Now populate data in a separate session
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        logger.info("Populating total_purchase_sum from existing orders...")
        try:
            # Calculate sum of orders for each user and update
            result = await session.execute(text("""
                UPDATE users
                SET total_purchase_sum = (
                    SELECT COALESCE(SUM(total_sum), 0)
                    FROM orders
                    WHERE orders.user_id = users.id
                )
                WHERE total_purchase_sum = 0.0;
            """))
            await session.commit()
            logger.info(f"✅ Updated {result.rowcount} users with order totals.")
        except Exception as e:
            logger.error(f"Error updating totals: {e}")
            await session.rollback()
            sys.exit(1)

    logger.info("✅ Migration completed successfully!")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
