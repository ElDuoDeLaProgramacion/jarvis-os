#!/usr/bin/env bash
# Las skills de documentos para Orión: pdf, docx, xlsx y pptx (oficiales de Anthropic, como plugin de
# Claude Code: su licencia no deja copiarlas al repo) y lo que necesitan canvas-design y webapp-testing,
# que sí viven en .claude/skills. Córrelo una vez en el PC (dentro de WSL) y otra en el servidor:
#   ./scripts/instalar-skills.sh
set -euo pipefail
cd "$(dirname "$0")/.."
paso() { echo; echo "== $* =="; }

paso "Programas (PDF, Office, Node)"
sudo apt-get update -qq
sudo apt-get install -y -qq poppler-utils qpdf pandoc libreoffice-writer libreoffice-calc libreoffice-impress \
  nodejs npm python3-pip fonts-dejavu >/dev/null

paso "Librerías de Python"
# --break-system-packages: Ubuntu 24 no deja pip fuera de un venv; con --user solo toca a este usuario.
python3 -m pip install -q --user --break-system-packages \
  pypdf pdfplumber reportlab openpyxl pandas python-docx python-pptx pillow playwright
python3 -m playwright install --with-deps chromium

paso "Librerías de Node (docx y presentaciones)"
sudo npm install -g --silent docx pptxgenjs

paso "Skills oficiales pdf, docx, xlsx y pptx"
claude plugin marketplace add anthropics/skills || true
claude plugin install document-skills@anthropic-agent-skills

echo
echo "Listo. Orión ya puede hacer PDF, Word, Excel y PowerPoint, diseños (canvas-design) y probar páginas (webapp-testing)."
