---
name: construir-coleccion-postman
description: >-
  Construye o actualiza en Postman, usando el servidor MCP de Postman, una
  colección con una petición por operación de openapi.json: método, ruta,
  cuerpo de ejemplo cuando aplica, resumen y descripción copiados de la
  especificación, y un test que comprueba el código de estado del caso
  correcto. Busca o crea el espacio de trabajo del proyecto sin duplicarlo.
  Úsala cuando openapi.json haya cambiado y la colección de Postman deba
  reflejarlo, o cuando la colección todavía no exista.
allowed-tools: >-
  mcp__postman__getWorkspaces, mcp__postman__createWorkspace,
  mcp__postman__getCollections, mcp__postman__getCollection,
  mcp__postman__createCollection, mcp__postman__createCollectionRequest,
  mcp__postman__updateCollectionRequest, Read, Bash(git rev-parse *)
---

# construir-coleccion-postman

Lee `openapi.json` en la raíz del repositorio y lo traduce a una colección de
Postman con una petición por operación, usando las herramientas del servidor
MCP de Postman. Vuelve a invocarse cada vez que la especificación cambia: crea
lo que falta y actualiza lo que ya existe, sin duplicar espacios de trabajo ni
peticiones.

## Límite de la skill

- Lee `openapi.json`. No lo genera, no lo modifica, no lo regenera desde el
  código.
- No toca ningún archivo bajo `app/`, `alembic/`, `docs/contrato-api.md` ni
  ningún otro archivo del repositorio. El único destino de esta skill es la
  cuenta de Postman conectada por el servidor MCP.
- No hace `git commit`, `git push` ni ningún cambio en el árbol de trabajo o
  el historial.
- No decide si `openapi.json` coincide con lo que genera el código ahora
  mismo: eso ya lo cubre el hook `verificar-openapi.sh` antes de cada commit.
  Si `openapi.json` no existe o no es JSON válido, se dice y se para.
- Solo usa las herramientas del servidor `postman` declaradas en
  `allowed-tools`, más `Read` para `openapi.json` y `Bash(git rev-parse *)`
  para derivar el nombre del espacio de trabajo. Ninguna herramienta de
  Postman que no esté en esa lista.

## De dónde sale cada dato

Todo lo que esta skill escribe en Postman sale de `openapi.json`, sin
inventar nada que no esté declarado ahí:

- **Método y ruta** — la clave del método (`get`, `post`, `patch`, `delete`,
  …) y la clave de `paths` en la que aparece. Los parámetros de ruta
  (`{project_id}`) se copian tal cual: Postman los reconoce como variables de
  ruta por la sintaxis `{{project_id}}` — la petición los declara como
  variable de path, no los resuelve con un valor.
- **Resumen** — `operation.summary`. Es el `name` de la petición en Postman.
- **Descripción** — `operation.description`, si la operación la declara; si
  no, cadena vacía. Es el `description` de la petición en Postman.
- **Cuerpo de ejemplo** — cuando la operación declara
  `requestBody.content.application/json.schema`, un objeto JSON que
  satisface ese schema: un valor por cada propiedad en `required`, del tipo
  declarado, y por cada propiedad con `example` o con el primer valor de
  `enum`, se usa ese valor tal cual. No inventes campos que el schema no
  declara. Si la operación no declara `requestBody`, la petición no lleva
  cuerpo.
- **Caso correcto y su código** — de `operation.responses`, el código que no
  empieza por `4` ni por `5` (un único código así por operación en esta
  especificación: `200`, `201` o `204`). Ese es el código que el test
  comprueba.

## Procedimiento

1. **Lee `openapi.json`.** Si no existe o `json.load` falla, dilo y para: no
   es trabajo de esta skill regenerarlo ni arreglarlo.

2. **Resuelve el espacio de trabajo del proyecto**, sin crear uno nuevo si ya
   existe:
   - Deriva el nombre del espacio de trabajo del repositorio: el nombre del
     directorio remoto (`git rev-parse --show-toplevel`, tomando el último
     segmento de la ruta) — en este repositorio, `curso-claude-code-api`.
   - Llama a `getWorkspaces` y busca, por coincidencia exacta de `name`, un
     espacio de trabajo con ese nombre.
   - Si existe, úsalo. Si no existe, créalo con `createWorkspace`
     (`type: "personal"`, salvo que el usuario ya tenga establecido en este
     repositorio un tipo distinto — en ese caso, pregunta antes de asumirlo).
   - No llames a `createWorkspace` si `getWorkspaces` ya devolvió una
     coincidencia exacta de nombre: ese es el requisito de "no crear uno
     nuevo cada vez que se invoque".

3. **Resuelve la colección del proyecto**, con el mismo criterio de
   no-duplicar:
   - Llama a `getCollections` con el `workspace` resuelto en el paso 2 y
     busca, por coincidencia exacta de `name`, una colección con el nombre
     del proyecto (el mismo nombre derivado en el paso 2, o el `info.title`
     de `openapi.json` si el usuario prefiere ese).
   - Si existe, tráela completa con `getCollection` (`model: "full"`) para
     conocer sus peticiones actuales: id, nombre, método, ruta.
   - Si no existe, créala con `createCollection` vacía (`item: []`) en ese
     `workspace`, con el `info.title` o el nombre derivado como `name`.

4. **Recorre cada operación de `openapi.json`** (cada combinación de ruta y
   método en `paths`) y, para cada una:
   - Arma el `name` (resumen), `description`, `method`, `url` y, si aplica,
     el cuerpo de ejemplo, como se describe en "De dónde sale cada dato".
   - Arma el test de código de estado (ver "El test de código de estado").
   - Si la colección traída en el paso 3 ya tiene una petición cuyo método y
     ruta coinciden con esta operación, actualízala con
     `updateCollectionRequest` — solo si algo cambió (nombre, descripción,
     cuerpo o el código que comprueba el test; si nada cambió, no llames a
     la herramienta). Si no existe, créala con `createCollectionRequest`.
   - Lleva la cuenta: cuántas peticiones se crearon y cuántas se
     actualizaron.

5. **Informa al usuario**, al terminar:
   - Si el espacio de trabajo se creó o ya existía, y su nombre.
   - Si la colección se creó o ya existía, y su nombre.
   - Cuántas peticiones se crearon y cuántas se actualizaron, sobre el total
     de operaciones de `openapi.json`.
   - Cualquier operación que se haya saltado y por qué (por ejemplo, un
     `requestBody` cuyo schema no se pudo traducir a un ejemplo).

## El test de código de estado

Postman no tiene un campo estructurado "código esperado": la comprobación se
declara como un script de test en JavaScript, adjunto a la petición vía
`events` con `listen: "test"`. Cada petición lleva exactamente un evento de
test con este contenido, sustituyendo `<CODIGO>` por el código del caso
correcto de esa operación:

```javascript
pm.test("responde <CODIGO>", () => {
  pm.response.to.have.status(<CODIGO>);
});
```

No agregues comprobaciones adicionales (esquema del cuerpo, cabeceras,
tiempo de respuesta): el pedido es verificar el código de estado del caso
correcto, no construir una suite de contrato completa dentro de Postman —
eso ya lo hacen los tests de `tests/` contra el código.

## Qué no hacer

- No copies en la petición códigos de error (`404`, `409`, `422`) como
  comprobación: el test verifica el caso correcto, no todos los casos que la
  especificación declara.
- No crees una petición por cada código de respuesta de una operación: una
  petición por operación, con un solo test dentro.
- No uses `putCollection` para reescribir la colección entera: esa
  herramienta reemplaza todo el contenido y no está en `allowed-tools` de
  esta skill. Cada petición se crea o actualiza individualmente con
  `createCollectionRequest` / `updateCollectionRequest`.
- No adivines un espacio de trabajo o una colección por similitud de nombre:
  la coincidencia para no duplicar es exacta. Si hay más de una coincidencia
  exacta (dos espacios de trabajo con el mismo nombre, por ejemplo), para y
  pregunta al usuario cuál usar en vez de elegir uno.
- No inventes un valor de ejemplo para una propiedad que el schema no
  restringe (sin `example`, sin `enum`, sin tipo simple deducible): usa un
  valor mínimo válido para el tipo (`""`, `0`, `false`, `[]`, `{}` según
  corresponda) en vez de inventar contenido con significado.
