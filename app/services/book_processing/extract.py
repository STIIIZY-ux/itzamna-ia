"""Extracción de texto de documentos (PDF/texto) de forma local y segura.

El texto extraído es DATOS NO CONFIABLES: nunca se ejecuta ni se interpreta
como instrucciones.
"""

from __future__ import annotations

from io import BytesIO


def extract_pdf_text(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(data))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages)


def extract_text(data: bytes, content_type: str) -> str:
    """Extrae texto según el tipo de contenido."""
    if content_type == "application/pdf":
        return extract_pdf_text(data)
    if content_type in ("text/plain", "text/markdown"):
        return data.decode("utf-8", errors="replace")
    return ""
