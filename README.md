# TaskFlow API

Base de la API de TaskFlow: FastAPI gestionada con [uv](https://docs.astral.sh/uv/)
y Python 3.12, con persistencia en PostgreSQL.

El comportamiento observable (endpoints, códigos HTTP, esquemas de respuesta,
normalización) está en [`docs/contrato-api.md`](docs/contrato-api.md). Las
peticiones de ejemplo, encadenadas y listas para ejecutar, están en
[`api.http`](api.http).

## Requisitos

- Python 3.12
- uv
- Docker con Compose v2

## Puesta en marcha

Ejecuta los pasos en orden desde la raíz del repositorio. Un paso por línea.

```sh
# 1. Instalar las dependencias exactamente como fija el lock.
uv sync --locked

# 2. Levantar PostgreSQL en segundo plano.
docker compose up -d

# 3. Esperar a que la base acepte conexiones (healthcheck del contenedor).
docker compose ps --format '{{.Service}} {{.Health}}'

# 4. Aplicar las migraciones: catálogo de estados, tablas projects y tasks, columna due_at.
uv run alembic upgrade head

# 5. Arrancar la API en http://localhost:8000 (Ctrl+C para parar).
uv run uvicorn app.main:app --reload
```

Con la API arrancando, abre otra terminal para probar un endpoint.

```sh
# 6. Comprobación mínima: la API responde antes de tocar ninguna tabla.
curl http://localhost:8000/health

# 7. Recorrido completo de peticiones encadenadas: abre api.http en un cliente
#    REST (VS Code REST Client, IntelliJ HTTP Client) y ejecútalas de arriba
#    abajo. Cada petición reutiliza el id que devolvió la anterior.
```

Para detener y retirar los contenedores al terminar:

```sh
docker compose down
```

## Configuración

`compose.yaml` arranca con valores por defecto seguros para desarrollo local, así
que funciona sin `.env`. Tanto la API (`app/db.py`) como las migraciones
(`alembic/env.py`) leen `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`,
`POSTGRES_HOST` y `POSTGRES_PORT`, con los mismos valores por defecto que el
contenedor. Para personalizarlo, copia `.env.example` a `.env` y ajusta esas
variables; `.env` no se versiona.

## Comandos de desarrollo

```sh
# Tests (corren contra la base PostgreSQL de los pasos 2 a 4; nunca SQLite).
uv run pytest -q

# Linter.
uv run ruff check .
```

## Estructura

- `app/main.py` — aplicación ASGI, expuesta como `app.main:app`.
- `app/models.py` — modelos SQLAlchemy: `State`, `Project` y `Task`.
- `app/db.py` — URL de conexión y `sessionmaker` async desde variables de entorno.
- `alembic/versions/` — migraciones: catálogo de estados, tablas `projects` y
  `tasks`, y la columna `due_at` de `tasks`.
- `tests/test_health.py` — verifica `GET /health` mediante una petición ASGI.
- `tests/test_states.py`, `tests/test_states_migration.py` — catálogo de estados.
- `tests/test_projects.py` — CRUD de Proyectos por HTTP contra la base real.
- `tests/test_projects_migration.py` — `upgrade`/`downgrade` de la tabla `projects`.
- `tests/test_tasks.py` — CRUD y filtros de Tareas por HTTP contra la base real.
- `tests/test_tasks_migration.py` — `upgrade`/`downgrade` de la tabla `tasks`.
- `compose.yaml` — servicio `db` con PostgreSQL 18-alpine.
