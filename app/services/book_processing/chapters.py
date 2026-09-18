"""Detección determinista de capítulos en texto extraído.

No asume una única convención ("Capítulo 1"). Si no se detecta estructura,
devuelve una lista vacía (se marca como ambiguo, sin inventar).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_HEADING_PATTERNS = [
    re.compile(r"^\s*(?:cap[ií]tulo|chapter)\s+([0-9]+|[ivxlcdm]+)\b[:\-.\s]*(.*)$", re.IGNORECASE),
    re.compile(r"^\s*(?:tema|unidad|lecci[oó]n|secci[oó]n|unit|lesson)\s+([0-9]+)\b[:\-.\s]*(.*)$", re.IGNORECASE),
    re.compile(r"^\s*([0-9]{1,3})\.[\t ]+(.+)$"),
]


@dataclass(frozen=True)
class ChapterSpec:
    number: str | None
    title: str
    content: str


def match_heading(line: str) -> tuple[str | None, str] | None:
    """Devuelve ``(número, título)`` si la línea es un encabezado de capítulo."""
    for pattern in _HEADING_PATTERNS:
        m = pattern.match(line)
        if m:
            number = m.group(1) if len(m.groups()) >= 1 else None
            title = m.group(2).strip() if len(m.groups()) >= 2 else ""
            if not title:
                title = f"Capítulo {number}" if number else "Sección"
            return number, title
    return None


def detect_chapters(text: str) -> list[ChapterSpec]:
    """Divide el texto en capítulos según los encabezados detectados."""
    chapters: list[ChapterSpec] = []
    current_number: str | None = None
    current_title: str = ""
    current_lines: list[str] = []

    def flush() -> None:
        if current_title:
            chapters.append(
                ChapterSpec(
                    number=current_number,
                    title=current_title,
                    content="\n".join(current_lines).strip(),
                )
            )

    for line in text.splitlines():
        heading = match_heading(line)
        if heading is not None:
            flush()
            current_number, current_title = heading
            current_lines = []
        else:
            current_lines.append(line)

    flush()
    return chapters
