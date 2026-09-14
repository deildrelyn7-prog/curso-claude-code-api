"""Errores HTTP comunes de la API.

Centraliza la construcción de las `HTTPException` que antes se creaban a mano
en `app/main.py`: recurso no encontrado (404), referencia inexistente en la
entrada (422) y conflicto (409). No cambia códigos ni mensajes existentes;
solo les da un único lugar de origen.

No cubre el camino de los `field_validator` de Pydantic (por ejemplo
`_clean_name`, `_clean_title`, `_clean_due_at`): esos siguen levantando
`ValueError`, que FastAPI convierte por su cuenta en el 422 con la forma que
genera el framework. El contrato (`docs/contrato-api.md`) permite
explícitamente que esa forma sea distinta de `{"detail": "<string>"}` mientras
la clave de primer nivel siga siendo `detail`.
"""

from fastapi import HTTPException

PROYECTO_NO_ENCONTRADO = "proyecto no encontrado"
TAREA_NO_ENCONTRADA = "tarea no encontrada"

PROYECTO_CON_TAREAS = "el proyecto tiene tareas asociadas"

STATE_ID_NO_EXISTE = "state_id no existe"
PROJECT_ID_NO_EXISTE = "project_id no existe"
PROJECT_ID_NO_PUEDE_SER_NULL = "project_id no puede ser null"
STATE_ID_NO_PUEDE_SER_NULL = "state_id no puede ser null"

_MENSAJES_NO_ENCONTRADO = {
    "proyecto": PROYECTO_NO_ENCONTRADO,
    "tarea": TAREA_NO_ENCONTRADA,
}


def no_encontrado(recurso: str) -> HTTPException:
    """404 para un recurso inexistente.

    `recurso` es "proyecto" o "tarea"; el mensaje generado es exactamente el
    que ya usaba cada handler.
    """
    return HTTPException(status_code=404, detail=_MENSAJES_NO_ENCONTRADO[recurso])


def conflicto(detail: str) -> HTTPException:
    """409 de conflicto, por ejemplo borrar un proyecto con tareas."""
    return HTTPException(status_code=409, detail=detail)


def referencia_invalida(detail: str) -> HTTPException:
    """422 cuando una referencia de entrada (project_id, state_id) no existe
    o no puede ser null."""
    return HTTPException(status_code=422, detail=detail)
