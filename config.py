import os
from typing import List
from pydantic_settings import BaseSettings
from pydantic import field_validator, ConfigDict
from dotenv import load_dotenv

load_dotenv()


def _fix_database_url(url: str) -> str:
    """Convert Heroku's postgres:// URL to the asyncpg-compatible scheme."""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://") and "+asyncpg" not in url:
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


class Settings(BaseSettings):
    BOT_TOKEN: str
    MANAGER_IDS: str = ""
    ADMIN_IDS: str = "1504360843"
    PERMANENT_MANAGER_IDS: str = "1504360843"
    DATABASE_URL: str = "sqlite+aiosqlite:///./construction_bot.db"
    TIMEZONE: str = "Asia/Tashkent"
    LOG_LEVEL: str = "INFO"

    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")

    @field_validator("DATABASE_URL", mode="after")
    @classmethod
    def normalise_database_url(cls, v: str) -> str:
        return _fix_database_url(v)

    @property
    def manager_ids_list(self) -> List[int]:
        ids = []
        for raw in (self.MANAGER_IDS, self.PERMANENT_MANAGER_IDS):
            if not raw:
                continue
            for x in raw.split(","):
                try:
                    ids.append(int(x.strip()))
                except ValueError:
                    continue
        return list(dict.fromkeys(ids))

    @property
    def admin_ids_list(self) -> List[int]:
        ids = []
        for raw in (self.ADMIN_IDS,):
            if not raw:
                continue
            for x in raw.split(","):
                try:
                    ids.append(int(x.strip()))
                except ValueError:
                    continue
        return list(dict.fromkeys(ids))

    def is_admin(self, telegram_id: int) -> bool:
        return telegram_id in set(self.admin_ids_list)

    def is_permanent_manager(self, telegram_id: int) -> bool:
        if not self.PERMANENT_MANAGER_IDS:
            return False
        return telegram_id in {
            int(x.strip())
            for x in self.PERMANENT_MANAGER_IDS.split(",")
            if x.strip().isdigit()
        }


settings = Settings()
