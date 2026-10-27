#!/usr/bin/env bash
# Da o quita la entrada a la sala de Orión Equipo. Cada persona entra con su usuario y contraseña.
# Lo corre David en el servidor:
#   ./equipo/persona.sh agregar ana         -> crea a 'ana'; tú escribes su contraseña
#   ./equipo/persona.sh clave ana           -> le pones una contraseña nueva (si se le olvidó)
#   ./equipo/persona.sh quitar ana          -> ya no entra (al instante)
#   ./equipo/persona.sh lista
set -euo pipefail
CODIGO="$(cd "$(dirname "$0")/.." && pwd)"
CASA=/home/equipo
ARCHIVO="$CASA/personas"

cifrar() {
  python3 - "$1" <<PY
import sys; sys.path.insert(0, "$CODIGO/equipo")
import seguridad
print(seguridad.cifrar_clave(sys.argv[1]))
PY
}

accion=${1:-}; nombre=${2:-}
case "$accion" in
  agregar|clave)
    [[ "$nombre" =~ ^[a-z0-9_-]{2,20}$ ]] || { echo "Usuario en minúscula, 2-20 caracteres, sin espacios (ej.: ana, luis_p)"; exit 1; }
    sudo -u equipo touch "$ARCHIVO"; sudo chmod 600 "$ARCHIVO"
    existe=$(sudo grep -c "^$nombre	" "$ARCHIVO" || true)
    if [ "$accion" = agregar ] && [ "$existe" != 0 ]; then echo "$nombre ya existe. Para cambiar su contraseña: ./equipo/persona.sh clave $nombre"; exit 1; fi
    if [ "$accion" = clave ] && [ "$existe" = 0 ]; then echo "$nombre no existe todavía. Créalo con: agregar $nombre"; exit 1; fi
    # La eliges tú (no se ve en pantalla). Mínimo 8 caracteres.
    read -rsp "Contraseña para $nombre (mínimo 8): " clave; echo
    [ "${#clave}" -ge 8 ] || { echo "Muy corta (mínimo 8 caracteres)."; exit 1; }
    read -rsp "Escríbela otra vez: " clave2; echo
    [ "$clave" = "$clave2" ] || { echo "No coinciden."; exit 1; }
    hash=$(cifrar "$clave")
    sudo sed -i "/^$nombre	/d" "$ARCHIVO"
    printf '%s\t%s\n' "$nombre" "$hash" | sudo tee -a "$ARCHIVO" >/dev/null
    url=$(sudo grep -oP '^ORION_EQUIPO_URL=\K.*' "$CASA/.env" 2>/dev/null || echo "https://<la dirección de la sala>")
    echo
    echo "Listo. Pásale esto a $nombre por privado:"
    echo "  Entra en:   $url"
    echo "  Usuario:    $nombre"
    echo "  Contraseña: la que acabas de escribir"
    ;;
  quitar)
    [ -n "$nombre" ] || { echo "Falta el usuario"; exit 1; }
    sudo sed -i "/^$nombre	/d" "$ARCHIVO" && echo "$nombre ya no entra."
    ;;
  lista)
    sudo cut -f1 "$ARCHIVO" 2>/dev/null || echo "(nadie todavía)"
    ;;
  *) sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'; exit 1 ;;
esac
