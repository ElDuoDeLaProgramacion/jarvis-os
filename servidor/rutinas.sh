#!/usr/bin/env bash
# Deja en el cron del servidor la actualización desde GitHub (scripts/actualizar.sh) y la ronda de la
# billetera simulada (scripts/billetera.py), que no hace nada hasta que David la inicia.
# Las rutinas de horario (resumen, plan, cierre...) se quitaron: JARVIS ya no habla sin que le pidan.
# Solo toca el bloque de JARVIS del crontab, así que también borra las rutinas viejas que quedaran.
set -euo pipefail
cd "$(dirname "$0")/.."
repo=$(printf '%q' "$(pwd)")
bloque="# JARVIS rutinas (servidor/rutinas.sh)
# Cada 15 minutos trae lo nuevo de GitHub (scripts/actualizar.sh), así no hace falta git pull.
*/15 * * * * cd $repo && ./scripts/actualizar.sh
# Billetera de Orión: una ronda cada 2 horas (máximo 3 operaciones al día). Sin experimento iniciado (o en pausa) no hace nada.
7 */2 * * * cd $repo && mkdir -p logs && python3 scripts/billetera.py ronda >> logs/billetera.log 2>&1
# Vigilante sin IAs: si una moneda se movió 5 % desde la última ronda, convoca una de emergencia.
22,52 * * * * cd $repo && mkdir -p logs && python3 scripts/billetera.py vigilar >> logs/billetera.log 2>&1
# fin JARVIS rutinas"
{ { crontab -l 2>/dev/null || true; } | sed '/^# JARVIS rutinas/,/^# fin JARVIS rutinas/d'; echo "$bloque"; } | crontab -
echo "$bloque"
