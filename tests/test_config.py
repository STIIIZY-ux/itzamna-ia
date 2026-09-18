"""Tests de configuración."""

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_settings_loads_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABC-DEF")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_ID", "42")
    settings = Settings(_env_file=())
    assert settings.telegram_bot_token == "123456:ABC-DEF"
    assert settings.telegram_allowed_user_id == 42


def test_settings_defaults() -> None:
    settings = Settings(
        _env_file=(),
        telegram_bot_token="123456:ABC-DEF",
        telegram_allowed_user_id=42,
    )
    assert settings.environment == "development"
    assert settings.use_webhook is False
    assert settings.port == 8080
    assert settings.is_development is True


def test_settings_empty_token_raises() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=(), telegram_bot_token="", telegram_allowed_user_id=1)


def test_settings_invalid_token_format_raises() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=(),
            telegram_bot_token="sin-dos-puntos",
            telegram_allowed_user_id=1,
        )


def test_settings_negative_user_id_raises() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=(), telegram_bot_token="1:a", telegram_allowed_user_id=-5)


def test_settings_webhook_secret_defaults_to_none() -> None:
    settings = Settings(_env_file=(), telegram_bot_token="1:a", telegram_allowed_user_id=1)
    assert settings.telegram_webhook_secret is None


def test_settings_webhook_secret_loads_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "1:a")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_ID", "1")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "mi-secreto")
    settings = Settings(_env_file=())
    assert settings.telegram_webhook_secret == "mi-secreto"
