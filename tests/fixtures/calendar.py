"""Fixtures de prueba derivados de la estructura de ``icalexport.ics`` (Moodle).

El archivo real no está incluido en el repositorio; estos fixtures representan
fielmente la estructura descrita (eventos con UID/SUMMARY/DESCRIPTION/DTSTART/
DTEND/CATEGORIES, enlaces, instrucciones, materiales, duplicados). Se usan
únicamente en pruebas; nunca en producción.
"""

#: Evento duplicado: dos representaciones equivalentes de la misma actividad.
PROGRAMACION_DESCRIPTION = (
    "Materia: Programación\n"
    "Tema: 1.1 Estructura secuencial\n"
    "Conceptos: algoritmo, diagrama de flujo, pseudocódigo, lenguaje C, "
    "estructura secuencial.\n"
    "Materiales: videos, práctica guiada, archivo fuente, archivo ejecutable, "
    "documento Word, capturas.\n"
    "Instrucciones: revisar los materiales y resolver la práctica guiada."
)

CALENDAR_EVENTS = [
    # 1. Actividad con instrucciones.
    {
        "id": "evt-instrucciones",
        "summary": "Tarea 2: Ejercicios de repaso",
        "description": "Instrucciones: resolver los ejercicios 1 al 10 del libro.",
        "start": {"dateTime": "2026-09-08T23:59:00-07:00", "timeZone": "America/Tijuana"},
        "end": {"dateTime": "2026-09-08T23:59:00-07:00", "timeZone": "America/Tijuana"},
    },
    # 2. Actividad con varios enlaces.
    {
        "id": "evt-enlaces",
        "summary": "Lectura de materiales",
        "description": (
            "Materia: Historia\n"
            "Lectura obligatoria:\n"
            "https://example.com/capitulo1.pdf\n"
            "https://example.com/video\n"
            "https://example.com/practica"
        ),
        "start": {"date": "2026-09-09"},
        "end": {"date": "2026-09-09"},
    },
    # 3/6/7. Actividad duplicada: "está en fecha de entrega" vs "debería estar completada".
    {
        "id": "evt-1-entrega",
        "summary": "1.1 Estructura secuencial está en fecha de entrega",
        "description": PROGRAMACION_DESCRIPTION,
        "start": {"dateTime": "2026-09-04T23:59:00-07:00", "timeZone": "America/Tijuana"},
        "end": {"dateTime": "2026-09-04T23:59:00-07:00", "timeZone": "America/Tijuana"},
    },
    {
        "id": "evt-1-completada",
        "summary": "1.1 Estructura secuencial debería estar completada",
        "description": PROGRAMACION_DESCRIPTION,
        "start": {"dateTime": "2026-09-04T23:59:00-07:00", "timeZone": "America/Tijuana"},
        "end": {"dateTime": "2026-09-04T23:59:00-07:00", "timeZone": "America/Tijuana"},
    },
    # 4. Actividad relacionada con lectura.
    {
        "id": "evt-lectura",
        "summary": "Control de lectura capítulos 1-3",
        "description": "Materia: Literatura\nLectura: capítulos 1-3 del libro de texto.",
        "start": {"date": "2026-09-10"},
        "end": {"date": "2026-09-10"},
    },
    # 5. Actividad con descripción extensa.
    {
        "id": "evt-extensa",
        "summary": "Proyecto final de Programación",
        "description": (
            "Materia: Programación\n"
            "Descripción extensa: desarrollar un proyecto que integre estructuras "
            "secuenciales, condicionales y bucles. Incluye requisitos, rúbrica, "
            "entregables y criterios de evaluación."
        ),
        "start": {"dateTime": "2026-09-20T23:59:00-07:00", "timeZone": "America/Tijuana"},
        "end": {"dateTime": "2026-09-20T23:59:00-07:00", "timeZone": "America/Tijuana"},
    },
]
