#!/usr/bin/env bash
# Arranca el puente de WhatsApp y lo vuelve a lanzar si el túnel o la red se caen.
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH"
while true; do
  python3 whatsapp/puente.py
  echo "$(date -Iseconds) El puente se detuvo; reintento en 30 s." >> logs/whatsapp.log
  sleep 30
done
