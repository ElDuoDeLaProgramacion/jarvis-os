#!/usr/bin/env bash
# Arranca el puente de WhatsApp y lo vuelve a lanzar si se cae la red o la conexión.
# La primera vez muestra el QR para vincular. Con --codigo 57300XXXXXXX da un código en vez del QR.
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH"
mkdir -p logs
if [ ! -d whatsapp/node_modules ]; then ./whatsapp/instalar.sh || exit 1; fi
while true; do
  node whatsapp/puente.mjs "$@"
  echo "$(date -Iseconds) El puente se detuvo; reintento en 30 s." >> logs/whatsapp.log
  sleep 30
done
