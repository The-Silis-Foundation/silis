import os
import sys

import glob
import re

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))

# 0. Auto-configure DISPLAY, XAUTHORITY, and QT_QPA_PLATFORM for seamless GUI display
def configure_display_and_auth():
    if not os.environ.get("DISPLAY"):
        sockets = glob.glob("/tmp/.X11-unix/X*")
        nums = []
        for s in sockets:
            m = re.search(r'X(\d+)', os.path.basename(s))
            if m:
                nums.append(int(m.group(1)))
        if nums:
            disp_num = 1 if 1 in nums else sorted(nums)[0]
            os.environ["DISPLAY"] = f":{disp_num}"
        else:
            os.environ["DISPLAY"] = ":1"

    if not os.environ.get("XAUTHORITY"):
        uid = os.getuid()
        cands = [
            f"/run/user/{uid}/gdm/Xauthority",
            f"/run/user/{uid}/Xauthority",
            os.path.expanduser("~/.Xauthority")
        ]
        for c in cands:
            if os.path.isfile(c) and os.access(c, os.R_OK):
                os.environ["XAUTHORITY"] = c
                break

    if "QT_QPA_PLATFORM" not in os.environ:
        os.environ["QT_QPA_PLATFORM"] = "xcb"

configure_display_and_auth()

# 1. PDK Root default inside project directory
if "PDK_ROOT" not in os.environ:
    os.environ["PDK_ROOT"] = os.path.join(REPO_ROOT, "third-party", "pdks")
try:
    os.makedirs(os.environ["PDK_ROOT"], exist_ok=True)
except Exception:
    pass

# 1b. Third-party plugins and libraries (e.g. ghdl.so for Yosys)
THIRD_PARTY_PLUGINS = os.path.join(REPO_ROOT, "third-party", "plugins")
THIRD_PARTY_BIN = os.path.join(REPO_ROOT, "third-party", "bin")
os.environ["YOSYS_PLUGINS"] = THIRD_PARTY_PLUGINS

ghdl_prefix = os.path.join(THIRD_PARTY_PLUGINS, "ghdl", "gcc", "vhdl")
if os.path.isdir(ghdl_prefix):
    os.environ["GHDL_PREFIX"] = ghdl_prefix

cur_ld = os.environ.get("LD_LIBRARY_PATH", "")
if THIRD_PARTY_PLUGINS not in cur_ld:
    os.environ["LD_LIBRARY_PATH"] = f"{THIRD_PARTY_PLUGINS}:{cur_ld}" if cur_ld else THIRD_PARTY_PLUGINS

cur_path = os.environ.get("PATH", "")
if THIRD_PARTY_BIN not in cur_path:
    os.environ["PATH"] = f"{THIRD_PARTY_BIN}:{cur_path}"

# 2. Ensure REPO_ROOT is first on sys.path
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
elif sys.path[0] != REPO_ROOT:
    sys.path.remove(REPO_ROOT)
    sys.path.insert(0, REPO_ROOT)

# 3. Add engine directories to sys.path
_engine_subdirs = [
    "terminal", "clocktreeviewer", "synthengine", 
    "backendflow/fast_viewer", "backendflow/siliconpeeker",
    "editor", "schematicviewer", "third-party/GDS3D"
]
for _sub in _engine_subdirs:
    _p = os.path.join(REPO_ROOT, _sub)
    if _p not in sys.path:
        sys.path.append(_p)

# 4. Dynamic QtWebEngine discovery
def setup_qt_webengine():
    appdir = os.environ.get("APPDIR")
    candidate_procs = []
    
    # Check AppImage layout
    if appdir:
        candidate_procs.extend([
            os.path.join(appdir, "usr", "lib", "qt6", "libexec", "QtWebEngineProcess"),
            os.path.join(appdir, "opt", "python", "lib", f"python{sys.version_info.major}.{sys.version_info.minor}", "site-packages", "PyQt6", "Qt6", "libexec", "QtWebEngineProcess"),
        ])
    
    # Check user-local PyQt6 package
    candidate_procs.append(os.path.expanduser(f"~/.local/lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages/PyQt6/Qt6/libexec/QtWebEngineProcess"))

    # Check installed PyQt6 package
    try:
        import PyQt6
        candidate_procs.append(os.path.join(os.path.dirname(PyQt6.__file__), "Qt6", "libexec", "QtWebEngineProcess"))
    except Exception:
        pass
        
    # Standard system fallbacks
    candidate_procs.extend([
        "/usr/lib/qt6/libexec/QtWebEngineProcess",
        "/usr/lib/x86_64-linux-gnu/qt6/libexec/QtWebEngineProcess",
        "/usr/local/lib/qt6/libexec/QtWebEngineProcess"
    ])
    
    for p in candidate_procs:
        if os.path.isfile(p) and os.access(p, os.X_OK):
            os.environ["QTWEBENGINEPROCESS_PATH"] = p
            base = os.path.dirname(os.path.dirname(p))
            res_dir = os.path.join(base, "resources")
            loc_dir = os.path.join(base, "translations", "qtwebengine_locales")
            if os.path.isdir(res_dir):
                os.environ["QTWEBENGINE_RESOURCES_PATH"] = res_dir
            if os.path.isdir(loc_dir):
                os.environ["QTWEBENGINE_LOCALES_PATH"] = loc_dir
            break

setup_qt_webengine()

# 5. Enable context sharing if PyQt6 is available
try:
    from PyQt6.QtCore import QCoreApplication, Qt
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
except Exception:
    pass
