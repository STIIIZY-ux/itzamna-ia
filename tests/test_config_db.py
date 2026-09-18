"""Tests de configuración de persistencia."""

import pytest

from app.config import Settings


def test_database_url_defaults_to_none() -> None:
    settings = Settings(_env_file=(), telegram_bot_token="1:a", telegram_allowed_user_id=1)
    assert settings.database_url is None


def test_database_url_loads_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "1:a")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_ID", "1")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
    settings = Settings(_env_file=())
    assert settings.database_url == "postgresql+asyncpg://u:p@localhost/db"


def test_database_pool_defaults() -> None:
    settings = Settings(_env_file=(), telegram_bot_token="1:a", telegram_allowed_user_id=1)
    assert settings.database_pool_size == 5
    assert settings.database_max_overflow == 10
    assert settings.database_echo is False
