#!/usr/bin/env bash
# Punto de entrada por texto: ./scripts/jarvis.sh "plan de hoy"
# La capa de voz (fase 4) llamará a este mismo script con el texto transcrito.
set -euo pipefail

cd "$(dirname "$0")/.."

if [ $# -eq 0 ]; then
  echo "Uso: $0 \"tu petición\"" >&2
  exit 1
fi

pedido="$*"
mkdir -p logs
echo "$(date -Iseconds) > $pedido" >> logs/jarvis.log

respuesta=$(claude -p "$pedido" \
  --allowedTools "Read,Write,Edit,Glob,Grep,WebSearch,WebFetch,Bash(date:*),Bash(mkdir:*),Bash(ls:*),Bash(mv:*),Bash(git status:*),Bash(git diff:*),Bash(git log:*),Bash(git checkout -b:*),Bash(git add:*),Bash(git commit:*),Bash(npm test:*),Bash(python3:*),Bash(pdftotext:*)")

echo "$(date -Iseconds) < $respuesta" >> logs/jarvis.log
echo "$respuesta"
