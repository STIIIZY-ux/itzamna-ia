"""Tests del cifrado de tokens (Fernet)."""

import pytest
from cryptography.fernet import Fernet

from app.integrations.google.crypto import TokenCipher, TokenCipherError


def _key() -> str:
    return Fernet.generate_key().decode()


def test_roundtrip() -> None:
    cipher = TokenCipher(_key())
    token = "un-refresh-token-secreto"
    encrypted = cipher.encrypt(token)
    assert token not in encrypted
    assert cipher.decrypt(encrypted) == token


def test_invalid_key_raises() -> None:
    with pytest.raises(TokenCipherError):
        TokenCipher("clave-no-válida")


def test_decrypt_tampered_raises() -> None:
    cipher = TokenCipher(_key())
    with pytest.raises(TokenCipherError):
        cipher.decrypt("texto-alterado")
