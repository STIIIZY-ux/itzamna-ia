"""OAuth 2.0 de Google: flujo de autorización, refresh y revocación.

Todo el flujo se realiza sobre ``httpx`` (async) sin el SDK oficial. Los
permisos se limitan a lectura de eventos (scope mínimo).
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx

from .errors import (
    GoogleAccessRevokedError,
    GoogleAuthError,
    GoogleRateLimitError,
    GoogleServiceUnavailableError,
)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"

SCOPE_CALENDAR_READ = "https://www.googleapis.com/auth/calendar.events.readonly"


@dataclass(frozen=True)
class OAuthConfig:
    """Configuración OAuth del cliente (valores de Google Cloud Console)."""

    client_id: str
    client_secret: str
    redirect_uri: str


@dataclass(frozen=True)
class Tokens:
    """Resultado del intercambio/refresh de tokens."""

    access_token: str
    refresh_token: str | None
    expires_in: int | None
    scope: str | None

    @property
    def expires_at(self) -> datetime | None:
        if self.expires_in is None:
            return None
        return datetime.now(timezone.utc) + timedelta(seconds=self.expires_in)


def build_auth_url(
    config: OAuthConfig,
    state: str,
    scope: str = SCOPE_CALENDAR_READ,
) -> str:
    """Construye la URL de autorización (flujo ``authorization_code``).

    ``access_type=offline`` y ``prompt=consent`` garantizan la obtención de un
    ``refresh_token``.
    """
    params = {
        "client_id": config.client_id,
        "redirect_uri": config.redirect_uri,
        "response_type": "code",
        "scope": scope,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


def _map_error(status_code: int, data: dict) -> Exception:
    error = data.get("error", "")
    if status_code == 429:
        return GoogleRateLimitError()
    if status_code >= 500:
        return GoogleServiceUnavailableError()
    if status_code in (400, 401) and error == "invalid_grant":
        return GoogleAccessRevokedError("El refresh token fue revocado o expiró")
    return GoogleAuthError(f"OAuth error {status_code}: {error or data}")


async def _post_token(params: dict) -> Tokens:
    async with httpx.AsyncClient(timeout=httpx.Timeout(20.0)) as client:
        response = await client.post(GOOGLE_TOKEN_URL, data=params)
    try:
        data = response.json()
    except ValueError:
        data = {}
    if response.status_code >= 400:
        raise _map_error(response.status_code, data)
    return Tokens(
        access_token=data["access_token"],
        refresh_token=data.get("refresh_token"),
        expires_in=data.get("expires_in"),
        scope=data.get("scope"),
    )


async def exchange_code(config: OAuthConfig, code: str) -> Tokens:
    """Intercambia un ``code`` de autorización por tokens."""
    return await _post_token(
        {
            "code": code,
            "client_id": config.client_id,
            "client_secret": config.client_secret,
            "redirect_uri": config.redirect_uri,
            "grant_type": "authorization_code",
        }
    )


async def refresh_access_token(config: OAuthConfig, refresh_token: str) -> Tokens:
    """Renueva el ``access_token`` usando el ``refresh_token``."""
    return await _post_token(
        {
            "refresh_token": refresh_token,
            "client_id": config.client_id,
            "client_secret": config.client_secret,
            "grant_type": "refresh_token",
        }
    )


async def revoke_token(token: str) -> None:
    """Revoca un token (access o refresh) en Google."""
    async with httpx.AsyncClient(timeout=httpx.Timeout(20.0)) as client:
        response = await client.post(GOOGLE_REVOKE_URL, params={"token": token})
    # 200 y 400 (token ya inválido) se consideran éxito.
    if response.status_code not in (200, 400):
        try:
            data = response.json()
        except ValueError:
            data = {}
        raise _map_error(response.status_code, data)
