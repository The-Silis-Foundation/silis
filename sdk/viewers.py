"""
silis/sdk/viewers.py
Standalone Window Viewers for Silis ASIC Artifacts.
Provides dedicated QMainWindow wrappers with standard window controls (minimize,
maximize, close), zoom/pan controls, and search for:
- Physical Layouts (DEF) via FastSiliconPeeker / SiliconPeeker
- 3D GDSII Structures via GDS3D
- Digital Waveforms via SignalPeeker (VCD)
- RTL / Gate Schematics via SilisSchematic
- Full GUI Environment via open_gui()
"""

import os
import sys
from typing import Optional, Any, Union

from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLineEdit,
    QLabel,
    QToolBar,
    QFileDialog,
    QMessageBox,
    QDialog,
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QAction, QIcon

from cli_flow import find_project_file


import subprocess

_APP_INSTANCE: Optional[QApplication] = None


def _ensure_desktop_env():
    """
    Auto-detects and configures X11 DISPLAY and XAUTHORITY so GUI windows
    always appear on the user's active desktop without any manual environment setup.
    """
    if "DISPLAY" not in os.environ or not os.environ["DISPLAY"]:
        if os.path.exists("/tmp/.X11-unix"):
            sockets = sorted([s for s in os.listdir("/tmp/.X11-unix") if s.startswith("X")])
            if sockets:
                os.environ["DISPLAY"] = sockets[-1].replace("X", ":")
        if "DISPLAY" not in os.environ or not os.environ["DISPLAY"]:
            os.environ["DISPLAY"] = ":1"
    
    if "XAUTHORITY" not in os.environ or not os.environ["XAUTHORITY"]:
        for cand in [
            f"/run/user/{os.getuid()}/gdm/Xauthority",
            "/run/user/1000/gdm/Xauthority",
            os.path.expanduser("~/.Xauthority"),
        ]:
            if os.path.isfile(cand):
                os.environ["XAUTHORITY"] = cand
                break

    # If QT_QPA_PLATFORM was offscreen, clear it for visible desktop rendering
    if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
        del os.environ["QT_QPA_PLATFORM"]


def _ensure_app() -> QApplication:
    """Ensures a persistent QApplication instance is initialized for visible desktop UI."""
    global _APP_INSTANCE
    _ensure_desktop_env()
    app = QApplication.instance()
    if not app:
        _APP_INSTANCE = QApplication(["silis", "-platform", "xcb"])
        app = _APP_INSTANCE
    else:
        _APP_INSTANCE = app
    return app


# ------------------------------------------------------------------------------
# 1. Layout Viewer (DEF)
# ------------------------------------------------------------------------------
def view_layout(
    def_path: str,
    parent: Optional[QWidget] = None,
    title: Optional[str] = None,
    show: bool = True,
    detach: Optional[bool] = None,
) -> Any:
    """
    Opens a standalone window showing SiliconPeeker / FastSiliconPeeker canvas
    with zoom, pan, and search controls.
    
    By default (detach=None), when called standalone with show=True, it automatically
    launches in a detached interactive desktop process so pipeline scripts don't freeze
    and users never have to configure DISPLAY, XAUTHORITY, or subprocess wrappers.
    Pass detach=False to construct and return a QMainWindow in-process.
    """
    _ensure_desktop_env()
    abs_def = os.path.abspath(def_path)
    if os.path.isdir(abs_def):
        candidates = [
            os.path.join(abs_def, "results", "temp.def"),
            os.path.join(abs_def, "results", "routed.def"),
            os.path.join(abs_def, "results", "placed.def"),
            os.path.join(abs_def, "results", "floorplanned.def"),
        ]
        import glob
        candidates.extend(glob.glob(os.path.join(abs_def, "results", "*.def")))
        candidates.extend(glob.glob(os.path.join(abs_def, "*.def")))
        for cand in candidates:
            if os.path.isfile(cand) and os.path.getsize(cand) > 0:
                abs_def = cand
                break

    win_title = title or f"Silis SiliconPeeker Layout — {os.path.basename(abs_def)}"

    if detach is None:
        detach = (show and parent is None)

    if detach:
        silis_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        repo_root = os.path.dirname(silis_dir)
        launcher_script = (
            "import sys, os; "
            "repo_root = sys.argv[1]; silis_dir = sys.argv[2]; abs_def = sys.argv[3]; win_title = sys.argv[4]; "
            "sys.path.insert(0, silis_dir); sys.path.insert(0, repo_root); import silis; "
            "from PyQt6.QtWidgets import QApplication; "
            "app = QApplication(sys.argv); "
            "win = silis.view_layout(abs_def, title=win_title, show=True, detach=False); "
            "win.resize(1150, 800); win.show(); win.raise_(); win.activateWindow(); "
            "sys.exit(app.exec())"
        )
        cmd = [sys.executable, "-c", launcher_script, repo_root, silis_dir, abs_def, win_title]
        env = os.environ.copy()
        _ensure_desktop_env()
        env["DISPLAY"] = os.environ.get("DISPLAY", ":1")
        if "XAUTHORITY" in os.environ:
            env["XAUTHORITY"] = os.environ["XAUTHORITY"]
        env["QT_QPA_PLATFORM"] = "xcb"
        proc = subprocess.Popen(cmd, env=env, start_new_session=True)
        print(f"[SILIS] Desktop SiliconPeeker Layout window launched (PID: {proc.pid})")
        return proc
    _ensure_app()
    abs_def = os.path.abspath(def_path)
    win_title = title or f"Silis SiliconPeeker Layout — {os.path.basename(abs_def)}"

    win = QMainWindow(parent)
    win.setWindowFlags(
        Qt.WindowType.Window
        | Qt.WindowType.WindowMinMaxButtonsHint
        | Qt.WindowType.WindowCloseButtonHint
    )
    win.setWindowTitle(win_title)
    win.resize(1150, 780)

    # Central Container
    central = QWidget(win)
    layout = QVBoxLayout(central)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    # Try FastSiliconPeeker first, fallback to SiliconPeeker
    from backendflow.siliconpeeker.peeker import FastSiliconPeeker, SiliconPeeker

    peeker = None
    try:
        peeker = FastSiliconPeeker(parent=central)
        if not getattr(peeker, "core", None):
            peeker = SiliconPeeker(parent=central)
    except Exception:
        peeker = SiliconPeeker(parent=central)

    # Top Toolbar for Zoom / Search Controls
    tb = QToolBar("Layout Controls", win)
    tb.setIconSize(QSize(18, 18))
    tb.setMovable(False)
    tb.setStyleSheet("background: #252526; color: #f0f0f0; border-bottom: 1px solid #3c3c3c;")

    act_zoom_in = QAction("🔍+ Zoom In", win)
    act_zoom_out = QAction("🔍- Zoom Out", win)
    act_fit = QAction("↔ Fit", win)
    act_reload = QAction("⟳ Reload", win)

    def do_zoom_in():
        if hasattr(peeker, "scale"):
            peeker.scale(1.25, 1.25)
        elif hasattr(peeker, "core") and peeker.core:
            peeker.core.pan_to(peeker.core.get_center_x(), peeker.core.get_center_y(), peeker.core.get_zoom() * 1.25)

    def do_zoom_out():
        if hasattr(peeker, "scale"):
            peeker.scale(0.8, 0.8)
        elif hasattr(peeker, "core") and peeker.core:
            peeker.core.pan_to(peeker.core.get_center_x(), peeker.core.get_center_y(), peeker.core.get_zoom() * 0.8)

    def do_fit():
        if hasattr(peeker, "fit_with_slack"):
            peeker.fit_with_slack()
        elif hasattr(peeker, "core") and peeker.core:
            peeker.core.fit_in_view()

    def do_reload():
        if os.path.isfile(abs_def):
            peeker.load_def_file(abs_def)

    act_zoom_in.triggered.connect(do_zoom_in)
    act_zoom_out.triggered.connect(do_zoom_out)
    act_fit.triggered.connect(do_fit)
    act_reload.triggered.connect(do_reload)

    tb.addAction(act_zoom_in)
    tb.addAction(act_zoom_out)
    tb.addAction(act_fit)
    tb.addAction(act_reload)
    tb.addSeparator()

    # Search Box in Toolbar
    search_lbl = QLabel("  Find: ", win)
    search_lbl.setStyleSheet("color: #ccc; font-size: 11px;")
    tb.addWidget(search_lbl)

    search_input = QLineEdit(win)
    search_input.setPlaceholderText("Instance / Macro...")
    search_input.setFixedWidth(160)
    search_input.setStyleSheet("background: #1e1e1e; color: #fff; border: 1px solid #555; padding: 2px 6px; border-radius: 3px;")

    def on_search():
        txt = search_input.text().strip()
        if hasattr(peeker, "on_search_instance"):
            peeker.on_search_instance(txt)

    search_input.returnPressed.connect(on_search)
    tb.addWidget(search_input)

    btn_search = QPushButton("Search", win)
    btn_search.setStyleSheet("background: #388bfd; color: white; padding: 2px 8px; border-radius: 3px; font-size: 11px;")
    btn_search.clicked.connect(on_search)
    tb.addWidget(btn_search)

    win.addToolBar(tb)

    layout.addWidget(peeker)
    win.setCentralWidget(central)

    # Load File
    if os.path.isfile(abs_def):
        peeker.load_def_file(abs_def)
        if hasattr(peeker, "fit_with_slack"):
            peeker.fit_with_slack()
        elif hasattr(peeker, "core") and peeker.core:
            peeker.core.fit_in_view()

    win.peeker_widget = peeker

    if show:
        win.show()
    return win


# ------------------------------------------------------------------------------
# 2. 3D GDS Viewer
# ------------------------------------------------------------------------------
def view_gds3d(
    gds_path: str,
    tech_path: Optional[str] = None,
    parent: Optional[QWidget] = None,
    title: Optional[str] = None,
    show: bool = True,
) -> QMainWindow:
    """
    Opens a standalone QMainWindow showing the hardware-accelerated GDS3D viewer.
    """
    _ensure_app()
    abs_gds = os.path.abspath(gds_path)
    win_title = title or f"Silis GDS3D Viewer — {os.path.basename(abs_gds)}"

    win = QMainWindow(parent)
    win.setWindowFlags(
        Qt.WindowType.Window
        | Qt.WindowType.WindowMinMaxButtonsHint
        | Qt.WindowType.WindowCloseButtonHint
    )
    win.setWindowTitle(win_title)
    win.resize(1150, 780)

    from backendflow.gdsviewer.gds3d import GDS3DPort

    gds_port = GDS3DPort(parent_ide=None)
    win.setCentralWidget(gds_port)

    from PyQt6.QtGui import QGuiApplication
    win.gds_port = gds_port
    win.loaded_gds = abs_gds

    # In headless offscreen test environments without a hardware OpenGL context,
    # avoid native OpenGL draw calls to prevent driver segfaults.
    is_offscreen = (
        QGuiApplication.platformName() == "offscreen"
        or os.environ.get("QT_QPA_PLATFORM") == "offscreen"
    )

    if os.path.isfile(abs_gds) and not is_offscreen:
        try:
            if tech_path and os.path.isfile(tech_path) and gds_port.core:
                gds_port.core.load_gds(abs_gds, os.path.abspath(tech_path), "")
            else:
                gds_port.load_gds(abs_gds)
        except Exception as e:
            print(f"[GDS3D Warning] Failed to render 3D GDS: {e}")

    if show:
        win.show()
    return win


# ------------------------------------------------------------------------------
# 3. Waveform Viewer (VCD)
# ------------------------------------------------------------------------------
class _DummyIDE:
    """Lightweight adapter allowing SignalPeeker to run standalone."""
    def __init__(self, cwd: str):
        self.cwd = cwd

    def log_system(self, msg: str, tag: str = "INFO"):
        pass


def view_waveforms(
    vcd_path: str,
    parent: Optional[QWidget] = None,
    title: Optional[str] = None,
    show: bool = True,
) -> QMainWindow:
    """
    Opens a standalone QMainWindow showing SignalPeeker for VCD waveform debugging.
    """
    _ensure_app()
    abs_vcd = os.path.abspath(vcd_path)
    win_title = title or f"Silis SignalPeeker — {os.path.basename(abs_vcd)}"

    win = QMainWindow(parent)
    win.setWindowFlags(
        Qt.WindowType.Window
        | Qt.WindowType.WindowMinMaxButtonsHint
        | Qt.WindowType.WindowCloseButtonHint
    )
    win.setWindowTitle(win_title)
    win.resize(1100, 650)

    from signalpeeker.code import SignalPeeker

    dummy_ide = _DummyIDE(os.path.dirname(abs_vcd))
    peeker = SignalPeeker(dummy_ide)
    win.setCentralWidget(peeker)

    if os.path.isfile(abs_vcd):
        peeker.load_file(abs_vcd)

    win.signal_peeker = peeker

    if show:
        win.show()
    return win


# ------------------------------------------------------------------------------
# 4. Schematic Viewer
# ------------------------------------------------------------------------------
def view_schematic(
    file_path: str,
    parent: Optional[QWidget] = None,
    title: Optional[str] = None,
    show: bool = True,
) -> QMainWindow:
    """
    Opens a standalone QMainWindow showing SilisSchematic.
    Supports JSON (digitaljs), SVG, or synthesized structural files.
    """
    _ensure_app()
    abs_path = os.path.abspath(file_path)
    win_title = title or f"Silis Schematic Viewer — {os.path.basename(abs_path)}"

    win = QMainWindow(parent)
    win.setWindowFlags(
        Qt.WindowType.Window
        | Qt.WindowType.WindowMinMaxButtonsHint
        | Qt.WindowType.WindowCloseButtonHint
    )
    win.setWindowTitle(win_title)
    win.resize(1100, 750)

    from schematicviewer.graphiccanvas import SilisSchematic

    schem = SilisSchematic(parent=win)

    # Top Toolbar
    tb = QToolBar("Schematic Controls", win)
    tb.setStyleSheet("background: #252526; color: #fff; border-bottom: 1px solid #333;")
    act_fit = QAction("↔ Fit In View", win)
    act_fit.triggered.connect(lambda: schem.fitInView())
    tb.addAction(act_fit)
    win.addToolBar(tb)

    win.setCentralWidget(schem)

    if os.path.isfile(abs_path):
        if abs_path.endswith(".json"):
            schem.load_json(abs_path, "top", "block")
        elif abs_path.endswith(".svg"):
            schem.load_svg(abs_path)

    win.schem_widget = schem

    if show:
        win.show()
    return win


# ------------------------------------------------------------------------------
# 5. Full Silis GUI
# ------------------------------------------------------------------------------
def open_gui(
    project_path: Optional[str] = None,
    target_tab: Optional[str] = None,
    exec_loop: bool = False,
) -> QMainWindow:
    """
    Launches the full interactive SilisIDE window.
    """
    app = _ensure_app()

    proj_to_open = None
    if project_path:
        proj_to_open = find_project_file(project_path)
        if not proj_to_open and os.path.isdir(project_path):
            proj_to_open = os.path.abspath(project_path)

    import silis
    SilisIDE = getattr(silis, "SilisIDE", None)
    if not SilisIDE:
        from silis.silis import SilisIDE
    from pdkmanagers.pdk.manager import SSAForge

    SSAForge.load_aliases()

    window = SilisIDE(project_file=proj_to_open)

    if target_tab:
        t = target_tab.lower()
        if t in ["synth", "synthesis", "4"]:
            window.switch_world(0)
            window.frontend_tabs.setCurrentIndex(3)
        elif t in ["schem", "schematic", "3"]:
            window.switch_world(0)
            window.frontend_tabs.setCurrentIndex(2)
        elif t in ["waves", "waveform", "2"]:
            window.switch_world(0)
            window.frontend_tabs.setCurrentIndex(1)
        elif t in ["compile", "editor", "1"]:
            window.switch_world(0)
            window.frontend_tabs.setCurrentIndex(0)
        elif t in ["layout", "backend", "floorplan", "place", "route"]:
            window.switch_world(1)
            window.backend_widget.viz_tabs.setCurrentIndex(0)

    window.show()

    if exec_loop:
        app.exec()
    return window


def open_floorplanner(
    project_path: Optional[str] = None,
    exec_loop: bool = True,
) -> QDialog:
    """
    Launches the Interactive Floorplanner Studio dialog directly via the Python SDK.
    Enables visual die sizing, core margin tuning, macro placement/rotation,
    halo margin adjustments, and blockage creation.
    """
    app = _ensure_app()
    from silis.sdk.project import Project, find_project_file
    from silis.pdkmanagers.pdk.manager import SSAForge
    from silis.backendflow.floorplanner.floorplanner import InteractiveFloorplannerWidget

    pdk_mgr = SSAForge()
    proj = None
    if project_path:
        proj = Project.load(project_path)
    else:
        proj_file = find_project_file(os.getcwd())
        if proj_file:
            proj = Project.load(proj_file)

    p_cfg = proj.config if proj else {}
    dialog = InteractiveFloorplannerWidget(p_cfg, pdk_mgr)
    dialog.show()

    if exec_loop:
        app.exec()
    return dialog


def open_ioplacer(
    project_path: Optional[str] = None,
    exec_loop: bool = True,
) -> QDialog:
    """
    Launches the Silis I/O Placer Studio dialog directly via the Python SDK.
    Enables visual peripheral pin distribution, edge grouping, pitch tuning,
    wirebond pad ring generation (Single & Dual Staggered), and macro packaging.
    """
    app = _ensure_app()
    from silis.sdk.project import Project, find_project_file
    from silis.pdkmanagers.pdk.manager import SSAForge
    from silis.backendflow.floorplanner.ioplacer import IOPlacerDialog

    pdk_mgr = SSAForge()
    proj = None
    if project_path:
        proj = Project.load(project_path)
    else:
        proj_file = find_project_file(os.getcwd())
        if proj_file:
            proj = Project.load(proj_file)

    p_cfg = proj.config if proj else {}
    dialog = IOPlacerDialog(p_cfg, pdk_mgr)
    dialog.show()

    if exec_loop:
        app.exec()
    return dialog


# ------------------------------------------------------------------------------
# 6. Third-Party EDA Viewers (Magic, KLayout, GTKWave, OpenROAD GUI)
# ------------------------------------------------------------------------------
def view_magic(gds_path: str, tech_path: Optional[str] = None) -> Optional[subprocess.Popen]:
    """
    Launches Magic VLSI layout GUI in an independent window displaying the given GDS.
    """
    _ensure_desktop_env()
    abs_gds = os.path.abspath(gds_path)
    if not os.path.isfile(abs_gds):
        raise FileNotFoundError(f"GDS file not found: {abs_gds}")

    # Discover PDK tech file if not supplied
    tech_file = tech_path
    if not tech_file:
        silis_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        parent_root = os.path.dirname(silis_root)
        cands = []
        for base in [silis_root, parent_root]:
            cands.extend([
                os.path.join(base, "third-party", "pdks", "volare", "sky130", "versions", "0fe599b2afb6708d281543108caf8310912f54af", "sky130A", "libs.tech", "magic", "sky130A.tech"),
                os.path.join(base, "third-party", "pdks", "volare", "sky130", "versions", "0fe599b2afb6708d281543108caf8310912f54af", "sky130A", "libs.tech", "magic", "sky130A.magicrc"),
                os.path.join(base, "third-party", "pdks", "sky130A", "libs.tech", "magic", "sky130A.tech"),
                os.path.join(base, "third-party", "pdks", "sky130A", "libs.tech", "magic", "sky130A.magicrc"),
            ])
        for c in cands:
            if os.path.isfile(c):
                tech_file = c
                break

    cmd = ["magic", "-d", "XR"]
    if tech_file and tech_file.endswith(".tech"):
        cmd.extend(["-T", tech_file])
    cmd.append(abs_gds)

    env = os.environ.copy()
    env["DISPLAY"] = os.environ.get("DISPLAY", ":1")
    if "XAUTHORITY" in os.environ:
        env["XAUTHORITY"] = os.environ["XAUTHORITY"]

    proc = subprocess.Popen(cmd, cwd=os.path.dirname(abs_gds), env=env, start_new_session=True)
    print(f"[SILIS] Magic GUI launched for '{os.path.basename(abs_gds)}' (PID: {proc.pid})")
    return proc


def view_gtkwave(vcd_path: str) -> Optional[subprocess.Popen]:
    """
    Launches GTKWave in an independent window displaying the given VCD simulation dump.
    """
    _ensure_desktop_env()
    abs_vcd = os.path.abspath(vcd_path)
    if not os.path.isfile(abs_vcd):
        raise FileNotFoundError(f"VCD file not found: {abs_vcd}")

    env = os.environ.copy()
    env["DISPLAY"] = os.environ.get("DISPLAY", ":1")
    if "XAUTHORITY" in os.environ:
        env["XAUTHORITY"] = os.environ["XAUTHORITY"]

    proc = subprocess.Popen(["gtkwave", abs_vcd], cwd=os.path.dirname(abs_vcd), env=env, start_new_session=True)
    print(f"[SILIS] GTKWave launched for '{os.path.basename(abs_vcd)}' (PID: {proc.pid})")
    return proc


def view_openroad_gui(def_or_odb_path: str) -> Optional[subprocess.Popen]:
    """
    Launches native OpenROAD GUI in an independent window displaying the routed DEF/ODB.
    """
    _ensure_desktop_env()
    abs_file = os.path.abspath(def_or_odb_path)
    if not os.path.isfile(abs_file):
        raise FileNotFoundError(f"DEF/ODB file not found: {abs_file}")

    env = os.environ.copy()
    env["DISPLAY"] = os.environ.get("DISPLAY", ":1")
    if "XAUTHORITY" in os.environ:
        env["XAUTHORITY"] = os.environ["XAUTHORITY"]

    if abs_file.endswith(".odb"):
        cmd = ["openroad", "-gui", "-db", abs_file]
    else:
        silis_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        parent_root = os.path.dirname(silis_root)
        cands_tlef = []
        cands_sc = []
        for base in [silis_root, parent_root]:
            cands_tlef.extend([
                os.path.join(base, "third-party", "pdks", "sky130A", "libs.ref", "sky130_fd_sc_hd", "techlef", "sky130_fd_sc_hd__nom.tlef"),
                os.path.join(base, "third-party", "pdks", "volare", "sky130", "versions", "0fe599b2afb6708d281543108caf8310912f54af", "sky130A", "libs.ref", "sky130_fd_sc_hd", "techlef", "sky130_fd_sc_hd__nom.tlef"),
            ])
            cands_sc.extend([
                os.path.join(base, "third-party", "pdks", "sky130A", "libs.ref", "sky130_fd_sc_hd", "lef", "sky130_fd_sc_hd.lef"),
                os.path.join(base, "third-party", "pdks", "volare", "sky130", "versions", "0fe599b2afb6708d281543108caf8310912f54af", "sky130A", "libs.ref", "sky130_fd_sc_hd", "lef", "sky130_fd_sc_hd.lef"),
            ])
        tlef = next((c for c in cands_tlef if os.path.isfile(c)), "")
        sc_lef = next((c for c in cands_sc if os.path.isfile(c)), "")
        
        loader_script = os.path.join(os.path.dirname(abs_file), "_openroad_gui_loader.tcl")
        lines = []
        if tlef:
            lines.append(f'read_lef "{tlef}"')
        if sc_lef:
            lines.append(f'read_lef "{sc_lef}"')
        lines.append(f'read_def "{abs_file}"')
        lines.append('gui::show')
        with open(loader_script, "w") as f:
            f.write("\n".join(lines) + "\n")
        cmd = ["openroad", "-gui", loader_script]

    proc = subprocess.Popen(cmd, cwd=os.path.dirname(abs_file), env=env, start_new_session=True)
    print(f"[SILIS] OpenROAD Native GUI launched for '{os.path.basename(abs_file)}' (PID: {proc.pid})")
    return proc

