"""Seed categories and products per specification.

Run locally or on Heroku (heroku run python scripts/seed_categories.py).
This script is idempotent: it will remove existing products and categories and recreate them.
"""
import sys
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from config import settings

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
    return db_url


def main():
    db_url = settings.DATABASE_URL
    if not db_url:
        logger.error("DATABASE_URL not set")
        sys.exit(1)

    sync_url = to_sync_url(db_url)
    logger.info(f"Connecting to DB: {sync_url}")

    connect_args = {"check_same_thread": False} if sync_url.startswith("sqlite:") else {}
    engine = create_engine(sync_url, connect_args=connect_args)

    with engine.begin() as conn:
        # Ensure `accepted_at` exists on orders to avoid runtime errors (safety for running on Heroku)
        try:
            if sync_url.startswith("sqlite:"):
                rows = conn.execute(text("PRAGMA table_info(orders);")).fetchall()
                cols = [r[1] for r in rows]
                if "accepted_at" not in cols:
                    logger.info("Adding missing 'accepted_at' column to orders table before seeding")
                    conn.execute(text("ALTER TABLE orders ADD COLUMN accepted_at DATETIME;"))
            else:
                # For other DBs, try a safe add (Postgres supports IF NOT EXISTS)
                try:
                    conn.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS accepted_at TIMESTAMP;"))
                except Exception:
                    # Fallback: check information_schema and add if required
                    info = conn.execute(text(
                        "SELECT column_name FROM information_schema.columns WHERE table_name='orders' AND column_name='accepted_at';"
                    )).fetchone()
                    if not info:
                        logger.info("Adding 'accepted_at' column to orders table (non-sqlite)")
                        conn.execute(text("ALTER TABLE orders ADD COLUMN accepted_at TIMESTAMP;"))
        except Exception as e:
            logger.error(f"Could not ensure accepted_at column: {e}")
            # continue — seed can proceed but may still error elsewhere
        # Create categories table if not exists (simple SQL)
        try:
            if sync_url.startswith("sqlite:"):
                conn.execute(text(
                    "CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, created_at DATETIME);"
                ))
                # Add category_id column to products if missing
                cols = [r[1] for r in conn.execute(text("PRAGMA table_info(products);")).fetchall()]
                if "category_id" not in cols:
                    logger.info("Adding category_id column to products table")
                    conn.execute(text("ALTER TABLE products ADD COLUMN category_id INTEGER;"))
            else:
                # Postgres / other
                conn.execute(text(
                    "CREATE TABLE IF NOT EXISTS categories (id SERIAL PRIMARY KEY, name VARCHAR(255) UNIQUE NOT NULL, created_at TIMESTAMP);")
                )
                # Add column if not exists
                try:
                    conn.execute(text("ALTER TABLE products ADD COLUMN IF NOT EXISTS category_id INTEGER;"))
                except Exception:
                    # Some DB flavors don't support IF NOT EXISTS for ALTER
                    pass
        except OperationalError as e:
            logger.error(f"Schema change error: {e}")
            sys.exit(1)

        # Remove existing products and categories (as requested)
        logger.info("Deleting existing products and categories (if any)")
        try:
            conn.execute(text("DELETE FROM products;"))
        except Exception:
            pass
        try:
            conn.execute(text("DELETE FROM categories;"))
        except Exception:
            pass

        # Insert categories and products
        logger.info("Inserting categories and products")
        for cat_name, products in CATEGORIES:
            res = conn.execute(text("INSERT INTO categories (name, created_at) VALUES (:name, datetime('now'))"), {"name": cat_name})
            # get last inserted id (sqlite)
            if sync_url.startswith("sqlite:"):
                cat_id = conn.execute(text("SELECT last_insert_rowid();")).scalar()
            else:
                # For Postgres return id
                cat_id = None
                try:
                    cat_id = res.lastrowid
                except Exception:
                    # fallback: query id by name
                    cat_id = conn.execute(text("SELECT id FROM categories WHERE name = :name"), {"name": cat_name}).scalar()

            for prod_name, unit in products:
                conn.execute(text(
                    "INSERT INTO products (name, unit, category_id, created_at) VALUES (:name, :unit, :cat, now())"
                ), {"name": prod_name, "unit": unit, "cat": cat_id})

    logger.info("Seeding complete.")


if __name__ == '__main__':
    main()
