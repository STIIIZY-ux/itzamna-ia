"""Tests del servicio de libros (registro y procesamiento de PDFs)."""

from app.domain.enums import BookStatus
from app.services.books import BookService
from app.storage.local import LocalFileStorage

PDF_TEXT = (
    "%PDF-1.4\n"
    "Capítulo 1\nIntroducción\n\nContenido del capítulo uno.\n\n"
    "Capítulo 2\nDesarrollo\n\nContenido del capítulo dos."
)


async def _make_user(user_service) -> int:
    user = await user_service.get_or_create_by_telegram(telegram_id=1500)
    return user.id


def _service(session_factory, tmp_path):
    return BookService(session_factory, LocalFileStorage(tmp_path))


async def test_register_and_process_book(session, session_factory, tmp_path, user_service) -> None:
    user_id = await _make_user(user_service)
    service = _service(session_factory, tmp_path)

    book = await service.register(user_id=user_id, title="Libro de prueba")
    assert book.status is BookStatus.PENDING

    processed = await service.process(
        book_id=book.id, user_id=user_id, data=PDF_TEXT.encode(), content_type="text/plain"
    )
    assert processed.status is BookStatus.READY
    assert processed.num_chapters == 2


async def test_process_without_structure(session, session_factory, tmp_path, user_service) -> None:
    user_id = await _make_user(user_service)
    service = _service(session_factory, tmp_path)
    book = await service.register(user_id=user_id, title="Sin capítulos")
    processed = await service.process(
        book_id=book.id, user_id=user_id, data=b"texto sin estructura", content_type="text/plain"
    )
    assert processed.status is BookStatus.READY
    assert processed.num_chapters == 0


async def test_attach_pending_no_pending_book(session, session_factory, tmp_path, user_service) -> None:
    user_id = await _make_user(user_service)
    service = _service(session_factory, tmp_path)
    # Sin libro pendiente -> attach devuelve None.
    from app.db.models import Resource

    resource = Resource(user_id=user_id, storage_key="no-existe", resource_type="pdf")
    assert await service.attach_pending(user_id=user_id, resource=resource) is None


async def test_register_book_isolation(session, session_factory, tmp_path, user_service) -> None:
    a = await _make_user(user_service)
    b_user = await user_service.get_or_create_by_telegram(telegram_id=1600)
    service = _service(session_factory, tmp_path)
    await service.register(user_id=a, title="Libro de A")

    from app.db.session import session_scope
    from app.repositories.learning import BookRepository

    async with session_scope(session_factory) as s:
        books_b = await BookRepository(s).list(user_id=b_user.id)
    assert books_b == []
