"""Cifrado simétrico (Fernet) para tokens OAuth en reposo."""

from cryptography.fernet import Fernet, InvalidToken


class TokenCipherError(Exception):
    """Error al cifrar/descifrar un token."""


class TokenCipher:
    """Cifra/descifra tokens usando AES-CBC+HMAC vía Fernet.

    La clave debe ser una cadena base64 URL-safe de 32 bytes (la genera
    ``Fernet.generate_key()``).
    """

    def __init__(self, key: str) -> None:
        try:
            self._fernet = Fernet(key.encode("ascii"))
        except ValueError as exc:
            raise TokenCipherError(
                "GOOGLE_TOKEN_ENCRYPTION_KEY no es una clave Fernet válida"
            ) from exc

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")

    def decrypt(self, token: str) -> str:
        try:
            return self._fernet.decrypt(token.encode("ascii")).decode("utf-8")
        except InvalidToken as exc:
            raise TokenCipherError("No se pudo descifrar el token almacenado") from exc
