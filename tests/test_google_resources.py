"""Tests de extracción de materias y recursos."""

from app.integrations.google.resources import classify_resource, extract_resources
from app.integrations.google.subjects import extract_subject, normalize_subject_name


def test_extract_subject_from_title() -> None:
    assert extract_subject("[Cálculo] Entrega 1", None) == "Cálculo"


def test_extract_subject_from_description() -> None:
    assert extract_subject("Tarea", "Materia: Programación") == "Programación"


def test_extract_subject_none() -> None:
    assert extract_subject("Tarea simple", "Sin materia") is None


def test_normalize_subject_collapses_whitespace() -> None:
    assert normalize_subject_name("  cálculo    ii ") == "Cálculo Ii"


def test_classify_resource_pdf() -> None:
    assert classify_resource("https://x.com/a.pdf") == "pdf"
    assert classify_resource("https://x.com/file", "application/pdf") == "pdf"


def test_classify_resource_link_and_image() -> None:
    assert classify_resource("https://x.com/page") == "enlace"
    assert classify_resource("https://x.com/img.png", "image/png") == "imagen"


def test_extract_resources_dedupes() -> None:
    raw = {"description": "ver https://a.com/x ver https://a.com/x"}
    resources = extract_resources(raw)
    assert len(resources) == 1
