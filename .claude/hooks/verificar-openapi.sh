#!/usr/bin/env bash
# Hook PreToolUse (matcher Bash) para TaskFlow API.
#
# Bloquea un `git commit` cuando openapi.json en la raiz del repositorio no
# coincide con la especificacion que genera el codigo ahora mismo. Cualquier
# otro comando pasa sin tocar nada.
#
# Distingue el commit del resto leyendo .tool_input.command del JSON que
# Claude Code entrega por stdin y comprobando que el primer token sea "git" y
# el primer subcomando (saltando flags globales como `git -c ... commit`) sea
# "commit".
#
# Salida:
#   exit 0            -> deja pasar el comando
#   exit 2 + stderr   -> bloquea; stderr se muestra a Claude como el motivo
#
# Si la comprobacion tarda mas que el timeout del hook, Claude Code corta el
# proceso y el commit NO se bloquea (fail-open por diseno: preferimos que
# falle a que deje esperando).

set -u

RAIZ="${CLAUDE_PROJECT_DIR:-.}"
REGEN='uv run python -c "import json; from app.main import app; json.dump(app.openapi(), open('"'"'openapi.json'"'"', '"'"'w'"'"'), indent=2, ensure_ascii=False, sort_keys=True)"'

entrada="$(cat)"

# ¿El comando es un `git commit`? Sale con codigo 0 si lo es.
es_commit="$(
  printf '%s' "$entrada" | python3 -c '
import json, shlex, sys
try:
    cmd = json.load(sys.stdin).get("tool_input", {}).get("command", "")
    toks = shlex.split(cmd)
except Exception:
    print("no"); sys.exit(0)
if not toks or toks[0] != "git":
    print("no"); sys.exit(0)
i, n = 1, len(toks)
dos_args = {"-c", "-C", "--git-dir", "--work-tree", "--namespace", "--exec-path"}
while i < n:
    t = toks[i]
    if t in dos_args:
        i += 2; continue
    if t.startswith("-"):
        i += 1; continue
    print("si" if t == "commit" else "no"); sys.exit(0)
print("no")
'
)"

[ "$es_commit" = "si" ] || exit 0

cd "$RAIZ" || exit 0
[ -f openapi.json ] || exit 0

generado="$(uv run python -c "import json,sys; from app.main import app; json.dump(app.openapi(), sys.stdout, indent=2, ensure_ascii=False, sort_keys=True)" 2>/dev/null)"

# No se pudo generar (import roto, uv no disponible). No es trabajo de este
# hook diagnosticarlo; deja pasar el commit.
[ -n "$generado" ] || exit 0

[ "$generado" = "$(cat openapi.json)" ] && exit 0

cat >&2 <<EOF
Commit bloqueado: openapi.json no coincide con la especificacion que genera el codigo.

Para desbloquear, regenera la copia versionada desde la raiz del repositorio y
anade el archivo al commit:

  $REGEN
  git add openapi.json

Despues repite el commit. Si el cambio de codigo NO debia tocar la
especificacion, revisa que no hayas modificado rutas, modelos ni docstrings de
endpoints.
EOF
exit 2
