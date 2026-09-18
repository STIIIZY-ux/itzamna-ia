"""Tests de los handlers de fotos/documentos (evidencia)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.bot.handlers import handle_document, handle_photo
from app.services.accountability import AccountabilityService

ALLOWED_ID = 123
JPEG = b"\xff\xd8\xff" + b"\x00" * 64


@pytest.fixture
def _env(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABC-DEF")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_ID", str(ALLOWED_ID))
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "files"))


def make_photo_update(user_id: int) -> MagicMock:
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = user_id
    update.effective_user.first_name = "Test"
    update.effective_user.username = "test"
    update.message = AsyncMock()
    update.message.message_id = 5
    photo = MagicMock()
    photo.file_id = "file-123"
    photo.file_unique_id = "fu-123"
    photo.file_size = 1000
    update.message.photo = [photo]
    update.message.document = None
    return update


def make_document_update(user_id: int) -> MagicMock:
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = user_id
    update.effective_user.first_name = "Test"
    update.effective_user.username = "test"
    update.message = AsyncMock()
    update.message.message_id = 6
    update.message.photo = []
    doc = MagicMock()
    doc.file_id = "doc-123"
    doc.file_unique_id = "fud-123"
    doc.file_name = "guia.pdf"
    doc.file_size = 1000
    update.message.document = doc
    return update


def make_context(session_factory) -> MagicMock:
    context = MagicMock()
    context.bot_data = {"session_factory": session_factory}
    fake_file = MagicMock()
    fake_file.download_as_bytearray = AsyncMock(return_value=bytearray(JPEG))
    context.bot = MagicMock()
    context.bot.get_file = AsyncMock(return_value=fake_file)
    context.args = []
    return context


async def _allowed_user(user_service) -> int:
    user = await user_service.get_or_create_by_telegram(telegram_id=ALLOWED_ID)
    return user.id


async def test_handle_photo_unauthorized(session_factory, _env) -> None:
    update = make_photo_update(999)
    context = make_context(session_factory)
    await handle_photo(update, context)
    update.message.reply_text.assert_awaited_once()
    assert "No estás autorizado" in update.message.reply_text.call_args.args[0]


async def test_handle_photo_with_task(
    session, session_factory, user_service, task_service, _env
) -> None:
    user_id = await _allowed_user(user_service)
    task = await task_service.create_task(user_id=user_id, title="Tarea con evidencia")
    await AccountabilityService(session_factory).mark_evidence_requested(
        user_id=user_id, task_id=task.id
    )

    update = make_photo_update(ALLOWED_ID)
    context = make_context(session_factory)
    await handle_photo(update, context)

    assert "Evidencia recibida y guardada" in update.message.reply_text.call_args.args[0]


async def test_handle_photo_without_task(
    session, session_factory, user_service, _env
) -> None:
    await _allowed_user(user_service)
    update = make_photo_update(ALLOWED_ID)
    context = make_context(session_factory)
    await handle_photo(update, context)

    assert "no identifiqué la tarea" in update.message.reply_text.call_args.args[0]


async def test_handle_document_pdf(
    session, session_factory, user_service, _env
) -> None:
    await _allowed_user(user_service)
    update = make_document_update(ALLOWED_ID)
    context = make_context(session_factory)
    # Simula un PDF real.
    context.bot.get_file.return_value.download_as_bytearray.return_value = bytearray(
        b"%PDF-1.4" + b"\x00" * 64
    )
    await handle_document(update, context)

    assert "Documento recibido" in update.message.reply_text.call_args.args[0]
