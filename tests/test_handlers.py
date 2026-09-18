"""Tests de los manejadores del bot."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.error import InvalidToken

from app.bot.handlers import (
    GREETING,
    NOT_AUTHORIZED,
    build_reply,
    handle_application_error,
    handle_text,
    is_user_authorized,
    register_handlers,
    start_command,
)

ALLOWED_ID = 123
TOKEN = "123456:ABC-DEF"


@pytest.fixture
def _allowed_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABC-DEF")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_ID", str(ALLOWED_ID))


def make_update(user_id: int, text: str | None = None) -> MagicMock:
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = user_id
    update.effective_user.first_name = "Test"
    update.message = AsyncMock()
    update.message.text = text
    return update


@pytest.mark.parametrize(
    "user_id, expected",
    [(ALLOWED_ID, True), (999, False), (None, False)],
)
def test_is_user_authorized(
    _allowed_env: None, user_id: int | None, expected: bool
) -> None:
    assert is_user_authorized(user_id) is expected


def test_build_reply_greeting() -> None:
    assert build_reply("Hola") == GREETING
    assert build_reply("hola") == GREETING


def test_build_reply_fallback() -> None:
    assert build_reply("Necesito ayuda") == "Recibí tu mensaje: Necesito ayuda"


def test_build_reply_empty() -> None:
    assert build_reply(None) == GREETING


def test_handle_text_authorized(_allowed_env: None) -> None:
    update = make_update(ALLOWED_ID, "Hola")
    context = MagicMock()
    asyncio.run(handle_text(update, context))
    update.message.reply_text.assert_awaited_once_with(GREETING)


def test_handle_text_unauthorized(_allowed_env: None) -> None:
    update = make_update(999, "Hola")
    context = MagicMock()
    asyncio.run(handle_text(update, context))
    update.message.reply_text.assert_awaited_once_with(NOT_AUTHORIZED)


def test_start_command_authorized(_allowed_env: None) -> None:
    update = make_update(ALLOWED_ID, "/start")
    context = MagicMock()
    asyncio.run(start_command(update, context))
    update.message.reply_text.assert_awaited_once_with(
        "Hola, Test. Estoy listo para ayudarte."
    )


def test_start_command_unauthorized(_allowed_env: None) -> None:
    update = make_update(999, "/start")
    context = MagicMock()
    asyncio.run(start_command(update, context))
    update.message.reply_text.assert_awaited_once_with(NOT_AUTHORIZED)


async def test_error_handler_redacts_token(_allowed_env: None) -> None:
    error = InvalidToken(f"token rechazado: {TOKEN}")
    context = MagicMock()
    context.error = error

    with patch("app.bot.handlers.logger") as mock_logger:
        await handle_application_error(None, context)

    mock_logger.error.assert_called_once()
    message = mock_logger.error.call_args.args[1]
    assert TOKEN not in message
    assert "[REDACTED]" in message


async def test_error_handler_handles_missing_error(_allowed_env: None) -> None:
    context = MagicMock()
    context.error = None

    with patch("app.bot.handlers.logger") as mock_logger:
        await handle_application_error(None, context)

    mock_logger.error.assert_called_once_with(
        "Error desconocido al procesar una actualización de Telegram"
    )


def test_register_handlers_adds_error_handler(_allowed_env: None) -> None:
    application = MagicMock()
    register_handlers(application)
    application.add_error_handler.assert_called_once_with(handle_application_error)
