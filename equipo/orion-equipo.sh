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

# ~/.env: cómo autenticar el motor + JARVIS_OBJETIVOS_SEGURIDAD.
if [ -f "$HOME/.env" ]; then set -a; . "$HOME/.env"; set +a; fi
# El motor acepta cualquiera de las formas de Claude Code, no solo la API key de Anthropic (ver equipo/MOTOR.md):
#   ANTHROPIC_API_KEY · CLAUDE_CODE_OAUTH_TOKEN (suscripción) · ANTHROPIC_BASE_URL+ANTHROPIC_AUTH_TOKEN (pasarela)
#   · CLAUDE_CODE_USE_BEDROCK / CLAUDE_CODE_USE_VERTEX · o una sesión ya iniciada (~/.claude/.credentials.json).
if [ -z "${ANTHROPIC_API_KEY:-}${CLAUDE_CODE_OAUTH_TOKEN:-}${ANTHROPIC_AUTH_TOKEN:-}${CLAUDE_CODE_USE_BEDROCK:-}${CLAUDE_CODE_USE_VERTEX:-}" ] \
   && [ ! -f "$HOME/.claude/.credentials.json" ]; then
  echo "Falta configurar el motor (ver equipo/MOTOR.md): una API key, un token de suscripción o una pasarela." >&2
  exit 1
fi
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

# No abortamos si claude falla: queremos ver su error, no quedarnos en silencio.
cerr=$(mktemp 2>/dev/null) || cerr="logs/.err.$$"
set +e
salida=$(claude "${opciones[@]}" 2>"$cerr" </dev/null)
codigo=$?
set -e
errc=$(cat "$cerr" 2>/dev/null); rm -f "$cerr" 2>/dev/null || true

id_sesion=""; es_error="0"; respuesta=""
if datos=$(printf '%s' "$salida" | python3 -c 'import json, sys
d = json.load(sys.stdin)
print(d.get("session_id") or "")
print("1" if d.get("is_error") else "0")
print(d.get("result") or "")' 2>/dev/null); then
  id_sesion=$(printf '%s\n' "$datos" | sed -n 1p)
  es_error=$(printf '%s\n' "$datos" | sed -n 2p)
  respuesta=$(printf '%s\n' "$datos" | sed -n '3,$p')
else
  respuesta="$salida"
fi

# ¿Hubo respuesta de verdad?
if [ "$codigo" -eq 0 ] && [ "$es_error" != "1" ] && [ -n "${respuesta//[[:space:]]/}" ]; then
  [ -n "$id_sesion" ] && echo "SESION=$id_sesion" >&2
  echo "$(date -Iseconds) < $respuesta" >> logs/orion.log
  echo "$respuesta"
  exit 0
fi

# Falló: saca a la luz el motivo real (el "result" de claude, o su stderr), no un "sin detalle".
if [ -n "${respuesta//[[:space:]]/}" ]; then
  motivo="$respuesta"
else
  motivo=$(printf '%s' "$errc" | grep -viE '^[[:space:]]*$' | tail -n 2 | tr '\n' ' ')
fi
[ -n "$motivo" ] || motivo="el motor no respondió (código $codigo); revisa: sudo journalctl -u orion-equipo-gw -n 30"
echo "$(date -Iseconds) ! $motivo" >> logs/orion.log
echo "$motivo" >&2
exit 1
