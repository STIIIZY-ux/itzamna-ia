"""Repositorio de usuarios."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User


class UserRepository:
    """Acceso a datos de :class:`User`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: int) -> User | None:
        return await self._session.get(User, user_id)

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        result = await self._session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        telegram_id: int,
        username: str | None = None,
        first_name: str | None = None,
    ) -> User:
        user = User(telegram_id=telegram_id, username=username, first_name=first_name)
        self._session.add(user)
        await self._session.flush()
        return user

    async def get_or_create(
        self,
        *,
        telegram_id: int,
        username: str | None = None,
        first_name: str | None = None,
    ) -> User:
        """Obtiene el usuario por ``telegram_id`` o lo crea.

        Maneja la condición de carrera entre creaciones concurrentes mediante
        la restricción única sobre ``telegram_id``.
        """
        user = await self.get_by_telegram_id(telegram_id)
        if user is not None:
            return user
        try:
            return await self.create(
                telegram_id=telegram_id, username=username, first_name=first_name
            )
        except IntegrityError:
            await self._session.rollback()
            user = await self.get_by_telegram_id(telegram_id)
            if user is None:
                raise
            return user
