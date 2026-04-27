import os
from typing import List
from pydantic_settings import BaseSettings
from pydantic import field_validator, ConfigDict
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    BOT_TOKEN: str
    MANAGER_IDS: str = ""
    DATABASE_URL: str = "sqlite+aiosqlite:///./construction_bot.db"
    TIMEZONE: str = "Asia/Tashkent"
    LOG_LEVEL: str = "INFO"

    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")

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
