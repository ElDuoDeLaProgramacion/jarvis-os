#!/usr/bin/env bash
# Trae lo nuevo de GitHub (rama main) sin tocar tus cambios locales.
# Lo corren solos el cron del servidor y una tarea de Windows en el PC; también a mano:
#   ./scripts/actualizar.sh
# Solo avanza si es un avance limpio (fast-forward). Si algo choca con un cambio local, no toca nada
# y lo deja anotado en logs/actualizar.log.
set -uo pipefail
cd "$(dirname "$0")/.."
mkdir -p logs
exec 8>logs/.actualizar.lock
flock -n 8 || exit 0

nota() { echo "$(date -Iseconds) $*"; }

rama=$(git rev-parse --abbrev-ref HEAD)
if [ "$rama" != main ]; then nota "estás en la rama $rama, no actualizo"; exit 0; fi
git fetch -q origin main || { nota "no pude conectar con GitHub"; exit 1; }
antes=$(git rev-parse HEAD)
[ "$antes" = "$(git rev-parse origin/main)" ] && exit 0
if ! salida=$(git merge -q --ff-only origin/main 2>&1); then
  nota "no pude actualizar (¿cambios locales en los mismos archivos?):"; echo "$salida"; exit 1
fi
cambios=$(git diff --name-only "$antes" HEAD)
nota "actualizado $(git rev-parse --short "$antes") -> $(git rev-parse --short HEAD):"
echo "$cambios" | sed 's/^/  /'

cambio() { echo "$cambios" | grep -qE "$1"; }
# Lo que hay que hacer después en el servidor (allí existe el servicio jarvis-app).
if [ -f /etc/systemd/system/jarvis-app.service ]; then
  if cambio '^rutinas/rutinas\.csv$'; then ./servidor/rutinas.sh >/dev/null && nota "rutinas del cron al día"; fi
  if cambio '^whatsapp/(package|instalar\.sh)'; then
    ./whatsapp/instalar.sh >/dev/null 2>&1 && nota "librerías de WhatsApp al día" || nota "falló ./whatsapp/instalar.sh"
  fi
  if cambio '^servidor/instalar\.sh$'; then nota "cambió el instalador: corre ./servidor/instalar.sh cuando puedas"; fi
  reiniciar=jarvis-app
  if cambio '^whatsapp/'; then reiniciar="$reiniciar jarvis-whatsapp"; fi
  if cambio '^(servidor|scripts|voz|whatsapp|\.claude)/|^CLAUDE\.md$'; then
    sudo -n systemctl restart $reiniciar && nota "reiniciado: $reiniciar" \
      || nota "no pude reiniciar $reiniciar (corre ./servidor/instalar.sh una vez)"
  fi
elif cambio '^(hud|voz)/'; then
  nota "cambió el HUD o la voz: se usa la versión nueva al reiniciar sesión"
fi
