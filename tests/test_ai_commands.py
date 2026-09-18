"""Tests de los comandos de IA (tutor y emergencia)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.bot.handlers import panic_command, tutor_command
from app.domain.enums import TaskPriority
from tests.fake_ai import FakeAIService

ALLOWED_ID = 123


@pytest.fixture
def _env(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABC-DEF")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_ID", str(ALLOWED_ID))
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "files"))


def make_update(user_id: int, text: str) -> MagicMock:
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = user_id
    update.effective_user.first_name = "Test"
    update.effective_user.username = "test"
    update.message = AsyncMock()
    update.message.text = text
    return update


def make_context(session_factory, ai) -> MagicMock:
    context = MagicMock()
    context.bot_data = {"session_factory": session_factory, "ai_service": ai}
    context.args = []
    return context


async def _allowed_user(user_service) -> int:
    user = await user_service.get_or_create_by_telegram(telegram_id=ALLOWED_ID)
    return user.id


async def test_tutor_unauthorized(session_factory, _env) -> None:
    update = make_update(999, "/concepto")
    context = make_context(session_factory, FakeAIService())
    await tutor_command(update, context)
    assert "No estás autorizado" in update.message.reply_text.call_args.args[0]


async def test_tutor_no_ai(session, session_factory, user_service, _env) -> None:
    await _allowed_user(user_service)
    update = make_update(ALLOWED_ID, "/concepto")
    context = make_context(session_factory, None)
    await tutor_command(update, context)
    assert "IA no está disponible" in update.message.reply_text.call_args.args[0]


async def test_tutor_no_tasks(session, session_factory, user_service, _env) -> None:
    await _allowed_user(user_service)
    update = make_update(ALLOWED_ID, "/concepto")
    context = make_context(session_factory, FakeAIService())
    await tutor_command(update, context)
    assert "No tienes tareas pendientes" in update.message.reply_text.call_args.args[0]


async def test_tutor_with_task(
    session, session_factory, user_service, task_service, _env
) -> None:
    user_id = await _allowed_user(user_service)
    await task_service.create_task(user_id=user_id, title="Estructuras secuenciales")
    update = make_update(ALLOWED_ID, "/concepto")
    context = make_context(session_factory, FakeAIService(["💡 Concepto: orden de ejecución"]))
    await tutor_command(update, context)
    assert "Concepto" in update.message.reply_text.call_args.args[0]


async def test_panic_deterministic(
    session, session_factory, user_service, task_service, _env
) -> None:
    user_id = await _allowed_user(user_service)
    await task_service.create_task(
        user_id=user_id,
        title="Entrega",
        priority=TaskPriority.URGENTE,
    )
    update = make_update(ALLOWED_ID, "/panic")
    context = make_context(session_factory, None)
    await panic_command(update, context)
    assert "FASE 1" in update.message.reply_text.call_args.args[0]


async def test_panic_no_tasks(session, session_factory, user_service, _env) -> None:
    await _allowed_user(user_service)
    update = make_update(ALLOWED_ID, "/panic")
    context = make_context(session_factory, None)
    await panic_command(update, context)
    assert "No hay ninguna actividad en estado crítico" in update.message.reply_text.call_args.args[0]
