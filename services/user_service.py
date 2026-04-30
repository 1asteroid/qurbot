import logging
from typing import Optional, List
from sqlalchemy import select, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from config import settings
from database.models import User

logger = logging.getLogger(__name__)


class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _ensure_permanent_manager(self, user: User) -> User:
        if user and settings.is_permanent_manager(user.telegram_id) and not user.is_manager:
            user.is_manager = True
            self.session.add(user)
            await self.session.commit()
            await self.session.refresh(user)
        return user

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        if user:
            return await self._ensure_permanent_manager(user)
        return None

    async def create(self, telegram_id: int, full_name: str, phone: str) -> User:
        # Manager tekshiruvi
        is_manager = telegram_id in settings.manager_ids_list or settings.is_permanent_manager(telegram_id)
        
        user = User(
            telegram_id=telegram_id, 
            full_name=full_name, 
            phone=phone,
            is_manager=is_manager
        )
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        logger.info(f"Created user telegram_id={telegram_id} name={full_name} is_manager={is_manager}")
        return user

    async def get_or_create(self, telegram_id: int, full_name: str, phone: str) -> tuple[User, bool]:
        user = await self.get_by_telegram_id(telegram_id)
        if user:
            return user, False
        user = await self.create(telegram_id, full_name, phone)
        return user, True

    async def get_all_latest(self, limit: int = 30) -> List[User]:
        result = await self.session.execute(
            select(User).order_by(desc(User.created_at)).limit(limit)
        )
        return list(result.scalars().all())

    async def search(self, query: str) -> List[User]:
        pattern = f"%{query}%"
        result = await self.session.execute(
            select(User)
            .where(or_(User.full_name.ilike(pattern), User.phone.ilike(pattern)))
            .order_by(desc(User.created_at))
            .limit(20)
        )
        return list(result.scalars().all())

    async def get_by_id(self, user_id: int) -> Optional[User]:
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
