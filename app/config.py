"""Application settings loaded from environment / .env (never hardcode secrets)."""
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Telegram
    BOT_TOKEN: str
    BOT_USERNAME: str
    WEBHOOK_SECRET: str
    PUBLIC_URL: str
    ADMIN_TELEGRAM_ID: int

    # Database
    DATABASE_URL: str = "sqlite:///./shopbot.db"

    # Business
    SUBSCRIPTION_PRICE_ETB: int = 500
    PAYMENT_ACCOUNT: str = ""
    TRIAL_DAYS: int = 14

    # AI
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    AI_PER_CUSTOMER_HOURLY: int = 10
    AI_PER_SHOP_DAILY: int = 300
    AI_GLOBAL_DAILY: int = 3000

    # Misc
    IMAGE_CACHE_DIR: str = "/tmp/shopbot-img"
    IMAGE_CACHE_MAX_MB: int = 200
    LOG_LEVEL: str = "INFO"
    ENV: str = "development"
    INITDATA_MAX_AGE_SECONDS: int = 24 * 3600

    @field_validator("PUBLIC_URL")
    @classmethod
    def _strip_slash(cls, v: str) -> str:
        return v.rstrip("/")

    @field_validator("DATABASE_URL")
    @classmethod
    def _normalize_db_url(cls, v: str) -> str:
        # Managed Postgres providers often hand out "postgres://"; SQLAlchemy 2 + psycopg3 need this form.
        if v.startswith("postgres://"):
            v = "postgresql+psycopg://" + v[len("postgres://"):]
        elif v.startswith("postgresql://"):
            v = "postgresql+psycopg://" + v[len("postgresql://"):]
        return v

    @property
    def webhook_url(self) -> str:
        return f"{self.PUBLIC_URL}/telegram/webhook"

    @property
    def webapp_url(self) -> str:
        return f"{self.PUBLIC_URL}/app/"

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()
