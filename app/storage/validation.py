"""Validación de archivos por contenido (magic bytes), no por extensión/MIME."""

from __future__ import annotations

_ALLOWED_CONTENT_TYPES = frozenset(
    {"image/jpeg", "image/png", "image/webp", "application/pdf"}
)


class FileValidationError(Exception):
    """El archivo no superó la validación de contenido."""


def detect_content_type(data: bytes) -> str | None:
    """Detecta el tipo de contenido por sus bytes mágicos.

    Devuelve el MIME detectado o ``None`` si no es un tipo permitido.
    """
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    return None


def is_image(content_type: str) -> bool:
    return content_type in {"image/jpeg", "image/png", "image/webp"}


def is_pdf(content_type: str) -> bool:
    return content_type == "application/pdf"


def is_allowed_content_type(content_type: str) -> bool:
    return content_type in _ALLOWED_CONTENT_TYPES


def extension_for(content_type: str) -> str:
    return {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
        "application/pdf": "pdf",
    }[content_type]
