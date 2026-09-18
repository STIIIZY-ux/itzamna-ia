"""Servicio de credenciales OAuth de Google Calendar."""

from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import GoogleCredential
from app.db.session import session_scope
from app.integrations.google.auth import OAuthConfig, Tokens, refresh_access_token
from app.integrations.google.crypto import TokenCipher
from app.integrations.google.errors import GoogleAuthError
from app.repositories.google_credentials import GoogleCredentialRepository

_ACCESS_TOKEN_BUFFER = timedelta(minutes=5)


class GoogleCredentialsService:
    """Gestiona el ciclo de vida de las credenciales OAuth (cifradas)."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        cipher: TokenCipher,
        config: OAuthConfig,
    ) -> None:
        self._session_factory = session_factory
        self._cipher = cipher
        self._config = config

    async def save_tokens(self, user_id: int, tokens: Tokens) -> None:
        """Almacena tokens tras el flujo de autorización (refresh + access)."""
        if not tokens.refresh_token:
            raise GoogleAuthError("No se recibió refresh_token en el intercambio")
        async with session_scope(self._session_factory) as session:
            repo = GoogleCredentialRepository(session)
            await repo.upsert(
                user_id=user_id,
                refresh_token_encrypted=self._cipher.encrypt(tokens.refresh_token),
                access_token_encrypted=self._cipher.encrypt(tokens.access_token),
                token_expires_at=tokens.expires_at,
                scopes=tokens.scope,
            )

    async def has_credentials(self, user_id: int) -> bool:
        async with session_scope(self._session_factory) as session:
            repo = GoogleCredentialRepository(session)
            return await repo.get_by_user(user_id) is not None

    async def get_access_token(self, user_id: int) -> str:
        """Devuelve un access token válido, renovándolo si es necesario."""
        async with session_scope(self._session_factory) as session:
            repo = GoogleCredentialRepository(session)
            cred = await repo.get_by_user(user_id)
            if cred is None:
                raise GoogleAuthError("No hay credenciales de Google conectadas")

            if _access_token_is_valid(cred):
                return self._cipher.decrypt(cred.access_token_encrypted)  # type: ignore[arg-type]

            refresh_token = self._cipher.decrypt(cred.refresh_token_encrypted)
            tokens = await refresh_access_token(self._config, refresh_token)
            cred.access_token_encrypted = self._cipher.encrypt(tokens.access_token)
            cred.token_expires_at = tokens.expires_at
            if tokens.scope:
                cred.scopes = tokens.scope
            await session.flush()
            return tokens.access_token

    async def get_refresh_token(self, user_id: int) -> str:
        async with session_scope(self._session_factory) as session:
            cred = await GoogleCredentialRepository(session).get_by_user(user_id)
            if cred is None:
                raise GoogleAuthError("No hay credenciales de Google conectadas")
            return self._cipher.decrypt(cred.refresh_token_encrypted)

    async def revoke(self, user_id: int) -> None:
        async with session_scope(self._session_factory) as session:
            repo = GoogleCredentialRepository(session)
            await repo.delete(user_id)


def _access_token_is_valid(cred: GoogleCredential) -> bool:
    return bool(
        cred.access_token_encrypted
        and cred.token_expires_at
        and cred.token_expires_at > datetime.now(timezone.utc) + _ACCESS_TOKEN_BUFFER
    )
