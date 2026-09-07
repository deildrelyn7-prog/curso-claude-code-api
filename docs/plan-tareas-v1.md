# Plan: recurso Tareas v1 de TaskFlow API

Alcance de esta iteración: implementar el recurso Tareas en su versión v1
contra PostgreSQL en incrementos commiteables, cubriendo `POST /tasks`,
`GET /tasks` (con filtros `project_id` y `state_id`, solos y combinados),
`GET /tasks/{id}`, `PATCH /tasks/{id}` y `DELETE /tasks/{id}`, más la
normalización de `title` que fija el contrato. Cada incremento deja la suite
en verde y se espera aprobación antes de encadenar el siguiente.

## Fuentes

- `docs/contrato-api.md` — sección **Tareas v1**, más las secciones
  transversales **Convenciones**, **Normalización de texto**,
  **Orden de las listas**, **Esquemas de Respuesta** y
  **Matriz Mínima de Tests**.
- `docs/decisiones-ingenieria.md` — Postgres para persistencia, esquema por
  migraciones Alembic con `upgrade`/`downgrade` probados en ambos sentidos,
  caso rojo antes de la capacidad, no debilitar tests existentes, `.env` no
  se abre.
- `README.md` — comandos canónicos (`uv sync --locked`, `uv run pytest -q`,
  `uv run ruff check .`, `docker compose up -d`, `uv run uvicorn app.main:app`,
  `uv run alembic ...`).
- `docs/plan-persistencia.md` y `docs/plan-proyectos.md` — molde de formato y
  nivel de detalle; el segundo fija el patrón de aislamiento entre corridas
  (`downgrade base` + `upgrade head`) y el estilo de los tests de migración.
- Historial: `git log --oneline` y los cuerpos de los commits `bb4a064` y
  `c0b89c9`, que integraron el modelo `Project`, su migración y el CRUD de
  Proyectos.

No se modifican: `docs/contrato-api.md`, `docs/decisiones-ingenieria.md`,
`CLAUDE.md`, `.gitignore`, `.env`. No se abre `.env`.

## Estado de partida (rama `feature/tasks`, a la altura de `main`)

- `app/main.py`: FastAPI con `GET /health`, `GET /states` y el CRUD parcial de
  Proyectos (`POST /projects`, `GET /projects`, `GET /projects/{id}`,
  `PATCH /projects/{id}`). Toda la lectura/escritura pasa por
  `get_sessionmaker()`. La validación de `name` de proyecto usa `_clean_name`:
  `strip()` y rechazo del vacío con `ValueError` (que FastAPI/Pydantic
  traducen a `422`).
- `app/db.py`: `get_database_url()` arma `postgresql+asyncpg://...` desde
  variables de entorno (mismos nombres que `.env.example`); `get_engine()` y
  `get_sessionmaker()` async.
- `app/models.py`: `Base = DeclarativeBase`, modelo `State`
  (`id`, `code` único, `sort_order`) y modelo `Project`
  (`id`, `name` no nulo, `description` nullable). No existe modelo `Task`.
- `alembic/`: `env.py` async, URL desde `app.db.get_database_url()`,
  `target_metadata = None`. Migraciones encadenadas:
  `7a7144ffd331_inicial` (no-op) → `306b627a3936_crea_tabla_states_con_seed`
  (crea `states`, siembra las 4 filas con `on_conflict_do_nothing`) →
  `e7a3a73c8c3b_crea_tabla_projects` (crea `projects`, `downgrade` la borra).
  `head` es `e7a3a73c8c3b`.
- `tests/`: `test_health.py`, `test_db.py` (`SELECT 1`),
  `test_states.py`, `test_states_migration.py`, `test_projects.py`
  (CRUD HTTP con fixture `autouse` que hace `downgrade base` + `upgrade head`),
  `test_projects_migration.py` (`upgrade`/`downgrade` de `projects` por
  `subprocess`). No hay `conftest.py`.
- `pytest`: `asyncio_mode = "auto"`, `pythonpath = ["."]`.
- `ruff`: `select = ["E", "F", "I", "UP", "B"]`, `line-length = 100`.
- Dependencias ya presentes: `fastapi`, `uvicorn`, `sqlalchemy[asyncio]`,
  `asyncpg`, `alembic`; dev: `pytest`, `pytest-asyncio`, `httpx`, `ruff`.
  Este plan no añade dependencias.
- No existe tabla ni modelo `tasks`. No existe ningún endpoint bajo `/tasks`.

## Decisiones tomadas para este plan

Resueltas con el usuario antes de redactar; el plan no las deja en condicional:

1. **`POST /tasks` con `project_id` o `state_id` inexistente responde `422`.**
   El contrato exige validar proyecto y estado y prohíbe crear la referencia
   implícitamente, pero no fija el código; el equipo adopta `422` (entrada
   inválida), no `404` ni `409`. El cuerpo tiene `detail` en el primer nivel.

2. **`state_id` es opcional en `POST /tasks`; omitirlo crea la tarea en
   `PENDIENTE`.** El estado por defecto es la fila del catálogo con
   `code = "PENDIENTE"` (la de `sort_order` 1). Si el cuerpo trae `state_id`,
   debe apuntar a un estado existente o es `422` (decisión 1). `project_id`
   **sí** es obligatorio: omitirlo es `422`.

3. **`DELETE /projects/{id}` entra en esta iteración (Incremento 9).**
   Decisión revisada por el usuario a mitad de la iteración: la deuda que el
   plan de Proyectos dejó pendiente "para la sesión de Tareas, cuando exista
   `tasks`" se cierra aquí, ya que la tabla `tasks` existe tras el
   Incremento 1. `204` si el proyecto no tiene tareas, `409` si las tiene; sin
   borrado en cascada implícito (contrato, sección Proyectos).

4. **`title` se normaliza como fija el contrato**, y de forma más estricta que
   el `name` de proyecto: (a) se recorta el espacio de los extremos; (b) se
   rechaza con `422` si tras el recorte no queda **ningún carácter visible**,
   comprobando por categoría Unicode y rechazando `Cc`, `Cf`, `Zl`, `Zp` y
   `Zs`. El valor guardado es el recortado. En `PATCH /tasks/{id}`, si el
   cuerpo trae `title`, se le aplica la misma regla. `description` es opcional:
   omitirla o enviar `null` la guarda y la devuelve como `null`.
   La sesión 7 profundiza en el caso del invisible que parece válido; este
   plan ya deja la comprobación por categoría implementada, no un `strip()` a
   secas.

5. **Modelo `Task` y tabla `tasks`:** columnas `id` (entero, PK, generada por
   la base), `title` (string, no nulo), `description` (string, nullable),
   `project_id` (entero, no nulo, FK a `projects.id`), `state_id` (entero, no
   nulo, FK a `states.id`). `due_at` **no** se añade en v1 (es v2). Las dos FK
   se declaran a nivel de esquema en la migración; la validación de existencia
   que devuelve `422` se hace además en la capa de aplicación para controlar
   el código y el cuerpo del error (una violación de FK cruda daría `500`).

6. **Tests:** de extremo a extremo por HTTP vía `httpx.ASGITransport(app=app)`
   contra la base PostgreSQL real migrada, igual que `tests/test_projects.py`;
   **más** un test de migración estilo `tests/test_projects_migration.py` que
   ejercita `upgrade`/`downgrade` de la tabla `tasks` en ambos sentidos, con
   el caso rojo (tabla ausente) como primer paso.

7. **Aislamiento entre corridas:** `tests/test_tasks.py` usa una fixture
   `autouse` que corre `uv run alembic downgrade base` seguido de
   `uv run alembic upgrade head` al inicio de cada test (mismo patrón que
   `tests/test_projects.py`). Con `tasks` y `projects` vacías y el catálogo de
   estados resembrado, los tests asumen `id` de proyecto y de tarea desde 1 y
   `state_id` 1..4 en el orden del catálogo (`PENDIENTE`=1, `EN_CURSO`=2,
   `BLOQUEADA`=3, `HECHA`=4).

## Incrementos

### Incremento 1 — Modelo y migración de la tabla `tasks`

Definir el modelo `Task` en `app/models.py` sobre la `Base` ya existente, con
`id` (entero, PK), `title` (string, no nulo), `description` (string, nullable),
`project_id` (entero, no nulo, `ForeignKey("projects.id")`) y `state_id`
(entero, no nulo, `ForeignKey("states.id")`). Generar una migración Alembic
nueva encadenada a `e7a3a73c8c3b` que cree la tabla `tasks` en `upgrade`
—con sus dos restricciones de clave foránea— y la elimine en `downgrade`.
Sin seed: la tabla nace vacía. No se toca `app/main.py` ni `env.py`.

**Comprobación:**

1. Caso rojo, antes de aplicar la migración nueva. Añadir
   `tests/test_tasks_migration.py` con un test que haga
   `uv run alembic downgrade base`, luego `uv run alembic upgrade` hasta la
   revisión de `projects` (`e7a3a73c8c3b`), y afirme que la tabla `tasks`
   **no** existe. Ese test falla mientras la migración nueva no exista o esté
   mal encadenada.
2. Añadir la migración. El mismo archivo de test verifica, tras
   `uv run alembic upgrade head`: `tasks` existe; tiene columnas `id`,
   `title`, `description`, `project_id`, `state_id`; `title`, `project_id` y
   `state_id` son `NOT NULL` y `description` admite nulos; existen dos claves
   foráneas, una a `projects` y otra a `states` (vía
   `inspect(...).get_foreign_keys("tasks")`). Tras
   `uv run alembic downgrade base`, `tasks` desaparece.
   `uv run alembic upgrade head` seguido de `uv run alembic downgrade -1`
   deja el esquema sin `tasks` pero con `projects` y `states` intactas.
3. Comandos: `docker compose up -d`, luego `uv run pytest -q` en verde y
   `uv run ruff check .` sin hallazgos. `tests/test_projects_migration.py`,
   `tests/test_states_migration.py`, `tests/test_projects.py` y
   `tests/test_states.py` siguen pasando sin cambios.

### Incremento 2 — Normalización de `title` (utilidad + caso rojo)

Añadir a `app/main.py` una función de normalización de `title` independiente
de `_clean_name`: recorta los extremos y, si tras el recorte todo el texto
cae en las categorías Unicode `Cc`, `Cf`, `Zl`, `Zp`, `Zs` (o queda vacío),
lanza `ValueError` (que FastAPI traduce a `422`). El valor devuelto es el
recortado. Todavía no se expone ningún endpoint `/tasks`; la función se
prueba a través del primer endpoint del Incremento 3, pero este incremento
deja escrito el caso rojo.

**Comprobación:**

1. Añadir a `tests/test_tasks.py` (que ya trae la fixture de aislamiento) un
   test parametrizado que, una vez exista `POST /tasks` (Incremento 3),
   confirme `422` para: `""`, `"   "` (espacios ASCII), `"​"`
   (`U+200B`, `Cf`), `" "` (`Zl`), `" "` (`Zs` sola). Mientras
   `POST /tasks` no exista, el test falla por `404`/`405`; ese es el rojo que
   este incremento introduce y el Incremento 3 pone en verde.
2. Comandos: `uv run pytest -q` muestra ese test en rojo tras este incremento
   (documentado en el cuerpo del commit), y `uv run ruff check .` limpio.
   Ningún test anterior se toca.

Nota: si se prefiere no dejar rojo en `main` de la rama entre incrementos, el
Incremento 2 y el 3 se pueden confirmar juntos; el plan los separa para dejar
explícita la exigencia de "caso rojo antes de la capacidad" de
`docs/decisiones-ingenieria.md`.

### Incremento 3 — `POST /tasks` y `GET /tasks` sin filtros

Añadir a `app/main.py` los endpoints de creación y listado, leyendo y
escribiendo la tabla `tasks` vía `get_sessionmaker()` (mismo patrón que
Proyectos). Esquemas de entrada y salida (modelos Pydantic) tales que:

- `POST /tasks` acepta `title` (requerido), `description` (opcional),
  `project_id` (requerido) y `state_id` (opcional). `title` se normaliza con
  la utilidad del Incremento 2; si queda sin carácter visible → `422` con
  `detail`. Antes de insertar se comprueba que `project_id` apunta a un
  proyecto existente; si no, `422` con `detail`. Si el cuerpo trae `state_id`,
  se comprueba que apunta a un estado existente; si no, `422` con `detail`.
  Si `state_id` se omite, se resuelve el `id` del estado `PENDIENTE` y se usa
  ese. En éxito → `201` con el recurso creado: exactamente
  `{"id", "title", "description", "project_id", "state_id"}` (v1: **sin**
  `due_at`), con `description` en `null` cuando no se envió.
- `GET /tasks` sin parámetros → `200` con una lista JSON en la raíz (sin
  objeto envolvente), ordenada por `id` ascendente, cada elemento con
  exactamente esas cinco claves.

**Comprobación:**

1. `tests/test_tasks.py` (HTTP vía `httpx.ASGITransport`, fixture de
   aislamiento). Preparación común de cada test: crear vía `POST /projects`
   los proyectos que el caso necesite.
2. Casos:
   - `POST /tasks` con `{"title": "Regar", "project_id": 1}` → `201` y cuerpo
     exactamente
     `{"id": 1, "title": "Regar", "description": null, "project_id": 1, "state_id": 1}`
     (`state_id` 1 = `PENDIENTE`).
   - `POST /tasks` con `{"title": "Podar", "description": "el seto",
     "project_id": 1, "state_id": 2}` → `201` y las cinco claves con esos
     valores.
   - `POST /tasks` con `title` que no deja carácter visible (los cinco valores
     del Incremento 2) → `422` con `detail`.
   - `POST /tasks` sin `title` → `422` con `detail`.
   - `POST /tasks` sin `project_id` → `422` con `detail`.
   - `POST /tasks` con `project_id` inexistente (p. ej. `999`) → `422` con
     `detail`; un `GET /tasks` posterior devuelve `[]`.
   - `POST /tasks` con `state_id` inexistente (p. ej. `99`) → `422` con
     `detail`.
   - `POST /tasks` con `title` `"  Regar  "` → `201` y `title` igual a
     `"Regar"` (recortado).
   - `GET /tasks` tras crear dos tareas → `200` y cuerpo exactamente
     `[{"id": 1, ...}, {"id": 2, ...}]` en ese orden.
   - Orden estable: dos `GET /tasks` consecutivos devuelven los `id` en la
     misma posición.
   - Esquema exacto: `assert set(obj.keys()) == {"id", "title",
     "description", "project_id", "state_id"}` para cada objeto; en particular
     **no** aparece `due_at`.
3. Comandos: `docker compose up -d`, `uv run pytest -q` en verde (incluido el
   test rojo del Incremento 2, ahora verde), `uv run ruff check .` limpio.
   Ningún test anterior se modifica ni falla.

### Incremento 4 — Filtros `project_id` y `state_id` en `GET /tasks`

Ampliar `GET /tasks` para aceptar los parámetros de consulta `project_id` y
`state_id`, opcionales, enteros, solos o combinados. Con ambos presentes se
aplican en conjunción (AND). El resultado se ordena por `id` ascendente
**también con filtros aplicados** (contrato, tabla de orden). Un valor no
entero en cualquiera de los dos parámetros lo rechaza el enrutador con `422`.
Un `project_id` o `state_id` que no corresponde a ninguna fila no es error:
devuelve `[]`.

**Comprobación:**

1. En `tests/test_tasks.py` (misma preparación), sembrar un escenario fijo:
   dos proyectos; varias tareas repartidas entre ambos proyectos y entre al
   menos dos estados (`PENDIENTE` y `EN_CURSO`), creadas en orden conocido
   para fijar los `id`.
2. Casos:
   - `GET /tasks?project_id=1` → `200` y solo las tareas de ese proyecto, en
     `id` ascendente.
   - `GET /tasks?state_id=2` → `200` y solo las tareas en `EN_CURSO`, en `id`
     ascendente.
   - `GET /tasks?project_id=1&state_id=1` → `200` y solo las que cumplen
     ambas, en `id` ascendente.
   - `GET /tasks?project_id=999` → `200` y `[]`.
   - `GET /tasks?state_id=abc` → `422`.
   - Orden estable con filtro: dos llamadas idénticas con filtro devuelven los
     `id` en la misma posición.
   - Esquema exacto en cada elemento de las respuestas filtradas.
3. Comandos: `docker compose up -d`, `uv run pytest -q` en verde,
   `uv run ruff check .` limpio. Sin cambios en tests previos.

### Incremento 5 — `GET /tasks/{id}`

Añadir a `app/main.py` el endpoint de detalle: `GET /tasks/{id}` → `200` con
el recurso (las cinco claves de v1) si existe, o `404` con
`{"detail": "<mensaje>"}` si no existe. El `{id}` se interpreta como entero;
un valor no entero lo rechaza el enrutador con `422`.

**Comprobación:**

1. En `tests/test_tasks.py` (misma preparación), casos:
   - Crear una tarea vía `POST`, leer su `id`, luego `GET /tasks/{id}` →
     `200` y cuerpo idéntico al que devolvió el `POST`.
   - `GET /tasks/999` sobre base sin ese `id` → `404` con `detail` en el
     primer nivel.
   - Esquema exacto en la respuesta `200`: las cinco claves, ni una más.
2. Comandos: `docker compose up -d`, `uv run pytest -q` en verde,
   `uv run ruff check .` limpio. Sin cambios en tests previos.

### Incremento 6 — `PATCH /tasks/{id}`

Añadir a `app/main.py` el endpoint de actualización parcial:
`PATCH /tasks/{id}` acepta un cuerpo con un subconjunto de
`{"title", "description", "project_id", "state_id"}`. Reglas:

- Si la tarea no existe → `404` con `{"detail": ...}`.
- Si el cuerpo trae `title`, se normaliza con la utilidad del Incremento 2; si
  queda sin carácter visible → `422` con `detail`. El `title` guardado es el
  valor recortado.
- Si el cuerpo trae `description` (incluido `null` explícito), se actualiza a
  ese valor.
- Si el cuerpo trae `project_id`, debe apuntar a un proyecto existente; si no
  → `422` con `detail`.
- Si el cuerpo trae `state_id`, debe apuntar a un estado existente; si no →
  `422` con `detail`.
- Un campo ausente en el cuerpo no se toca.
- En éxito → `200` con el recurso completo tras la actualización, con
  exactamente las cinco claves de v1.

"Actualización parcial consistente" (contrato): tras el `PATCH`, un `GET`
del mismo recurso devuelve exactamente lo que devolvió el `PATCH`.

**Comprobación:**

1. En `tests/test_tasks.py`, casos:
   - Crear "Regar" en proyecto 1, luego `PATCH` con `{"state_id": 2}` → `200`
     y `state_id` 2; `GET` posterior devuelve lo mismo.
   - `PATCH` con `{"title": "  Regar más  "}` → `200` y `title` igual a
     `"Regar más"` (recortado).
   - `PATCH` con `{"title": "​"}` → `422` con `detail`; un `GET`
     posterior muestra el `title` sin cambios.
   - `PATCH` con `{"description": null}` sobre una tarea con descripción →
     `200` y `description` en `null`.
   - `PATCH` con `{"project_id": 2}` (proyecto 2 existe) → `200` y
     `project_id` 2.
   - `PATCH` con `{"project_id": 999}` → `422` con `detail`.
   - `PATCH` con `{"state_id": 99}` → `422` con `detail`.
   - `PATCH /tasks/999` → `404` con `detail`.
   - Esquema exacto en cada `200`: las cinco claves.
2. Comandos: `docker compose up -d`, `uv run pytest -q` en verde,
   `uv run ruff check .` limpio. Ningún test anterior se debilita ni falla.

### Incremento 7 — `DELETE /tasks/{id}`

Añadir a `app/main.py` el endpoint de borrado: `DELETE /tasks/{id}` → `204`
sin cuerpo si la tarea existe (y se elimina), o `404` con `{"detail": ...}`
si no existe. No hay efectos sobre el proyecto ni sobre el estado.

**Comprobación:**

1. En `tests/test_tasks.py`, casos:
   - Crear una tarea, `DELETE /tasks/{id}` → `204` y cuerpo vacío
     (`response.content == b""`); un `GET /tasks/{id}` posterior → `404`; un
     `GET /tasks` posterior no la incluye.
   - `DELETE /tasks/999` → `404` con `detail`.
   - Borrar una tarea de un proyecto y comprobar que
     `GET /projects/{id}` del proyecto sigue devolviendo `200` (el proyecto no
     se toca).
2. Comandos: `docker compose up -d`, `uv run pytest -q` en verde,
   `uv run ruff check .` limpio. Sin cambios en tests previos.

### Incremento 9 — `DELETE /projects/{id}` con `204`/`409`

Añadir a `app/main.py` el endpoint de borrado de proyecto:
`DELETE /projects/{id}` → `204` sin cuerpo si el proyecto existe y **no**
tiene tareas asociadas (y se elimina); `409` con `{"detail": ...}` si el
proyecto tiene al menos una tarea; `404` con `{"detail": ...}` si el proyecto
no existe. No hay borrado en cascada: el `409` bloquea, no arrastra las
tareas. El chequeo de tareas asociadas se hace en la capa de aplicación
(`SELECT` de conteo o `EXISTS` sobre `tasks` filtrando por `project_id`).

**Comprobación:**

1. En `tests/test_projects.py` (fixture de aislamiento ya presente), casos:
   - Crear un proyecto sin tareas, `DELETE /projects/{id}` → `204`, cuerpo
     vacío (`response.content == b""`); un `GET /projects/{id}` posterior →
     `404`.
   - Crear un proyecto, crear una tarea sobre ese proyecto vía `POST /tasks`,
     `DELETE /projects/{id}` → `409` con `detail` en el primer nivel; un
     `GET /projects/{id}` posterior sigue devolviendo `200` y un
     `GET /tasks` sigue mostrando la tarea (no hubo cascada).
   - `DELETE /projects/999` → `404` con `detail`.
2. Comandos: `docker compose up -d`, `uv run pytest -q` en verde,
   `uv run ruff check .` limpio. Ningún test anterior se debilita ni falla.

### Incremento 8 — Actualizar `README.md` con el recorrido de Tareas

Añadir a `README.md`: en la introducción, mención del recurso Tareas; en el
recorrido, una línea `curl` de ejemplo para `POST /tasks` y otra para
`GET /tasks` (y su forma con filtros), análogas a las de `/projects`; en la
sección de estructura, `app/models.py` con `Task`, `tests/test_tasks.py` y
`tests/test_tasks_migration.py`, y la migración nueva en
`alembic/versions/`. Solo documentación; no cambia el contrato.

**Comprobación:**

1. `uv run pytest -q` sigue en verde y `uv run ruff check .` limpio (el
   cambio no toca código).
2. Revisión manual: los comandos citados en el `README.md` son ejecutables
   tal cual desde la raíz y coinciden con los de los incrementos anteriores.

## Fuera de alcance

- **Tareas v2 completo:** `due_at` (columna, validación de zona horaria,
  rechazo `422` de fecha sin zona, serialización en UTC con `Z` y sin
  microsegundos) y el filtro `GET /tasks?overdue=true`. Es otra iteración; la
  columna `due_at` **no** se añade a la tabla ni al modelo en v1.
- **Recordatorios, scheduler, zona preferida del usuario y cambio automático
  de estado:** el contrato los declara fuera de alcance de v2; con más razón
  fuera de v1.
- **Borrado en cascada** de proyecto a tareas: el contrato lo descarta.
- **Endpoints de Estados más allá de `GET /states`:** el catálogo es cerrado.
- **Skills, hooks y CI.**

## Preguntas pendientes

Ninguna. Las decisiones abiertas del contrato para Tareas v1 —código de la
referencia inexistente, obligatoriedad y defecto de `state_id`, alcance de
`DELETE /projects/{id}` (revisado a mitad de iteración: entra como
Incremento 9)— se resolvieron con el usuario y están fijadas en la sección
"Decisiones tomadas para este plan". El plan se considera cerrado.
