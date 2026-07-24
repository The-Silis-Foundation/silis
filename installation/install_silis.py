import os
import subprocess
import sys

def run_cmd(cmd, use_sudo=False):
    if use_sudo:
        cmd = ["sudo"] + cmd
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Error executing: {' '.join(cmd)}")
        sys.exit(1)

# --- Configuration ---
# Setting this to a stable 2024 release where OpenROAD is well-supported
OLD_DATE = "2024-11-20" 
URL = f"https://github.com/YosysHQ/oss-cad-suite-build/releases/download/{OLD_DATE}/oss-cad-suite-linux-x64-{OLD_DATE.replace('-', '')}.tgz"

TOOLS_DIR = "/opt/silistools"
IDE_DIR = "/opt/siliside"
SILIS_BIN_LINK = "/usr/local/bin/silis"
OPENROAD_BIN_LINK = "/usr/local/bin/openroad"
DESKTOP_PATH = os.path.expanduser("~/.local/share/applications/silis.desktop")

print(f"🚀 Starting Downgrade/Installation to OSS CAD Suite version: {OLD_DATE}...")

# 0. Clean up previous installation to avoid conflicts
print("🧹 Cleaning up old installation files...")
if os.path.exists("/tmp/oss-cad.tgz"):
    os.remove("/tmp/oss-cad.tgz")
run_cmd(["rm", "-rf", TOOLS_DIR], use_sudo=True)

# 1. Setup Folders
print("📂 Creating system directories...")
run_cmd(["mkdir", "-p", TOOLS_DIR, IDE_DIR], use_sudo=True)
run_cmd(["chown", "-R", f"{os.getlogin()}:{os.getlogin()}", TOOLS_DIR, IDE_DIR], use_sudo=True)

# 2. Download Hardware Engines (Older Version)
print(f"📦 Downloading version {OLD_DATE} (approx 670MB)...")
run_cmd(["wget", "-c", "-O", "/tmp/oss-cad.tgz", URL])

# 3. Extraction
print("📦 Extracting toolchain to /opt/silistools...")
run_cmd(["tar", "-xzf", "/tmp/oss-cad.tgz", "-C", TOOLS_DIR, "--strip-components=1"])

# 4. Create Global 'openroad' Command
print("🔗 Making OpenROAD globally callable...")
or_wrapper = f"""#!/bin/bash
export PATH="{TOOLS_DIR}/bin:$PATH"
exec {TOOLS_DIR}/bin/openroad "$@"
"""
with open("/tmp/openroad_wrapper", "w") as f:
    f.write(or_wrapper)
run_cmd(["mv", "/tmp/openroad_wrapper", OPENROAD_BIN_LINK], use_sudo=True)
run_cmd(["chmod", "+x", OPENROAD_BIN_LINK], use_sudo=True)

# 5. Python Environment setup for IDE
print("🐍 Setting up Silis Python environment...")
# Ensure we clear the old venv for compatibility
run_cmd(["rm", "-rf", f"{IDE_DIR}/venv"])
run_cmd(["python3", "-m", "venv", f"{IDE_DIR}/venv"])
pip_path = f"{IDE_DIR}/venv/bin/pip"
run_cmd([pip_path, "install", "PyQt6", "numpy", "pyyaml"])

# 6. Deploy Silis Monolith
print("📂 Deploying Silis monolith...")
if os.path.exists("pocpnrv12.py"):
    run_cmd(["cp", "pocpnrv12.py", f"{IDE_DIR}/main.py"])
else:
    print("⚠️ Warning: pocpnrv12.py not found in current directory. Skipping copy.")

# 7. Create Global 'silis' Command
print("🔗 Creating global 'silis' command...")
silis_wrapper = f"""#!/bin/bash
export PATH="{TOOLS_DIR}/bin:$PATH"
{IDE_DIR}/venv/bin/python {IDE_DIR}/main.py "$@"
"""
with open("/tmp/silis_wrapper", "w") as f:
    f.write(silis_wrapper)
run_cmd(["mv", "/tmp/silis_wrapper", SILIS_BIN_LINK], use_sudo=True)
run_cmd(["chmod", "+x", SILIS_BIN_LINK], use_sudo=True)

# 8. Create a local shell launcher
print("📜 Creating local shell launcher (run_silis.sh)...")
with open("run_silis.sh", "w") as f:
    f.write(silis_wrapper)
os.chmod("run_silis.sh", 0o775)

# 9. Desktop Integration
desktop_content = f"""[Desktop Entry]
Name=Silis IDE
Exec={SILIS_BIN_LINK}
Icon=utilities-terminal
Type=Application
Categories=Development;Engineering;
"""
with open(DESKTOP_PATH, "w") as f:
    f.write(desktop_content)

print("\n✅ SUCCESS: Installation Finished with older toolchain!")
print(f"👉 Toolchain version: {OLD_DATE}")
print("👉 Type 'openroad' to run the engine.")
print("👉 Type 'silis' to run your IDE.")
