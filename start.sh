#!/bin/bash

echo "Setting up Silis EDA environment..."

# Install system dependencies
apt-get update -qq
apt-get install -y -qq \
    wget \
    xvfb \
    x11vnc \
    novnc \
    websockify \
    libxcb-xinerama0 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-render-util0 \
    libxcb-shape0 \
    libxcb-xkb1 \
    libxkbcommon-x11-0 \
    libgl1 \
    python3 \
    python3-pip

# Install Python packages
pip3 install -q PyQt6 gdstk numpy

# Install OpenROAD
if ! command -v openroad &> /dev/null; then
    echo "Downloading OpenROAD..."
    wget -q https://github.com/The-OpenROAD-Project/OpenROAD/releases/download/v2.0-18118/openroad_Ubuntu22.04_amd64.tar.gz \
        -O /tmp/openroad.tar.gz
    tar -xzf /tmp/openroad.tar.gz -C /usr/local --strip-components=1
    rm /tmp/openroad.tar.gz
    echo "OpenROAD ready!"
fi

# Start virtual display
Xvfb :99 -screen 0 1600x900x24 &
export DISPLAY=:99
sleep 2

# Start VNC
x11vnc -display :99 -nopw -forever -quiet &
sleep 1

# Start noVNC browser viewer
websockify --web /usr/share/novnc 6080 localhost:5900 &
sleep 1

echo "✅ Done! Go to PORTS tab and click port 6080"

python3 /workspaces/silis/dev_eatheswar/pocpnrv37.py
