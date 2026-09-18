"""CLI para autorizar Google Calendar (flujo OAuth manual).

Uso::

    python -m app.integrations.google.authorize

Imprime una URL de autorización, pide el código y guarda los tokens cifrados.
"""

import asyncio
import secrets

from app.config import get_settings
from app.db.engine import get_session_factory
from app.integrations.google.auth import (
    SCOPE_CALENDAR_READ,
    build_auth_url,
    exchange_code,
)
from app.integrations.google.factory import build_stack
from app.services.users import UserService


async def _run() -> None:
    settings = get_settings()

    if not settings.google_client_id or not settings.google_client_secret:
        raise SystemExit("GOOGLE_CLIENT_ID y GOOGLE_CLIENT_SECRET no están configurados")
    if not settings.google_redirect_uri:
        raise SystemExit("GOOGLE_REDIRECT_URI no está configurado")
    if not settings.database_url:
        raise SystemExit("DATABASE_URL no está configurado")

    from app.integrations.google.auth import OAuthConfig

    config = OAuthConfig(
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        redirect_uri=settings.google_redirect_uri,
    )
    state = secrets.token_urlsafe(16)
    url = build_auth_url(config, state=state, scope=SCOPE_CALENDAR_READ)

    print("Abre esta URL en tu navegador y autoriza el acceso:")
    print(url)
    print()
    code = input("Pega aquí el código de autorización: ").strip()
    if not code:
        raise SystemExit("No se recibió ningún código.")

    session_factory = get_session_factory()
    user = await UserService(session_factory).get_or_create_by_telegram(
        telegram_id=settings.telegram_allowed_user_id,
    )

    tokens = await exchange_code(config, code)
    stack = build_stack(session_factory)
    await stack.credentials.save_tokens(user.id, tokens)
    print("Credenciales guardadas correctamente (cifradas).")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
