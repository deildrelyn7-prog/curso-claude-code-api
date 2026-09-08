# Convenciones de la API

Fuente de verdad del comportamiento observable: `docs/contrato-api.md`. Estas
reglas no lo reemplazan; recogen cómo se aplica al escribir código.

## Esquema de respuesta exacto

Cualquier endpoint nuevo o modificado devuelve **exactamente** los campos que
`docs/contrato-api.md` declara para ese recurso en la sección "Esquemas de
Respuesta": ni un campo de más ni uno de menos.

- Un campo opcional ausente se devuelve como `null`, no se omite.
- Un campo que no está en el contrato no aparece en la respuesta, aunque exista
  en el modelo o en la tabla.
- Añadir un campo a una respuesta es un cambio de contrato: primero se
  actualiza `docs/contrato-api.md` (esquema y, si aplica, códigos y matriz de
  tests), en un commit aparte, y después el código.

Los tests de esquema exacto (`set(obj.keys()) == TASK_KEYS` y equivalentes) son
vinculantes: no se debilitan para acomodar un campo nuevo.

## No se debilita un test para conseguir verde

No se debilita ni elimina un test existente para conseguir verde. Si el
comportamiento acordado cambió, primero se actualiza `docs/contrato-api.md` y
después el test, en un commit separado.

Esta regla vale para cualquier test del repositorio y cualquier cambio de
comportamiento, no solo para los tests de esquema de la sección anterior.

## Un campo nuevo se añade en sus tres capas

Cuando el contrato incorpora un campo a un recurso, la implementación lo añade
en las tres capas, no en una suelta:

1. **Migración** — la columna en la base, con la revisión de Alembic
   correspondiente y su `downgrade`. Si el campo tiene un dominio acotado, la
   restricción va también aquí (un `CHECK`, un `NOT NULL`).
2. **Esquema** — la columna en el modelo SQLAlchemy (`app/models.py`),
   declarando el mismo tipo y la misma restricción que la migración, de modo
   que el modelo y el esquema físico coincidan.
3. **Validación** — la aceptación y el rechazo en el endpoint
   (`app/main.py`): el campo en los modelos Pydantic de entrada, su
   `field_validator` con las reglas del contrato (un valor inválido responde
   `422` con `detail`), la serialización en la respuesta, y la persistencia en
   el alta y en la edición parcial.

Un campo que entra por una capa y no por las otras —columna sin validación,
validación sin migración— está a medias.

Precedente de las tres capas juntas: el campo `due_at` de tarea (Tareas v2),
con su migración, su columna en el modelo y su validación en el endpoint.
