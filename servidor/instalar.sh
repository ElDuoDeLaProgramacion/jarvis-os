#!/usr/bin/env bash
# Deja a JARVIS viviendo en un servidor Ubuntu (Oracle Cloud gratis, ver servidor/README.md).
# Se puede ejecutar varias veces: solo hace lo que falta.
#   ./servidor/instalar.sh
set -euo pipefail
cd "$(dirname "$0")/.."
REPO=$(pwd)
YO=$(id -un)
ZONA=${JARVIS_ZONA:-America/Bogota}
export PATH="$HOME/.local/bin:$PATH"
mkdir -p logs "$HOME/.local/bin"
paso() { echo; echo "== $*"; }

paso "Paquetes del sistema"
sudo apt-get update -qq
sudo apt-get install -y -qq git curl python3 python3-venv cron syncthing nmap lynis >/dev/null

paso "Zona horaria: $ZONA (para que las rutinas salgan a tu hora)"
sudo timedatectl set-timezone "$ZONA"

paso "WhatsApp: Node.js y librerías"
./whatsapp/instalar.sh

paso "Claude Code"
if ! command -v claude >/dev/null; then curl -fsSL https://claude.ai/install.sh | bash; fi
claude --version || true
# Para que "claude" y "node" funcionen en la terminal sin volver a entrar al servidor.
grep -q '.local/bin' "$HOME/.bashrc" 2>/dev/null || echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"

paso "Clave de la app del celular"
touch .env
if ! grep -q "^JARVIS_API_TOKEN=.\{24,\}" .env; then
  sed -i '/^JARVIS_API_TOKEN=/d' .env
  echo "JARVIS_API_TOKEN=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')" >> .env
fi
echo "Está en .env (JARVIS_API_TOKEN). La pegas una sola vez en la app."

paso "Servicios (arrancan solos al encender el servidor)"
servicio() {  # nombre, descripción, comando
  sudo tee "/etc/systemd/system/$1.service" >/dev/null <<UNIDAD
[Unit]
Description=$2
After=network-online.target
Wants=network-online.target

[Service]
User=$YO
WorkingDirectory=$REPO
Environment=PATH=$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin
Environment=HOME=$HOME
ExecStart=$3
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
UNIDAD
}
servicio jarvis-app "JARVIS: API y app del celular" "/usr/bin/python3 $REPO/servidor/api.py"
servicio jarvis-whatsapp "JARVIS: puente de WhatsApp" "$HOME/.local/bin/node $REPO/whatsapp/puente.mjs"
[ -x "$HOME/.local/bin/node" ] || sudo sed -i "s|$HOME/.local/bin/node|$(command -v node)|" /etc/systemd/system/jarvis-whatsapp.service
sudo systemctl daemon-reload
sudo systemctl enable --now jarvis-app
sudo systemctl restart jarvis-app
if [ -f whatsapp/sesion/creds.json ]; then
  sudo systemctl enable --now jarvis-whatsapp
  sudo systemctl restart jarvis-whatsapp
else
  echo "WhatsApp aún no está vinculado: ejecuta ./whatsapp/iniciar.sh, escanea el QR, ciérralo con Ctrl+C"
  echo "y vuelve a correr este instalador."
fi

paso "Actualización automática"
# scripts/actualizar.sh (cron, cada 15 min) solo puede reiniciar los servicios de JARVIS, nada más.
regla=/etc/sudoers.d/jarvis-actualizar
sc=$(command -v systemctl)
echo "$YO ALL=(root) NOPASSWD: $sc restart jarvis-app, $sc restart jarvis-app jarvis-whatsapp" | sudo tee "$regla" >/dev/null
sudo chmod 440 "$regla"
sudo visudo -cf "$regla" >/dev/null || { sudo rm -f "$regla"; echo "Aviso: no pude crear $regla"; }

paso "Rutinas y actualización (cron)"
./servidor/rutinas.sh

paso "Syncthing (bóveda sincronizada con el PC)"
sudo systemctl enable --now "syncthing@$YO"

paso "Tailscale (red privada entre el servidor y tu celular)"
if ! command -v tailscale >/dev/null; then curl -fsSL https://tailscale.com/install.sh | sh; fi
if ! tailscale status >/dev/null 2>&1; then
  echo "Abre el enlace que sale abajo y entra con la misma cuenta que usarás en el celular."
  sudo tailscale up
fi
# La primera vez Tailscale puede pedir activar HTTPS en tu red con un enlace: ábrelo y espera aquí.
echo "Si sale un enlace para activar HTTPS (Serve), ábrelo y actívalo."
sudo tailscale serve --bg 7788
direccion=$(tailscale status --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))')

echo
echo "Listo."
echo "  App del celular: https://$direccion/app/"
command -v claude >/dev/null && [ -d "$HOME/.claude" ] || echo "  Falta entrar a Claude: ejecuta  claude  y elige tu cuenta (una vez)."
echo "  Para usar claude en esta terminal: source ~/.bashrc"
echo "  Siguiente: servidor/README.md, pasos 5 a 7 (bóveda, WhatsApp y apagar lo del PC)."
