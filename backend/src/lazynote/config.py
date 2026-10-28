from functools import lru_cache
from typing import List

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    """Application configuration loaded from environment variables and .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application settings
    APP_NAME: str = "Lazy Note API"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    PORT: int = 8000

    # Database
    POSTGRES_CONNECTION_STRING: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/lazynote",
        description="PostgreSQL connection string",
    )

    # Storage settings
    STORAGE_DRIVER: str = "local"  # "local" | "r2"
    UPLOAD_DIR: str = "./uploads"

    # Cloudflare R2 / S3 storage (optional)
    R2_ACCOUNT_ID: str | None = None
    R2_ACCESS_KEY_ID: str | None = None
    R2_SECRET_ACCESS_KEY: str | None = None
    R2_BUCKET_NAME: str | None = None

    # AI & Speech Services
    SARVAM_API_KEY: str | None = None
    GEMINI_API_KEY: str | None = None

    # CORS Allowed Origins
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    @property
    def async_database_url(self) -> str:
        """Ensure database URL has the asyncpg dialect prefix for SQLAlchemy async engine."""
        url = self.POSTGRES_CONNECTION_STRING
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()
