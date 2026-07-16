import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from config import settings
from database.models import Base, Unit

logger = logging.getLogger(__name__)

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def init_db() -> None:
    """Create all tables if they don't exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        unit_rows = (await conn.execute(text("SELECT COUNT(*) FROM units;"))).scalar_one()
        if unit_rows == 0:
            for unit_name in ["kg", "chelak", "dona", "metr"]:
                await conn.execute(
                    text("INSERT INTO units (name, created_at) VALUES (:name, CURRENT_TIMESTAMP);"),
                    {"name": unit_name},
                )
        if settings.DATABASE_URL.startswith("sqlite"):
            rows = (await conn.execute(text("PRAGMA table_info(orders);"))).fetchall()
            columns = {row[1] for row in rows}
            if "receipt_message_id" not in columns:
                await conn.execute(text("ALTER TABLE orders ADD COLUMN receipt_message_id INTEGER;"))
            user_rows = (await conn.execute(text("PRAGMA table_info(users);"))).fetchall()
            user_columns = {row[1] for row in user_rows}
            if "is_admin" not in user_columns:
                await conn.execute(text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT 0;"))
        else:
            result = await conn.execute(text(
                "SELECT column_name FROM information_schema.columns WHERE table_name='orders' AND column_name='receipt_message_id';"
            ))
            if not result.fetchone():
                await conn.execute(text("ALTER TABLE orders ADD COLUMN receipt_message_id INTEGER;"))
            result = await conn.execute(text(
                "SELECT column_name FROM information_schema.columns WHERE table_name='users' AND column_name='is_admin';"
            ))
            if not result.fetchone():
                await conn.execute(text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT FALSE;"))

        backfill_sql = text("UPDATE users SET is_admin = :is_admin, is_manager = :is_manager WHERE telegram_id = :telegram_id;")
        for telegram_id in settings.admin_ids_list:
            await conn.execute(
                backfill_sql,
                {"is_admin": True, "is_manager": True, "telegram_id": telegram_id},
            )
    logger.info("Database initialized successfully.")


async def get_session() -> AsyncSession:
    """Dependency-style session getter."""
    async with AsyncSessionFactory() as session:
        yield session
