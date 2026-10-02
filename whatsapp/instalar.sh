#!/usr/bin/env bash
# Instala lo que necesita el WhatsApp de JARVIS (una sola vez, en Ubuntu/WSL):
#   - cloudflared, para el túnel gratis de Cloudflare (sin cuenta ni dominio)
#   - las variables que faltan en .env (el secreto del webhook se genera solo)
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p "$HOME/.local/bin" logs

if ! command -v cloudflared >/dev/null && [ ! -x "$HOME/.local/bin/cloudflared" ]; then
  echo "Descargando cloudflared (Cloudflare, oficial)..."
  arq=$(uname -m); case "$arq" in x86_64) arq=amd64 ;; aarch64) arq=arm64 ;; esac
  curl -fsSL -o "$HOME/.local/bin/cloudflared" \
    "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-$arq"
  chmod +x "$HOME/.local/bin/cloudflared"
fi
"$HOME/.local/bin/cloudflared" --version 2>/dev/null || cloudflared --version

touch .env
agregar() { grep -q "^$1=" .env || echo "$1=$2" >> .env; }
agregar KAPSO_API_KEY ""
agregar KAPSO_PHONE_NUMBER_ID ""
agregar WHATSAPP_PERMITIDOS ""
agregar KAPSO_WEBHOOK_SECRET "$(python3 -c 'import secrets; print(secrets.token_hex(32))')"

echo
echo "Listo. Abre .env y completa KAPSO_API_KEY, KAPSO_PHONE_NUMBER_ID y WHATSAPP_PERMITIDOS"
echo "(ver whatsapp/README.md). Luego prueba con:  ./whatsapp/iniciar.sh"
