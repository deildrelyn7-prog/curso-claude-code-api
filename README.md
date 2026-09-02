# TaskFlow API

Base de la API de TaskFlow: FastAPI gestionada con [uv](https://docs.astral.sh/uv/)
y Python 3.12. Esta primera entrega expone únicamente `GET /health`.

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

# 5. Servir la API (Ctrl+C para parar)
uv run uvicorn app.main:app --reload

#    En otra terminal, comprobar el endpoint de salud:
#    curl http://localhost:8000/health  ->  {"status":"ok"}

# 6. Parar y retirar los contenedores
docker compose down
```

## Configuración

`compose.yaml` arranca con valores por defecto seguros para desarrollo local, así
que funciona sin `.env`. Para personalizarlo, copia `.env.example` a `.env` y
ajusta `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` y `POSTGRES_PORT`.

## Estructura

- `app/main.py` — aplicación ASGI, expuesta como `app.main:app`.
- `tests/test_health.py` — verifica `GET /health` mediante una petición ASGI.
- `compose.yaml` — servicio `db` con PostgreSQL 18-alpine.
