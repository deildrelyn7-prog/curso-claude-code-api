---
name: actualizar-memorias
description: >-
  Revisa la conversación actual y vuelca en el sistema de memoria persistente
  (MEMORY.md + archivos por tema) lo que se aprendió: decisiones tomadas,
  correcciones o confirmaciones del usuario sobre el método de trabajo, y
  estado nuevo del proyecto. Además detecta si algo aprendido debería
  reflejarse en CLAUDE.md (documentación vinculante del repo) y lo propone al
  final, sin editarlo sin aprobación. Úsala cuando el usuario pida actualizar
  memoria, contexto o "lo que aprendimos", o al cerrar un hito (PR mergeado,
  incremento cerrado) que cambia el estado del repositorio.
---

# actualizar-memorias

Revisa la sesión en curso y actualiza el sistema de memoria persistente del
usuario (el directorio de memoria de auto-memory: `MEMORY.md` como índice más
un archivo por tema) para que quede al día con lo aprendido, sin duplicar lo
que ya estaba y sin inventar nada que no haya pasado en la conversación.
Además revisa si algo de lo aprendido debería quedar escrito en `CLAUDE.md`
del repositorio, y si es así lo propone —nunca lo edita sin que el usuario
apruebe primero.

## Límite de la skill

- Escribe **sin pedir aprobación** solo en el directorio de memoria del
  proyecto (los archivos `.md` con frontmatter `type:
  user|feedback|project|reference` y su índice `MEMORY.md`). No es este mismo
  repositorio: vive fuera del árbol de trabajo, en la carpeta de memoria
  asociada a esta ruta de proyecto.
- `CLAUDE.md` es código versionado del repositorio, no memoria de sesión:
  la skill nunca lo edita directamente. Como mucho, al final del pase,
  **propone** una edición concreta y espera aprobación explícita antes de
  tocarlo — igual que cualquier cambio al repositorio en este proyecto.
- No toca `.claude/rules/`, `docs/contrato-api.md` ni
  `docs/decisiones-ingenieria.md` bajo ningún concepto, ni siquiera como
  propuesta: son fuentes de verdad con su propio proceso de cambio (commit
  aparte, a veces ticket explícito) que excede el alcance de esta skill.
- No modifica código, tests, ni hace commits ni ninguna operación de `git`.
  Si el usuario aprueba la propuesta de `CLAUDE.md`, la skill edita el
  archivo pero no lo commitea: el commit de ese cambio sigue las reglas
  normales del repositorio (mensaje mostrado antes de confirmar).
- No guarda información derivable del código o del historial de git (rutas,
  arquitectura, quién cambió qué): eso se lee con `git log`/`git blame` o
  leyendo el archivo, no se congela en memoria.
- No guarda estado efímero de la tarea en curso (un archivo a medio editar,
  un comando que falló y se reintentó): la memoria es para lo que sigue
  siendo cierto o relevante en la próxima sesión.

## Procedimiento

1. **Localiza el directorio de memoria.** Es la carpeta de memoria de
   auto-memory correspondiente a este directorio de trabajo (contiene
   `MEMORY.md` y los archivos de memoria existentes). Si no la tienes ya
   presente en contexto, lístala.

2. **Lee `MEMORY.md` completo** para saber qué memorias existen y de qué
   trata cada una, y decide cuáles tocan por el tema de esta sesión. No leas
   a ciegas todos los archivos de memoria si `MEMORY.md` ya deja claro cuáles
   son irrelevantes para lo que pasó en esta conversación.

3. **Lee el contenido completo de cada memoria candidata a tocar** antes de
   editarla. Nunca escribas una memoria nueva sobre un tema que ya tiene
   archivo sin haber leído el archivo existente primero: el resultado sería
   una duplicación o una contradicción silenciosa.

4. **Repasa la conversación actual y clasifica lo aprendido** en las cuatro
   categorías de memoria, sin forzar nada que no encaje:
   - **`user`** — algo nuevo sobre el rol, las preferencias o el conocimiento
     del usuario.
   - **`feedback`** — una corrección explícita del usuario sobre cómo
     trabajar ("no hagas X", "para de Y") o una confirmación de que un
     enfoque no obvio funcionó ("sí, así está bien", aceptar sin objeción una
     elección poco convencional). Ambas direcciones cuentan: guardar solo
     correcciones sesga hacia la cautela y pierde enfoques ya validados.
   - **`project`** — hechos nuevos sobre el estado del repositorio: qué se
     integró a `main`, qué PR se abrió o cerró, qué quedó pendiente y por
     qué, decisiones de alcance. Toda fecha relativa ("el jueves", "ayer") se
     convierte a fecha absoluta antes de guardar.
   - **`reference`** — un puntero nuevo a un sistema externo (un tablero, un
     proyecto de issues, un canal) mencionado en la sesión.
   Si nada de la conversación aporta algo nuevo en una categoría, no se
   fuerza una entrada — no todas las actualizaciones tocan las cuatro.

5. **Para cada hallazgo, decide entre editar y crear:**
   - Si ya existe una memoria sobre el tema y sigue vigente en lo esencial:
     **edítala** con `Edit` — agrega el hecho nuevo, corrige lo que quedó
     obsoleto (una regla que se movió de archivo, un estado que cambió), y
     actualiza `modified` en el frontmatter. No dupliques contenido que ya
     está bien dicho en el archivo.
   - Si el tema es nuevo y no cabe razonablemente en ninguna memoria
     existente: **créala** con `Write`, con frontmatter completo
     (`name`, `description`, `metadata.type`) y cuerpo siguiendo la
     estructura del tipo (`feedback`/`project` llevan **Why:** y
     **How to apply:**; `user` y `reference` van directo al contenido).
   - Si una memoria existente quedó falsa o contradicha por lo que pasó en
     la sesión (no solo incompleta), corrígela en el lugar; no dejes las dos
     versiones conviviendo en archivos distintos.

6. **Enlaza con `[[nombre]]`** hacia memorias relacionadas, existan ya o se
   estén creando en este mismo pase. Un enlace a un nombre que todavía no
   tiene archivo es válido: marca algo pendiente de documentar, no es un
   error.

7. **Actualiza `MEMORY.md`** para que cada memoria tocada o creada tenga su
   línea (`- [Título](archivo.md) — gancho de una frase, menos de ~150
   caracteres`). `MEMORY.md` es índice puro: si un hallazgo no amerita
   archivo propio porque ya vive dentro de una memoria existente, no le
   sumes una línea aparte.

8. **Evalúa si algo aprendido pertenece a `CLAUDE.md`.** Léelo. Solo cuenta
   como candidato lo que es:
   - **Vigente para cualquier sesión futura**, no un detalle de esta tarea
     puntual (un comando canónico nuevo, un documento de verdad que se
     agregó, un flujo de rama que cambió, un requisito de estilo que aplica
     siempre) — no un hecho de estado que ya vive en memoria `project`
     (ese es el trabajo de los pasos 4-7, no de este paso).
   - **No derivable de leer el código o `.claude/rules/`** — si ya se puede
     inferir del repositorio, no hace falta escribirlo.
   Si no hay ningún candidato, dilo explícitamente en el resumen ("nada para
   `CLAUDE.md` esta vez") y sigue al paso 9 sin más.
   Si hay uno o más candidatos, para cada uno redacta la edición exacta
   (qué sección de `CLAUDE.md` cambia, texto propuesto) y preséntala al
   usuario junto con el resumen del paso 9, dejando claro que es una
   propuesta que espera aprobación — no la apliques todavía.

9. **Cierra con un resumen breve** de qué archivos de memoria se crearon,
   cuáles se editaron y qué aprendizaje concreto capturó cada uno, seguido de
   la propuesta de `CLAUDE.md` del paso 8 si la hay. No repitas el contenido
   completo de las memorias: el resumen es para que el usuario confirme que
   se entendió bien lo ocurrido, no un segundo lugar donde leer la memoria
   entera.

10. **Si el usuario aprueba la propuesta de `CLAUDE.md`**, aplícala con
    `Edit` tal cual se presentó (o con los ajustes que el usuario pida) y
    dilo. Si no responde o la rechaza, no se toca `CLAUDE.md`; la sesión
    sigue con la memoria ya actualizada de los pasos anteriores, que no
    depende de esta aprobación.

## Qué no hacer

- No copies fragmentos largos de la conversación o del diff dentro de una
  memoria: se resume el aprendizaje, no se transcribe la sesión.
- No crees una memoria nueva para algo que ya está cubierto, aunque con otras
  palabras, por una memoria existente — se edita esa.
- No edites `CLAUDE.md` sin aprobación previa explícita, ni siquiera cuando
  el candidato parezca obvio: siempre se presenta como propuesta primero.
- No toques `.claude/rules/` ni ningún otro archivo del árbol de trabajo del
  repositorio, ni siquiera como propuesta: fuera del alcance de esta skill
  por completo.
- No inventes candidatos para `CLAUDE.md` para tener algo que mostrar: si la
  sesión no dejó nada vigente y no derivable del código, se dice que no hay
  propuesta.
- No guardes una corrección o confirmación sin su razón: una memoria de tipo
  `feedback` o `project` sin **Why:** no le sirve a una sesión futura para
  juzgar un caso límite.
- No dejes fechas relativas ("ayer", "la semana pasada") en el cuerpo de una
  memoria: se resuelven a fecha absoluta antes de guardar.
- No pidas confirmación antes de escribir; si algo es ambiguo entre dos
  memorias existentes, usa el juicio propio y dilo en el resumen final en vez
  de detener el trabajo.
