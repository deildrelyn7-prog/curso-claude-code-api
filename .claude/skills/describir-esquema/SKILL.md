---
name: describir-esquema
description: >-
  Genera docs/esquema.md a partir del estado real de app/models.py y
  alembic/versions/ en el momento de invocarla: un diagrama de tablas y
  relaciones en Mermaid más un diccionario de datos con una fila por columna.
  Describe el esquema físico; no lo modifica. Úsala cuando el esquema haya
  cambiado y su documentación esté desactualizada, o cuando no exista.
---

# describir-esquema

Produce un único documento, `docs/esquema.md`, que describe el esquema de base
de datos de TaskFlow API tal como está definido **hoy** en el repositorio: las
tablas, sus columnas y las relaciones entre ellas. El documento tiene dos
partes —un diagrama y un diccionario de datos— y no repite lo que ya fija
`docs/contrato-api.md`: lo enlaza.

## Límite de la skill

Esta skill **describe y no modifica**. Al invocarla:

- No edita `app/models.py` ni ningún otro archivo de `app/`.
- No crea, edita ni borra migraciones en `alembic/versions/`. No corre
  `alembic upgrade`, `alembic downgrade`, `alembic revision` ni `--autogenerate`.
- No toca `docs/contrato-api.md` ni `docs/decisiones-ingenieria.md`.
- No toca la base de datos: no levanta ni para el contenedor, no ejecuta
  `psql`, no se conecta a Postgres, no inspecciona el esquema vivo con
  reflection.
- El único archivo que escribe es `docs/esquema.md`.

Para leer el estado actual usa solo lectura: `ls`, `git log`, `git show`,
`git diff` y leer archivos. Nada que modifique el árbol, el entorno o la base.

## De dónde sale la verdad del esquema

El esquema se describe a partir de **dos fuentes del repositorio**, en este
orden:

1. **`app/models.py`** — los modelos SQLAlchemy. Es la vista declarativa y
   completa del esquema: cada tabla, cada columna con su tipo Python/SQLAlchemy,
   `nullable`, `unique`, `primary_key`, y las `ForeignKey`.
2. **`alembic/versions/`** — las migraciones, leídas **en orden de
   `down_revision`**, de la raíz (`down_revision = None`) a la cabeza. Aportan
   lo que el modelo no dice por sí solo: qué restricciones existen en el
   esquema físico (un `CHECK`, un `NOT NULL` añadido después, una
   `UniqueConstraint` con nombre), en qué migración entró cada columna, y
   cualquier dato sembrado (el seed del catálogo de estados).

Si el modelo y las migraciones se contradicen (un tipo distinto, un `nullable`
que no coincide, una columna en uno y no en el otro), **no lo resuelvas por tu
cuenta**: anótalo en una sección "Discrepancias detectadas" al final de
`docs/esquema.md`, con el archivo y la línea de cada lado, y díselo al usuario
en el resumen. Describir el esquema no es arreglarlo.

## Qué NO se escribe en docs/esquema.md

`docs/contrato-api.md` ya fija comportamiento observable. `docs/esquema.md`
describe el esquema físico y **enlaza** al contrato en vez de copiarlo. En
concreto, no se repite:

- El catálogo de valores de estado (`PENDIENTE`, `EN_CURSO`, …) ni su orden:
  eso vive en `docs/contrato-api.md#estados`. El diccionario de datos, en la
  fila de `states.code`, enlaza ahí.
- Las reglas de normalización de `title`, la serialización de `due_at` en UTC
  con `Z`, los códigos HTTP, los esquemas de respuesta: todo eso es contrato.
  Si una columna tiene una regla de contrato asociada, su celda "significado"
  enlaza a la sección correspondiente en vez de explicarla.
- El porqué de las decisiones (migración vs. script de Docker, `409` sin
  cascada): vive en `docs/contrato-api.md` y `docs/decisiones-ingenieria.md`.

`docs/esquema.md` sí dice, porque no está en ningún otro lado: el nombre físico
de cada tabla y columna, el tipo SQLAlchemy, `nullable`, las claves y su
`ON DELETE`, y en qué migración entró cada columna.

## Procedimiento

1. **Reúne el estado real.** No supongas qué tablas ni qué columnas hay.
   Inyecta y lee:
   - `git ls-files app/models.py alembic/versions/` — la lista exacta de
     archivos de modelo y migración que hay ahora en el repositorio.
   - `git diff --stat HEAD -- app/models.py alembic/versions/` — si hay
     cambios sin commitear en esas rutas, para describir el árbol de trabajo
     tal cual, no el último commit.
   - El contenido completo de `app/models.py`.
   - El contenido completo de **cada** archivo bajo `alembic/versions/`
     (excluyendo `__pycache__`).
   De `docs/contrato-api.md` **no** inyectes el cuerpo: basta su tabla de
   contenidos / lista de encabezados, para saber a qué anclas (`#estados`,
   `#tareas-v2-fechas-límite`, …) enlazar.

2. **Ordena las migraciones por `down_revision`.** Construye la cadena desde
   la revisión con `down_revision = None` hasta la cabeza. Si la cadena tiene
   una rama o un merge, dilo en el resumen: el orden deja de ser único y el
   "en qué migración entró" hay que matizarlo.

3. **Arma la lista de tablas y columnas** recorriendo `app/models.py`. Para
   cada columna anota: nombre físico, tipo SQLAlchemy tal como está escrito
   (`String`, `Integer`, `DateTime(timezone=True)`, …), `nullable`,
   `primary_key`, `unique`, y si es `ForeignKey` a qué columna apunta.

4. **Cruza con las migraciones en orden.** Para cada columna añade en qué
   revisión se creó (la que la introdujo con `create_table` o `add_column`).
   Añade cualquier restricción que esté en la migración y no en el modelo
   (`CHECK`, constraint con nombre, `server_default`). Registra el `ON DELETE`
   de cada `ForeignKeyConstraint` (si no lo declara, es `NO ACTION`; dilo
   así). Anota si una migración siembra datos en la tabla y enlaza al
   contrato en vez de listar los valores.

5. **Escribe el diagrama** como bloque Mermaid `erDiagram` dentro de
   `docs/esquema.md` (bloque ```` ```mermaid ````). Mermaid es texto: se
   versiona, se diferencia en un diff y GitHub lo renderiza en el `.md` sin
   herramientas extra. El diagrama incluye:
   - Una entidad por tabla, con sus columnas y tipo abreviado.
   - `PK` en la clave primaria, `FK` en las foráneas, `UK` en las únicas.
   - Una relación por cada `ForeignKey`, con cardinalidad
     (`projects ||--o{ tasks : "tiene"`), leída del `nullable` de la columna
     FK: `o{` si la FK admite nulos, `|{` si es `NOT NULL`.
   No metas en el diagrama nada que no esté en modelo o migración.

6. **Escribe el diccionario de datos** como una tabla Markdown por cada
   tabla física, una fila por columna, con estas columnas:
   `columna | tipo | nulos | significado`.
   - `tipo`: el tipo SQLAlchemy tal como aparece en el modelo.
   - `nulos`: `sí` / `no`, del `nullable`.
   - `significado`: **solo cuando no es evidente por el nombre.** Para `id`,
     `name`, `title` no hace falta glosa. Para `sort_order`, `state_id`,
     `due_at`, `project_id` sí: una frase, y si la regla es de contrato, un
     enlace a `docs/contrato-api.md#<ancla>` en lugar de la explicación.
   Debajo de cada tabla, una línea con las claves foráneas y su `ON DELETE`,
   y otra con la revisión de Alembic en que se creó la tabla y las revisiones
   que la alteraron después.

7. **Estructura de `docs/esquema.md`:**
   - Título y una frase de alcance ("Esquema físico de la base de TaskFlow
     API. Generado a partir de `app/models.py` y `alembic/versions/`.
     El comportamiento observable vive en `docs/contrato-api.md`.").
   - Fuentes: los dos orígenes y la fecha o el commit sobre el que se generó.
   - Diagrama (bloque Mermaid).
   - Diccionario de datos (una subsección por tabla).
   - Discrepancias detectadas, si las hay (si no, la sección se omite).

8. **Enseña el archivo al usuario** antes de darlo por terminado, y en el
   resumen di: qué tablas y columnas se documentaron, sobre qué commit o
   árbol se generó, si hubo discrepancias entre modelo y migraciones, y si la
   cadena de migraciones no era lineal.

## Qué no hacer

- No describas una tabla o columna "que debería existir" según el contrato
  pero no está en el modelo ni en una migración. La skill describe lo que hay.
- No corrijas una discrepancia entre modelo y migración editando ninguno de
  los dos: se anota y se reporta.
- No copies dentro de `docs/esquema.md` el catálogo de estados, las reglas de
  normalización, la serialización de `due_at` ni los códigos HTTP: se enlaza
  a `docs/contrato-api.md`.
- No uses un formato de diagrama binario o que dependa de un render externo
  (una imagen exportada, un `.drawio`): tiene que ser texto que se diffea y
  que GitHub renderiza solo. Mermaid `erDiagram` cumple; ASCII art también,
  pero Mermaid se mantiene mejor.
- No inspecciones la base viva para "confirmar": la fuente es el repositorio,
  no una instancia de Postgres que puede estar en cualquier estado.
- No dejes una celda "significado" con una paráfrasis del nombre de la
  columna ("`project_id`: el id del proyecto"): o aporta algo (qué pasa al
  borrar, que es FK, la regla de contrato enlazada) o se deja vacía.
