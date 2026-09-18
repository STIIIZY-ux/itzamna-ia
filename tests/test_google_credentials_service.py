"""Tests del servicio de credenciales de Google (cifrado + refresh)."""

import pytest
from cryptography.fernet import Fernet

from app.integrations.google.auth import OAuthConfig, Tokens
from app.integrations.google.crypto import TokenCipher
from app.integrations.google.errors import GoogleAuthError
from app.services.google_credentials import GoogleCredentialsService

CONFIG = OAuthConfig(client_id="c", client_secret="s", redirect_uri="http://localhost")


@pytest.fixture
def cipher() -> TokenCipher:
    return TokenCipher(Fernet.generate_key().decode())


@pytest.fixture
def creds_service(session_factory, cipher):
    return GoogleCredentialsService(session_factory, cipher, CONFIG)


async def _user_id(user_service) -> int:
    user = await user_service.get_or_create_by_telegram(telegram_id=600)
    return user.id


def _tokens(access="at-1", refresh="rt-1", expires_in=3600) -> Tokens:
    return Tokens(
        access_token=access, refresh_token=refresh, expires_in=expires_in, scope="cal"
    )


async def test_save_and_get_valid_token(
    session, session_factory, creds_service, user_service, monkeypatch
) -> None:
    user_id = await _user_id(user_service)
    await creds_service.save_tokens(user_id=user_id, tokens=_tokens())
    assert await creds_service.get_access_token(user_id) == "at-1"


async def test_get_access_token_refreshes_when_expired(
    session, session_factory, creds_service, user_service, monkeypatch
) -> None:
    user_id = await _user_id(user_service)
    await creds_service.save_tokens(user_id=user_id, tokens=_tokens(expires_in=1))

    async def fake_refresh(config, refresh_token):
        return Tokens(access_token="at-2", refresh_token=None, expires_in=3600, scope="cal")

    monkeypatch.setattr("app.services.google_credentials.refresh_access_token", fake_refresh)
    assert await creds_service.get_access_token(user_id) == "at-2"


async def test_get_access_token_without_credentials_raises(
    session, creds_service
) -> None:
    with pytest.raises(GoogleAuthError):
        await creds_service.get_access_token(99)


async def test_refresh_token_stored_encrypted(
    session, creds_service, user_service
) -> None:
    user_id = await _user_id(user_service)
    await creds_service.save_tokens(user_id=user_id, tokens=_tokens(refresh="super-secreto"))
    stored = await creds_service.get_refresh_token(user_id)
    assert stored == "super-secreto"


async def test_revoke_deletes_credentials(session, creds_service, user_service) -> None:
    user_id = await _user_id(user_service)
    await creds_service.save_tokens(user_id=user_id, tokens=_tokens())
    await creds_service.revoke(user_id)
    with pytest.raises(GoogleAuthError):
        await creds_service.get_access_token(user_id)
