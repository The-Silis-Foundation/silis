#!/bin/bash

echo "========================================"
echo "   Setting up Silis EDA Tool..."
echo "========================================"

# Install OpenROAD AFTER codespace loads (so build doesn't timeout)
if ! command -v openroad &> /dev/null; then
    echo "Installing OpenROAD (one time, ~5 mins)..."
    wget -q https://github.com/The-OpenROAD-Project/OpenROAD/releases/download/v2.0-18118/openroad_Ubuntu22.04_amd64.tar.gz \
        -O /tmp/openroad.tar.gz
    tar -xzf /tmp/openroad.tar.gz -C /usr/local --strip-components=1
    rm /tmp/openroad.tar.gz
    echo "OpenROAD installed!"
fi

# Start virtual display
Xvfb :99 -screen 0 1600x900x24 &
export DISPLAY=:99
sleep 2

# Start VNC
x11vnc -display :99 -nopw -forever -quiet &
sleep 1

# Start noVNC on port 6080
websockify --web /usr/share/novnc 6080 localhost:5900 &
sleep 1

echo ""
echo "✅ Ready! Go to PORTS tab → click port 6080"
echo ""

python3 /workspace/dev_eatheswar/pocpnrv37.py
