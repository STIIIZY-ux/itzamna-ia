"""Tests de validación de archivos (magic bytes)."""

from app.storage.validation import (
    detect_content_type,
    extension_for,
    is_image,
    is_pdf,
)


def test_detect_jpeg() -> None:
    assert detect_content_type(b"\xff\xd8\xff" + b"\x00" * 16) == "image/jpeg"


def test_detect_png() -> None:
    assert detect_content_type(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16) == "image/png"


def test_detect_webp() -> None:
    assert detect_content_type(b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 16) == "image/webp"


def test_detect_pdf() -> None:
    assert detect_content_type(b"%PDF-1.4" + b"\x00" * 16) == "application/pdf"


def test_detect_garbage() -> None:
    assert detect_content_type(b"hola mundo") is None


def test_detect_executable_elf() -> None:
    assert detect_content_type(b"\x7fELF" + b"\x00" * 16) is None


def test_detect_empty() -> None:
    assert detect_content_type(b"") is None


def test_classification_helpers() -> None:
    assert is_image("image/jpeg") is True
    assert is_pdf("application/pdf") is True
    assert is_image("application/pdf") is False


def test_extension_for() -> None:
    assert extension_for("image/jpeg") == "jpg"
    assert extension_for("image/png") == "png"
    assert extension_for("application/pdf") == "pdf"
