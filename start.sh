#!/bin/bash

echo "========================================"
echo "   🚀 Launching Silis EDA Tool..."
echo "========================================"

# Start virtual display (fake screen, needed in Codespace)
Xvfb :99 -screen 0 1600x900x24 &
export DISPLAY=:99
sleep 2

# Start VNC server on that virtual display
x11vnc -display :99 -nopw -forever -quiet &
sleep 1

# Start noVNC — this lets you see the GUI inside your browser
websockify --web /usr/share/novnc 6080 localhost:5900 &
sleep 1

echo ""
echo "✅ Ready! Open the PORTS tab → click port 6080 to see the GUI"
echo ""

# Find and run the latest Silis tool file
python3 /workspace/experimental/POCPNRV25
