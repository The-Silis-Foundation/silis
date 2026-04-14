#!/bin/bash
echo "Starting Silis EDA..."

# Install display tools
apt-get install -y -qq xvfb x11vnc novnc websockify

# Install Python packages
pip install -q PyQt6 gdstk numpy

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

echo "✅ Open PORTS tab → click port 6080"

# Launch Silis
python3 /workspaces/silis/dev_eatheswar/pocpnrv37.py
