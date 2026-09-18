"""Motor async de PostgreSQL y factory de sesiones con pool.

El motor y el ``async_sessionmaker`` se crean de forma perezosa y se cachean
a nivel de proceso. ``dispose_engine`` libera el pool y cierra conexiones.
"""

import logging

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings

logger = logging.getLogger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Devuelve (creándolo si es necesario) el motor async global."""
    global _engine
    if _engine is None:
        settings = get_settings()
        if not settings.database_url:
            raise RuntimeError("DATABASE_URL no está configurado")
        _engine = create_async_engine(
            settings.database_url,
            pool_pre_ping=True,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            echo=settings.database_echo,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Devuelve (creándolo si es necesario) el ``async_sessionmaker`` global."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(),
            expire_on_commit=False,
        )
    return _session_factory


async def dispose_engine() -> None:
    """Cierra el pool y libera todas las conexiones del motor."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
