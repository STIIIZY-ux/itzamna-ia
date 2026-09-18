"""Tests del endpoint /telegram (webhook seguro)."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app

TOKEN = "123456:ABC-DEF"
SECRET = "webhook-super-secreto"


@pytest.fixture
def fake_application() -> MagicMock:
    fake = MagicMock()
    fake.bot = MagicMock()
    fake.process_update = AsyncMock()
    return fake


@pytest.fixture
def client(fake_application: MagicMock) -> TestClient:
    app.state.telegram_application = fake_application
    app.state.bot_ready = True
    return TestClient(app)


@pytest.fixture
def webhook_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", TOKEN)
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_ID", "42")
    monkeypatch.setenv("USE_WEBHOOK", "true")
    monkeypatch.setenv("WEBHOOK_URL", "https://example.com/telegram")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", SECRET)


def _post(client: TestClient, header: str | None) -> None:
    headers = {"X-Telegram-Bot-Api-Secret-Token": header} if header is not None else {}
    return client.post("/telegram", json={"update_id": 1}, headers=headers)


def test_webhook_with_correct_secret(
    webhook_env: None, client: TestClient, fake_application: MagicMock
) -> None:
    response = _post(client, SECRET)
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    fake_application.process_update.assert_awaited_once()


def test_webhook_with_incorrect_secret(
    webhook_env: None, client: TestClient, fake_application: MagicMock
) -> None:
    response = _post(client, "secreto-erroneo")
    assert response.status_code == 403
    fake_application.process_update.assert_not_awaited()


def test_webhook_without_header(
    webhook_env: None, client: TestClient, fake_application: MagicMock
) -> None:
    response = _post(client, None)
    assert response.status_code == 403
    fake_application.process_update.assert_not_awaited()


def test_webhook_disabled(
    client: TestClient, fake_application: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", TOKEN)
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_ID", "42")
    monkeypatch.setenv("USE_WEBHOOK", "false")
    response = _post(client, SECRET)
    assert response.status_code == 404
    fake_application.process_update.assert_not_awaited()


def test_webhook_without_secret(
    client: TestClient, fake_application: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", TOKEN)
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_ID", "42")
    monkeypatch.setenv("USE_WEBHOOK", "true")
    monkeypatch.setenv("WEBHOOK_URL", "https://example.com/telegram")
    monkeypatch.delenv("TELEGRAM_WEBHOOK_SECRET", raising=False)
    response = _post(client, SECRET)
    assert response.status_code == 403
    fake_application.process_update.assert_not_awaited()


def test_webhook_malformed_json(
    webhook_env: None, client: TestClient, fake_application: MagicMock
) -> None:
    response = client.post(
        "/telegram",
        content=b"{invalid",
        headers={
            "X-Telegram-Bot-Api-Secret-Token": SECRET,
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 400
    fake_application.process_update.assert_not_awaited()


def test_webhook_non_dict_payload(
    webhook_env: None, client: TestClient, fake_application: MagicMock
) -> None:
    response = client.post(
        "/telegram",
        json=[1, 2, 3],
        headers={"X-Telegram-Bot-Api-Secret-Token": SECRET},
    )
    assert response.status_code == 400
    fake_application.process_update.assert_not_awaited()
