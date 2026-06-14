#!/usr/bin/env bash
# TGM Drive — Installer & Launcher per Linux
# Esegui questo script dalla root del progetto:
#   chmod +x scripts/install-linux.sh
#   ./scripts/install-linux.sh
#
# Al termine, potrai avviare l'app con il comando globale:
#   tgm-drive

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
LAUNCHER_NAME="tgm-drive"
LAUNCHER_BIN="$HOME/.local/bin/$LAUNCHER_NAME"

# ── Colori ──────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "${BOLD}🚀 TGM Drive — Installer Linux${NC}\n"

# ── 1. Verifica Python ──────────────────────────────────────────────────
echo -e "${YELLOW}[1/4]${NC} Verifica Python 3.10+..."
if ! command -v python3 &>/dev/null; then
    echo -e "${RED}❌ python3 non trovato. Installa Python 3.10 o superiore.${NC}"
    echo "   Ubuntu/Debian: sudo apt install python3 python3-venv python3-pip"
    echo "   Fedora:        sudo dnf install python3 python3-pip"
    echo "   Arch:          sudo pacman -S python python-pip"
    exit 1
fi

PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
    echo -e "${RED}❌ Python $PY_VERSION rilevato. Richiesto Python 3.10+.${NC}"
    exit 1
fi
echo -e "   ${GREEN}✅ Python $PY_VERSION${NC}"

# ── 2. Crea virtual environment ─────────────────────────────────────────
echo -e "${YELLOW}[2/4]${NC} Creazione virtual environment in .venv/..."
python3 -m venv "$VENV_DIR"
echo -e "   ${GREEN}✅ Virtual environment creato${NC}"

# ── 3. Installa dipendenze ──────────────────────────────────────────────
echo -e "${YELLOW}[3/4]${NC} Installazione dipendenze Python..."
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -r "$PROJECT_DIR/requirements.txt"
echo -e "   ${GREEN}✅ Dipendenze installate${NC}"

# ── 4. Crea il launcher globale ─────────────────────────────────────────
echo -e "${YELLOW}[4/4]${NC} Creazione launcher globale '${LAUNCHER_NAME}'..."
mkdir -p "$HOME/.local/bin"

cat > "$LAUNCHER_BIN" << 'LAUNCHER_EOF'
#!/usr/bin/env bash
# TGM Drive Launcher — generato automaticamente da install-linux.sh
PROJECT_DIR="__PROJECT_DIR__"
VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"
MAIN_SCRIPT="$PROJECT_DIR/main.py"

if [ ! -f "$MAIN_SCRIPT" ]; then
    echo "❌ TGM Drive non trovato in $PROJECT_DIR"
    echo "   Reinstalla con: cd \"\$PROJECT_DIR\" && ./scripts/install-linux.sh"
    exit 1
fi

cd "$PROJECT_DIR"
exec "$VENV_PYTHON" "$MAIN_SCRIPT" "$@"
LAUNCHER_EOF

# Inietta il percorso assoluto del progetto
sed -i "s|__PROJECT_DIR__|$PROJECT_DIR|" "$LAUNCHER_BIN"

chmod +x "$LAUNCHER_BIN"
echo -e "   ${GREEN}✅ Launcher creato: $LAUNCHER_BIN${NC}"

# ── Verifica PATH ───────────────────────────────────────────────────────
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo -e "\n${YELLOW}⚠️  $HOME/.local/bin non è nel tuo PATH.${NC}"
    echo "   Aggiungi questa riga al tuo ~/.bashrc o ~/.zshrc:"
    echo -e "   ${BOLD}export PATH=\"\$HOME/.local/bin:\$PATH\"${NC}"
    echo "   Poi esegui: ${BOLD}source ~/.bashrc${NC} (o riavvia il terminale)"
fi

echo -e "\n${BOLD}${GREEN}✅ Installazione completata!${NC}"
echo -e "   Ora puoi avviare TGM Drive da qualsiasi terminale con:"
echo -e "   ${BOLD}${GREEN}tgm-drive${NC}\n"
