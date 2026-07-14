"""Compatibility wrapper for the base data seeder.

Some deployments still call scripts/seed_all.py. Keep it as a thin wrapper so
those commands continue to work.
"""

from seed_categories import main


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())