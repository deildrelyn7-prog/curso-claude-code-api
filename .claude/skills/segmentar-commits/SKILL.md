---
name: segmentar-commits
description: >-
  Reparte los cambios sin commitear del árbol de trabajo en una secuencia de
  commits con una sola intención cada uno, en un orden donde cada commit deja
  el repositorio comprobable. Úsala cuando haya trabajo hecho y sin repartir y
  quieras un historial legible. Propone el reparto y espera aprobación antes
  de confirmar.
---

# segmentar-commits

Toma lo que hay sin commitear en el árbol de trabajo y propone cómo partirlo en
commits: qué archivos —o qué partes de un archivo— van en cada uno, en qué
orden, y con qué mensaje. No confirma nada hasta que el usuario aprueba el
reparto.

## Límite de la skill

- No hace `git commit`, `git push`, `git reset`, `git rebase` ni `git stash`
  hasta tener aprobación explícita del reparto propuesto.
- No escribe ni modifica código, tests ni documentación para "arreglar" un
  commit intermedio. Si el reparto exige un cambio de código que no está hecho,
  eso se dice y se para: no es trabajo de esta skill.
- No crea ni borra ramas.
- Antes de la aprobación solo usa comandos de lectura: `git status`,
  `git diff`, `git log`, `git show`, leer archivos.

## Procedimiento

1. **Parte del estado real del repositorio.** No supongas qué hay cambiado.
   Inyecta y lee:
   - `git status --short` — la lista de archivos modificados, nuevos y
     eliminados, con su estado de staging.
   - `git diff --stat` y `git diff --stat --staged` — el resumen por archivo:
     cuántas líneas cambian en cada uno, sin el contenido del diff.
   Con eso tienes el **mapa** del cambio: qué archivos entran en juego y cuánto
   se movió cada uno. No inyectes el diff completo (ver "Por qué el resumen y
   no el diff completo").
   Si necesitas ver el contenido de un archivo concreto para decidir en qué
   commit va o si hay que partirlo, léelo entonces, ese archivo, no todos.

2. **Agrupa por intención, no por archivo ni por tipo de archivo.** Un commit
   = una sola cosa que el repositorio gana o pierde. Un mismo archivo puede
   repartirse entre varios commits (staging por partes con `git add -p`) si
   contiene cambios de intenciones distintas. Varios archivos van juntos si
   sirven a la misma intención (por ejemplo, un modelo y su migración; un
   endpoint y su prueba, si el proyecto los trata como una unidad).

3. **Ordena para que cada commit deje el repositorio comprobable.** "Comprobable"
   quiere decir: después de aplicar ese commit y los anteriores, hay una
   comprobación concreta que pasa —la suite en verde, un endpoint que responde,
   una migración que corre en ambos sentidos—. Un commit que sólo tiene sentido
   junto al siguiente está mal cortado: fúndelos o mueve la frontera.
   - Lo que otro cambio necesita va antes que ese cambio (un modelo antes del
     endpoint que lo usa; una dependencia antes del código que la importa).
   - Si ningún orden deja todos los commits en verde porque el trabajo se hizo
     entrelazado, dilo: propón el orden menos malo y nombra qué commit queda
     temporalmente rojo y por qué.

4. **Elige el prefijo de Conventional Commits por lo que hace el commit, no por
   la extensión de los archivos.** Un commit que sólo mueve documentación es
   `docs:` aunque toque un `.py` de ejemplo; un commit que añade
   comportamiento observable es `feat:` aunque el grueso del diff esté en
   tests; un commit que sólo añade o cambia pruebas sin cambiar
   comportamiento es `test:`. Prefijos habituales: `feat`, `fix`, `refactor`,
   `test`, `docs`, `chore`, `build`, `ci`. Si un commit hace dos cosas y no
   sabes qué prefijo ponerle, está mal cortado.

5. **Redacta cada mensaje.** Encabezado en imperativo, una línea, con su
   prefijo. Cuerpo en prosa que diga qué cambia y por qué, no un listado de
   archivos. Si el repositorio tiene una convención de pie de commit
   (co-autoría, enlace de sesión, referencia a ticket), aplícala.

6. **Enseña el reparto y espera aprobación.** Presenta, en orden:
   - Para cada commit: número, encabezado propuesto, lista de archivos (y si
     alguno va parcial, qué parte), y la comprobación que queda verde tras él.
   - Cualquier archivo que quede sin asignar y por qué.
   - Cualquier commit que quede temporalmente rojo y por qué.
   No ejecutes ningún `git add` ni `git commit` hasta que el usuario apruebe.
   Si el usuario pide ajustes, rehaz la propuesta entera y vuelve a enseñarla.

7. **Al confirmar, sigue el reparto aprobado al pie de la letra.** Si al
   ejecutar aparece algo que el mapa no anticipaba (un archivo que hay que
   partir más fino, un conflicto de orden), para y vuelve al paso 6 con la
   propuesta corregida.

## Qué no hacer

- No inyectes `git diff` sin `--stat`: es el contenido, no el mapa, y es lo
  que encarece la invocación sin cambiar la decisión de reparto.
- No propongas un commit "varios" ni "ajustes varios": si no tiene una sola
  intención nombrable, está mal cortado.
- No elijas el prefijo por dónde cayó el diff. `feat:` con casi todo el cambio
  en `tests/` es correcto si lo que el commit aporta es comportamiento nuevo.
- No confirmes nada sin aprobación, ni siquiera el primer commit "que es
  obvio".
- No modifiques el trabajo para que un commit intermedio quede verde. Eso es
  cambiar el código, no segmentarlo.
