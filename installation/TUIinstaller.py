import os
import subprocess
import sys
import shutil
import urllib.request

# --- Configuration ---
SILIS_REPO_RAW = "https://raw.githubusercontent.com/The-Silis-Foundation/silis/main/experimental/POCPNRV25/pocpnrv25.py"
ICON_URL = "https://raw.githubusercontent.com/The-Silis-Foundation/silis/main/reference/silisicon.png"

INSTALL_DIR = "/opt/siliside"
BIN_LINK = "/usr/local/bin/silis"
UNINSTALL_LINK = "/usr/local/bin/silis-uninstall"

ICON_PATH = "/usr/share/pixmaps/silis.png"
DESKTOP_APP = "/usr/share/applications/silis.desktop"
DESKTOP_UNINSTALL = "/usr/share/applications/silis-uninstall.desktop"

# --- TUI System ---
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

class TUI:
    @staticmethod
    def header():
        os.system('clear')
        print(f"{Colors.CYAN}{Colors.BOLD}")
        print(r"""
 ███████╗██╗██╗     ██╗███████╗
 ██╔════╝██║██║     ██║██╔════╝
 ███████╗██║██║     ██║███████╗
 ╚════██║██║██║     ██║╚════██║
 ███████║██║███████╗██║███████║
 ╚══════╝╚═╝╚══════╝╚═╝╚══════╝
   Silicon Scaffold Installer
        """)
        print(f"{Colors.ENDC}")
        print(f"{Colors.BLUE}≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡≡{Colors.ENDC}\n")

    @staticmethod
    def status(step, msg):
        print(f"[ {Colors.WARNING}⏳{Colors.ENDC} ] {Colors.BOLD}{step}:{Colors.ENDC} {msg}...")

    @staticmethod
    def success(step, msg):
        print(f"[ {Colors.GREEN}✅{Colors.ENDC} ] {Colors.BOLD}{step}:{Colors.ENDC} {msg}")

    @staticmethod
    def fail(step, msg):
        print(f"[ {Colors.FAIL}❌{Colors.ENDC} ] {Colors.BOLD}{step}:{Colors.ENDC} {msg}")
        sys.exit(1)

# --- [FIXED] Visible Command Runner ---
# If you used my previous snippet, the argument was named 'live'
def run_cmd(cmd, shell=False, verbose=False):
    import time
    try:
        if verbose:
            # SPINNER MODE: Hides logs, shows a rotating bar
            process = subprocess.Popen(
                cmd, 
                shell=shell, 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.PIPE # Capture errors just in case
            )
            
            chars = "|/-\\"
            i = 0
            while process.poll() is None:
                sys.stdout.write(f"\r[ {chars[i]} ] Working...")
                sys.stdout.flush()
                time.sleep(0.1)
                i = (i + 1) % len(chars)
            
            # Clear the spinner line when done
            sys.stdout.write("\r" + " " * 20 + "\r") 
            
            if process.returncode != 0:
                # If it failed, show the error log
                print(f"\n{Colors.FAIL}Command Failed:{Colors.ENDC}")
                print(process.stderr.read().decode())
                return False
        else:
            # Silent mode
            subprocess.run(
                cmd, 
                shell=shell, 
                check=True, 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.PIPE
            )
    except Exception as e:
        return False
    return True

# --- PHASE 1: Magic Builder ---
def install_magic_from_source():
    TUI.status("Magic", "Checking for Magic 8.3+")
    try:
        res = subprocess.run(["magic", "--version"], capture_output=True, text=True)
        if "8.3" in res.stdout:
            TUI.success("Magic", "Magic 8.3+ already installed")
            return
    except:
        pass

    TUI.status("Magic", "Installing Build Dependencies")
    # Using verbose=True to show APT progress
    deps = ["m4", "tcsh", "csh", "libx11-dev", "tcl-dev", "tk-dev", "libcairo2-dev", "mesa-common-dev", "libglu1-mesa-dev", "libncurses-dev", "build-essential"]
    if not run_cmd(["apt-get", "install", "-y"] + deps, verbose=True):
        TUI.fail("Magic", "Failed to install build dependencies")
    
    TUI.status("Magic", "Cloning Magic VLSI Source")
    if os.path.exists("/tmp/magic_src"): shutil.rmtree("/tmp/magic_src")
    if not run_cmd(["git", "clone", "--depth=1", "https://github.com/RTimothyEdwards/magic", "/tmp/magic_src"]):
        TUI.fail("Magic", "Git clone failed")

    TUI.status("Magic", "Compiling (configure & make)...")
    try:
        # Verbose build so user knows it's not frozen
        subprocess.run("./configure --disable-werror", shell=True, cwd="/tmp/magic_src", check=True)
        subprocess.run("make -j$(nproc)", shell=True, cwd="/tmp/magic_src", check=True)
        TUI.status("Magic", "Installing binaries")
        subprocess.run("make install", shell=True, cwd="/tmp/magic_src", check=True)
    except Exception as e:
        TUI.fail("Magic", f"Build failed: {e}")

    TUI.success("Magic", "Magic VLSI 8.3+ Compiled & Installed")

# --- PHASE 2: Uninstaller Generator ---
def generate_uninstaller():
    script = f"""#!/usr/bin/python3
import os
import sys
import shutil
import subprocess

def confirm(prompt):
    try:
        return input(f"{{prompt}} [y/N]: ").lower().startswith('y')
    except: return False

print("🗑️  SILIS UNINSTALLER")
print("=====================")

print(f"Removing IDE files at {INSTALL_DIR}...")
if os.path.exists("{INSTALL_DIR}"): shutil.rmtree("{INSTALL_DIR}")

print("Removing Binaries...")
if os.path.exists("{BIN_LINK}"): os.remove("{BIN_LINK}")
if os.path.exists("{UNINSTALL_LINK}"): os.remove("{UNINSTALL_LINK}")

print("Removing Desktop Entries...")
if os.path.exists("{DESKTOP_APP}"): os.remove("{DESKTOP_APP}")
if os.path.exists("{DESKTOP_UNINSTALL}"): os.remove("{DESKTOP_UNINSTALL}")
if os.path.exists("{ICON_PATH}"): os.remove("{ICON_PATH}")

print("✅ Silis Core removed.")

print("\\n⚠️  DEPENDENCY CLEANUP")
if confirm("Uninstall dependencies (pip packages & apt tools)?"):
    print("Running cleanup...")
    # Using break-system-packages for uninstallation too
    subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", "volare", "gdstk", "PyQt6", "--break-system-packages"], stderr=subprocess.DEVNULL)
    subprocess.run(["apt-get", "remove", "-y", "yosys", "iverilog", "gtkwave"], stderr=subprocess.DEVNULL)
    print("✅ Dependencies removed.")

print("\\n👋 Uninstallation Complete.")
"""
    os.makedirs(INSTALL_DIR, exist_ok=True)
    with open(f"{INSTALL_DIR}/uninstall_silis.py", "w") as f:
        f.write(script)
    os.chmod(f"{INSTALL_DIR}/uninstall_silis.py", 0o755)

    with open(UNINSTALL_LINK, "w") as f:
        f.write(f"#!/bin/bash\nsudo {sys.executable} {INSTALL_DIR}/uninstall_silis.py")
    os.chmod(UNINSTALL_LINK, 0o755)

# --- MAIN INSTALLER FLOW ---

if os.geteuid() != 0:
    print("❌ Run as root: sudo python3 installer_v2.py")
    sys.exit(1)

TUI.header()

# 1. System Update
TUI.status("System", "Updating APT Repositories")
run_cmd(["apt-get", "update"], verbose=True)

# 2. Basic Tools
TUI.status("EDA", "Installing Yosys, IVerilog, Graphviz, Git")
run_cmd(["apt-get", "install", "-y", "yosys", "iverilog", "gtkwave", "graphviz", "python3-pip", "python3-tk", "git"], verbose=True)

# 3. Magic VLSI (Build from Source)
install_magic_from_source()

# 4. Python Deps
TUI.status("Python", "Installing System-Wide Libs")

pip_cmd = [
    sys.executable, "-m", "pip", "install", 
    "-q",   # <--- Quiet mode (suppresses text logs)
    "--no-warn-script-location"
]

pkgs = ["volare", "gdstk", "numpy", "pyyaml", "PyQt6"]
pip_cmd.extend(pkgs)

# Check for PEP 668
try:
    subprocess.run([sys.executable, "-m", "pip", "install", "--break-system-packages", "numpy"], 
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    pip_cmd.append("--break-system-packages")
except: 
    pass

# Run with verbose=True to trigger the spinner we just wrote
if not run_cmd(pip_cmd, verbose=True):
    TUI.fail("Python", "Pip install failed")

TUI.success("Python", "Libraries Installed")

# 5. Core Files
TUI.status("Silis", f"Creating Directory {INSTALL_DIR}")
if os.path.exists(INSTALL_DIR): shutil.rmtree(INSTALL_DIR)
os.makedirs(INSTALL_DIR, exist_ok=True)

TUI.status("Silis", "Downloading Core Source Code")
try:
    urllib.request.urlretrieve(SILIS_REPO_RAW, f"{INSTALL_DIR}/main.py")
    TUI.success("Silis", "Source Code Downloaded")
except Exception as e:
    TUI.fail("Silis", f"Download failed: {e}")

# 6. Icons & Desktop
TUI.status("Assets", "Downloading Application Icon")

# Ensure the directory exists
if not os.path.exists("/usr/share/pixmaps"):
    os.makedirs("/usr/share/pixmaps", exist_ok=True)

try:
    # Use the RAW GitHub link to ensure we get the file, not the HTML page
    # (HTML pages saved as .png are corrupted/pixelated)
    RAW_ICON_URL = "https://raw.githubusercontent.com/The-Silis-Foundation/silis/main/reference/silisicon.png"
    
    # Download with a user-agent to avoid GitHub blocking scripts
    req = urllib.request.Request(
        RAW_ICON_URL, 
        headers={'User-Agent': 'Mozilla/5.0'}
    )
    with urllib.request.urlopen(req) as response, open(ICON_PATH, 'wb') as out_file:
        shutil.copyfileobj(response, out_file)
        
    TUI.success("Assets", "High-Res Icon Downloaded")
except Exception as e:
    # Fallback to a generic high-quality system icon if download fails
    TUI.status("Assets", "Download failed, using system fallback")
    ICON_PATH = "utilities-terminal" 

# Create the Desktop Entry
app_desktop = f"""[Desktop Entry]
Name=Silis IDE
Comment=Silicon Scaffold
Exec={BIN_LINK}
Icon={ICON_PATH}
Type=Application
Categories=Development;Engineering;Electronics;
Terminal=false
StartupWMClass=SilisIDE
"""

with open(DESKTOP_APP, "w") as f:
    f.write(app_desktop)
os.chmod(DESKTOP_APP, 0o644) # Readable by all users

# Create Launcher Script
with open(BIN_LINK, "w") as f:
    f.write(f"#!/bin/bash\nexport SILIS_HOME='{INSTALL_DIR}'\nexec {sys.executable} {INSTALL_DIR}/main.py \"$@\"")
os.chmod(BIN_LINK, 0o755)

TUI.success("Assets", "Desktop Shortcuts Created")

# 7. Uninstaller
TUI.status("System", "Generating Uninstaller")
generate_uninstaller()

print(f"\n{Colors.GREEN}{Colors.BOLD}INSTALLATION COMPLETE!{Colors.ENDC}")
print(f"   • IDE Command:   {Colors.CYAN}silis{Colors.ENDC}")
print(f"   • Magic VLSI:    {Colors.CYAN}v8.3+ (Built from Source){Colors.ENDC}")
print("\nLaunch Silis from your application menu or terminal.")
