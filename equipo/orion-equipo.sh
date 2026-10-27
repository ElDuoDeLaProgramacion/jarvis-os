#!/usr/bin/env bash
# Orión Equipo: el Orión que usan los amigos de ciberseguridad (equipo/README.md).
# Lo llama equipo/servidor.py, uno a la vez:
#   equipo/orion-equipo.sh [--reanudar ID] -- "Ana: ¿qué es un header HSTS?"
# Imprime la respuesta y "SESION=<id>" por stderr para seguir la conversación.
#
# Corre como el usuario "equipo", dentro de ~/espacio (su propia bóveda, CLAUDE.md y habilidades).
# No ve el repo de David ni su bóveda, y no tiene correo, agenda, WhatsApp, Spotify ni billetera:
# esas herramientas ni existen aquí.
set -euo pipefail

CODIGO="$(cd "$(dirname "$0")/.." && pwd)"
ESPACIO="${ORION_EQUIPO_ESPACIO:-$HOME/espacio}"
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"

reanudar=""
while [ $# -gt 0 ]; do
  case "$1" in
    --reanudar) reanudar="$2"; shift 2 ;;
    --) shift; break ;;
    *) break ;;
  esac
done
[ $# -gt 0 ] || { echo "Uso: $0 [--reanudar ID] -- \"petición\"" >&2; exit 1; }
pedido="$*"

# ~/.env: ANTHROPIC_API_KEY (clave propia del equipo, con tope de gasto) y JARVIS_OBJETIVOS_SEGURIDAD.
if [ -f "$HOME/.env" ]; then set -a; . "$HOME/.env"; set +a; fi
[ -n "${ANTHROPIC_API_KEY:-}" ] || { echo "Falta ANTHROPIC_API_KEY en $HOME/.env" >&2; exit 1; }
# Los conectores de claude.ai (Gmail, Calendar, Drive, Spotify...) son de una cuenta: aquí no se cargan.
export ENABLE_CLAUDEAI_MCP_SERVERS=false
# scripts/seguridad.sh: ni "local" ni localhost, solo la lista de objetivos del equipo.
export JARVIS_SEGURIDAD_SIN_LOCAL=1

cd "$ESPACIO"
mkdir -p logs
echo "$(date -Iseconds) > $pedido" >> logs/orion.log

# Leer y escribir dentro del espacio, buscar en la web, el QA de solo lectura y el harness de pentest.
# Las pruebas activas del harness esperan la autorización de David (equipo/pentest.sh); el QA pasivo
# corre ya. En modo -p lo que no está en esta lista se niega solo.
seg="$CODIGO/scripts/seguridad.sh"
pen="$CODIGO/equipo/pentest.sh"
permitidas=(
  Skill "Read(./**)" Glob Grep "Write(./boveda/**)" "Edit(./boveda/**)"
  WebSearch WebFetch
  "Bash($seg web:*)" "Bash($seg puertos:*)" "Bash($seg objetivos)"
  # Código de los proyectos: David lo copia en ~/espacio/proyectos (seguridad.sh trabaja desde otra carpeta,
  # por eso la ruta va completa).
  "Bash($seg dependencias $ESPACIO/proyectos/:*)" "Bash($seg codigo $ESPACIO/proyectos/:*)"
  # Harness de pentest: el propio script pone los dos candados (objetivo de David + autorización).
  "Bash($pen:*)"
)
opciones=(-p "$pedido" --output-format json
  --allowedTools "$(IFS=,; echo "${permitidas[*]}")"
  --disallowedTools "Task,Agent,NotebookEdit"
  --strict-mcp-config --mcp-config '{"mcpServers":{}}'
  --setting-sources project
  --model "${ORION_EQUIPO_MODELO:-sonnet}")
[ -n "$reanudar" ] && opciones+=(--resume "$reanudar")

salida=$(claude "${opciones[@]}" </dev/null)
if datos=$(printf '%s' "$salida" | python3 -c 'import json, sys
d = json.load(sys.stdin)
print(d.get("session_id") or "")
print(d.get("result") or "")' 2>/dev/null); then
  id_sesion=$(printf '%s\n' "$datos" | head -n 1)
  respuesta=$(printf '%s\n' "$datos" | tail -n +2)
else
  id_sesion=""; respuesta="$salida"
fi
[ -n "$id_sesion" ] && echo "SESION=$id_sesion" >&2
echo "$(date -Iseconds) < $respuesta" >> logs/orion.log
echo "$respuesta"
