"""Servicio de usuarios."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import User
from app.db.session import session_scope
from app.repositories.users import UserRepository


class UserService:
    """Casos de uso sobre usuarios internos."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_or_create_by_telegram(
        self,
        *,
        telegram_id: int,
        username: str | None = None,
        first_name: str | None = None,
    ) -> User:
        """Vincula una identidad de Telegram a un usuario interno."""
        async with session_scope(self._session_factory) as session:
            repo = UserRepository(session)
            return await repo.get_or_create(
                telegram_id=telegram_id, username=username, first_name=first_name
            )

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        async with session_scope(self._session_factory) as session:
            repo = UserRepository(session)
            return await repo.get_by_telegram_id(telegram_id)
