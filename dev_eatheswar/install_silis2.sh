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

# =============================================
#   STEP 1 — SYSTEM UPDATE
# =============================================
echo ""
echo -e "${BOLD}[STEP 1/7] Updating system packages...${NC}"
sudo apt-get update -qq
echo -e "${GREEN}✅ System updated${NC}"

# =============================================
#   STEP 2 — PYTHON & PIP
# =============================================
echo ""
echo -e "${BOLD}[STEP 2/7] Installing Python3 and pip...${NC}"
sudo apt-get install -y python3 python3-pip python3-venv > /dev/null 2>&1
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
    > /dev/null 2>&1
echo -e "${GREEN}✅ Qt6 display libraries installed${NC}"

# =============================================
#   STEP 4 — PYTHON PACKAGES
# =============================================
echo ""
echo -e "${BOLD}[STEP 4/7] Installing Python packages (PyQt6, gdstk, numpy)...${NC}"
pip3 install --upgrade pip > /dev/null 2>&1
pip3 install PyQt6 PyQt6-Qt6 PyQt6-sip gdstk numpy > /dev/null 2>&1
echo -e "${GREEN}✅ Python packages installed${NC}"

# =============================================
#   STEP 5 — EDA TOOLS
# =============================================
echo ""
echo -e "${BOLD}[STEP 5/7] Installing EDA tools...${NC}"

# --- Icarus Verilog ---
echo -ne "  ⏳ Installing Icarus Verilog...    "
sudo apt-get install -y iverilog > /dev/null 2>&1
if command -v iverilog &> /dev/null; then
    echo -e "${GREEN}✅ iverilog $(iverilog -V 2>&1 | head -1)${NC}"
else
    echo -e "${RED}❌ Icarus Verilog failed${NC}"
fi

# --- Yosys ---
echo -ne "  ⏳ Installing Yosys...             "
sudo apt-get install -y yosys > /dev/null 2>&1
if command -v yosys &> /dev/null; then
    echo -e "${GREEN}✅ $(yosys --version 2>&1 | head -1)${NC}"
else
    echo -e "${RED}❌ Yosys failed${NC}"
fi

# --- Graphviz (for schematic generation) ---
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
echo -ne "  ⏳ Installing OpenROAD (this takes a few minutes)... "
OPENROAD_URL="https://github.com/The-OpenROAD-Project/OpenROAD/releases/download/v2.0-18118/openroad_Ubuntu22.04_amd64.tar.gz"

# Check Ubuntu version for correct binary
if [[ "$VER" == "20.04" ]]; then
    OPENROAD_URL="https://github.com/The-OpenROAD-Project/OpenROAD/releases/download/v2.0-18118/openroad_Ubuntu20.04_amd64.tar.gz"
fi

wget -q "$OPENROAD_URL" -O /tmp/openroad.tar.gz
if [ $? -eq 0 ]; then
    sudo tar -xzf /tmp/openroad.tar.gz -C /usr/local --strip-components=1
    rm /tmp/openroad.tar.gz
    if command -v openroad &> /dev/null; then
        echo -e "${GREEN}✅ OpenROAD installed${NC}"
    else
        echo -e "${RED}❌ OpenROAD binary not found after install${NC}"
    fi
else
    echo -e "${RED}❌ OpenROAD download failed. Check your internet connection.${NC}"
fi

# =============================================
#   STEP 6 — OPENSTA (for timing analysis)
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
#   STEP 7 — CLONE REPO & SETUP
# =============================================
echo ""
echo -e "${BOLD}[STEP 6/7] Setting up Silis EDA...${NC}"

INSTALL_DIR="$HOME/silis-eda"

if [ ! -d "$INSTALL_DIR" ]; then
    echo -ne "  ⏳ Cloning Silis repo...           "
    git clone https://github.com/The-Silis-Foundation/silis.git "$INSTALL_DIR" > /dev/null 2>&1
    echo -e "${GREEN}✅ Cloned to $INSTALL_DIR${NC}"
else
    echo -e "${CYAN}  ℹ️  Silis directory already exists at $INSTALL_DIR${NC}"
fi

# =============================================
#   CREATE LAUNCHER
# =============================================
echo ""
echo -e "${BOLD}[STEP 7/7] Creating launcher...${NC}"

# Desktop launcher
cat > "$HOME/Desktop/Silis-EDA.desktop" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Silis EDA
Comment=Silicon Scaffold EDA Tool
Exec=python3 $INSTALL_DIR/dev_eatheswar/pocpnrv37.py
Icon=utilities-terminal
Terminal=false
Categories=Science;Engineering;
EOF
chmod +x "$HOME/Desktop/Silis-EDA.desktop" 2>/dev/null

# Terminal launcher command
sudo bash -c "cat > /usr/local/bin/silis << 'EOF'
#!/bin/bash
python3 $INSTALL_DIR/dev_eatheswar/pocpnrv37.py
EOF"
sudo chmod +x /usr/local/bin/silis

echo -e "${GREEN}✅ Launcher created${NC}"

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
echo -e "  ${CYAN}Option 3:${NC} python3 $INSTALL_DIR/dev_eatheswar/pocpnrv37.py"
echo ""
echo -e "${BOLD}Launch now? (y/n):${NC} "
read -r LAUNCH
if [[ "$LAUNCH" == "y" || "$LAUNCH" == "Y" ]]; then
    python3 "$INSTALL_DIR/dev_eatheswar/pocpnrv37.py"
fi
