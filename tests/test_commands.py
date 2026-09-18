"""Tests de los comandos del planner/accountability."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from app.bot.handlers import (
    commit_command,
    mode_command,
    next_command,
    silence_command,
    status_command,
)
from app.db.models import Commitment
from app.domain.enums import CommitmentStatus

ALLOWED_ID = 123


@pytest.fixture
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABC-DEF")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_ID", str(ALLOWED_ID))


def make_update(user_id: int) -> MagicMock:
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = user_id
    update.effective_user.first_name = "Test"
    update.effective_user.username = "test"
    update.message = AsyncMock()
    return update


def make_context(session_factory, args: list[str] | None = None) -> MagicMock:
    context = MagicMock()
    context.bot_data = {"session_factory": session_factory}
    context.args = args or []
    return context


async def _allowed_user(user_service) -> int:
    user = await user_service.get_or_create_by_telegram(telegram_id=ALLOWED_ID)
    return user.id


async def test_next_command_unauthorized(session_factory, _env) -> None:
    update = make_update(999)
    context = make_context(session_factory)
    await next_command(update, context)
    update.message.reply_text.assert_awaited_once()
    assert "No estás autorizado" in update.message.reply_text.call_args.args[0]


async def test_next_command_no_tasks(session, session_factory, user_service, _env) -> None:
    await _allowed_user(user_service)
    update = make_update(ALLOWED_ID)
    context = make_context(session_factory)
    await next_command(update, context)
    assert "No tienes tareas pendientes" in update.message.reply_text.call_args.args[0]


async def test_next_command_with_task(session, session_factory, user_service, task_service, _env) -> None:
    user_id = await _allowed_user(user_service)
    await task_service.create_task(user_id=user_id, title="Entregar ensayo")
    update = make_update(ALLOWED_ID)
    context = make_context(session_factory)
    await next_command(update, context)
    assert "Entregar ensayo" in update.message.reply_text.call_args.args[0]


async def test_estado_command(session, session_factory, user_service, task_service, _env) -> None:
    user_id = await _allowed_user(user_service)
    await task_service.create_task(user_id=user_id, title="Tarea A")
    update = make_update(ALLOWED_ID)
    context = make_context(session_factory)
    await status_command(update, context)
    text = update.message.reply_text.call_args.args[0]
    assert "Pendientes" in text
    assert "Tarea A" in text


async def test_silencio_command(session, session_factory, user_service, _env) -> None:
    await _allowed_user(user_service)
    update = make_update(ALLOWED_ID)
    context = make_context(session_factory, args=["30"])
    await silence_command(update, context)
    assert "Silencio activado" in update.message.reply_text.call_args.args[0]


async def test_silencio_off(session, session_factory, user_service, _env) -> None:
    await _allowed_user(user_service)
    update = make_update(ALLOWED_ID)
    context = make_context(session_factory, args=["off"])
    await silence_command(update, context)
    assert "Silencio desactivado" in update.message.reply_text.call_args.args[0]


async def test_empiezo_command_creates_commitment(
    session, session_factory, user_service, task_service, _env
) -> None:
    user_id = await _allowed_user(user_service)
    task = await task_service.create_task(user_id=user_id, title="Tarea B")
    update = make_update(ALLOWED_ID)
    context = make_context(session_factory, args=[str(task.id)])
    await commit_command(update, context)
    assert "Compromiso registrado" in update.message.reply_text.call_args.args[0]

    commitments = (
        (await session.execute(
            select(Commitment).where(Commitment.task_id == task.id, Commitment.status == CommitmentStatus.ACTIVO)
        ))
        .scalars()
        .all()
    )
    assert len(commitments) == 1


async def test_mode_command(session, session_factory, user_service, _env) -> None:
    await _allowed_user(user_service)
    update = make_update(ALLOWED_ID)
    context = make_context(session_factory, args=["guerra"])
    await mode_command(update, context)
    assert "Modo: guerra" in update.message.reply_text.call_args.args[0]
