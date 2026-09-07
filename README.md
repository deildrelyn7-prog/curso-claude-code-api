# TaskFlow API

Base de la API de TaskFlow: FastAPI gestionada con [uv](https://docs.astral.sh/uv/)
y Python 3.12. Expone `GET /health`, el catálogo `GET /states` y el recurso
Proyectos (`POST`, `GET` de colección, `GET` de detalle y `PATCH`).

## Requisitos

- Python 3.12
- uv
- Docker con Compose v2

## Recorrido

Ejecuta los pasos en orden desde la raíz del repositorio.

```sh
# 1. Instalar dependencias exactamente como fija el lock
uv sync --locked

# 2. Tests
uv run pytest -q

# 3. Linter
uv run ruff check .

# 4. Levantar PostgreSQL en segundo plano
docker compose up -d

# 5. Aplicar las migraciones (crea el catálogo de estados y la tabla projects)
uv run alembic upgrade head

# 6. Servir la API (Ctrl+C para parar)
uv run uvicorn app.main:app --reload

#    En otra terminal, comprobar los endpoints:
#    curl http://localhost:8000/health   ->  {"status":"ok"}
#    curl http://localhost:8000/states   ->  [{"id":1,"code":"PENDIENTE"}, ...]
#    curl -X POST http://localhost:8000/projects \
#         -H 'Content-Type: application/json' -d '{"name":"Casa"}'
#         ->  {"id":1,"name":"Casa","description":null}
#    curl http://localhost:8000/projects  ->  [{"id":1,"name":"Casa","description":null}]

# 7. Parar y retirar los contenedores
docker compose down
```

## Configuración

`compose.yaml` arranca con valores por defecto seguros para desarrollo local, así
que funciona sin `.env`. Para personalizarlo, copia `.env.example` a `.env` y
ajusta `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` y `POSTGRES_PORT`.

## Estructura

- `app/main.py` — aplicación ASGI, expuesta como `app.main:app`.
- `app/models.py` — modelos SQLAlchemy: `State` y `Project`.
- `app/db.py` — URL de conexión y `sessionmaker` async desde variables de entorno.
- `alembic/versions/` — migraciones: catálogo de estados y tabla `projects`.
- `tests/test_health.py` — verifica `GET /health` mediante una petición ASGI.
- `tests/test_states.py`, `tests/test_states_migration.py` — catálogo de estados.
- `tests/test_projects.py` — CRUD de Proyectos por HTTP contra la base real.
- `tests/test_projects_migration.py` — `upgrade`/`downgrade` de la tabla `projects`.
- `compose.yaml` — servicio `db` con PostgreSQL 18-alpine.
