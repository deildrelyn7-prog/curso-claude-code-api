#!/usr/bin/env bash
# Hook PostToolUse (matcher Edit|Write) para TaskFlow API.
#
# Se dispara justo despues de que una herramienta de edicion termina. Filtra
# por el archivo editado leyendo .tool_input.file_path del JSON que Claude
# Code entrega por stdin:
#
#   - app/main.py, app/models.py -> afectan el esquema OpenAPI que sirve la
#     app. Regenera openapi.json automaticamente (comando puro y
#     determinista, ver README.md).
#   - alembic/versions/*.py      -> afectan el esquema fisico de la base.
#     openapi.json no cambia por una migracion; en su lugar avisa que
#     docs/esquema.md puede haber quedado desactualizado y nombra la skill
#     que lo regenera (describir-esquema), porque esa regeneracion la hace un
#     modelo interpretando el codigo, no un comando de shell.
#
# Cualquier otro archivo editado no dispara nada.
#
# Salida: exit 0 siempre. Este hook informa; no bloquea la edicion.

set -u

RAIZ="${CLAUDE_PROJECT_DIR:-.}"
cd "$RAIZ" || exit 0

entrada="$(cat)"

archivo="$(
  printf '%s' "$entrada" | python3 -c '
import json, sys
try:
    print(json.load(sys.stdin).get("tool_input", {}).get("file_path", ""))
except Exception:
    print("")
'
)"

[ -n "$archivo" ] || exit 0

# Ruta relativa a la raiz del repo, para comparar contra los patrones.
relativa="${archivo#"$RAIZ"/}"

case "$relativa" in
  app/main.py|app/models.py)
    uv run python -c "import json; from app.main import app; json.dump(app.openapi(), open('openapi.json', 'w'), indent=2, ensure_ascii=False, sort_keys=True)" 2>/dev/null \
      && echo "openapi.json regenerado tras editar $relativa." \
      || echo "Aviso: no se pudo regenerar openapi.json tras editar $relativa (revisar manualmente)." >&2
    ;;
esac

case "$relativa" in
  app/main.py|app/models.py|alembic/versions/*.py)
    echo "docs/esquema.md puede haber quedado desactualizado tras editar $relativa. Para regenerarlo, invoca la skill describir-esquema."
    ;;
esac

exit 0
