"""Cleanup script: remove all data except products and categories.

Usage:
    - Non-interactive: set env var `CONFIRM_CLEAN_DB=1` or pass `--yes`.
    - Interactive: run without `--yes` to see counts, then run with `--yes`.

Run on the target server: `python scripts/cleanup_database.py --yes`
"""
import asyncio
import argparse
import logging
import os
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import text
from ..database.db import engine
from ..config import settings

logger = logging.getLogger("cleanup")


async def get_counts(conn):
    tables = [
        "order_items",
        "orders",
        "users",
        "products",
        "categories",
    ]
    counts = {}
    for t in tables:
        try:
            res = await conn.execute(text(f"SELECT COUNT(*) FROM {t};"))
            counts[t] = res.scalar_one()
        except Exception:
            counts[t] = None
    return counts


async def cleanup(confirm: bool):
    async with engine.begin() as conn:
        counts = await get_counts(conn)
        print("Current row counts:")
        for k, v in counts.items():
            print(f"  {k}: {v}")

        if not confirm and os.environ.get("CONFIRM_CLEAN_DB") != "1":
            print("\nNo confirmation given. Re-run with `--yes` or set `CONFIRM_CLEAN_DB=1` to proceed.")
            return

        print("\nDeleting data (preserving products and categories)...")

        # Delete in safe order to satisfy foreign keys
        await conn.execute(text("DELETE FROM order_items;"))
        await conn.execute(text("DELETE FROM orders;"))
        await conn.execute(text("DELETE FROM users;"))

        print("Delete commands executed. Committing transaction...")

    # engine.begin() commits on exit if no exceptions
    print("Cleanup finished. Current counts after cleanup:")
    async with engine.connect() as conn:
        counts_after = await get_counts(conn)
        for k, v in counts_after.items():
            print(f"  {k}: {v}")


def main():
    parser = argparse.ArgumentParser(description="Cleanup DB but keep products and categories")
    parser.add_argument("--yes", action="store_true", help="Actually perform the cleanup")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    # DATABASE_URL is loaded from the environment via config.py
    print(f"Using DB URL: {settings.DATABASE_URL.split('://')[0]}://***")

    asyncio.run(cleanup(confirm=args.yes))


if __name__ == "__main__":
    main()
