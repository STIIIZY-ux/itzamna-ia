"""Utilidades de seguridad: saneamiento de secretos en logs y errores."""

import logging
import os
import traceback
from typing import Any

from pydantic import ValidationError

from app.config import get_settings

REDACTED = "[REDACTED]"

_SECRET_ENV_VARS = (
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_WEBHOOK_SECRET",
    "DATABASE_URL",
    "GOOGLE_CLIENT_SECRET",
    "GOOGLE_TOKEN_ENCRYPTION_KEY",
    "AI_API_KEY",
    "GEMINI_API_KEY",
)


def _current_secrets() -> list[str]:
    """Devuelve los secretos conocidos a redactar.

    Incluye tanto los valores crudos de las variables de entorno como los de
    ``Settings``. Esto permite redactar incluso cuando la configuración no puede
    cargarse (p. ej. token con formato inválido), porque los valores crudos del
    entorno siempre están disponibles. Nunca lanza.
    """
    secrets: list[str] = []
    for key in _SECRET_ENV_VARS:
        value = os.environ.get(key)
        if value:
            secrets.append(value)

    try:
        settings = get_settings()
    except ValidationError:
        return secrets

    if settings.telegram_bot_token not in secrets:
        secrets.append(settings.telegram_bot_token)
    if settings.telegram_webhook_secret and settings.telegram_webhook_secret not in secrets:
        secrets.append(settings.telegram_webhook_secret)
    return secrets


def redact_secrets(text: str) -> str:
    """Reemplaza cualquier secreto conocido por ``[REDACTED]`` en ``text``."""
    for secret in _current_secrets():
        if secret:
            text = text.replace(secret, REDACTED)
    return text


def redact_exception(exc: BaseException) -> str:
    """Formatea el traceback completo de una excepción sin revelar secretos."""
    lines = traceback.format_exception(type(exc), exc, exc.__traceback__)
    return redact_secrets("".join(lines))


def _redact_arg(arg: Any) -> Any:
    if isinstance(arg, str):
        return redact_secrets(arg)
    text = str(arg)
    redacted = redact_secrets(text)
    return redacted if redacted != text else arg


def _redact_args(args: object) -> Any:
    if isinstance(args, tuple):
        return tuple(_redact_arg(arg) for arg in args)
    if isinstance(args, dict):
        return {key: _redact_arg(value) for key, value in args.items()}
    return args


def _format_exc_info(exc_info: tuple) -> str:
    return "".join(traceback.format_exception(*exc_info))


class SecretsFilter(logging.Filter):
    """Filtro de logging que elimina secretos de cada registro antes de emitirlo."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_secrets(record.msg)
        if record.args:
            record.args = _redact_args(record.args)
        if record.exc_info:
            record.exc_text = redact_secrets(_format_exc_info(record.exc_info))
            record.exc_info = None
        return True


def install_secrets_filter() -> None:
    """Instala el filtro de secretos en el logger raíz y sus handlers."""
    root = logging.getLogger()
    if not any(isinstance(f, SecretsFilter) for f in root.filters):
        root.addFilter(SecretsFilter())
    for handler in root.handlers:
        handler.addFilter(SecretsFilter())
