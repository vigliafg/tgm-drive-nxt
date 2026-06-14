#!/usr/bin/env bash
# TGM Drive — Build eseguibile standalone con PyInstaller (Linux)
# Esegui dalla root del progetto:
#   chmod +x scripts/build-linux.sh
#   ./scripts/build-linux.sh
#
# Output: dist/TGM-Drive (eseguibile one-file)

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

VENV_DIR="$PROJECT_DIR/.venv"
EXE_NAME="TGM-Drive"
DIST_DIR="$PROJECT_DIR/dist"

# ── Colori ────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

echo -e "${BOLD}🔨 TGM Drive — Build PyInstaller (Linux)${NC}\n"

# ── 1. Verifica virtual environment ───────────────────────────────
echo -e "${YELLOW}[1/4]${NC} Setup ambiente..."
if [ ! -d "$VENV_DIR" ]; then
    echo -e "   Creazione virtual environment..."
    python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"
echo -e "   ${GREEN}✅ Ambiente attivo${NC}"

# ── 2. Installa dipendenze ────────────────────────────────────────
echo -e "${YELLOW}[2/4]${NC} Installazione dipendenze..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
pip install --quiet pyinstaller
echo -e "   ${GREEN}✅ Dipendenze installate${NC}"

# ── 3. Pulizia build precedenti ───────────────────────────────────
echo -e "${YELLOW}[3/4]${NC} Pulizia build precedenti..."
rm -rf build/ dist/ *.spec
echo -e "   ${GREEN}✅ Pulito${NC}"

# ── 4. Build con PyInstaller ──────────────────────────────────────
echo -e "${YELLOW}[4/4]${NC} Build eseguibile one-file..."
echo -e "   ⏳ Questo potrebbe richiedere 1-2 minuti...\n"

pyinstaller \
    --onefile \
    --name "$EXE_NAME" \
    --add-data "README.md:." \
    --hidden-import PyQt6 \
    --hidden-import PyQt6.QtCore \
    --hidden-import PyQt6.QtGui \
    --hidden-import PyQt6.QtWidgets \
    --hidden-import telethon \
    --hidden-import telethon.tl.types \
    --hidden-import telethon.tl.functions.channels \
    --collect-all telethon \
    --noconfirm \
    main.py

echo ""

# ── Verifica ──────────────────────────────────────────────────────
if [ -f "$DIST_DIR/$EXE_NAME" ]; then
    SIZE=$(du -h "$DIST_DIR/$EXE_NAME" | cut -f1)
    echo -e "${BOLD}${GREEN}✅ Build completato!${NC}"
    echo -e "   Eseguibile: ${BOLD}$DIST_DIR/$EXE_NAME${NC}"
    echo -e "   Dimensione: ${BOLD}$SIZE${NC}\n"
    echo -e "   Per eseguirlo: ${BOLD}./dist/$EXE_NAME${NC}"
else
    echo -e "${RED}❌ Build fallito. Controlla gli errori sopra.${NC}"
    exit 1
fi
