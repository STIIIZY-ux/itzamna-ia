"""Tests del control de lectura y el fixture de calendario."""

from app.db.session import session_scope
from app.domain.enums import QuizType, TaskSource
from app.repositories.tasks import TaskRepository
from app.services.calendar_sync import CalendarSyncService
from app.services.reading import ReadingControlService
from tests.fake_ai import FakeAIService
from tests.fixtures.calendar import CALENDAR_EVENTS, PROGRAMACION_DESCRIPTION

TZ = "America/Tijuana"


class FakeClient:
    def __init__(self, events):
        self._events = events

    async def list_events(self, *, user_id, calendar_id, time_min, time_max):
        return list(self._events)


async def _make_user(user_service) -> int:
    user = await user_service.get_or_create_by_telegram(telegram_id=1700)
    return user.id


async def test_calendar_fixtures_dedup_and_normalize(session, session_factory, user_service) -> None:
    user_id = await _make_user(user_service)
    service = CalendarSyncService(
        session_factory=session_factory,
        client=FakeClient(CALENDAR_EVENTS),
        timezone=TZ,
        calendar_id="primary",
        time_window_days=30,
    )
    await service.sync(user_id=user_id)

    async with session_scope(session_factory) as s:
        tasks = await TaskRepository(s).list_by_source(user_id=user_id, source=TaskSource.GOOGLE_CALENDAR)

    titles = {t.title for t in tasks}
    # El duplicado "1.1 Estructura secuencial" se consolida en una sola tarea.
    secuenciales = [t for t in tasks if "1.1 Estructura secuencial" in t.title]
    assert len(secuenciales) == 1
    assert any("Lectura" in t for t in titles)
    assert any("Proyecto final" in t for t in titles)


async def test_fixture_description_has_materials(session) -> None:
    assert "algoritmo" in PROGRAMACION_DESCRIPTION
    assert "diagrama de flujo" in PROGRAMACION_DESCRIPTION
    assert "pseudocódigo" in PROGRAMACION_DESCRIPTION


async def test_reading_control_generates_quiz(session, session_factory, tmp_path, user_service) -> None:
    from app.services.books import BookService
    from app.storage.local import LocalFileStorage

    user_id = await _make_user(user_service)
    book_service = BookService(session_factory, LocalFileStorage(tmp_path))
    book = await book_service.register(user_id=user_id, title="Libro")
    await book_service.process(
        book_id=book.id,
        user_id=user_id,
        data="Capítulo 1: Introducción\n\nContenido del capítulo uno.".encode(),
        content_type="text/plain",
    )

    ai = FakeAIService(
        ['{"questions": [{"type": "short_answer", "prompt": "De que trata el capitulo?", "expected_answer": "Introduccion", "explanation": "..."}]}']
    )
    quiz = await ReadingControlService(session_factory, ai).chapter_control(
        user_id=user_id, book_id=book.id
    )
    assert quiz is not None
    assert quiz.quiz_type is QuizType.CHAPTER


async def test_reading_control_without_ai_returns_none(
    session, session_factory, tmp_path, user_service
) -> None:
    from app.services.books import BookService
    from app.storage.local import LocalFileStorage

    user_id = await _make_user(user_service)
    book_service = BookService(session_factory, LocalFileStorage(tmp_path))
    book = await book_service.register(user_id=user_id, title="Libro")
    await book_service.process(
        book_id=book.id, user_id=user_id, data=b"Cap\xc3\xadtulo 1: X\n\ntexto", content_type="text/plain"
    )

    quiz = await ReadingControlService(session_factory, None).chapter_control(
        user_id=user_id, book_id=book.id
    )
    assert quiz is None
