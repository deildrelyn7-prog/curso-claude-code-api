# Reglas de estilo de código

## Repartir cambios existentes no reescribe código

Ninguna automatización de este proyecto que reparta o reorganice cambios ya
existentes en el árbol de trabajo —segmentar un diff en varios commits,
reordenar commits, mover un cambio de un commit a otro— reescribe código para
simular un estado intermedio.

El reparto se hace **exclusivamente** con `git add` sobre el cambio que ya
existe en el árbol:

- `git add <archivo>` cuando el archivo entero va en ese commit, o
- `git add -p` cuando hay que separar fragmentos de un mismo archivo que
  pertenecen a intenciones distintas,

seguido de `git commit`. No se edita un archivo, no se revierte a un estado
previo, no se reconstruye a mano el contenido que tendría en un punto
intermedio de la historia. Al terminar, el árbol de trabajo es idéntico byte a
byte a como estaba antes de repartir; lo único que cambia es cómo quedó
distribuido el cambio entre commits.

Si el reparto deseado exige un cambio de código que no está hecho en el árbol
(un test que falta, un ajuste para que un commit intermedio compile), eso se
dice y se para: no es trabajo de la automatización de reparto.
