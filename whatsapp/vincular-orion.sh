#!/usr/bin/env bash
# Le da a Orión su propio número de WhatsApp: tú le escribes desde tu WhatsApp, como a un contacto, y él
# sigue leyendo tus chats con la vinculación que ya tienes.
#
#   ./whatsapp/vincular-orion.sh 57300XXXXXXX    (el número de Orión, con 57; da un código de 8 letras)
#   ./whatsapp/vincular-orion.sh                 (sin número: muestra un QR)
#
# En el celular donde está el WhatsApp de Orión: Dispositivos vinculados > Vincular dispositivo >
# Vincular con número de teléfono, y escribe el código. Para volver a como antes: borra whatsapp/sesion-orion/
# y reinicia el puente.
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH"
if [ ! -d whatsapp/node_modules ]; then ./whatsapp/instalar.sh || exit 1; fi
numero=$(printf %s "$1" | tr -cd 0-9)
if [ -n "$numero" ]; then
  node whatsapp/puente.mjs --orion --codigo "$numero" || exit 1
else
  node whatsapp/puente.mjs --orion || exit 1
fi
# El puente que ya corre sigue con tu número; al reiniciarlo arranca también el de Orión.
if systemctl list-unit-files jarvis-whatsapp.service >/dev/null 2>&1 && systemctl is-enabled --quiet jarvis-whatsapp 2>/dev/null; then
  sudo systemctl restart jarvis-whatsapp && echo Puente reiniciado. Orión te va a saludar desde su número.
else
  echo Reinicia el puente para que Orión empiece a hablarte desde su número.
fi
