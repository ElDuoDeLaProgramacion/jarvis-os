#!/usr/bin/env bash
# Lo que ejecuta el Programador de tareas de Windows a cada hora del "día real":
# encola la intención como rutina y arranca el corredor.
#   ./scripts/rutina.sh "plan de hoy"
set -euo pipefail

cd "$(dirname "$0")/.."
JARVIS_ORIGEN=rutina ./scripts/encolar.sh "$@" > /dev/null
./scripts/corredor.sh
