#!/usr/bin/env bash
# Instala lo que necesita el WhatsApp de JARVIS (una sola vez, en Ubuntu/WSL):
#   - Node.js 20 o más nuevo (si no está, se descarga el oficial en ~/.local/node, sin sudo)
#   - las librerías del puente (Baileys, la que usa WhatsApp Web)
#   - faster-whisper, para entender las notas de voz
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

# Notas de voz: faster-whisper en su propio entorno de Python (whatsapp/.venv). Si falla, el resto sigue.
if [ ! -x whatsapp/.venv/bin/python ]; then
  echo "Instalando el transcriptor de notas de voz (faster-whisper)..."
  if python3 -m venv whatsapp/.venv 2>/dev/null; then
    whatsapp/.venv/bin/pip install -q --upgrade pip faster-whisper "av<19" || echo "Aviso: no pude instalar faster-whisper; las notas de voz no se transcribirán."
  else
    rm -rf whatsapp/.venv
    echo "Aviso: falta python3-venv. Instálalo con:  sudo apt install -y python3-venv  y vuelve a ejecutar este script."
  fi
fi
# PyAV 19 quitó un parámetro que faster-whisper usa al leer las notas de voz: se queda en la 18.
if [ -x whatsapp/.venv/bin/pip ]; then whatsapp/.venv/bin/pip install -q "av<19" || true; fi

touch .env
grep -q "^WHATSAPP_PERMITIDOS=" .env || echo "WHATSAPP_PERMITIDOS=" >> .env

echo
echo "Listo. Ahora vincula tu WhatsApp:  ./whatsapp/iniciar.sh   (y escanea el QR)"
