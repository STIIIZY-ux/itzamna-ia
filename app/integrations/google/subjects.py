"""Identificación conservadora de la materia de un evento.

La materia puede aparecer como ``[Materia]`` en el título o como
``Materia:``/``Asignatura:`` en la descripción. Se evita crear variantes
triviales normalizando mayúsculas/espacios.
"""

import re

_TITLE_PREFIX = re.compile(r"^\s*\[([^\]]+)\]\s*")
_DESCRIPTION_LABEL = re.compile(
    r"(?:materia|asignatura|subject)\s*[:：]\s*(.+)", re.IGNORECASE
)


def normalize_subject_name(name: str) -> str:
    """Normaliza un nombre de materia (colapsa espacios, title-case)."""
    return " ".join(name.split()).strip().title()


def extract_subject(summary: str, description: str | None) -> str | None:
    """Devuelve el nombre de materia si se puede identificar de forma fiable."""
    match = _TITLE_PREFIX.match(summary or "")
    if match and match.group(1).strip():
        return normalize_subject_name(match.group(1))

    if description:
        match = _DESCRIPTION_LABEL.search(description)
        if match and match.group(1).strip():
            return normalize_subject_name(match.group(1))

    return None
