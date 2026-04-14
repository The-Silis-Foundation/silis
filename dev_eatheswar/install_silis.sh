#!/bin/bash

# =============================================
#   SILIS EDA - Installation Manager
#   Silicon Scaffold Setup Script
#   Supports: Ubuntu 20.04 / 22.04 / 24.04
# =============================================

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Banner
echo -e "${CYAN}"
echo "███████╗ ██╗ ██╗      ██╗ ███████╗"
echo "██╔════╝ ██║ ██║      ██║ ██╔════╝"
echo "███████╗ ██║ ██║      ██║ ███████╗"
echo "╚════██║ ██║ ██║      ██║ ╚════██║"
echo "███████║ ██║ ███████╗ ██║ ███████║"
echo "╚══════╝ ╚═╝ ╚══════╝ ╚═╝ ╚══════╝"
echo -e "${NC}"
echo -e "${BOLD}Silis — Silicon Scaffold | Installation Manager${NC}"
echo "================================================="
echo ""

# ---- Check OS ----
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$NAME
    VER=$VERSION_ID
else
    echo -e "${RED}[ERROR] Cannot detect OS. This script supports Ubuntu only.${NC}"
    exit 1
fi

echo -e "${CYAN}[INFO] Detected OS: $OS $VER${NC}"
echo ""

# ---- Check Ubuntu ----
if [[ "$OS" != *"Ubuntu"* ]]; then
    echo -e "${RED}[ERROR] This script is designed for Ubuntu. Exiting.${NC}"
    exit 1
fi

# ---- Sudo check ----
if [ "$EUID" -ne 0 ]; then
    echo -e "${YELLOW}[INFO] Requesting sudo access for system packages...${NC}"
    sudo -v
fi

INSTALL_DIR="$HOME/silis-eda"
VENV_DIR="$INSTALL_DIR/venv"

# =============================================
#   STEP 1 — SYSTEM UPDATE & CORE TOOLS
# =============================================
echo ""
echo -e "${BOLD}[STEP 1/7] Updating system and installing core tools...${NC}"
sudo apt-get update -qq
# Fixed: Added git and wget which are required later
sudo apt-get install -y git wget curl > /dev/null 2>&1 || { echo -e "${RED}❌ Core tools installation failed.${NC}"; exit 1; }
echo -e "${GREEN}✅ System updated and core tools installed${NC}"

# =============================================
#   STEP 2 — PYTHON & VENV
# =============================================
echo ""
echo -e "${BOLD}[STEP 2/7] Installing Python3 and venv...${NC}"
sudo apt-get install -y python3 python3-pip python3-venv > /dev/null 2>&1 || { echo -e "${RED}❌ Python3 installation failed.${NC}"; exit 1; }
echo -e "${GREEN}✅ Python3 ready: $(python3 --version)${NC}"

# =============================================
#   STEP 3 — QT / DISPLAY DEPENDENCIES
# =============================================
echo ""
echo -e "${BOLD}[STEP 3/7] Installing Qt6 and display libraries...${NC}"
sudo apt-get install -y \
    libxcb-xinerama0 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-render-util0 \
    libxcb-shape0 \
    libxcb-xkb1 \
    libxkbcommon-x11-0 \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libdbus-1-3 \
    libfontconfig1 \
    libfreetype6 \
    > /dev/null 2>&1 || { echo -e "${RED}❌ Qt6 dependencies failed.${NC}"; exit 1; }
echo -e "${GREEN}✅ Qt6 display libraries installed${NC}"

# =============================================
#   STEP 4 — CLONE REPO & VIRTUAL ENV SETUP
# =============================================
echo ""
echo -e "${BOLD}[STEP 4/7] Setting up Silis EDA Environment...${NC}"

if [ ! -d "$INSTALL_DIR" ]; then
    echo -ne "  ⏳ Cloning Silis repo...           "
    git clone https://github.com/The-Silis-Foundation/silis.git "$INSTALL_DIR" > /dev/null 2>&1
    echo -e "${GREEN}✅ Cloned to $INSTALL_DIR${NC}"
else
    echo -e "${CYAN}  ℹ️  Silis directory already exists at $INSTALL_DIR${NC}"
fi

echo -ne "  ⏳ Creating Python Virtual Environment... "
python3 -m venv "$VENV_DIR"
echo -e "${GREEN}✅ Venv created${NC}"

echo -ne "  ⏳ Installing Python packages...          "
# Fixed: Using isolated venv pip to avoid Ubuntu 24.04 global pip block
"$VENV_DIR/bin/pip" install --upgrade pip > /dev/null 2>&1
"$VENV_DIR/bin/pip" install PyQt6 PyQt6-Qt6 PyQt6-sip gdstk numpy > /dev/null 2>&1
echo -e "${GREEN}✅ Packages installed in venv${NC}"

# =============================================
#   STEP 5 — EDA TOOLS
# =============================================
echo ""
echo -e "${BOLD}[STEP 5/7] Installing EDA tools...${NC}"

# --- Icarus Verilog ---
echo -ne "  ⏳ Installing Icarus Verilog...    "
sudo apt-get install -y iverilog > /dev/null 2>&1
if command -v iverilog &> /dev/null; then
    echo -e "${GREEN}✅ iverilog $(iverilog -V 2>&1 | head -1 | awk '{print $4}')${NC}"
else
    echo -e "${RED}❌ Icarus Verilog failed${NC}"
fi

# --- Yosys ---
echo -ne "  ⏳ Installing Yosys...             "
sudo apt-get install -y yosys > /dev/null 2>&1
if command -v yosys &> /dev/null; then
    echo -e "${GREEN}✅ $(yosys --version 2>&1 | head -1 | awk '{print $1, $2}')${NC}"
else
    echo -e "${RED}❌ Yosys failed${NC}"
fi

# --- Graphviz ---
echo -ne "  ⏳ Installing Graphviz...          "
sudo apt-get install -y graphviz > /dev/null 2>&1
if command -v dot &> /dev/null; then
    echo -e "${GREEN}✅ Graphviz ready${NC}"
else
    echo -e "${RED}❌ Graphviz failed${NC}"
fi

# --- Magic VLSI ---
echo -ne "  ⏳ Installing Magic VLSI...        "
sudo apt-get install -y magic > /dev/null 2>&1
if command -v magic &> /dev/null; then
    echo -e "${GREEN}✅ Magic VLSI ready${NC}"
else
    echo -e "${YELLOW}⚠️  Magic not in apt. Skipping (optional).${NC}"
fi

# --- Netgen ---
echo -ne "  ⏳ Installing Netgen...            "
sudo apt-get install -y netgen > /dev/null 2>&1
if command -v netgen &> /dev/null; then
    echo -e "${GREEN}✅ Netgen ready${NC}"
else
    echo -e "${YELLOW}⚠️  Netgen not in apt. Skipping (optional).${NC}"
fi

# --- OpenROAD ---
echo ""
echo -ne "  ⏳ Installing OpenROAD (Downloading binary)... "
# Fixed: OpenROAD logic for 24.04 and explicit error handling
OPENROAD_VER="v2.0-18118"
OPENROAD_URL="https://github.com/The-OpenROAD-Project/OpenROAD/releases/download/${OPENROAD_VER}/openroad_Ubuntu22.04_amd64.tar.gz"

if [[ "$VER" == "20.04" ]]; then
    OPENROAD_URL="https://github.com/The-OpenROAD-Project/OpenROAD/releases/download/${OPENROAD_VER}/openroad_Ubuntu20.04_amd64.tar.gz"
elif [[ "$VER" == "24.04" ]]; then
    echo -ne "${YELLOW}(Using 22.04 binary for 24.04)... ${NC}"
fi

wget -q "$OPENROAD_URL" -O /tmp/openroad.tar.gz
if [ $? -eq 0 ]; then
    sudo tar -xzf /tmp/openroad.tar.gz -C /usr/local --strip-components=1
    rm /tmp/openroad.tar.gz
    if command -v openroad &> /dev/null; then
        echo -e "${GREEN}✅ OpenROAD installed${NC}"
    else
        echo -e "${RED}❌ OpenROAD binary unpacked but not found in PATH${NC}"
    fi
else
    echo -e "${RED}❌ Download failed. Link may be dead or network is down.${NC}"
fi

# =============================================
#   STEP 6 — OPENSTA
# =============================================
echo ""
echo -ne "  ⏳ Installing OpenSTA...           "
sudo apt-get install -y opensta > /dev/null 2>&1
if command -v sta &> /dev/null; then
    echo -e "${GREEN}✅ OpenSTA ready${NC}"
else
    echo -e "${YELLOW}⚠️  OpenSTA not in apt. Skipping (optional).${NC}"
fi

# =============================================
#   STEP 7 — CREATE LAUNCHER
# =============================================
echo ""
echo -e "${BOLD}[STEP 7/7] Creating launchers...${NC}"

# Desktop launcher
# Fixed: Pointing to the venv python executable
cat > "$HOME/Desktop/Silis-EDA.desktop" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Silis EDA
Comment=Silicon Scaffold EDA Tool
Exec=$VENV_DIR/bin/python $INSTALL_DIR/dev_eatheswar/pocpnrv37.py
Icon=utilities-terminal
Terminal=false
Categories=Science;Engineering;
EOF
chmod +x "$HOME/Desktop/Silis-EDA.desktop" 2>/dev/null

# Terminal launcher command
# Fixed: Pointing to the venv python executable and passing arguments "$@"
sudo bash -c "cat > /usr/local/bin/silis << 'EOF'
#!/bin/bash
$VENV_DIR/bin/python $INSTALL_DIR/dev_eatheswar/pocpnrv37.py \"\$@\"
EOF"
sudo chmod +x /usr/local/bin/silis

echo -e "${GREEN}✅ Launchers created natively and for terminal${NC}"

# =============================================
#   SUMMARY
# =============================================
echo ""
echo "================================================="
echo -e "${BOLD}${GREEN}🎉 Silis EDA Installation Complete!${NC}"
echo "================================================="
echo ""
echo -e "${BOLD}Installed tools:${NC}"
command -v iverilog   &>/dev/null && echo -e "  ${GREEN}✅ Icarus Verilog${NC}" || echo -e "  ${RED}❌ Icarus Verilog${NC}"
command -v yosys      &>/dev/null && echo -e "  ${GREEN}✅ Yosys${NC}"          || echo -e "  ${RED}❌ Yosys${NC}"
command -v openroad   &>/dev/null && echo -e "  ${GREEN}✅ OpenROAD${NC}"       || echo -e "  ${RED}❌ OpenROAD${NC}"
command -v magic      &>/dev/null && echo -e "  ${GREEN}✅ Magic VLSI${NC}"     || echo -e "  ${YELLOW}⚠️  Magic (optional)${NC}"
command -v netgen     &>/dev/null && echo -e "  ${GREEN}✅ Netgen${NC}"         || echo -e "  ${YELLOW}⚠️  Netgen (optional)${NC}"
command -v dot        &>/dev/null && echo -e "  ${GREEN}✅ Graphviz${NC}"       || echo -e "  ${RED}❌ Graphviz${NC}"
command -v sta        &>/dev/null && echo -e "  ${GREEN}✅ OpenSTA${NC}"        || echo -e "  ${YELLOW}⚠️  OpenSTA (optional)${NC}"
echo ""
echo -e "${BOLD}How to launch Silis EDA:${NC}"
echo -e "  ${CYAN}Option 1:${NC} Type 'silis' in terminal"
echo -e "  ${CYAN}Option 2:${NC} Double-click 'Silis-EDA' on Desktop"
echo -e "  ${CYAN}Option 3:${NC} $VENV_DIR/bin/python $INSTALL_DIR/dev_eatheswar/pocpnrv37.py"
echo ""
echo -ne "${BOLD}Launch now? (y/n):${NC} "
read -r LAUNCH
if [[ "$LAUNCH" == "y" || "$LAUNCH" == "Y" ]]; then
    "$VENV_DIR/bin/python" "$INSTALL_DIR/dev_eatheswar/pocpnrv37.py"
fi
