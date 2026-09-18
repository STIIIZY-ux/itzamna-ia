"""Almacenamiento local en disco (costo $0, privado).

Los archivos se guardan en un directorio privado (no servido públicamente)
bajo nombres generados internamente (UUID). Nunca se usa el nombre original
del usuario como path.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from .base import FileStorage

_KEY_PATTERN = re.compile(r"^[a-f0-9]{32}\.[a-z0-9]{2,5}$")


class LocalFileStorage(FileStorage):
    """Almacenamiento simple en un directorio local."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    def save(self, data: bytes, extension: str) -> str:
        ext = extension.lstrip(".").lower()
        key = f"{uuid.uuid4().hex}.{ext}"
        path = self._path(key)
        # Evita colisiones (extremadamente improbable con UUID).
        with open(path, "xb") as fh:
            fh.write(data)
        return key

    def load(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        path = self._path(key)
        path.unlink(missing_ok=True)

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def _path(self, key: str) -> Path:
        if not _KEY_PATTERN.match(key):
            raise ValueError("clave de almacenamiento inválida")
        return self._root / key
