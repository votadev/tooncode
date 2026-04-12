#!/bin/bash
# ToonCode Installer — one-line install via git
set -e

CYAN='\033[36m'
GREEN='\033[32m'
DIM='\033[2m'
RED='\033[31m'
RESET='\033[0m'

echo ""
echo -e "${CYAN}  ████████╗ ██████╗  ██████╗ ███╗   ██╗ ██████╗ ██████╗ ██████╗ ███████╗${RESET}"
echo -e "${CYAN}     ██║   ██║   ██║██║   ██║██╔██╗ ██║██║     ██║   ██║██║  ██║█████╗  ${RESET}"
echo -e "${CYAN}     ╚═╝    ╚═════╝  ╚═════╝ ╚═╝  ╚═══╝ ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝${RESET}"
echo -e "                         by ${RED}VotaLab${RESET}  |  Free AI Coding Agent"
echo ""

# Check Python
PYTHON=""
for cmd in python3 python; do
    if command -v $cmd &>/dev/null; then
        ver=$($cmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
        major=$(echo $ver | cut -d. -f1)
        minor=$(echo $ver | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ]; then
            PYTHON=$cmd
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo -e "${RED}Error: Python 3.10+ required${RESET}"
    echo "Install: https://www.python.org/downloads/"
    exit 1
fi
echo -e "${DIM}Python: $($PYTHON --version)${RESET}"

# Install dir
INSTALL_DIR="$HOME/.tooncode"

if [ -d "$INSTALL_DIR/.git" ]; then
    echo -e "${DIM}Updating existing installation...${RESET}"
    cd "$INSTALL_DIR" && git pull --quiet
else
    echo -e "${DIM}Cloning ToonCode...${RESET}"
    git clone --depth 1 https://github.com/votalab/tooncode.git "$INSTALL_DIR"
fi

# Install Python deps
echo -e "${DIM}Installing dependencies...${RESET}"
$PYTHON -m pip install --quiet --disable-pip-version-check -r "$INSTALL_DIR/requirements.txt"

# Create launcher script
BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/tooncode" << 'LAUNCHER'
#!/bin/bash
PYTHON=$(command -v python3 || command -v python)
exec $PYTHON "$HOME/.tooncode/tooncode.py" "$@"
LAUNCHER
chmod +x "$BIN_DIR/tooncode"

# Check PATH
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    SHELL_RC=""
    [ -f "$HOME/.bashrc" ] && SHELL_RC="$HOME/.bashrc"
    [ -f "$HOME/.zshrc" ] && SHELL_RC="$HOME/.zshrc"
    if [ -n "$SHELL_RC" ]; then
        echo "export PATH=\"$BIN_DIR:\$PATH\"" >> "$SHELL_RC"
        echo -e "${DIM}Added $BIN_DIR to PATH in $SHELL_RC${RESET}"
    fi
fi

echo ""
echo -e "${GREEN}ToonCode installed!${RESET}"
echo -e "Run: ${CYAN}tooncode${RESET}"
echo -e "Update: ${DIM}cd ~/.tooncode && git pull${RESET}"
echo ""
