#!/usr/bin/env bash
# Instala lo que necesita el WhatsApp de JARVIS (una sola vez, en Ubuntu/WSL):
#   - Node.js 20 o más nuevo (si no está, se descarga el oficial en ~/.local/node, sin sudo)
#   - las librerías del puente (Baileys, la que usa WhatsApp Web)
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p "$HOME/.local/bin" logs
export PATH="$HOME/.local/bin:$PATH"

version_node() { node -p 'process.versions.node.split(".")[0]' 2>/dev/null || echo 0; }
if [ "$(version_node)" -lt 20 ]; then
  echo "Descargando Node.js 22 (nodejs.org, oficial)..."
  arq=$(uname -m); case "$arq" in x86_64) arq=x64 ;; aarch64) arq=arm64 ;; esac
  nombre=$(curl -fsSL https://nodejs.org/dist/latest-v22.x/ | grep -o "node-v22[0-9.]*-linux-$arq.tar.xz" | head -n 1)
  rm -rf "$HOME/.local/node" && mkdir -p "$HOME/.local/node"
  curl -fsSL "https://nodejs.org/dist/latest-v22.x/$nombre" | tar -xJ -C "$HOME/.local/node" --strip-components=1
  for b in node npm npx; do ln -sf "$HOME/.local/node/bin/$b" "$HOME/.local/bin/$b"; done
fi
echo "Node $(node --version)"

(cd whatsapp && npm ci --no-audit --no-fund)

touch .env
grep -q "^WHATSAPP_PERMITIDOS=" .env || echo "WHATSAPP_PERMITIDOS=" >> .env

echo
echo "Listo. Ahora vincula tu WhatsApp:  ./whatsapp/iniciar.sh   (y escanea el QR)"
