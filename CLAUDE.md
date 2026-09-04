# CLAUDE.md

Guía para Claude Code en este repositorio.

## Fuentes de verdad

- `docs/contrato-api.md` fija el comportamiento observable (códigos HTTP,
  esquemas, normalización). Es vinculante. Solo se modifica cuando el ticket
  dice explícitamente que cambia el contrato, en un commit aparte del código.
- `docs/decisiones-ingenieria.md` recoge las decisiones del equipo que no se
  deducen del código (base de datos, migraciones, pruebas, datos locales).
- `README.md` contiene los comandos canónicos del repositorio.

## Comandos canónicos

Gestión con `uv` desde la raíz del repositorio. Detalle completo en
`README.md`.

- Instalar dependencias: `uv sync --locked`
- Ejecutar tests: `uv run pytest -q`
- Lint: `uv run ruff check .`

## Persistencia

- Las pruebas que ejercitan persistencia corren contra PostgreSQL, nunca
  SQLite. Detalle en `docs/decisiones-ingenieria.md`.

## Pruebas

- No se debilita ni elimina un test existente para conseguir verde. Si el
  comportamiento acordado cambió, primero se actualiza `docs/contrato-api.md`
  y después el test, en un commit separado.

## Datos locales

- No abrir, mostrar, editar ni añadir a Git el archivo `.env`.
