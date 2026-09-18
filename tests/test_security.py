"""Tests de saneamiento de secretos en logs y errores."""

import io
import logging

import pytest

from app.security import (
    REDACTED,
    SecretsFilter,
    install_secrets_filter,
    redact_exception,
    redact_secrets,
)

TOKEN = "123456:ABC-DEF"


@pytest.fixture
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", TOKEN)
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_ID", "42")


def test_redact_secrets_replaces_token(_env: None) -> None:
    result = redact_secrets(f"Error: token {TOKEN} inválido")
    assert TOKEN not in result
    assert REDACTED in result


def test_redact_secrets_without_secret_is_noop(_env: None) -> None:
    result = redact_secrets("mensaje sin secretos")
    assert result == "mensaje sin secretos"


def test_redact_exception_hides_token(_env: None) -> None:
    exc = ValueError(f"falló con token {TOKEN}")
    result = redact_exception(exc)
    assert TOKEN not in result
    assert REDACTED in result
    assert "ValueError" in result


def test_secrets_filter_redacts_message_and_args(_env: None) -> None:
    record = logging.LogRecord(
        name="test",
        level=logging.ERROR,
        pathname=__file__,
        lineno=0,
        msg="falló con token %s",
        args=(TOKEN,),
        exc_info=None,
    )
    assert SecretsFilter().filter(record) is True
    assert TOKEN not in record.getMessage()
    assert REDACTED in record.getMessage()


def test_secrets_filter_redacts_url_in_args(_env: None) -> None:
    import httpx

    url = httpx.URL(f"https://api.telegram.org/bot{TOKEN}/getMe")
    record = logging.LogRecord(
        name="httpx",
        level=logging.INFO,
        pathname=__file__,
        lineno=0,
        msg='HTTP Request: %s %s "%s %d %s"',
        args=("POST", url, "HTTP/1.1", 401, "Unauthorized"),
        exc_info=None,
    )
    assert SecretsFilter().filter(record) is True
    assert TOKEN not in record.getMessage()
    assert REDACTED in record.getMessage()


def test_token_never_appears_in_logged_message(_env: None) -> None:
    logger = logging.getLogger("test.redaction")
    logger.setLevel(logging.ERROR)
    logger.propagate = False
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(SecretsFilter())
    logger.addHandler(handler)
    try:
        logger.error("No se pudo conectar usando el token %s", TOKEN)
    finally:
        logger.removeHandler(handler)
    output = stream.getvalue()
    assert TOKEN not in output
    assert REDACTED in output


def test_secrets_filter_redacts_exc_info(_env: None) -> None:
    try:
        raise ValueError(f"token expuesto {TOKEN}")
    except ValueError as exc:
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=0,
            msg="error",
            args=(),
            exc_info=(type(exc), exc, exc.__traceback__),
        )
    assert SecretsFilter().filter(record) is True
    assert record.exc_info is None
    assert record.exc_text is not None
    assert TOKEN not in record.exc_text
    assert REDACTED in record.exc_text


def test_install_secrets_filter_is_idempotent() -> None:
    install_secrets_filter()
    install_secrets_filter()


def test_raw_env_secret_redacted_even_if_settings_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "SECRETO-SIN-COLON")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_ID", "42")
    result = redact_secrets("hubo un error con SECRETO-SIN-COLON")
    assert "SECRETO-SIN-COLON" not in result
    assert REDACTED in result
