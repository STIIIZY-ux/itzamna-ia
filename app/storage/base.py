"""Interfaz de almacenamiento de archivos."""

from __future__ import annotations

from abc import ABC, abstractmethod


class FileStorage(ABC):
    """Almacenamiento binario de archivos (objetos)."""

    @abstractmethod
    def save(self, data: bytes, extension: str) -> str:
        """Almacena ``data`` y devuelve la clave interna del objeto."""

    @abstractmethod
    def load(self, key: str) -> bytes:
        """Lee el objeto asociado a ``key``."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Elimina el objeto asociado a ``key``."""

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Indica si existe un objeto para ``key``."""
