#!/usr/bin/env bash
# Pasa rutinas/rutinas.csv al cron del servidor (lo mismo que instalar-rutinas.ps1 hace en Windows).
# Vuelve a ejecutarlo si cambias rutinas.csv. Solo toca el bloque de JARVIS del crontab.
set -euo pipefail
cd "$(dirname "$0")/.."
bloque=$(python3 - "$(pwd)" <<'PY'
import csv, shlex, sys
repo = sys.argv[1]
print("# JARVIS rutinas (servidor/rutinas.sh)")
with open("rutinas/rutinas.csv", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        hora, minuto = r["hora"].strip().split(":")
        pedido = shlex.quote(r["pedido"].strip()).replace("%", r"\%")
        print(f"{int(minuto)} {int(hora)} * * * cd {shlex.quote(repo)} && ./scripts/rutina.sh {pedido} >> logs/rutinas.log 2>&1")
# Cada 15 minutos trae lo nuevo de GitHub (scripts/actualizar.sh), así no hace falta git pull.
print(f"*/15 * * * * cd {shlex.quote(repo)} && ./scripts/actualizar.sh")
print("# fin JARVIS rutinas")
PY
)
{ { crontab -l 2>/dev/null || true; } | sed '/^# JARVIS rutinas/,/^# fin JARVIS rutinas/d'; echo "$bloque"; } | crontab -
echo "$bloque"
