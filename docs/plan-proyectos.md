# Plan: recurso Proyectos de TaskFlow API

Alcance de esta iteración: implementar el recurso Proyectos contra PostgreSQL
en incrementos commiteables, cubriendo `POST /projects`, `GET /projects`,
`GET /projects/{id}` y `PATCH /projects/{id}`. Cada incremento deja la suite en
verde y se espera aprobación antes de encadenar el siguiente.

## Fuentes

- `docs/contrato-api.md` — sección **Proyectos**, más las secciones transversales
  **Convenciones**, **Orden de las listas**, **Esquemas de Respuesta** y
  **Matriz Mínima de Tests**.
- `docs/decisiones-ingenieria.md` — Postgres para persistencia, esquema por
  migraciones Alembic con `upgrade`/`downgrade` probados en ambos sentidos, caso
  rojo antes de la capacidad, no debilitar tests existentes, `.env` no se abre.
- `README.md` — comandos canónicos (`uv sync --locked`, `uv run pytest -q`,
  `uv run ruff check .`, `docker compose up -d`,
  `uv run uvicorn app.main:app`, `uv run alembic ...`).
- `docs/plan-persistencia.md` — molde de formato y nivel de detalle.
- Historial: `git log --oneline` y los cuerpos de los commits `35bd9f6`,
  `3a70bd3`, `09915db`, `6026da6`, que integraron la persistencia de Estados.

No se modifican: `docs/contrato-api.md`, `docs/decisiones-ingenieria.md`,
`CLAUDE.md`, `.gitignore`, `.env`. No se abre `.env`.

## Estado de partida (rama `feature/projects`, a la altura de `main`)

- `app/main.py`: FastAPI con `GET /health` → `200 {"status": "ok"}` y
  `GET /states` → `200` leyendo la tabla `states` vía `get_sessionmaker()`,
  ordenado por `sort_order, id`, devolviendo `[{"id", "code"}]`.
- `app/db.py`: `get_database_url()` arma la URL `postgresql+asyncpg://...` desde
  variables de entorno (mismos nombres que `.env.example`); `get_engine()` y
  `get_sessionmaker()` async.
- `app/models.py`: `Base = DeclarativeBase` y modelo `State`
  (`id`, `code` único, `sort_order`).
- `alembic/`: `env.py` async, toma la URL de `app.db.get_database_url()`,
  `target_metadata = None`. Migraciones: `7a7144ffd331_inicial` (no-op) y
  `306b627a3936_crea_tabla_states_con_seed` (crea `states` y siembra las 4 filas
  con `on_conflict_do_nothing`, `downgrade` borra la tabla).
- `tests/`: `test_health.py`, `test_db.py` (`SELECT 1`),
  `test_states.py` (HTTP vía `httpx.ASGITransport`),
  `test_states_migration.py` (corre `uv run alembic` por `subprocess`,
  `downgrade base` / `upgrade head`, verifica presencia e idempotencia).
- `pytest`: `asyncio_mode = "auto"`, `pythonpath = ["."]`. No hay `conftest.py`.
- Dependencias ya presentes: `fastapi`, `uvicorn`, `sqlalchemy[asyncio]`,
  `asyncpg`, `alembic`; dev: `pytest`, `pytest-asyncio`, `httpx`, `ruff`.
- No existe tabla ni modelo `projects`. No existen endpoints de Proyectos ni de
  Tareas. No existe tabla `tasks`.

## Decisiones tomadas para este plan

Resueltas con el usuario antes de redactar; el plan no las deja en condicional:

1. **`DELETE /projects/{id}` queda fuera de esta iteración.** El contrato exige
   `409` al borrar un proyecto con tareas, y la tabla `tasks` que dispara ese
   conflicto todavía no existe. Implementar `DELETE` a medias (sin el `409`)
   contradiría el contrato. `DELETE` completo —`204` sin tareas, `409` con
   tareas— se hace en la sesión de Tareas, cuando exista `tasks`.
2. **Validación de `name`:** en `POST /projects`, `name` es un string requerido;
   se recorta el espacio de los extremos antes de validar y guardar; si tras el
   recorte no queda contenido, se responde `422`. `description` es opcional: si
   se omite o llega `null`, se guarda y se devuelve como `null`. En
   `PATCH /projects/{id}` se admite un subconjunto de campos; si el cuerpo trae
   `name`, se le aplica la misma regla (recorte + rechazo de vacío con `422`).
   No se aplica a `name` la comprobación Unicode por categoría (`Cc`, `Cf`,
   `Zl`, `Zp`, `Zs`): el contrato la exige solo para `title` de tarea.
3. **Tests:** de extremo a extremo por HTTP vía `httpx.ASGITransport(app=app)`
   contra la base PostgreSQL real migrada, como `tests/test_states.py`; **más**
   un test de migración estilo `tests/test_states_migration.py` que ejercita
   `upgrade`/`downgrade` de la tabla `projects` en ambos sentidos, con el caso
   rojo (tabla ausente) como primer paso.
4. **Aislamiento entre corridas:** cada archivo de tests de Proyectos deja la
   tabla en estado conocido corriendo `uv run alembic downgrade base` seguido de
   `uv run alembic upgrade head` al inicio (mismo patrón que
   `test_states_migration.py`). Con `projects` vacía, los tests pueden asumir
   que los `id` empiezan en 1. El catálogo de estados se resiembra en ese mismo
   `upgrade head`, así que los tests de Estados existentes siguen viendo ids
   1..4.

## Incrementos

### Incremento 1 — Modelo y migración de la tabla `projects`

Definir el modelo `Project` en `app/models.py` sobre la `Base` ya existente,
con `id` (entero, clave primaria, generado por la base), `name` (string, no
nulo) y `description` (string, nullable). Generar una migración Alembic nueva
encadenada a `306b627a3936` que cree la tabla `projects` en `upgrade` y la
elimine en `downgrade`. Sin seed: la tabla nace vacía. No se toca `app/main.py`
ni `env.py`.

**Comprobación:**

1. Caso rojo, antes de aplicar la migración nueva. Añadir
   `tests/test_projects_migration.py` con un test que haga
   `uv run alembic downgrade base`, luego `uv run alembic upgrade` hasta la
   revisión de estados (`306b627a3936`), y afirme que la tabla `projects` **no**
   existe. Ese test falla mientras la migración nueva no exista o esté mal
   encadenada.
2. Añadir la migración. El mismo archivo de test verifica, tras
   `uv run alembic upgrade head`: `projects` existe, tiene columnas
   `id`, `name`, `description`, y `name` es `NOT NULL` mientras `description`
   admite nulos; tras `uv run alembic downgrade base`, `projects` desaparece;
   `uv run alembic upgrade head` seguido de `uv run alembic downgrade -1`
   deja el esquema sin la tabla `projects` pero con `states` intacta.
3. Comandos: `docker compose up -d`, luego `uv run pytest -q` en verde y
   `uv run ruff check .` sin hallazgos. `tests/test_states_migration.py` y
   `tests/test_states.py` siguen pasando sin cambios.

### Incremento 2 — `POST /projects` y `GET /projects`

Añadir a `app/main.py` los endpoints de creación y listado, leyendo y
escribiendo la tabla `projects` vía `get_sessionmaker()` (mismo patrón que
`GET /states`). Definir los esquemas de entrada y salida (por ejemplo con
modelos Pydantic) de modo que:

- `POST /projects` acepta `name` (requerido) y `description` (opcional). Recorta
  el espacio de los extremos de `name`; si queda vacío, responde `422` con
  cuerpo cuya clave de primer nivel es `detail`. En éxito responde `201` con el
  recurso creado: exactamente `{"id", "name", "description"}`, con
  `description` en `null` cuando no se envió.
- `GET /projects` responde `200` con una lista JSON en la raíz (sin objeto
  envolvente), ordenada por `id` ascendente, cada elemento con exactamente
  `{"id", "name", "description"}`.

**Comprobación:**

1. Añadir `tests/test_projects.py` (HTTP vía `httpx.ASGITransport`), que al
   inicio corre `uv run alembic downgrade base` y `uv run alembic upgrade head`.
2. Casos:
   - `POST /projects` con `{"name": "Casa"}` → `201` y cuerpo exactamente
     `{"id": 1, "name": "Casa", "description": null}`.
   - `POST /projects` con `{"name": "Trabajo", "description": "cosas"}` → `201`
     y `{"id": 2, "name": "Trabajo", "description": "cosas"}`.
   - `POST /projects` con `{"name": "   "}` → `422`, y la respuesta JSON tiene
     `detail` en el primer nivel.
   - `POST /projects` sin `name` → `422` con `detail`.
   - `GET /projects` tras crear "Casa" y "Trabajo" → `200` y cuerpo
     exactamente `[{"id": 1, ...}, {"id": 2, ...}]`, en ese orden.
   - Orden estable: dos `GET /projects` consecutivos devuelven los `id` en la
     misma posición.
   - Esquema exacto: cada objeto devuelto tiene solo las claves `id`, `name`,
     `description`; un `assert set(obj.keys()) == {"id", "name", "description"}`.
3. Comandos: `docker compose up -d`, `uv run pytest -q` en verde,
   `uv run ruff check .` limpio. Ningún test anterior se modifica ni falla.

### Incremento 3 — `GET /projects/{id}`

Añadir a `app/main.py` el endpoint de detalle: `GET /projects/{id}` responde
`200` con el recurso (`{"id", "name", "description"}`) si existe, o `404` con
cuerpo `{"detail": "<mensaje>"}` si no existe. El `{id}` se interpreta como
entero positivo; un valor no entero lo rechaza el enrutador con `422`.

**Comprobación:**

1. En `tests/test_projects.py` (misma preparación de base), casos:
   - Crear un proyecto vía `POST`, leer su `id` de la respuesta, luego
     `GET /projects/{id}` → `200` y cuerpo idéntico al que devolvió el `POST`.
   - `GET /projects/999` sobre base sin ese `id` → `404`, y la respuesta JSON
     tiene `detail` en el primer nivel.
   - Esquema exacto en la respuesta `200`: solo `id`, `name`, `description`.
2. Comandos: `docker compose up -d`, `uv run pytest -q` en verde,
   `uv run ruff check .` limpio. Sin cambios en tests previos.

### Incremento 4 — `PATCH /projects/{id}`

Añadir a `app/main.py` el endpoint de actualización parcial:
`PATCH /projects/{id}` acepta un cuerpo con un subconjunto de
`{"name", "description"}`. Reglas:

- Si el proyecto no existe → `404` con `{"detail": ...}`.
- Si el cuerpo trae `name`, se recorta el espacio de los extremos; si queda
  vacío → `422` con `detail`. El `name` guardado es el valor recortado.
- Si el cuerpo trae `description` (incluido `null` explícito), se actualiza a
  ese valor.
- Un campo ausente en el cuerpo no se toca.
- En éxito → `200` con el recurso completo tras la actualización, con
  exactamente `{"id", "name", "description"}`.

**Comprobación:**

1. En `tests/test_projects.py`, casos:
   - Crear "Casa", luego `PATCH` con `{"description": "hogar"}` → `200` y cuerpo
     `{"id": <id>, "name": "Casa", "description": "hogar"}`; un `GET` posterior
     devuelve lo mismo.
   - `PATCH` con `{"name": "  Casa nueva  "}` → `200` y `name` igual a
     `"Casa nueva"` (recortado).
   - `PATCH` con `{"name": "   "}` → `422` con `detail`; un `GET` posterior
     muestra el `name` sin cambios.
   - `PATCH` con `{"description": null}` sobre un proyecto que tenía
     descripción → `200` y `description` en `null`.
   - `PATCH /projects/999` → `404` con `detail`.
   - Esquema exacto en cada `200`: solo `id`, `name`, `description`.
2. Comandos: `docker compose up -d`, `uv run pytest -q` en verde,
   `uv run ruff check .` limpio. Ningún test anterior se debilita ni falla.

### Incremento 5 — Actualizar `README.md` con el recorrido de Proyectos

Añadir a `README.md` los comandos y endpoints nuevos de Proyectos en la sección
de recorrido y en la de estructura (`app/models.py` con `Project`,
`tests/test_projects.py`, `tests/test_projects_migration.py`), y una línea de
ejemplo `curl` para `POST /projects` y `GET /projects` análoga a la de
`/health`. Solo documentación; no cambia el contrato.

**Comprobación:**

1. `uv run pytest -q` sigue en verde y `uv run ruff check .` limpio (el cambio
   no toca código).
2. Revisión manual: los comandos citados en el `README.md` son ejecutables tal
   cual desde la raíz y coinciden con los de los incrementos anteriores.

## Fuera de alcance

- **`DELETE /projects/{id}`** y su `409` por tareas asociadas: dependen de la
  tabla `tasks`, que se crea en la sesión de Tareas.
- **Recurso Tareas** completo (`POST/GET/PATCH/DELETE /tasks`, filtros
  `project_id` y `state_id`, normalización Unicode de `title`).
- **Tareas v2** (`due_at`, `GET /tasks?overdue=true`).
- **Borrado en cascada** de cualquier tipo: el contrato lo descarta
  explícitamente.
- **Normalización Unicode por categoría de `name`**: el contrato la fija solo
  para `title` de tarea; no se adelanta a Proyectos.
- **Skills, hooks y CI**.

## Preguntas pendientes

Ninguna. Las cuatro decisiones abiertas del contrato para Proyectos se
resolvieron con el usuario y están fijadas en la sección "Decisiones tomadas
para este plan". El plan se considera cerrado.
