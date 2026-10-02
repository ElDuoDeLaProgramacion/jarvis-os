#!/usr/bin/env bash
# Punto de entrada por texto: ./scripts/jarvis.sh "plan de hoy"
# El corredor de la cola (scripts/corredor.sh) y la voz (voz/jarvis_voz.py) llaman a este mismo script.
set -euo pipefail

cd "$(dirname "$0")/.."

# La voz y las rutinas llaman a este script sin cargar ~/.bashrc, así que aseguramos dónde está claude.
export PATH="$HOME/.local/bin:$PATH"

if [ $# -eq 0 ]; then
  echo "Uso: $0 \"tu petición\"" >&2
  exit 1
fi

pedido="$*"
mkdir -p logs
echo "$(date -Iseconds) > $pedido" >> logs/jarvis.log

# Claves locales (por ejemplo YOUTUBE_API_KEY) para scripts como canales.py.
if [ -f .env ]; then set -a; . ./.env; set +a; fi

# Herramientas que JARVIS puede usar sin preguntar. Las de Gmail y Calendar son solo de
# lectura y borradores: enviar, reenviar, borrar o crear eventos queda fuera a propósito.
permitidas=(
  Read Write Edit Glob Grep WebSearch WebFetch
  "Bash(date:*)" "Bash(mkdir:*)" "Bash(ls:*)" "Bash(mv:*)"
  "Bash(git status:*)" "Bash(git diff:*)" "Bash(git log:*)" "Bash(git checkout -b:*)"
  "Bash(git add:*)" "Bash(git commit:*)" "Bash(npm test:*)" "Bash(python3:*)" "Bash(pdftotext:*)"
)
# Conectores de claude.ai: "claude.ai Gmail" → mcp__claude_ai_Gmail (se listan ambas grafías por si acaso).
# Fuera a propósito: send_message, reply, forward, trash_*, *_spam, *label* y delete_draft (Gmail);
# create_event, update_event, delete_event y respond_to_event (Calendar).
for servidor in claude_ai_Gmail claude.ai_Gmail; do
  for h in search_threads get_thread get_message list_labels list_drafts get_draft create_draft update_draft; do
    permitidas+=("mcp__${servidor}__$h")
  done
done
for servidor in claude_ai_Google_Calendar claude.ai_Google_Calendar; do
  for h in list_calendars list_events get_event search_events suggest_time; do
    permitidas+=("mcp__${servidor}__$h")
  done
done

respuesta=$(claude -p "$pedido" --allowedTools "$(IFS=,; echo "${permitidas[*]}")")

echo "$(date -Iseconds) < $respuesta" >> logs/jarvis.log
echo "$respuesta"
