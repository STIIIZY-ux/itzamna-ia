"""Construcción del stack de integración con Google Calendar."""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_settings
from app.integrations.google.auth import OAuthConfig
from app.integrations.google.client import GoogleCalendarClient
from app.integrations.google.crypto import TokenCipher
from app.services.calendar_sync import CalendarSyncService
from app.services.google_credentials import GoogleCredentialsService


@dataclass
class GoogleStack:
    """Servicios de Google Calendar ya cableados."""

    credentials: GoogleCredentialsService
    sync: CalendarSyncService


def is_configured() -> bool:
    """Indica si la integración con Google está configurada."""
    settings = get_settings()
    return bool(
        settings.google_client_id
        and settings.google_client_secret
        and settings.google_redirect_uri
        and settings.google_token_encryption_key
    )


def build_stack(session_factory: async_sessionmaker[AsyncSession]) -> GoogleStack:
    """Construye los servicios de Google Calendar a partir de la configuración.

    Lanza ``RuntimeError`` si falta configuración obligatoria.
    """
    settings = get_settings()
    if not settings.google_client_id or not settings.google_client_secret:
        raise RuntimeError("GOOGLE_CLIENT_ID y GOOGLE_CLIENT_SECRET son obligatorios")
    if not settings.google_redirect_uri:
        raise RuntimeError("GOOGLE_REDIRECT_URI es obligatorio")
    if not settings.google_token_encryption_key:
        raise RuntimeError("GOOGLE_TOKEN_ENCRYPTION_KEY es obligatorio")

    cipher = TokenCipher(settings.google_token_encryption_key)
    config = OAuthConfig(
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        redirect_uri=settings.google_redirect_uri,
    )
    credentials = GoogleCredentialsService(session_factory, cipher, config)
    client = GoogleCalendarClient(credentials.get_access_token)
    sync = CalendarSyncService(
        session_factory=session_factory,
        client=client,
        timezone=settings.user_timezone,
        calendar_id=settings.google_calendar_id,
        time_window_days=settings.google_sync_time_window_days,
    )
    return GoogleStack(credentials=credentials, sync=sync)
