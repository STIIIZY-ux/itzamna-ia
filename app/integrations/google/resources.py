"""Extracción de recursos y enlaces desde un evento de Google Calendar.

Solo se registran referencias (URI, tipo). No se descarga nada en esta etapa.
"""

import re

from .schemas import NormalizedResource

_URL_PATTERN = re.compile(r"https?://[^\s<>\"']+")


def classify_resource(uri: str, mime_type: str | None = None) -> str:
    """Clasifica una URI en un tipo de recurso."""
    clean = uri.lower().split("?")[0].split("#")[0]
    if clean.endswith(".pdf") or (mime_type == "application/pdf"):
        return "pdf"
    if (mime_type or "").startswith("image/"):
        return "imagen"
    return "enlace"


def extract_resources(raw_event: dict) -> list[NormalizedResource]:
    """Extrae recursos de ``attachments`` y enlaces de description/location."""
    resources: list[NormalizedResource] = []
    seen: set[str] = set()

    def add(uri: str, name: str | None, rtype: str) -> None:
        key = uri.strip()
        if key and key not in seen:
            seen.add(key)
            resources.append(NormalizedResource(resource_type=rtype, name=name, uri=key))

    for attachment in raw_event.get("attachments") or []:
        uri = attachment.get("fileUrl")
        if uri:
            add(uri, attachment.get("title"), classify_resource(uri, attachment.get("mimeType")))

    text = " ".join(
        value
        for value in (raw_event.get("description"), raw_event.get("location"))
        if value
    )
    for url in _URL_PATTERN.findall(text or ""):
        add(url, None, classify_resource(url))

    return resources
