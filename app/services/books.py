"""Servicio de libros: registro y procesamiento de PDFs (capítulos)."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Book, Resource
from app.db.session import session_scope
from app.domain.enums import BookStatus
from app.repositories.learning import BookRepository, ChapterRepository
from app.storage.base import FileStorage

from .book_processing import detect_chapters, extract_text

logger = logging.getLogger(__name__)

_MAX_CHAPTER_CHARS = 100_000


class BookService:
    """Registra libros y procesa documentos para detectar capítulos."""

    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession], storage: FileStorage
    ) -> None:
        self._session_factory = session_factory
        self._storage = storage

    async def register(
        self, *, user_id: int, title: str, author: str | None = None, source: str | None = None
    ) -> Book:
        async with session_scope(self._session_factory) as session:
            return await BookRepository(session).create(
                user_id=user_id, title=title, author=author, source=source
            )

    async def attach_pending(self, *, user_id: int, resource: Resource) -> Book | None:
        """Asocia un PDF recién subido al libro pendiente y lo procesa."""
        if resource.storage_key is None:
            return None
        async with session_scope(self._session_factory) as session:
            repo = BookRepository(session)
            book = await repo.get_pending(user_id=user_id)
            if book is None:
                return None
            await repo.update(book, status=BookStatus.PROCESSING, storage_key=resource.storage_key)
        try:
            data = self._storage.load(resource.storage_key)
        except Exception as exc:  # noqa: BLE001
            logger.warning("No se pudo leer el PDF %s: %s", resource.storage_key, exc)
            async with session_scope(self._session_factory) as session:
                book = await BookRepository(session).get(user_id=user_id, book_id=book.id)
                if book is not None:
                    await BookRepository(session).update(book, status=BookStatus.FAILED)
            return None
        return await self.process(book_id=book.id, user_id=user_id, data=data, content_type="application/pdf")

    async def process(
        self, *, book_id: int, user_id: int, data: bytes, content_type: str
    ) -> Book:
        text = extract_text(data, content_type)
        chapters = detect_chapters(text)

        async with session_scope(self._session_factory) as session:
            book_repo = BookRepository(session)
            chapter_repo = ChapterRepository(session)
            book = await book_repo.get(user_id=user_id, book_id=book_id)
            if book is None:
                raise LookupError(f"Libro {book_id} no encontrado")

            for index, spec in enumerate(chapters):
                await chapter_repo.create(
                    book_id=book.id,
                    user_id=user_id,
                    number=spec.number,
                    title=spec.title,
                    order_index=index,
                    content=spec.content[:_MAX_CHAPTER_CHARS],
                )

            return await book_repo.update(
                book, status=BookStatus.READY, num_chapters=len(chapters)
            )
