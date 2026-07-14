"""Add `is_admin` column to `users` table and backfill configured admins.

Run on any server where DATABASE_URL points to the target database:

    python scripts/add_admin_column_migration.py

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

    try:
        async with engine.begin() as conn:
            if async_url.startswith("sqlite"):
                rows = (await conn.execute(text("PRAGMA table_info(users);"))).fetchall()
                cols = [r[1] for r in rows]
                if "is_admin" not in cols:
                    logger.info("Adding column 'is_admin' to 'users' table...")
                    await conn.execute(
                        text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT 0;")
                    )
                    logger.info("Column added successfully.")
                else:
                    logger.info("Column 'is_admin' already exists. Skipping add step.")
            else:
                result = await conn.execute(text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name='users' AND column_name='is_admin';"
                ))
                if result.fetchone():
                    logger.info("Column 'is_admin' already exists. Skipping add step.")
                else:
                    logger.info("Adding column 'is_admin' to 'users' table on PostgreSQL...")
                    await conn.execute(
                        text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT FALSE;")
                    )
                    logger.info("Column added successfully.")

            if settings.admin_ids_list:
                logger.info("Backfilling configured admins into users.is_admin...")
                update_sql = text(
                    "UPDATE users SET is_admin = :is_admin, is_manager = :is_manager WHERE telegram_id = :telegram_id;"
                )
                for telegram_id in settings.admin_ids_list:
                    await conn.execute(
                        update_sql,
                        {"is_admin": True, "is_manager": True, "telegram_id": telegram_id},
                    )
                logger.info("Configured admins backfilled.")
            else:
                logger.info("No configured admins found to backfill.")

        logger.info("✅ Migration completed successfully!")
    except Exception as exc:
        logger.error(f"Migration failed: {exc}")
        sys.exit(1)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())