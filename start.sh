#!/bin/bash

echo "========================================"
echo "   Launching Silis EDA Tool..."
echo "========================================"

# Start virtual display
Xvfb :99 -screen 0 1600x900x24 &
export DISPLAY=:99
sleep 2

# Start VNC server
x11vnc -display :99 -nopw -forever -quiet &
sleep 1

# Start noVNC browser viewer on port 6080
websockify --web /usr/share/novnc 6080 localhost:5900 &
sleep 1

echo ""
echo "GUI ready! Go to PORTS tab and click port 6080"
echo ""

# Launch YOUR Silis tool
python3 /workspace/dev_eatheswar/pocpnrv37.py
