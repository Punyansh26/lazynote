import pytest
from lazynote.config import Settings, get_settings


def test_settings_database_url_normalization():
    # Test postgresql:// conversion to postgresql+asyncpg://
    settings = Settings(
        POSTGRES_CONNECTION_STRING="postgresql://user:pass@localhost:5432/db"
    )
    assert settings.async_database_url == "postgresql+asyncpg://user:pass@localhost:5432/db"


def test_settings_preserves_asyncpg_prefix():
    settings = Settings(
        POSTGRES_CONNECTION_STRING="postgresql+asyncpg://user:pass@localhost:5432/db"
    )
    assert settings.async_database_url == "postgresql+asyncpg://user:pass@localhost:5432/db"


def test_cached_settings_instance():
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
