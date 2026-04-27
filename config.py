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
        if not self.MANAGER_IDS:
            return []
        ids = []
        for x in self.MANAGER_IDS.split(","):
            try:
                ids.append(int(x.strip()))
            except ValueError:
                continue
        return ids


settings = Settings()
