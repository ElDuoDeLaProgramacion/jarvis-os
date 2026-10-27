#!/usr/bin/env bash
# Da o quita la entrada a la sala de Orión Equipo. Lo corre David en el servidor:
#   ./equipo/persona.sh agregar ana     -> imprime el enlace con la clave de Ana (se lo pasas por privado)
#   ./equipo/persona.sh quitar ana      -> Ana ya no entra (al instante, sin reiniciar)
#   ./equipo/persona.sh lista
set -euo pipefail
ARCHIVO=/home/equipo/personas
accion=${1:-}; nombre=${2:-}
como() { sudo -u equipo -H "$@"; }

case "$accion" in
  agregar)
    [[ "$nombre" =~ ^[a-z0-9_-]{2,20}$ ]] || { echo "Nombre en minúscula, sin espacios (ej.: ana, luis_p)"; exit 1; }
    como touch "$ARCHIVO"; sudo chmod 600 "$ARCHIVO"
    if sudo grep -q "^$nombre " "$ARCHIVO"; then echo "$nombre ya tiene clave. Para cambiarla: quitar y agregar."; exit 1; fi
    clave=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
    echo "$nombre $clave" | como tee -a "$ARCHIVO" >/dev/null
    url=$(sudo grep -oP '^ORION_EQUIPO_URL=\K.*' /home/equipo/.env 2>/dev/null || echo "https://<la dirección de la sala>")
    echo "Enlace de $nombre (pásaselo por privado; quien lo tenga entra como $nombre):"
    echo "  $url/#clave=$clave"
    ;;
  quitar)
    [ -n "$nombre" ] || { echo "Falta el nombre"; exit 1; }
    sudo sed -i "/^$nombre /d" "$ARCHIVO" && echo "$nombre ya no entra."
    ;;
  lista)
    sudo cut -d' ' -f1 "$ARCHIVO" 2>/dev/null || echo "(nadie todavía)"
    ;;
  *) sed -n '2,5p' "$0" | sed 's/^# \{0,1\}//'; exit 1 ;;
esac
