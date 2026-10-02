#!/usr/bin/env bash
# Deja una intención en la cola para que el corredor la ejecute.
#   ./scripts/encolar.sh "plan de hoy"                 (origen: manual)
#   JARVIS_ORIGEN=rutina ./scripts/encolar.sh "..."    (origen: rutina)
# Imprime la ruta del archivo creado.
set -euo pipefail

cd "$(dirname "$0")/.."

if [ $# -eq 0 ]; then
  echo "Uso: $0 \"tu petición\"" >&2
  exit 1
fi

pedido="$*"
origen="${JARVIS_ORIGEN:-manual}"
mkdir -p cola/pendientes

# El nombre empieza con la marca de tiempo para que el corredor respete el orden de llegada.
marca=$(date +%Y%m%d-%H%M%S)-$$
archivo="cola/pendientes/$marca.md"

cat > "$archivo" <<FIN
---
pedido: "$(printf '%s' "$pedido" | sed 's/"/\\"/g')"
origen: $origen
creado: $(date -Iseconds)
---
FIN

echo "$archivo"
