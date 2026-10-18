#!/usr/bin/env bash
# Deja en el cron del servidor solo la actualización desde GitHub (scripts/actualizar.sh).
# Las rutinas de horario (resumen, plan, cierre...) se quitaron: JARVIS ya no habla sin que le pidan.
# Solo toca el bloque de JARVIS del crontab, así que también borra las rutinas viejas que quedaran.
set -euo pipefail
cd "$(dirname "$0")/.."
repo=$(printf '%q' "$(pwd)")
bloque="# JARVIS rutinas (servidor/rutinas.sh)
# Cada 15 minutos trae lo nuevo de GitHub (scripts/actualizar.sh), así no hace falta git pull.
*/15 * * * * cd $repo && ./scripts/actualizar.sh
# fin JARVIS rutinas"
{ { crontab -l 2>/dev/null || true; } | sed '/^# JARVIS rutinas/,/^# fin JARVIS rutinas/d'; echo "$bloque"; } | crontab -
echo "$bloque"
