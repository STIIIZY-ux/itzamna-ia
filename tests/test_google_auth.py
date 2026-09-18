"""Tests del flujo OAuth (auth.py) con httpx simulado."""

import pytest

from app.integrations.google.auth import (
    OAuthConfig,
    build_auth_url,
    exchange_code,
    refresh_access_token,
    revoke_token,
)
from app.integrations.google.errors import (
    GoogleAccessRevokedError,
    GoogleAuthError,
    GoogleRateLimitError,
    GoogleServiceUnavailableError,
)
from tests.fake_http import FakeResponse, install_fake_httpx

CONFIG = OAuthConfig(
    client_id="client-123",
    client_secret="secret-456",
    redirect_uri="http://localhost",
)


def test_build_auth_url_contains_expected_params() -> None:
    url = build_auth_url(CONFIG, state="abc123")
    assert "client_id=client-123" in url
    assert "redirect_uri=http%3A%2F%2Flocalhost" in url
    assert "access_type=offline" in url
    assert "prompt=consent" in url
    assert "state=abc123" in url
    assert "response_type=code" in url


async def test_exchange_code_success(monkeypatch) -> None:
    install_fake_httpx(
        monkeypatch,
        FakeResponse(
            200,
            {
                "access_token": "at-1",
                "refresh_token": "rt-1",
                "expires_in": 3600,
                "scope": "calendar",
            },
        ),
    )
    tokens = await exchange_code(CONFIG, "code-1")
    assert tokens.access_token == "at-1"
    assert tokens.refresh_token == "rt-1"
    assert tokens.expires_in == 3600


async def test_exchange_code_invalid_grant(monkeypatch) -> None:
    install_fake_httpx(monkeypatch, FakeResponse(400, {"error": "invalid_grant"}))
    with pytest.raises(GoogleAccessRevokedError):
        await exchange_code(CONFIG, "bad")


async def test_exchange_code_rate_limit(monkeypatch) -> None:
    install_fake_httpx(monkeypatch, FakeResponse(429, {"error": "rate_limit"}))
    with pytest.raises(GoogleRateLimitError):
        await exchange_code(CONFIG, "code")


async def test_exchange_code_server_error(monkeypatch) -> None:
    install_fake_httpx(monkeypatch, FakeResponse(503, {}))
    with pytest.raises(GoogleServiceUnavailableError):
        await exchange_code(CONFIG, "code")


async def test_exchange_code_unknown_error(monkeypatch) -> None:
    install_fake_httpx(monkeypatch, FakeResponse(400, {"error": "invalid_client"}))
    with pytest.raises(GoogleAuthError):
        await exchange_code(CONFIG, "code")


async def test_refresh_access_token(monkeypatch) -> None:
    install_fake_httpx(
        monkeypatch,
        FakeResponse(200, {"access_token": "at-2", "expires_in": 3600}),
    )
    tokens = await refresh_access_token(CONFIG, "rt-1")
    assert tokens.access_token == "at-2"
    assert tokens.refresh_token is None


async def test_revoke_token_success(monkeypatch) -> None:
    install_fake_httpx(monkeypatch, FakeResponse(200, {}))
    await revoke_token("at-x")  # no debe lanzar


async def test_revoke_token_invalid_token_is_ok(monkeypatch) -> None:
    install_fake_httpx(monkeypatch, FakeResponse(400, {}))
    await revoke_token("at-x")  # 400 (token ya inválido) es aceptable
