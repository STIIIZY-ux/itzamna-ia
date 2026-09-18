"""Tests de detección de capítulos y extracción de texto."""

from app.services.book_processing.chapters import detect_chapters
from app.services.book_processing.extract import extract_text

TEXT = (
    "Capítulo 1: Introducción\n\n"
    "Este es el contenido del capítulo uno.\n"
    "Más texto.\n\n"
    "Capítulo 2: Metodología\n\n"
    "Contenido del capítulo dos.\n\n"
    "Tema 3: Resultados\n\n"
    "Contenido del tema tres."
)


def test_detect_chapters_by_capitulo() -> None:
    chapters = detect_chapters(TEXT)
    assert len(chapters) == 3
    assert chapters[0].title == "Introducción"
    assert chapters[1].title == "Metodología"
    assert "contenido del capítulo uno" in chapters[0].content


def test_detect_chapters_no_structure_returns_empty() -> None:
    assert detect_chapters("Solo texto sin estructura clara.\nOtra línea.") == []


def test_detect_chapters_numbered_headings() -> None:
    chapters = detect_chapters("1. Introducción\nhola\n2. Desarrollo\nmundo")
    assert len(chapters) == 2
    assert chapters[0].number == "1"
    assert chapters[1].title == "Desarrollo"


def test_extract_text_plain() -> None:
    assert extract_text(b"hola mundo", "text/plain") == "hola mundo"


def test_extract_text_unsupported() -> None:
    assert extract_text(b"x", "image/png") == ""
