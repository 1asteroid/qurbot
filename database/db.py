import logging
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import text
from config import settings
from database.models import Base

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
        if settings.DATABASE_URL.startswith("sqlite"):
            rows = (await conn.execute(text("PRAGMA table_info(orders);"))).fetchall()
            columns = {row[1] for row in rows}
            if "receipt_message_id" not in columns:
                await conn.execute(text("ALTER TABLE orders ADD COLUMN receipt_message_id INTEGER;"))
        else:
            result = await conn.execute(text(
                "SELECT column_name FROM information_schema.columns WHERE table_name='orders' AND column_name='receipt_message_id';"
            ))
            if not result.fetchone():
                await conn.execute(text("ALTER TABLE orders ADD COLUMN receipt_message_id INTEGER;"))
    logger.info("Database initialized successfully.")


async def get_session() -> AsyncSession:
    """Dependency-style session getter."""
    async with AsyncSessionFactory() as session:
        yield session
