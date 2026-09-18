"""Repositorio de credenciales de Google Calendar."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import GoogleCredential


class GoogleCredentialRepository:
    """Acceso a datos de :class:`GoogleCredential`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_user(self, user_id: int) -> GoogleCredential | None:
        result = await self._session.execute(
            select(GoogleCredential).where(GoogleCredential.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        *,
        user_id: int,
        refresh_token_encrypted: str,
        access_token_encrypted: str | None = None,
        token_expires_at: datetime | None = None,
        scopes: str | None = None,
    ) -> GoogleCredential:
        credential = await self.get_by_user(user_id)
        if credential is None:
            credential = GoogleCredential(user_id=user_id)
            self._session.add(credential)
        credential.refresh_token_encrypted = refresh_token_encrypted
        credential.access_token_encrypted = access_token_encrypted
        credential.token_expires_at = token_expires_at
        if scopes is not None:
            credential.scopes = scopes
        await self._session.flush()
        return credential

    async def delete(self, user_id: int) -> bool:
        credential = await self.get_by_user(user_id)
        if credential is None:
            return False
        await self._session.delete(credential)
        await self._session.flush()
        return True
