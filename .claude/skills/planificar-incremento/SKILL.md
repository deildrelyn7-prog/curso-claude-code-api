---
name: planificar-incremento
description: >-
  Planifica el siguiente incremento de trabajo de este repositorio contra sus
  documentos de verdad y deja el plan en docs/. Úsala cuando haya que definir
  cómo abordar una capacidad nueva (un endpoint, un grupo de endpoints, una
  migración) antes de escribir código. Planifica y no implementa.
---

# planificar-incremento

Produce un plan de incremento para TaskFlow API: un documento en `docs/` que
parte el trabajo en incrementos numerados, cada uno con su comprobación
ejecutable, sin decisiones aplazadas y con el fuera de alcance declarado.

## Límite de la skill

Esta skill **planifica y no implementa**. Al invocarla:

- No crea ni modifica código de la aplicación ni de los tests.
- No instala ni actualiza dependencias (`uv add`, `uv sync`, editar
  `pyproject.toml` o `uv.lock`).
- No toca la base de datos: no corre migraciones, no levanta ni borra el
  contenedor, no ejecuta `psql`.
- El único archivo que escribe es el plan en `docs/`.

Para leer el estado actual puede usar comandos de solo lectura (`git log`,
`git show`, `git diff`, `ls`, leer archivos). Nada que modifique el árbol,
el entorno o la base.

## Documentos contra los que se planifica

Léelos antes de escribir una sola línea del plan. Son la fuente de verdad de
este repositorio:

- `docs/contrato-api.md` — comportamiento observable: rutas, códigos de
  estado, esquemas de respuesta exactos, orden de las listas, normalización
  de texto, matriz mínima de tests. Un plan solo propone cambiarlo si el
  encargo lo dice explícitamente.
- `docs/decisiones-ingenieria.md` — decisiones del equipo que no se deducen
  del código: Postgres para tests de persistencia, esquema por migraciones
  Alembic con `upgrade`/`downgrade` probados en ambos sentidos, caso rojo
  antes de la capacidad, no debilitar tests existentes, `.env` no se abre.
- `README.md` — comandos canónicos del repositorio (`uv sync --locked`,
  `uv run pytest -q`, `uv run ruff check .`, `docker compose up -d`,
  `uv run uvicorn app.main:app`). Las comprobaciones del plan se escriben
  con estos comandos.
- `docs/plan-persistencia.md` — plan de incrementos ya existente; úsalo como
  molde de formato y nivel de detalle.
- El historial relevante: `git log --oneline` y los cuerpos de commit de la
  última iteración, para saber qué ya está hecho y con qué criterio.

## Procedimiento

1. **Reúne el estado.** Lee los documentos de arriba. Corre `git log --oneline`
   y `git show` sobre los commits de la iteración previa. Identifica el punto
   de partida real: qué existe hoy en `app/`, `tests/`, `alembic/versions/`.

2. **Delimita el encargo.** Escribe en una o dos frases qué capacidad pide
   esta iteración, citando la sección de `docs/contrato-api.md` que la
   define. Si el encargo abarca varias secciones del contrato, dilo.

3. **Parte en incrementos numerados.** Cada incremento:
   - Es commiteable por separado y deja la suite en verde.
   - Tiene un título que dice qué añade.
   - Describe el cambio en prosa, sin escribir el código.
   - **Declara su propia comprobación ejecutable**: los comandos exactos que
     otra persona correría para verificarlo (de `README.md`), y qué resultado
     concreto se espera (código de estado, forma de la respuesta, filas en la
     tabla, `pytest` en verde). Una comprobación que no se puede ejecutar no
     vale.
   - Si el contrato pide un caso rojo primero (`docs/decisiones-ingenieria.md`),
     el incremento lo nombra como primer paso de su comprobación.

4. **No aplaces ninguna decisión.** Si algo necesario para el plan no se puede
   decidir con lo que hay en el repositorio —un detalle de esquema, un código
   de estado, un nombre de campo, el orden de una lista—, **pregúntalo al
   usuario y espera respuesta**. No lo escribas en condicional ("se podría…",
   "quizá convenga…", "una opción sería…"). El plan final no contiene
   condicionales de decisión: cada punto está decidido o está marcado como
   pregunta pendiente que bloquea.

5. **Declara el fuera de alcance.** Una sección explícita que lista qué NO
   entra en esta iteración: endpoints, campos, filtros, comportamientos del
   contrato que quedan para después, y por qué (normalmente: pertenecen a otra
   sesión o dependen de un incremento aún no hecho).

6. **Escribe el plan en `docs/`.** Nombre del archivo: `plan-<tema>.md`, donde
   `<tema>` dice de qué es el plan (por ejemplo `plan-proyectos.md`,
   `plan-tareas-v1.md`, `plan-due-at.md`). Estructura:
   - Título y alcance de la iteración (1-2 frases).
   - Fuentes (los documentos consultados).
   - Estado de partida.
   - Incrementos numerados, cada uno con su comprobación.
   - Fuera de alcance.
   - Preguntas pendientes, si las hay (y entonces el plan no se considera
     cerrado hasta que se respondan).

7. **Enséñale el plan al usuario** antes de darlo por terminado. No sigue a
   implementación: eso es otra sesión.

## Qué no hacer

- No escribas código de `app/` ni de `tests/` "para ilustrar".
- No propongas SQLite ni tocar `.env`; ambos están descartados en
  `docs/decisiones-ingenieria.md`.
- No inventes motivos: cada "por qué" del plan sale del contrato, de las
  decisiones de ingeniería o del encargo. Si no está en ninguno, es una
  pregunta pendiente.
- No dejes una comprobación en genérico ("probar que funciona"): siempre
  comando + resultado esperado.
