"""Almacenamiento de archivos de Itzamná IA."""

from .base import FileStorage
from .local import LocalFileStorage

__all__ = ["FileStorage", "LocalFileStorage"]
