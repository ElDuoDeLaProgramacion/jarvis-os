#!/usr/bin/env bash
# Arranca el HUD de JARVIS: ./scripts/hud.sh  ->  http://localhost:7777
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH"
exec python3 hud/servidor.py "$@"
