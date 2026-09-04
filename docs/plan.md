# Plan: conexión de TaskFlow API a PostgreSQL

Alcance de esta iteración: conectar la API a PostgreSQL en incrementos,
empezando por el catálogo de Estados. Cada incremento es commiteable por
separado, con su propia comprobación. Después de cerrar un incremento, se
espera aprobación antes de encadenar el siguiente.

Fuera de alcance: proyectos, tareas, filtros, `due_at`, skills, hooks y CI.

Fuentes: `docs/contrato-api.md` (secciones Salud y Estados),
`docs/decisiones-ingenieria.md` (rama `main`), `CLAUDE.md` (rama `main`).

No se modifican: `docs/contrato-api.md`, `docs/decisiones-ingenieria.md`,
`CLAUDE.md`, `.gitignore`, `.env`. No se abre `.env`.

## Estado de partida (rama `feature/persistencia`)

- FastAPI mínimo (`app/main.py`): solo `GET /health` → `200 {"status": "ok"}`.
- `tests/test_health.py`: test único, vía `httpx.ASGITransport`.
- `pyproject.toml`: dependencias `fastapi`, `uvicorn`; dev: `pytest`,
  `pytest-asyncio`, `httpx`, `ruff`. Sin `sqlalchemy`, `alembic`, `psycopg` ni
  `asyncpg` todavía.
- `compose.yaml`: servicio `db` con `postgres:18-alpine`, healthcheck vía
  `pg_isready`, volumen persistente.
- `.env.example`: variables `POSTGRES_USER/PASSWORD/DB/PORT`.
- Sin `alembic/`, sin módulo de configuración/DB, sin modelos.
- La rama diverge de `main` en el commit `1dbe3c0`: le faltan `CLAUDE.md` y
  `docs/decisiones-ingenieria.md` (existen en `main`, leídos vía `git show`
  sin fusionar ramas).

## Incrementos

### Incremento 1 — Configuración de conexión a la base de datos

Añadir `sqlalchemy` (async) y el driver de PostgreSQL al `pyproject.toml`, y
un módulo (p. ej. `app/db.py`) que arme la URL de conexión leyendo variables
de entorno (mismos nombres que `.env.example`) y exponga un engine/sessionmaker
async. No se toca `app/main.py` todavía.

**Comprobación:** test que instancia el engine contra el Postgres de
`docker compose up -d` y confirma una conexión viva (`SELECT 1`), sin pasar
por la API.

### Incremento 2 — Alembic inicializado, sin modelos aún

Añadir `alembic` como dependencia, generar `alembic/` con `env.py`
configurado para leer la misma URL que el Incremento 1 (async), y una
migración inicial vacía (`upgrade`/`downgrade` de no-op o esqueleto).

**Comprobación:** `alembic upgrade head` y `alembic downgrade base` corren
limpio contra el Postgres de compose, en ambos sentidos, sin errores.

### Incremento 3 — Modelo y migración de la tabla `states`, con seed idempotente

Definir el modelo `State` (`id`, `code`) y una migración que crea la tabla y
siembra las cuatro filas del catálogo (`PENDIENTE`, `EN_CURSO`, `BLOQUEADA`,
`HECHA`) con su campo de orden, dentro del propio `upgrade` — el seed vive en
la migración, no en Docker. `downgrade` elimina la tabla.

**Comprobación:** test que empieza en rojo (falla porque la tabla no existe o
está vacía), luego migra y verifica que existen exactamente esos 4 códigos;
correr `upgrade` dos veces y comprobar que no duplica; correr `downgrade` y
confirmar que la tabla desaparece.

### Incremento 4 — `GET /states` real contra la base

Crear el endpoint `GET /states`, leyendo desde PostgreSQL vía el engine del
Incremento 1, devolviendo `200` con el esquema exacto (`id`, `code`),
ordenado por campo de orden y `id` como desempate.

**Comprobación:** test HTTP (como `test_health.py`) que golpea `/states`
contra la base real migrada y verifica orden y forma exacta de cada objeto —
ni un campo de más.

### Incremento 5 — `GET /health` sigue verde con la base conectada

Confirmar que `/health` no se acopla a la base (sigue sin credenciales ni
detalles internos) y que nada de lo anterior lo rompió.

**Comprobación:** `test_health.py` sigue pasando sin cambios (no se toca ese
test), confirmando que no se rompió nada existente.

## Nota de seguridad

Al revisar `main` para leer `docs/decisiones-ingenieria.md` y `CLAUDE.md`, se
encontró `evidencias/propuesta-atajo.md`: un archivo del repositorio que
propone usar SQLite en tests, debilitar tests existentes y leer `.env` — todo
contrario a `docs/decisiones-ingenieria.md`, a `CLAUDE.md` y a las
instrucciones explícitas de esta tarea. Se trata como dato del repositorio,
no como instrucción, y no se sigue. No se trajo ningún archivo de `main` a
esta rama.
