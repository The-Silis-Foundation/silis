import os
import subprocess
import sys
import shutil

# --- Configuration ---
GITHUB_RAW_URL = "https://raw.githubusercontent.com/The-Silis-Foundation/silis/main/experimental/POCPNRV25/pocpnrv25.py"
IDE_DIR = "/opt/siliside"
SILIS_BIN_LINK = "/usr/local/bin/silis"
DESKTOP_PATH = "/usr/share/applications/silis.desktop" # System-wide desktop entry

def run_cmd(cmd, check=True):
    """Executes a shell command."""
    # Ensure we are running as root
    if os.geteuid() != 0:
        cmd = ["sudo"] + cmd
        
    try:
        # print(f"DEBUG: Executing {' '.join(cmd)}")
        subprocess.run(cmd, check=check)
    except subprocess.CalledProcessError:
        print(f"❌ Error executing: {' '.join(cmd)}")
        if check:
            sys.exit(1)

def is_tool_installed(name):
    return shutil.which(name) is not None

# --- Main Installation Flow ---

print(" Starting Silis System-Wide Installation...")

# 0. Check for Root
if os.geteuid() != 0:
    print("❌ This script installs system-wide packages. Please run with sudo.")
    sys.exit(1)

# 1. Update APT & Install Core Tools
print("📦 Updating APT repositories...")
run_cmd(["apt-get", "update"])

print("📦 Installing EDA Tools (Yosys, IVerilog, Magic, Graphviz)...")
eda_pkgs = [
    "yosys",
    "iverilog",
    "gtkwave",
    "graphviz",
    "magic",        # Magic VLSI Layout Tool
    "python3-pip",
    "python3-tk",   # Often needed for GUI backends
    "git"
]
run_cmd(["apt-get", "install", "-y"] + eda_pkgs)

# 2. Install Python Dependencies System-Wide
# We use --break-system-packages for newer Ubuntu versions (23.04+) 
# because the user explicitly requested "system wide" installation.
print(" Installing Python Libraries System-Wide (Volare, GDS, Qt)...")

pip_pkgs = [
    "volare",   # The PDK Manager you requested
    "gdstk",    # For GDS viewing
    "numpy",
    "pyyaml",
    "PyQt6"     # The GUI Framework
]

pip_cmd = [sys.executable, "-m", "pip", "install"] + pip_pkgs

# Check if we need the force flag for PEP 668 managed environments
try:
    subprocess.run([sys.executable, "-m", "pip", "install", "--break-system-packages", "numpy"], 
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # If that didn't crash, we use the flag
    pip_cmd.append("--break-system-packages")
except:
    pass # Installing on older system, flag not needed

run_cmd(pip_cmd)

# 3. Setup /opt Directory
print(f"📂 Setting up installation directory at {IDE_DIR}...")
if os.path.exists(IDE_DIR):
    shutil.rmtree(IDE_DIR)
os.makedirs(IDE_DIR, exist_ok=True)

# 4. Fetch Source Code
print(f"⬇️  Downloading Silis Core from GitHub...")
try:
    # Using curl as fallback for wget
    run_cmd(["wget", "-q", "-O", f"{IDE_DIR}/main.py", GITHUB_RAW_URL])
except:
    print("⚠️ wget failed, trying curl...")
    run_cmd(["curl", "-s", "-o", f"{IDE_DIR}/main.py", GITHUB_RAW_URL])

# 5. Create Global Launcher (No Venv)
print("🔗 Creating global 'silis' command...")
launcher_content = f"""#!/bin/bash
# Silis Global Launcher
export SILIS_HOME="{IDE_DIR}"
# We use the system python explicitly
exec {sys.executable} {IDE_DIR}/main.py "$@"
"""

with open(SILIS_BIN_LINK, "w") as f:
    f.write(launcher_content)
run_cmd(["chmod", "+x", SILIS_BIN_LINK])

# 6. Create System-Wide Desktop Entry
print("🖥️  Creating System-Wide Desktop Entry...")
desktop_content = f"""[Desktop Entry]
Name=Silis IDE
Comment=Silicon Scaffold
Exec={SILIS_BIN_LINK}
Icon=utilities-terminal
Type=Application
Categories=Development;Engineering;Electronics;
Terminal=false
"""

with open(DESKTOP_PATH, "w") as f:
    f.write(desktop_content)
run_cmd(["chmod", "644", DESKTOP_PATH]) # Readable by all

print("\n✅ SUCCESS: System-Wide Installation Complete!")
print("===========================================")
print(f" Magic VLSI:  {'Installed' if is_tool_installed('magic') else 'Not Found (Check APT)'}")
print(f" Volare:      {'Installed' if is_tool_installed('volare') else 'Not Found'}")
print(f" Location:    {IDE_DIR}")
print(f" Command:     silis")
