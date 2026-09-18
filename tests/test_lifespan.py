"""Tests del ciclo de vida (lifespan) de FastAPI + python-telegram-bot.

Se usa un ``Application`` simulado para verificar el cableado del lifespan sin
realizar llamadas de red.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABC-DEF")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_ID", "42")


def make_application() -> MagicMock:
    application = MagicMock()
    application.initialize = AsyncMock()
    application.start = AsyncMock()
    application.stop = AsyncMock()
    application.shutdown = AsyncMock()

    application.updater = MagicMock()
    application.updater.start_polling = AsyncMock()
    application.updater.stop = AsyncMock()

    application.bot = MagicMock()
    application.bot.get_me = AsyncMock(return_value=MagicMock(username="test_bot"))
    application.bot.set_webhook = AsyncMock()
    application.bot.delete_webhook = AsyncMock()
    return application


def test_lifespan_polling_success(
    _env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    application = make_application()
    monkeypatch.setattr("app.main.build_application", lambda: application)

    with TestClient(app) as client:
        assert app.state.bot_ready is True
        application.initialize.assert_awaited_once()
        application.start.assert_awaited_once()
        application.updater.start_polling.assert_awaited_once()
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    application.updater.stop.assert_awaited_once()
    application.stop.assert_awaited_once()
    application.shutdown.assert_awaited_once()
    assert app.state.bot_ready is False


def test_lifespan_startup_failure_is_degraded(
    _env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    application = make_application()
    application.initialize.side_effect = RuntimeError("boom")
    monkeypatch.setattr("app.main.build_application", lambda: application)

    with TestClient(app) as client:
        assert app.state.bot_ready is False
        response = client.get("/health")
        assert response.status_code == 503
        assert response.json() == {"status": "unhealthy"}

    # No se intenta detener lo que nunca arrancó.
    application.stop.assert_not_awaited()
    application.shutdown.assert_not_awaited()


def test_lifespan_webhook_requires_secret(
    _env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("USE_WEBHOOK", "true")
    monkeypatch.setenv("WEBHOOK_URL", "https://example.com/telegram")

    application = make_application()
    monkeypatch.setattr("app.main.build_application", lambda: application)

    with TestClient(app) as client:
        assert app.state.bot_ready is False
        assert client.get("/health").status_code == 503

    application.initialize.assert_not_awaited()


def test_lifespan_webhook_success(
    _env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("USE_WEBHOOK", "true")
    monkeypatch.setenv("WEBHOOK_URL", "https://example.com/telegram")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "secreto")

    application = make_application()
    monkeypatch.setattr("app.main.build_application", lambda: application)

    with TestClient(app) as client:
        assert app.state.bot_ready is True
        assert client.get("/health").status_code == 200

    application.bot.set_webhook.assert_awaited_once_with(
        url="https://example.com/telegram", secret_token="secreto"
    )
    application.bot.delete_webhook.assert_awaited_once()
