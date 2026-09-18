"""Procesamiento local de libros/documentos (extracción de texto y capítulos)."""

from .chapters import ChapterSpec, detect_chapters
from .extract import extract_text

__all__ = ["ChapterSpec", "detect_chapters", "extract_text"]
