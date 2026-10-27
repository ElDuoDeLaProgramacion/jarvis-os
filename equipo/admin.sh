#!/usr/bin/env bash
# Configura (o cambia) la entrada al panel de David: una clave y, opcional pero recomendado, un
# código de 6 dígitos de tu app autenticadora (Google/Microsoft Authenticator). Lo corre David:
#   ./equipo/admin.sh
set -euo pipefail
CODIGO="$(cd "$(dirname "$0")/.." && pwd)"
CASA=/home/equipo

echo "Panel de Orión Equipo"
read -rsp "Elige la clave del panel (mínimo 12 caracteres): " c1; echo
[ "${#c1}" -ge 12 ] || { echo "Muy corta."; exit 1; }
read -rsp "Escríbela otra vez: " c2; echo
[ "$c1" = "$c2" ] || { echo "No coinciden."; exit 1; }

read -rp "¿Añadir código de 6 dígitos (2 pasos)? Muy recomendado [S/n]: " dos
dos=${dos:-s}

# El Python corre como el usuario equipo (para escribir admin.json en su carpeta), y el usuario
# equipo no puede leer tu carpeta personal; por eso importamos seguridad.py de la copia instalada
# (/opt/orion-equipo), legible por él. Si aún no está instalado, caemos a la copia del repo.
INSTALADO=/opt/orion-equipo/equipo
sudo -u equipo python3 - "$c1" "$dos" "$INSTALADO" "$CODIGO/equipo" <<PY
import sys, json, os
for _p in (sys.argv[3], sys.argv[4]):
    if os.path.isfile(os.path.join(_p, "seguridad.py")):
        sys.path.insert(0, _p); break
import seguridad
clave, dos = sys.argv[1], sys.argv[2].lower()
reg = {"clave": seguridad.cifrar_clave(clave), "totp": ""}
if dos in ("s", "si", "sí", "y", "yes", ""):
    sec = seguridad.totp_secreto()
    reg["totp"] = sec
    uri = seguridad.otpauth(sec, "David")
    print("\nEscanea este QR con tu app autenticadora (o agrega la clave a mano):\n")
    try:
        import qrcode
        q = qrcode.QRCode(border=1); q.add_data(uri); q.print_ascii(invert=True)
    except Exception:
        pass
    print("\nClave para agregar a mano:", sec, "\n")
json.dump(reg, open("$CASA/admin.json", "w"))
print("Guardado en $CASA/admin.json")
PY
sudo chmod 600 "$CASA/admin.json"
sudo systemctl restart orion-equipo 2>/dev/null || true
url=$(sudo grep -oP '^ORION_EQUIPO_URL=\K.*' "$CASA/.env" 2>/dev/null || echo "https://<la dirección de la sala>")
echo "Listo. Entra a tu panel en:  $url/panel"
