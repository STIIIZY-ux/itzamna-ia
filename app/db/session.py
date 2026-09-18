"""Gestión de sesiones de base de datos."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .engine import get_session_factory


@asynccontextmanager
async def session_scope(
    factory: async_sessionmaker[AsyncSession] | None = None,
) -> AsyncIterator[AsyncSession]:
    """Provee una sesión con commit automático y rollback ante errores.

    Si no se pasa ``factory``, se usa la factory global del proceso. Los
    servicios inyectan su propia factory para poder usar una base distinta en
    tests.

    Uso::

        async with session_scope() as session:
            await do_something(session)
    """
    factory = factory or get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
