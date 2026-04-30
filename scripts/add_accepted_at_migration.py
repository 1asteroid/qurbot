"""Add `accepted_at` column to `orders` table for SQLite if missing.

Run on the server where your DATABASE_URL is configured (Heroku):

    heroku run python scripts/add_accepted_at_migration.py

The script is idempotent: it checks for existence and exits if column already present.
"""
import sys
import logging
from sqlalchemy import create_engine, text
from config import settings

logger = logging.getLogger("migration")
logging.basicConfig(level=logging.INFO)


def main():
    db_url = settings.DATABASE_URL
    if not db_url:
        logger.error("DATABASE_URL is not set in config.settings")
        sys.exit(1)

    # Support common async sqlite URL used in this project (sqlite+aiosqlite:///...) by
    # converting to sync sqlite URL for raw ALTER execution.
    if db_url.startswith("sqlite+aiosqlite://"):
        sync_url = db_url.replace("sqlite+aiosqlite://", "sqlite://", 1)
    else:
        sync_url = db_url

    logger.info(f"Connecting to database: {sync_url}")

    engine = create_engine(sync_url, connect_args={"check_same_thread": False} if sync_url.startswith("sqlite:") else {})

    with engine.connect() as conn:
        # Only handle SQLite automatically. For other DBs, show instructions.
        if sync_url.startswith("sqlite:"):
            logger.info("Detected SQLite. Checking table schema...")
            try:
                rows = conn.execute(text("PRAGMA table_info(orders);")).fetchall()
            except Exception as e:
                logger.error(f"Error reading table info: {e}")
                sys.exit(1)

            cols = [r[1] for r in rows]
            if "accepted_at" in cols:
                logger.info("Column 'accepted_at' already exists. Nothing to do.")
                return

            logger.info("Adding column 'accepted_at' to 'orders' table...")
            try:
                conn.execute(text("ALTER TABLE orders ADD COLUMN accepted_at DATETIME;"))
                logger.info("Column added successfully.")
            except Exception as e:
                logger.error(f"Failed to add column: {e}")
                sys.exit(1)
        else:
            logger.error("Automatic migration only implemented for SQLite.\n"
                         "For other databases run an ALTER TABLE to add `accepted_at` column, e.g.:\n"
                         "  ALTER TABLE orders ADD COLUMN accepted_at TIMESTAMP;\n"
                         "Then ensure your app restarts.")
            sys.exit(1)


if __name__ == "__main__":
    main()
