"""Construcción de la :class:`Application` de python-telegram-bot."""

from telegram.ext import Application, ApplicationBuilder

from app.config import get_settings


def build_application() -> Application:
    """Crea y devuelve la ``Application`` configurada con el token del bot."""
    settings = get_settings()
    return ApplicationBuilder().token(settings.telegram_bot_token).build()
