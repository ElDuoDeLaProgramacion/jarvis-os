#!/usr/bin/env bash
# Punto de entrada por texto: ./scripts/jarvis.sh "plan de hoy"
# El corredor de la cola (scripts/corredor.sh) y la voz (voz/jarvis_voz.py) llaman a este mismo script.
set -euo pipefail

cd "$(dirname "$0")/.."

# La voz y las rutinas llaman a este script sin cargar ~/.bashrc, así que aseguramos dónde está claude.
export PATH="$HOME/.local/bin:$PATH"

# Opciones de la voz (van antes de la petición):
#   --reanudar ID   sigue la conversación ID (respuestas a una pregunta de JARVIS)
#   --sesion        imprime "SESION=<id>" por stderr para poder reanudar después
#   --confirmado    David acaba de contestar "sí" en voz alta a un "¿lo envío?": se permite
#                   enviar ese correo. Solo vale junto con --reanudar y solo la pone la voz.
#   --voz           pedido hablado: usa el modelo rápido (JARVIS_MODELO_VOZ en .env, por defecto sonnet)
reanudar=""; sesion=0; confirmado=0; voz=0
while [ $# -gt 0 ]; do
  case "$1" in
    --reanudar) reanudar="$2"; shift 2 ;;
    --sesion) sesion=1; shift ;;
    --confirmado) confirmado=1; shift ;;
    --voz) voz=1; shift ;;
    --) shift; break ;;
    *) break ;;
  esac
done

if [ $# -eq 0 ]; then
  echo "Uso: $0 [--reanudar ID] [--sesion] [--confirmado] [--voz] \"tu petición\"" >&2
  exit 1
fi

pedido="$*"
mkdir -p logs
echo "$(date -Iseconds) > $pedido" >> logs/jarvis.log

# Claves locales (por ejemplo YOUTUBE_API_KEY) para scripts como canales.py.
if [ -f .env ]; then set -a; . ./.env; set +a; fi

# Herramientas que JARVIS puede usar sin preguntar. Gmail: leer y borradores; enviar solo
# tras un "sí" de David en voz (--confirmado); reenviar o borrar, nunca. Calendar: leer siempre; crear y
# cambiar eventos solo cuando David lo pide en directo (voz o terminal), nunca en rutinas.
permitidas=(
  Read Write Edit Glob Grep WebSearch WebFetch
  "Bash(date:*)" "Bash(mkdir:*)" "Bash(ls:*)" "Bash(mv:*)"
  "Bash(git status:*)" "Bash(git diff:*)" "Bash(git log:*)" "Bash(git init:*)" "Bash(git checkout -b:*)"
  "Bash(git add:*)" "Bash(git commit:*)" "Bash(npm test:*)" "Bash(python3:*)" "Bash(pdftotext:*)"
)
# Conectores de claude.ai: "claude.ai Gmail" → mcp__claude_ai_Gmail (se listan ambas grafías por si acaso).
# Fuera a propósito (send_message y reply solo con --confirmado): forward, trash_*, *_spam, *label* y delete_draft (Gmail);
# delete_event y respond_to_event (Calendar).
for servidor in claude_ai_Gmail claude.ai_Gmail; do
  for h in search_threads get_thread get_message list_labels list_drafts get_draft create_draft update_draft; do
    permitidas+=("mcp__${servidor}__$h")
  done
  # Enviar: solo en la respuesta a un "¿lo envío?" que David contestó "sí" (voz/jarvis_voz.py),
  # dentro de esa misma conversación y nunca desde la cola.
  if [ "$confirmado" = "1" ] && [ -n "$reanudar" ] && [ "${JARVIS_AUTOMATICO:-0}" != "1" ]; then
    for h in send_message reply; do
      permitidas+=("mcp__${servidor}__$h")
    done
  fi
done
# Spotify: buscar, ver qué suena, crear listas y guardar en la biblioteca. Quitar de la biblioteca, nunca.
for servidor in claude_ai_Spotify claude.ai_Spotify; do
  for h in search get_currently_playing generate_playlist save_to_library; do
    permitidas+=("mcp__${servidor}__$h")
  done
done
for servidor in claude_ai_Google_Calendar claude.ai_Google_Calendar; do
  for h in list_calendars list_events get_event search_events suggest_time; do
    permitidas+=("mcp__${servidor}__$h")
  done
  # La cola marca JARVIS_AUTOMATICO=1 en rutinas y botones: ahí nadie pidió crear nada.
  if [ "${JARVIS_AUTOMATICO:-0}" != "1" ]; then
    for h in create_event update_event; do
      permitidas+=("mcp__${servidor}__$h")
    done
  fi
done

opciones=(-p "$pedido" --output-format json --allowedTools "$(IFS=,; echo "${permitidas[*]}")")
# Además del repo, JARVIS puede trabajar en las carpetas de David (boveda/wiki/perfil.md):
# los proyectos en P:\ y sus archivos personales.
for carpeta in /mnt/p /mnt/c/Users/Usuario; do
  if [ -d "$carpeta" ]; then opciones+=(--add-dir "$carpeta"); fi
done
if [ -n "$reanudar" ]; then opciones+=(--resume "$reanudar"); fi
# Por voz importa la rapidez: un modelo más ágil. Las rutinas y la terminal usan el de siempre.
if [ "$voz" = "1" ]; then opciones+=(--model "${JARVIS_MODELO_VOZ:-sonnet}"); fi

# </dev/null: sin esto claude espera 3 s una entrada que nunca llega y avisa "no stdin data received".
salida=$(claude "${opciones[@]}" </dev/null)
# La salida JSON trae la respuesta ("result") y la conversación ("session_id").
if datos=$(printf '%s' "$salida" | python3 -c 'import json, sys
d = json.load(sys.stdin)
print(d.get("session_id") or "")
print(d.get("result") or "")' 2>/dev/null); then
  id_sesion=$(printf '%s\n' "$datos" | head -n 1)
  respuesta=$(printf '%s\n' "$datos" | tail -n +2)
else
  id_sesion=""; respuesta="$salida"
fi
if [ "$sesion" = "1" ] && [ -n "$id_sesion" ]; then echo "SESION=$id_sesion" >&2; fi

echo "$(date -Iseconds) < $respuesta" >> logs/jarvis.log
echo "$respuesta"
