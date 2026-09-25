#!/bin/bash

# JARVIS: Global Installer
# Target: macOS & Linux

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
NC='\033[0m'

OS_TYPE=$(uname -s | tr '[:upper:]' '[:lower:]')

echo -e "${BLUE}🚀 Starting JARVIS Global Installation for ${OS_TYPE}...${NC}"

# 1. Dependency Check
if [[ "$OS_TYPE" == "linux" ]]; then
    echo -e "${BLUE}🔍 Checking Linux dependencies...${NC}"
    if command -v apt-get &> /dev/null; then
        sudo apt-get update -y
        sudo apt-get install -y python3-venv python3-pip portaudio19-dev libffi-dev libssl-dev
    elif command -v dnf &> /dev/null; then
        sudo dnf install -y python3-devel portaudio-devel libffi-devel openssl-devel
    elif command -v pacman &> /dev/null; then
        sudo pacman -S --noconfirm --needed python python-pip portaudio
    elif command -v zypper &> /dev/null; then
        sudo zypper install -y python3 python3-pip portaudio-devel libffi-devel libopenssl-devel
    else
        echo -e "${YELLOW}⚠️ No supported package manager found (apt, dnf, pacman, zypper). Install Python 3.12+, pip, and portaudio manually.${NC}"
    fi
elif [[ "$OS_TYPE" == "darwin" ]]; then
    if ! command -v brew &> /dev/null; then
        echo -e "${YELLOW}⚠️ Homebrew not found. Some voice/audio features may require manual setup.${NC}"
    else
        if ! brew list portaudio &> /dev/null; then
            echo -e "${BLUE}📦 Installing portaudio...${NC}"
            brew install portaudio
        fi
    fi
fi

# 2. Directory Setup
INSTALL_DIR="$HOME/.jarvis-app"
mkdir -p "$INSTALL_DIR"

echo -e "${BLUE}📂 Setting up JARVIS in $INSTALL_DIR...${NC}"

# 3. Clone or Copy Files
# If we're already inside the install dir (re-run), there is nothing to copy.
if [ "$(pwd -P)" = "$(cd "$INSTALL_DIR" && pwd -P)" ]; then
    echo -e "${BLUE}📂 Already inside $INSTALL_DIR, skipping copy.${NC}"
elif [ -d ".git" ]; then
    echo -e "${BLUE}📂 Copying files from current directory...${NC}"
    cp -R . "$INSTALL_DIR"
else
    if ! command -v git &> /dev/null; then
        echo -e "${RED}❌ git is required to download JARVIS but was not found. Install git and re-run.${NC}"
        exit 1
    fi
    echo -e "${BLUE}📂 Cloning JARVIS repository...${NC}"
    git clone https://github.com/nave433-blip/jarvis-dev.git "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"

# 4. Virtual Environment & Install
echo -e "${BLUE}🐍 Creating virtual environment...${NC}"
# Use python3.12 if available, fallback to python3 (must be 3.12+)
PYTHON_BIN=$(command -v python3.12 || command -v python3)
if [ -z "$PYTHON_BIN" ]; then
    echo -e "${RED}❌ No python3 found. Install Python 3.12+ and re-run.${NC}"
    exit 1
fi
PY_VER=$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_OK=$("$PYTHON_BIN" -c 'import sys; print(1 if sys.version_info >= (3, 12) else 0)')
if [ "$PY_OK" != "1" ]; then
    echo -e "${RED}❌ JARVIS requires Python 3.12+ (found $PY_VER at $PYTHON_BIN). Install Python 3.12+ and re-run.${NC}"
    exit 1
fi
"$PYTHON_BIN" -m venv venv
source venv/bin/activate

echo -e "${BLUE}📦 Installing JARVIS and dependencies...${NC}"
pip install --upgrade pip
pip install -e .

# 5. Global Link
echo -e "${BLUE}🔗 Creating global link...${NC}"
BIN_PATH="/usr/local/bin/jarvis"

# Create a small wrapper script for the global command
cat <<EOF > jarvis-wrapper
#!/bin/bash
export JARVIS_ROOT="$INSTALL_DIR"
source \$JARVIS_ROOT/venv/bin/activate
exec python \$JARVIS_ROOT/cli.py "\$@"
EOF

chmod +x jarvis-wrapper

if [ -w "/usr/local/bin" ]; then
    mv jarvis-wrapper "$BIN_PATH"
    echo -e "${GREEN}✅ Successfully linked jarvis to $BIN_PATH${NC}"
else
    echo -e "${YELLOW}⚠️ No write access to /usr/local/bin. Using sudo...${NC}"
    sudo mv jarvis-wrapper "$BIN_PATH"
    sudo chown $(whoami) "$BIN_PATH"
    echo -e "${GREEN}✅ Successfully linked jarvis to $BIN_PATH (with sudo)${NC}"
fi

# 6. Final Setup
echo -e "${GREEN}✨ JARVIS is now installed globally!${NC}"
echo -e "Try typing '${BLUE}jarvis${NC}' in your terminal."
