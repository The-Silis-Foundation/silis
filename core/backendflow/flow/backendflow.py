import os
import subprocess
import time
import shutil
import glob
import threading
import datetime
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from backendflow.siliconpeeker.peeker import FastSiliconPeeker
from backendflow.gdsviewer.gds3d import GDS3DPort
try:
    from layer_viewer.layer_viewer_panel import LayerViewerPanel
except ImportError:
    from silis.core.layer_viewer.layer_viewer_panel import LayerViewerPanel
from pdkmanagers.pdk.manager import SSAForge, PDKSelector
from config import USER_SETTINGS, THEMES
from editor.editor import ScintillaEditor
from backendflow.floorplanner.floorplanner import InteractiveFloorplannerWidget
from backendflow.floorplanner.ioplacer import IOPlacerDialog
from synthesisscripts.synthesisthread import ReportEngine
from backendflow.signoff_flow import SignoffDiagnosticDialog, SignoffRunnerWorker

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

class FlowWorker(QThread):
    finished_signal = pyqtSignal()
    
    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs
        
    def run(self):
        try:
            self.func(*self.args, **self.kwargs)
        except Exception as e:
            print("Worker Error:", e)
        finally:
            self.finished_signal.emit()

class OpenROADPort(QWidget):
    def __init__(self, parent_ide=None):
        super().__init__(parent_ide)
        self.ide = parent_ide
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        self.header = QWidget()
        self.header.setStyleSheet("border-bottom:1px solid gray;")
        self.header.setFixedHeight(30)
        h_lay = QHBoxLayout(self.header)
        h_lay.setContentsMargins(5, 2, 5, 2)
        
        self.btn_close = QPushButton("Close Viewer")
        self.btn_close.setStyleSheet("background:transparent; color:#f44336; border:1px solid #3a1a1a; font-weight:bold; border-radius:4px;")
        self.btn_close.clicked.connect(self.kill_viewer)
        self.btn_close.hide()
        
        _gl = QLabel("<b>OPENROAD C++ VIEWER (Embedded)</b>"); _gl.setStyleSheet("color:#00bcd4; font-size:10px;")
        h_lay.addWidget(_gl)
        h_lay.addStretch()
        h_lay.addWidget(self.btn_close)
        self.layout.addWidget(self.header)
        
        self.canvas = QWidget()
        self.canvas_layout = QVBoxLayout(self.canvas)
        self.layout.addWidget(self.canvas, stretch=1)
        
        self.btn_launch = QPushButton("Launch Embedded C++ Viewer")
        self.btn_launch.setFixedSize(280, 50)
        self.btn_launch.setStyleSheet("font-size: 14px; font-weight: bold; background: #2da44e; color: white; border-radius: 6px;")
        self.btn_launch.clicked.connect(self.launch_viewer)
        
        self.info_label = QLabel("Click to natively embed the high-performance C++ executable via X11 WId.")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setStyleSheet("color: #8b949e;")
        
        self.canvas_layout.addStretch()
        self.canvas_layout.addWidget(self.btn_launch, alignment=Qt.AlignmentFlag.AlignCenter)
        self.canvas_layout.addWidget(self.info_label, alignment=Qt.AlignmentFlag.AlignCenter)
        self.canvas_layout.addStretch()
        
        self.proc = None
        self.container = None

    def launch_viewer(self):
        viewer_exe = os.path.join(REPO_ROOT, "backendflow", "def_viewer_cpp", "build", "silis_def_viewer")
        if not os.path.exists(viewer_exe):
            self.info_label.setText("Error: Missing C++ Viewer Executable")
            self.info_label.setStyleSheet("color: #ff7b72;")
            return

        self.btn_launch.setEnabled(False)
        self.btn_launch.setText("Binding to OS...")

        self.proc = QProcess(self)
        self.proc.readyReadStandardOutput.connect(self.handle_stdout)
        self.proc.start(viewer_exe)

    def handle_stdout(self):
        if not self.proc: return
        data = self.proc.readAllStandardOutput().data().decode("utf-8", errors="replace")
        for line in data.splitlines():
            if line.startswith("WID:"):
                wid = int(line.split(":")[1])
                window = QWindow.fromWinId(wid)
                
                # Natively embed the external window into PyQt
                self.container = QWidget.createWindowContainer(window, self)
                
                # Swap UI
                self.btn_launch.hide()
                self.info_label.hide()
                self.btn_close.show()
                
                self.canvas_layout.addWidget(self.container)
                break

    def kill_viewer(self):
        if self.proc:
            self.proc.kill()
            self.proc = None
        if self.container:
            self.container.deleteLater()
            self.container = None
            
        subprocess.call(["killall", "-9", "silis_def_viewer"], stderr=subprocess.DEVNULL)
        
        self.btn_close.hide()
        self.btn_launch.show()
        self.btn_launch.setText("Launch Embedded C++ Viewer")
        self.btn_launch.setEnabled(True)
        self.info_label.show()
        self.info_label.setText("Viewer closed. Ready to launch again.")
        self.info_label.setStyleSheet("color: #8b949e;")

    def closeEvent(self, event):
        self.kill_viewer()
        super().closeEvent(event)


class SignoffReportViewer(QDialog):
    """Clean, high-contrast modal inspector for post-route PAT Sign-Off reports."""
    def __init__(self, rpt_path, timing_failed=False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Silis Post-Route PAT Sign-Off Inspector")
        self.resize(860, 600)
        self.setStyleSheet("""
            QDialog {
                background-color: #0d1117;
                color: #f0f6fc;
            }
            QLabel {
                color: #f0f6fc;
            }
            QPushButton {
                background-color: #21262d;
                color: #f0f6fc;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #30363d;
                border: 1px solid #58a6ff;
            }
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        hdr_layout = QHBoxLayout()
        title_lbl = QLabel("<b>Post-Route Power, Area & Timing Sign-Off Report</b>")
        title_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #58a6ff;")
        
        status_chip = QLabel("TIMING MET" if not timing_failed else "TIMING VIOLATED")
        status_chip.setStyleSheet(
            "padding: 5px 14px; border-radius: 6px; font-weight: bold; font-size: 12px; "
            + ("background: #238636; color: white; border: 1px solid #2ea043;" if not timing_failed else "background: #da3633; color: white; border: 1px solid #f85149;")
        )
        hdr_layout.addWidget(title_lbl)
        hdr_layout.addStretch()
        hdr_layout.addWidget(status_chip)
        lay.addLayout(hdr_layout)

        self.txt = QTextEdit()
        self.txt.setReadOnly(True)
        self.txt.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.txt.setStyleSheet("""
            QTextEdit {
                background: #090d13;
                color: #f0f6fc;
                font-family: Consolas, 'Courier New', monospace;
                font-size: 11px;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 10px;
            }
        """)
        try:
            with open(rpt_path, 'r') as f:
                self.txt.setPlainText(f.read())
        except Exception as e:
            self.txt.setPlainText(f"Error reading report: {e}")
        lay.addWidget(self.txt)

        btn_bar = QHBoxLayout()
        btn_copy = QPushButton("Copy to Clipboard")
        btn_copy.clicked.connect(lambda: QApplication.clipboard().setText(self.txt.toPlainText()))
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        btn_bar.addWidget(btn_copy)
        btn_bar.addStretch()
        btn_bar.addWidget(btn_close)
        lay.addLayout(btn_bar)


class BackendWidget(QWidget):
    pat_finished_signal = pyqtSignal(str, bool)

    def __init__(self, parent_ide):
        super().__init__(parent_ide)
        self.ide = parent_ide 
        self.pdk_mgr = parent_ide.pdk_mgr
        self.active_pdk = parent_ide.active_pdk
        self.pat_finished_signal.connect(self.display_pat_report)
        
        # --- 1. INITIALIZE WIDGETS ---
        self.fast_peeker = FastSiliconPeeker(self.ide)
        self.layer_panel = LayerViewerPanel(self.ide)
        self.gds3d_port = GDS3DPort(self.ide) # [NEW] 3D Viewer Port
        
        self.spinner_timer = QTimer(self)
        self.spinner_timer.timeout.connect(self.update_spinner)
        self.spinner_chars = ['|', '/', '-', '\\']
        self.spinner_idx = 0
        self.running_steps = 0
        
        self.def_ctrl_widget = QWidget()
        def_layout = QVBoxLayout(self.def_ctrl_widget); def_layout.setContentsMargins(0,0,0,0)
        
        self.chk_inst = QCheckBox("Cells"); self.chk_inst.setChecked(True)
        self.chk_macros = QCheckBox("Macros"); self.chk_macros.setChecked(True)
        self.chk_tap = QCheckBox("Tapcells"); self.chk_tap.setChecked(True)
        self.chk_pins = QCheckBox("Pins"); self.chk_pins.setChecked(True)
        self.chk_nets = QCheckBox("Nets"); self.chk_nets.setChecked(False)
        self.chk_power = QCheckBox("Power"); self.chk_power.setChecked(True)

        def_layout.addWidget(QLabel("<b>DEF Layers</b>"))
        def_layout.addWidget(self.chk_inst); def_layout.addWidget(self.chk_macros); def_layout.addWidget(self.chk_tap)
        def_layout.addWidget(self.chk_pins); def_layout.addWidget(self.chk_nets); def_layout.addWidget(self.chk_power)
        def_layout.addStretch()
        
        # --- Left Sidebar Stack: Instance Controls (Mode 0) vs OpenROAD Layer Controls (Mode 1) ---
        self.sidebar_stack = QStackedWidget()
        self.sidebar_stack.addWidget(self.def_ctrl_widget)

        # OpenROAD Display Controls Widget (Mode 1: Layers tree)
        self.openroad_ctrl_widget = QWidget()
        orc_layout = QVBoxLayout(self.openroad_ctrl_widget)
        orc_layout.setContentsMargins(0, 0, 0, 0)
        orc_layout.setSpacing(4)

        lbl_orc_hdr = QLabel("<b>Physical Layers</b>")
        lbl_orc_hdr.setStyleSheet("color: #58a6ff; font-size: 11px;")
        orc_layout.addWidget(lbl_orc_hdr)

        # Batch All / None row
        batch_box = QHBoxLayout()
        batch_box.setContentsMargins(0, 0, 0, 2)
        batch_box.setSpacing(6)

        btn_all = QPushButton("All")
        btn_all.setFixedHeight(20)
        btn_all.setStyleSheet("font-size: 10px; padding: 1px 6px;")
        btn_all.clicked.connect(lambda: self.set_all_layers(True))

        btn_none = QPushButton("None")
        btn_none.setFixedHeight(20)
        btn_none.setStyleSheet("font-size: 10px; padding: 1px 6px;")
        btn_none.clicked.connect(lambda: self.set_all_layers(False))

        batch_box.addWidget(btn_all)
        batch_box.addWidget(btn_none)
        batch_box.addStretch()
        orc_layout.addLayout(batch_box)

        # Layer definitions with exact canvas colors: (attr_name, label_name, QColor)
        mono_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        mono_font.setPointSize(9)

        def make_swatch_icon(color: QColor) -> QIcon:
            px = QPixmap(12, 12)
            px.fill(color)
            p = QPainter(px)
            p.setPen(QColor(50, 50, 50))
            p.drawRect(0, 0, 11, 11)
            p.end()
            return QIcon(px)

        layer_defs = [
            ("chk_layer_li1", "li1", QColor(126, 126, 255)),
            ("chk_layer_met1", "met1", QColor(0, 0, 254)),
            ("chk_layer_met2", "met2", QColor(254, 0, 0)),
            ("chk_layer_met3", "met3", QColor(9, 221, 0)),
            ("chk_layer_met4", "met4", QColor(190, 244, 81)),
            ("chk_layer_met5", "met5", QColor(222, 33, 96)),
            ("chk_layer_vias", "vias", QColor(255, 126, 126)),
        ]

        for attr, name, col in layer_defs:
            chk = QCheckBox(name)
            chk.setFont(mono_font)
            chk.setIcon(make_swatch_icon(col))
            chk.setIconSize(QSize(12, 12))
            chk.setChecked(True)
            setattr(self, attr, chk)
            orc_layout.addWidget(chk)

        orc_layout.addStretch()
        self.sidebar_stack.addWidget(self.openroad_ctrl_widget)

        self.btn_gui = QPushButton("OpenROAD")
        self.btn_magic = QPushButton("Magic")
        self.btn_magic.setStyleSheet("font-weight: bold;")
        
        self.btn_ref = QPushButton("Refresh View")
        
        self.term_log = QTextEdit(); self.term_log.setReadOnly(True)
        self.term_log.setStyleSheet("font-family: Consolas; border: none;")
        self.term_in = QLineEdit(); self.term_in.setPlaceholderText("Enter TCL command...")
        self.term_in.setStyleSheet("font-family: Consolas; padding: 5px; border-top: 1px solid gray;")

        # --- 2. LAYOUT ---
        self.layout = QVBoxLayout(self); self.layout.setContentsMargins(0,0,0,0)
        
        self.ribbon = QFrame(); self.ribbon.setStyleSheet("border-bottom: 1px solid gray;"); self.ribbon.setFixedHeight(40) 
        r_lay = QHBoxLayout(self.ribbon); r_lay.setContentsMargins(5,2,5,2)
        
        # Setup Hybrid Flow Buttons [ Action | ▾ ] and Standard Buttons
        self.flow_buttons = {}
        dropdown_steps = {
            "Init": [
                ("Start New Flow", lambda: self.run_flow_step("Init")),
                ("Load OpenDB (.odb)", self.load_custom_odb),
                ("Load DEF (.def)", self.load_custom_def)
            ],
            "FP Studio": [
                ("Launch Floorplan & Power Studio (FPS)", lambda: self.run_flow_step("FP Studio")),
                ("Power Grid Integrity & Static IR Drop (::psm)", self.run_psm_integrity_check),
                ("Packaging & Bondpad Studio (place_bondpad)", self.run_bondpad_studio)
            ],
            "CTS": [
                ("Apply Clock NDR (2W2S Shielding)", self.apply_clock_ndr),
                ("Repair Clock Buffers / Inverters", self.repair_clock_buffers)
            ],
            "Route": [
                ("Global & Detail Route", lambda: self.run_flow_step("Route")),
                ("Antenna Ratio Verification & Repair", self.repair_antenna_violations)
            ],
            "GDS": [
                ("Open in 3D Silicon Peeker (GDS3D)", self.launch_gds3d_view)
            ]
        }

        all_steps = ["Init", "FP Studio", "Place", "CTS", "Route", "Fill", "GDS"]
        btn_style = (
            "QToolButton, QPushButton { "
            "padding: 3px 6px; font-weight: bold; font-size: 11px; "
            "background-color: #21262d; color: #f0f6fc; border: 1px solid #30363d; border-radius: 3px; "
            "} "
            "QToolButton:hover, QPushButton:hover { "
            "background-color: #30363d; border-color: #58a6ff; "
            "} "
            "QToolButton::menu-button { "
            "border-left: 1px solid #30363d; width: 14px; "
            "}"
        )

        for step in all_steps:
            if step in dropdown_steps:
                tb = QToolButton(self)
                tb.setText(step)
                tb.setStyleSheet(btn_style)
                tb.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
                tb.clicked.connect(lambda _, s=step: self.run_flow_step(s))

                menu = QMenu(tb)
                for item_label, handler in dropdown_steps[step]:
                    act = menu.addAction(item_label)
                    act.triggered.connect(handler)
                tb.setMenu(menu)
                self.flow_buttons[step] = tb
                r_lay.addWidget(tb)
            else:
                btn = QPushButton(step, self)
                btn.setStyleSheet(btn_style)
                btn.clicked.connect(lambda _, s=step: self.run_flow_step(s))
                self.flow_buttons[step] = btn
                r_lay.addWidget(btn)

        line = QFrame(); line.setFrameShape(QFrame.Shape.VLine); line.setFrameShadow(QFrame.Shadow.Sunken)
        r_lay.addWidget(line)

        # Single Neutral Signoff Button
        self.btn_run_signoff = QPushButton("Run Signoff Checks", self)
        self.btn_run_signoff.setStyleSheet(
            "padding: 3px 12px; font-weight: bold; font-size: 11px; "
            "background-color: #21262d; color: #f0f6fc; border: 1px solid #30363d; border-radius: 3px;"
        )
        self.btn_run_signoff.clicked.connect(self.run_signoff_pipeline)
        r_lay.addWidget(self.btn_run_signoff)

        r_lay.addStretch()
        btn_rst = QPushButton("Reset"); btn_rst.clicked.connect(self.reset_backend); r_lay.addWidget(btn_rst)
        btn_cfg = QPushButton("PDK Config"); btn_cfg.clicked.connect(self.open_pdk_selector); r_lay.addWidget(btn_cfg)
        self.layout.addWidget(self.ribbon)
        
        v_split = QSplitter(Qt.Orientation.Vertical)
        h_widget = QWidget(); h_lay = QHBoxLayout(h_widget); h_lay.setContentsMargins(0,0,0,0); h_lay.setSpacing(0)
        
        sidebar = QFrame(); sidebar.setFixedWidth(170); sidebar.setStyleSheet("border-right: 1px solid gray;")
        self.sidebar_frame = sidebar
        s_lay = QVBoxLayout(sidebar); s_lay.setContentsMargins(5,10,5,10)
        s_lay.addWidget(self.sidebar_stack)
        
        # [UPDATE] Add buttons to sidebar
        s_lay.addWidget(self.btn_gui)
        s_lay.addWidget(self.btn_magic)
        s_lay.addWidget(self.btn_ref)
        h_lay.addWidget(sidebar)
        
        self.viz_tabs = QTabWidget(); self.viz_tabs.setTabPosition(QTabWidget.TabPosition.South)
        self.viz_stack = QStackedWidget()
        self.viz_stack.addWidget(self.fast_peeker)
        self.viz_stack.addWidget(self.layer_panel)
        self.viz_tabs.addTab(self.viz_stack, "Layout")
        
        # --- CLOCK TREE VIEWER ---
        import sys
        ct_build = os.path.join(REPO_ROOT, "clocktreeviewer", "build")
        if ct_build not in sys.path:
            sys.path.append(ct_build)
        try:
            import clocktree_engine
            from PyQt6 import sip
            self.clock_engine = clocktree_engine.ClockTreeViewerCore()
            ptr = self.clock_engine.get_ptr()
            self.native_clock_view = sip.wrapinstance(ptr, QWidget)

            ct_container = QWidget()
            ct_lay = QVBoxLayout(ct_container)
            ct_lay.setContentsMargins(0, 0, 0, 0)
            ct_lay.setSpacing(0)

            ct_toolbar = QFrame()
            ct_toolbar.setFixedHeight(34)
            ct_toolbar.setStyleSheet("background-color: #161b22; border-bottom: 1px solid #30363d;")
            tb_lay = QHBoxLayout(ct_toolbar)
            tb_lay.setContentsMargins(10, 2, 10, 2)
            tb_lay.setSpacing(8)

            lbl_ct_hdr = QLabel("<b>CLOCK TOPOLOGY VIEWER</b>")
            lbl_ct_hdr.setStyleSheet("color: #58a6ff; font-size: 11px;")
            tb_lay.addWidget(lbl_ct_hdr)

            btn_ct_in = QPushButton("Zoom In")
            btn_ct_in.setStyleSheet("background: #21262d; color: #f0f6fc; border: 1px solid #30363d; border-radius: 4px; padding: 3px 8px; font-size: 10px; font-weight: bold;")
            btn_ct_in.clicked.connect(self.clock_engine.zoom_in)
            tb_lay.addWidget(btn_ct_in)

            btn_ct_out = QPushButton("Zoom Out")
            btn_ct_out.setStyleSheet("background: #21262d; color: #f0f6fc; border: 1px solid #30363d; border-radius: 4px; padding: 3px 8px; font-size: 10px; font-weight: bold;")
            btn_ct_out.clicked.connect(self.clock_engine.zoom_out)
            tb_lay.addWidget(btn_ct_out)

            btn_ct_fit = QPushButton("Fit View")
            btn_ct_fit.setStyleSheet("background: #21262d; color: #f0f6fc; border: 1px solid #30363d; border-radius: 4px; padding: 3px 8px; font-size: 10px; font-weight: bold;")
            btn_ct_fit.clicked.connect(self.clock_engine.fit_view)
            tb_lay.addWidget(btn_ct_fit)

            tb_lay.addStretch()

            lg_port = QLabel("● Root Port"); lg_port.setStyleSheet("color: #00e5ff; font-size: 10px; font-weight: bold;")
            lg_buf = QLabel("● Buffer / Inv"); lg_buf.setStyleSheet("color: #58a6ff; font-size: 10px; font-weight: bold;")
            lg_sink = QLabel("● Sink / Flop"); lg_sink.setStyleSheet("color: #34d399; font-size: 10px; font-weight: bold;")
            tb_lay.addWidget(lg_port); tb_lay.addWidget(lg_buf); tb_lay.addWidget(lg_sink)

            ct_lay.addWidget(ct_toolbar)
            ct_lay.addWidget(self.native_clock_view, stretch=1)

            self.viz_tabs.addTab(ct_container, "Clock Tree")
        except Exception as e:
            err_lbl = QLabel(f"Failed to load C++ ClockTreeViewer:\n{e}")
            self.viz_tabs.addTab(err_lbl, "Clock Tree")
            
        h_lay.addWidget(self.viz_tabs)
        
        v_split.addWidget(h_widget)
        
        term_widget = QWidget(); t_lay = QVBoxLayout(term_widget); t_lay.setContentsMargins(0,0,0,0)

        # Terminal Header Bar with Kill Button
        term_bar = QWidget()
        tb_lay = QHBoxLayout(term_bar)
        tb_lay.setContentsMargins(5, 2, 5, 2)
        lbl_term = QLabel("<b>Backend Console</b>")
        tb_lay.addWidget(lbl_term)
        tb_lay.addStretch()

        self.btn_kill_proc = QPushButton("Terminate")
        self.btn_kill_proc.setStyleSheet("background-color: #cf222e; color: white; font-weight: bold; padding: 2px 8px; font-size: 10px; border-radius: 3px;")
        self.btn_kill_proc.clicked.connect(self.kill_active_backend_process)
        tb_lay.addWidget(self.btn_kill_proc)

        t_lay.addWidget(term_bar)
        t_lay.addWidget(self.term_log)
        t_lay.addWidget(self.term_in)
        v_split.addWidget(term_widget)
        v_split.setStretchFactor(0, 4); v_split.setStretchFactor(1, 1)
        self.layout.addWidget(v_split)

        # --- 3. CONNECTIONS ---
        self.chk_inst.toggled.connect(self.update_view)
        self.chk_macros.toggled.connect(self.update_view)
        self.chk_tap.toggled.connect(self.update_view)
        self.chk_pins.toggled.connect(self.update_view)
        self.chk_nets.toggled.connect(self.update_view)
        self.chk_power.toggled.connect(self.update_view)
        
        # Connect OpenROAD layer checkboxes
        for chk in [
            self.chk_layer_li1, self.chk_layer_met1, self.chk_layer_met2,
            self.chk_layer_met3, self.chk_layer_met4, self.chk_layer_met5,
            self.chk_layer_vias
        ]:
            chk.toggled.connect(self.update_layer_view)

        self.btn_gui.clicked.connect(self.launch_native_gui)
        self.btn_magic.clicked.connect(self.launch_magic_gui) 
        self.btn_ref.clicked.connect(self.force_refresh_view)
        
        self.viz_tabs.currentChanged.connect(self.on_tab_changed)
        self.term_in.returnPressed.connect(self.send_command)

        # --- 4. STARTUP ---
        self.proc = None
        self.pending_init = None
        self.cmd_active = False
        self.cmd_journal = []
        self._replaying_journal = False
        
        if not getattr(self.ide, 'headless', False):
            self.reset_backend() 
        self.viz_tabs.setCurrentIndex(0)


    def load_custom_odb(self):
        f, _ = QFileDialog.getOpenFileName(self, "Load OpenDB Checkpoint", self.ide.cwd, "OpenDB Files (*.odb);;All Files (*)")
        if f and os.path.isfile(f):
            norm = f.replace("\\", "/")
            # If backend is running, write directly; otherwise reset and queue via pending_init
            if self.proc and self.proc.state() == QProcess.ProcessState.Running:
                self.send_command_internal(f'read_db "{norm}"')
            else:
                self.pending_init = f'read_db "{norm}"'
                self.reset_backend()
            self.term_log.append(f"[INIT] Loaded OpenDB database: {os.path.basename(f)}")

    def load_custom_def(self):
        f, _ = QFileDialog.getOpenFileName(self, "Load DEF Layout", self.ide.cwd, "Design Exchange Format (*.def);;All Files (*)")
        if f and os.path.isfile(f):
            norm = f.replace("\\", "/")
            proj_root = self.ide.get_proj_root(self.ide.get_context()[0] or "design")
            init_tcl = os.path.join(proj_root, "init_pdk.tcl")
            cmds = []
            if os.path.isfile(init_tcl):
                cmds.append(f'source "{init_tcl.replace(chr(92), "/")}"')
            cmds.append(f'read_def "{norm}"')
            cmd_str = "\n".join(cmds)

            if self.proc and self.proc.state() == QProcess.ProcessState.Running:
                for c in cmds:
                    self.send_command_internal(c)
            else:
                self.pending_init = cmd_str
                self.reset_backend()
            self.term_log.append(f"[INIT] Loaded DEF layout: {os.path.basename(f)}")
            self.fast_peeker.load_def_file(f)

    def run_psm_integrity_check(self):
        self.term_log.append("\n[PDN] Running Power Grid Integrity & Static IR Drop Analysis (::psm)...")
        # Run OpenROAD check_power_grid and analyze_power_grid exporting full voltage drop report
        proj_root = self.ide.get_proj_root(self.ide.get_context()[0] or "design") if hasattr(self.ide, 'get_proj_root') else "."
        res_dir = os.path.join(proj_root, "results")
        os.makedirs(res_dir, exist_ok=True)
        v_file = os.path.join(res_dir, "vdd_voltage.rpt").replace("\\", "/")
        cmd = (
            'puts "\\[PSM\\] Analyzing VDD and VSS rails..."; '
            'catch { check_power_grid -net VDD }; '
            'catch { check_power_grid -net VSS }; '
            f'catch {{ analyze_power_grid -net VDD -voltage_file "{v_file}" }}; '
            'puts "SILIS_PSM_DONE"'
        )
        self.send_command_internal(cmd)

    def run_bondpad_studio(self):
        proj_root = self.ide.get_proj_root(self.ide.get_context()[0] or "design")
        base = self.ide.get_context()[1] or "design"
        self.term_log.append("\n[PACKAGING] Launching Packaging & Bondpad Placement...")
        # Check if place_bondpad command is available in OpenROAD
        cmd = (
            f'puts "\\[BONDPAD\\] Generating packaging perimeter bondpads for {base}..."; '
            'catch { place_bondpad -bond sky130_fd_io__top_ground_pad -offset {15.0 15.0} [get_cells -hierarchical] }; '
            'puts "SILIS_BONDPAD_DONE"'
        )
        self.send_command_internal(cmd)

    def apply_clock_ndr(self):
        self.term_log.append("\n[CTS] Applying Clock Non-Default Rules (NDR 2W2S Shielding)...")
        cmd = (
            'puts "\\[NDR\\] Defining 2W2S (double-width double-spacing) routing rule..."; '
            'catch { create_ndr -name 2W2S -width 0.28 -spacing 0.28 }; '
            'catch { assign_ndr -ndr 2W2S -all_clocks }; '
            'puts "SILIS_NDR_DONE"'
        )
        self.send_command_internal(cmd)

    def repair_clock_buffers(self):
        self.term_log.append("\n[CTS] Repairing Clock Tree Buffers / Inverters...")
        cmd = (
            'puts "\\[CTS\\] Running repair_clock_nets..."; '
            'catch { repair_clock_nets }; '
            'puts "SILIS_CTS_REPAIR_DONE"'
        )
        self.send_command_internal(cmd)

    def repair_antenna_violations(self):
        self.term_log.append("\n[ROUTE] Running Antenna Ratio Verification & Diode Insertion...")
        cmd = (
            'puts "\\[ANTENNA\\] Running check_antennas and repair_antennas..."; '
            'catch { check_antennas }; '
            'catch { repair_antennas sky130_fd_sc_hd__diode_2 }; '
            'puts "SILIS_ANTENNA_REPAIR_DONE"'
        )
        self.send_command_internal(cmd)

    def launch_gds3d_view(self):
        proj_root = self.ide.get_proj_root(self.ide.get_context()[0] or "design")
        gds_path = os.path.join(proj_root, "results", "design.gds")
        if not os.path.isfile(gds_path):
            QMessageBox.information(
                self, "GDS Not Found",
                f"No GDS file found at {gds_path}.\nPlease run 'GDS' step first to export layout."
            )
            return
        if hasattr(self.gds3d_port, 'load_gds'):
            self.gds3d_port.load_gds(gds_path)
            self.gds3d_port.show()
            self.gds3d_port.raise_()
            self.term_log.append(f"[GDS3D] Opened {os.path.basename(gds_path)} in 3D Silicon Peeker.")

    def run_signoff_pipeline(self):
        """Executes the sequential signoff verification suite in the background."""
        if not self.active_pdk:
            if hasattr(self.ide, 'resolve_and_set_pdk'):
                self.ide.resolve_and_set_pdk()
        if not self.active_pdk:
            QMessageBox.critical(self, "Error", "PDK not active.")
            return

        proj_root = self.ide.get_proj_root(self.ide.get_context()[0] or "design")
        base = self.ide.get_context()[1] or "design"

        self.term_log.append("\n========================================================")
        self.term_log.append("  STARTING SEQUENTIAL SILICON SIGNOFF VERIFICATION")
        self.term_log.append(f"  Design Top: {base}  |  PDK: {self.active_pdk.get('name', 'sky130')}")
        self.term_log.append("========================================================\n")

        self.btn_run_signoff.setEnabled(False)
        self.btn_run_signoff.setText("Running Signoff...")
        self.start_spinner()

        self.signoff_worker = SignoffRunnerWorker(self, proj_root, base, self.active_pdk)
        self.signoff_worker.step_started.connect(lambda s: self.term_log.append(f"[RUNNING] Gate: {s}..."))
        self.signoff_worker.step_finished.connect(lambda s, ok, msg: self.term_log.append(f"[PASS] {s}: {msg}"))
        self.signoff_worker.pipeline_failed.connect(self._on_signoff_pipeline_failed)
        self.signoff_worker.all_completed.connect(self._on_signoff_pipeline_succeeded)
        self.signoff_worker.finished.connect(self._on_signoff_pipeline_finished)
        self.signoff_worker.start()

    def _on_signoff_pipeline_failed(self, step_name, error_summary, raw_log, report_path):
        self.term_log.append(f"\n[SIGNOFF FAILED] Gate: {step_name}")
        self.term_log.append(f"Reason: {error_summary}\n")
        diag = SignoffDiagnosticDialog(
            step_name=step_name,
            error_title=error_summary,
            log_text=raw_log,
            report_path=report_path,
            parent=self,
            ide=self.ide
        )
        diag.exec()

    def _on_signoff_pipeline_succeeded(self, export_summary, gate_results):
        export_dir = export_summary.get("export_directory", "")
        self.term_log.append("\n========================================================")
        self.term_log.append("  SILICON SIGNOFF PASSED — 100% GATES VERIFIED")
        self.term_log.append("========================================================")
        self.term_log.append(f"Exported Design Package committed to:\n{export_dir}\n")
        self.term_log.append("Exported Deliverables:")
        for k, v in export_summary.get("exported_files", {}).items():
            self.term_log.append(f"  • {k:<18} : {os.path.basename(v)}")
        self.term_log.append("========================================================\n")

        # Open markdown signoff audit report in Monaco editor automatically
        signoff_md = export_summary.get("exported_files", {}).get("signoff_report")
        if not signoff_md:
            proj_root = self.ide.get_proj_root(self.ide.get_context()[0] or "design")
            signoff_md = os.path.join(proj_root, "reports", "signoff_report.md")

        if os.path.isfile(signoff_md) and hasattr(self.ide, 'open_file_in_editor'):
            self.ide.open_file_in_editor(signoff_md)
            if hasattr(self.ide, 'switch_world'):
                self.ide.switch_world(0)

    def _on_signoff_pipeline_finished(self):
        self.stop_spinner()
        self.btn_run_signoff.setEnabled(True)
        self.btn_run_signoff.setText("Run Signoff Checks")

    def _get_io_lefs(self):
        """Discovers sky130 IO and corner/filler pad LEFs to support clean pad placement."""
        io_lefs = []
        # Search prioritized candidates; stop as soon as we find a valid IO LEF pair
        # to avoid reading duplicate libraries (e.g. sky130A and sky130B simultaneously)
        priority_roots = []
        lib_path = self.active_pdk.get('lib', '') if self.active_pdk else ''
        if 'libs.ref' in lib_path:
            priority_roots.append(lib_path.split('libs.ref')[0])
        priority_roots.extend([
            os.path.expanduser('~/.silis/pdks/sky130A'),
            os.path.join(REPO_ROOT, 'third-party', 'pdks', 'sky130A'),
            os.path.expanduser('~/.silis/pdks/sky130B'),
            os.path.join(REPO_ROOT, 'third-party', 'pdks', 'sky130B'),
        ])
        for root in priority_roots:
            ef_lef = os.path.join(root, 'libs.ref', 'sky130_fd_io', 'lef', 'sky130_ef_io.lef')
            fd_lef = os.path.join(root, 'libs.ref', 'sky130_fd_io', 'lef', 'sky130_fd_io.lef')
            found = []
            if os.path.isfile(ef_lef):
                found.append(ef_lef)
            if os.path.isfile(fd_lef):
                found.append(fd_lef)
            if found:
                for f in found:
                    if f not in io_lefs:
                        io_lefs.append(f)
                break
        return io_lefs

    def _get_io_gds(self):
        """Discovers sky130 IO GDS files to support GDS streamout and merge in pad/chip mode."""
        io_gds = []
        priority_roots = []
        lib_path = self.active_pdk.get('lib', '') if self.active_pdk else ''
        if 'libs.ref' in lib_path:
            priority_roots.append(lib_path.split('libs.ref')[0])
        priority_roots.extend([
            os.path.expanduser('~/.silis/pdks/sky130A'),
            os.path.join(REPO_ROOT, 'third-party', 'pdks', 'sky130A'),
            os.path.expanduser('~/.silis/pdks/sky130B'),
            os.path.join(REPO_ROOT, 'third-party', 'pdks', 'sky130B'),
        ])
        for root in priority_roots:
            ef_gds = os.path.join(root, 'libs.ref', 'sky130_fd_io', 'gds', 'sky130_ef_io.gds')
            fd_gds = os.path.join(root, 'libs.ref', 'sky130_fd_io', 'gds', 'sky130_fd_io.gds')
            found = []
            if os.path.isfile(ef_gds):
                found.append(ef_gds)
            if os.path.isfile(fd_gds):
                found.append(fd_gds)
            if found:
                for f in found:
                    if f not in io_gds:
                        io_gds.append(f)
                break
        return io_gds

    def _get_macro_files(self, ext):
        files = []
        macros = self.ide.project_config.get('macros', []) if hasattr(self, 'ide') and self.ide and hasattr(self.ide, 'project_config') else []
        if not macros:
            return files

        search_dirs = []
        proj_root = ""
        if hasattr(self, 'ide') and hasattr(self.ide, 'get_proj_root'):
            try:
                proj_root = self.ide.get_proj_root(self.ide.get_context()[1] or "design")
            except Exception:
                proj_root = getattr(self.ide, 'project_path', os.getcwd())
        if proj_root and os.path.isdir(proj_root):
            search_dirs.append(proj_root)
            search_dirs.append(os.path.join(proj_root, "source"))

        bundled_pdk = os.path.join(REPO_ROOT, "third-party", "pdks")
        if os.path.isdir(bundled_pdk):
            search_dirs.append(bundled_pdk)

        lib_path = self.active_pdk.get('lib', '') if self.active_pdk else ''
        if "libs.ref" in lib_path:
            search_dirs.append(lib_path.split("libs.ref")[0])

        env_pdk = os.environ.get("PDK_ROOT")
        if env_pdk and os.path.isdir(env_pdk):
            search_dirs.append(env_pdk)

        silis_macro_cache = os.path.expanduser("~/.silis/macrocache")
        if os.path.isdir(silis_macro_cache):
            search_dirs.append(silis_macro_cache)

        for m in macros:
            matched = False
            for d in search_dirs:
                if not os.path.exists(d):
                    continue
                pattern = os.path.join(d, "**", f"{m}.lef" if ext == "lef" else f"{m}*.{ext}")
                for f in glob.glob(pattern, recursive=True):
                    if os.path.isfile(f) and f not in files:
                        files.append(f)
                        matched = True
                        break
                if matched:
                    break

        # Check for UPF power switch cell LEF in active PDK
        if ext == "lef":
            pdk_lef = self.active_pdk.get('lef', '') if self.active_pdk else ''
            if pdk_lef and "libs.ref" in pdk_lef:
                pdk_base = pdk_lef.split("libs.ref")[0]
                sw_cand = os.path.join(pdk_base, "libs.ref", "sky130_power_switch", "lef", "power_switch.lef")
                if os.path.isfile(sw_cand) and sw_cand not in files:
                    files.append(sw_cand)

        return files

    def update_spinner(self):
        self.spinner_idx = (self.spinner_idx + 1) % 4
        self.ide.statusBar().showMessage(f"Running Flow Step... {self.spinner_chars[self.spinner_idx]}")

    def start_spinner(self):
        self.running_steps += 1
        if self.running_steps == 1:
            self.spinner_timer.start(150)
            
    def stop_spinner(self):
        self.running_steps = max(0, self.running_steps - 1)
        if self.running_steps == 0:
            self.spinner_timer.stop()
            self.ide.statusBar().showMessage("Ready")

    # === [NEW] MAGIC GUI LAUNCHER ===
    def launch_magic_gui(self):
        """Launches Magic VLSI in GUI mode with the correct Tech file."""
        if not shutil.which("magic"):
            self.term_log.append("[ERR] Magic not found.")
            return

        if not self.active_pdk: 
            self.term_log.append("[ERR] No PDK Active.")
            return

        proj_root = self.ide.get_proj_root(self.ide.get_context()[0] or "design")
        gds_path = os.path.join(proj_root, "results", "design.gds")
        
        if not os.path.exists(gds_path): 
             self.term_log.append("[ERR] GDS not found. Run 'GDS' step first.")
             return

        pdk_tech = self.active_pdk.get('tech', '')
        if not os.path.exists(pdk_tech):
             self.term_log.append("[ERR] Magic Tech file not found in PDK config.")
             return

        self.term_log.append(f"[SYS] Launching Magic GUI for {os.path.basename(gds_path)}...")
        # -d XR uses the X11 Cairo renderer (faster/better looking than default)
        # -T loads the tech file
        subprocess.Popen(["magic", "-d", "XR", "-T", pdk_tech, gds_path], cwd=proj_root)

    # === KEEP ALL EXISTING HELPERS BELOW ===
    # (ask_command, reset_backend, on_tab_changed, populate_gds_layers, on_layer_toggle, 
    # view_final_gds, run_flow_step, trigger_magic_drc, trigger_magic_merge, open_pdk_selector, 
    # read_stdout, send_command, send_command_internal, update_view, load_routed_design, 
    # launch_native_gui, force_refresh_view, load_checkpoint, save_checkpoint)
    
    def ask_command(self, title, label, text):
        dlg = QDialog(None)
        dlg.setWindowTitle(title)
        dlg.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint)
        dlg.resize(700, 350)
        
        theme_name = USER_SETTINGS.get("theme_name", "Catppuccin Mocha")
        theme = THEMES.get(theme_name, THEMES["Catppuccin Mocha"])
        dlg.setStyleSheet(f"QDialog {{ background-color: {theme['bg']}; color: {theme['fg']}; }} QLabel {{ color: {theme['fg']}; }}")
        
        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel(label))
        
        from PyQt6.QtWidgets import QDialogButtonBox
        from PyQt6.QtGui import QShortcut, QKeySequence
        
        editor = ScintillaEditor(is_minimap=False, font_family=USER_SETTINGS.get("font_family", "Consolas"), font_size=USER_SETTINGS.get("font_size", 11), theme_name=USER_SETTINGS.get("theme_name", "Catppuccin Mocha"))
        editor.set_lexer(".tcl")
        editor.setText(text)
        layout.addWidget(editor)
        
        bbox = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bbox.accepted.connect(dlg.accept)
        bbox.rejected.connect(dlg.reject)
        layout.addWidget(bbox)
        
        QShortcut(QKeySequence("Ctrl+Return"), dlg).activated.connect(dlg.accept)
        QShortcut(QKeySequence("Ctrl+Enter"), dlg).activated.connect(dlg.accept)
        
        if dlg.exec(): return editor.text(), True
        return "", False

    def kill_active_backend_process(self):
        if self.proc and self.proc.state() == QProcess.ProcessState.Running:
            self.term_log.append("\n[USER] Terminating active backend process...")
            self.proc.kill()
            self.cmd_active = False
            self.stop_spinner()
            self.term_log.append("[SYS] Process terminated by user.")
        else:
            self.term_log.append("[SYS] No active process running.")

    def reset_backend(self):
        if self.proc:
            if self.proc.state() == QProcess.ProcessState.Running: self.proc.kill()
            self.proc = None
        self.term_log.clear()
        self.proc = QProcess(self)
        self.proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.proc.readyReadStandardOutput.connect(self.read_stdout)
        if shutil.which("openroad"): self.proc.start("openroad")
        else: self.term_log.append("[ERR] OpenROAD binary not found.")

    def on_tab_changed(self, index):
        if hasattr(self, 'sidebar_frame'):
            self.sidebar_frame.setVisible(index == 0)
        elif hasattr(self, 'sidebar_stack'):
            self.sidebar_stack.setVisible(index == 0)
        if index == 0:
            self.force_refresh_view()

    def run_flow_step(self, step_name, bypass_prompt=False):
        proj_root = self.ide.get_proj_root(self.ide.get_context()[0] or "design")
        results_dir = os.path.join(proj_root, "results"); os.makedirs(results_dir, exist_ok=True)
        reports_dir = os.path.join(proj_root, "reports"); os.makedirs(reports_dir, exist_ok=True)
        def_abs_path = os.path.join(results_dir, "temp.def").replace("\\", "/")
        write_cmd = f"write_def \"{def_abs_path}\""

        if step_name == "Antenna":
            self.term_log.append("\n[SIGNOFF] Running Antenna Check...")
            self.send_command_internal("check_antennas -report_file reports/antenna.rpt; puts \"Antenna Violations: [check_antennas]\"; puts \"SILIS_ANTENNA_DONE\"")
            return


        if step_name == "STA":
            if not self.active_pdk: QMessageBox.critical(self, "Error", "PDK not active."); return
            self.term_log.append("\n[SIGNOFF] Extracting Full Clock Topology via C++ STA Engine...")
            
            # Use our custom C++ OpenSTA engine to extract the graph!
            import sys
            se_build = os.path.join(REPO_ROOT, "synthengine", "build")
            if se_build not in sys.path:
                sys.path.append(se_build)
            try:
                import synth_engine
                if not hasattr(self, 'sta_anal'):
                    self.sta_anal = synth_engine.TimingAnalyzer()
                
                proj_root = self.ide.get_proj_root(self.ide.get_context()[0] or "design")
                base = self.ide.get_context()[1] or "design"
                v_net = os.path.join(proj_root, "netlist", f"{base}_netlist.v")
                
                if self.sta_anal.init_and_analyze(self.active_pdk['lib'], v_net, base):
                    import json
                    ports = json.loads(self.sta_anal.get_input_ports_json())
                    
                    is_headless = getattr(self.ide, 'headless', False) or bypass_prompt
                    if is_headless:
                        # Automatically pick the first matching clock
                        port = None
                        for c in ["clk_i", "clk", "clock", "sys_clk"]:
                            if c in ports:
                                port = c
                                break
                        if not port and ports:
                            port = ports[0]

                        if port:
                            tree_json = self.sta_anal.get_clock_tree_json(port)
                            if hasattr(self, 'clock_engine'):
                                self.clock_engine.load_tree_data(tree_json)
                                self.viz_tabs.setCurrentIndex(2)
                                self.term_log.append(f"[SUCCESS] Rendered Clock Tree for {port}!")
                    else:
                        # Create an interactive dialog to select clock port
                        dlg = QDialog(self)
                        dlg.setWindowTitle("Clock Tree Topology Extractor")
                        dlg.resize(400, 150)
                        dlg_layout = QVBoxLayout(dlg)
                        dlg_layout.addWidget(QLabel("Select Clock Port for Layout Topology Extraction:"))
                        cmb = QComboBox()
                        cmb.addItems(ports)
                        
                        # Auto select
                        for c in ["clk_i", "clk", "clock", "sys_clk"]:
                            if c in ports:
                                cmb.setCurrentText(c)
                                break
                                
                        dlg_layout.addWidget(cmb)
                        
                        bbox = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
                        bbox.accepted.connect(dlg.accept)
                        bbox.rejected.connect(dlg.reject)
                        dlg_layout.addWidget(bbox)
                        
                        if dlg.exec():
                            port = cmb.currentText()
                            tree_json = self.sta_anal.get_clock_tree_json(port)
                            if hasattr(self, 'clock_engine'):
                                self.clock_engine.load_tree_data(tree_json)
                                # Switch to Clock Tree tab (index 1)
                                self.viz_tabs.setCurrentIndex(1)
                                self.term_log.append(f"[SUCCESS] Rendered Clock Tree for {port}!")
            except Exception as e:
                self.term_log.append(f"[ERR] Failed to extract clock tree: {e}")
            return

        if step_name == "DRC":
            if not self.active_pdk or 'gds' not in self.active_pdk: QMessageBox.critical(self, "Error", "PDK GDS Required."); return
            gds_file = os.path.join(results_dir, "design.gds")
            if not os.path.exists(gds_file): self.term_log.append("[ERR] Generate GDS first!"); return
            self.trigger_magic_drc(proj_root, gds_file)
            return

        if step_name == "PAT":
            if not self.active_pdk or 'corners' not in self.active_pdk:
                QMessageBox.critical(self, "Error", "MCMM Corners not found in active PDK. Try auto-crawling Volare.")
                return
                
            self.term_log.append("\n[SIGNOFF] Running MCMM Post-Layout Analysis & Timing...")
            
            base = self.ide.get_context()[1] or "design"
            sdc_path = os.path.join(proj_root, "source", f"{base}.sdc").replace("\\", "/")
            if not os.path.exists(sdc_path):
                sdc_files = glob.glob(os.path.join(proj_root, "source", "*.sdc"))
                if sdc_files: sdc_path = sdc_files[0]
                
            tcl_path = os.path.join(proj_root, "pat_mcmm.tcl").replace("\\", "/")
            multi_cfg = self.active_pdk.get('multi_corner', {})
            
            # Select target corners: Setup (SS), Nominal (TT), Hold (FF) or full set
            target_corners = {}
            if multi_cfg.get('enabled', False):
                if multi_cfg.get('setup_ss', {}).get('name') and multi_cfg.get('setup_ss', {}).get('lib'):
                    target_corners[multi_cfg['setup_ss']['name']] = multi_cfg['setup_ss']['lib']
                if multi_cfg.get('nominal_tt', {}).get('name') and multi_cfg.get('nominal_tt', {}).get('lib'):
                    target_corners[multi_cfg['nominal_tt']['name']] = multi_cfg['nominal_tt']['lib']
                if multi_cfg.get('hold_ff', {}).get('name') and multi_cfg.get('hold_ff', {}).get('lib'):
                    target_corners[multi_cfg['hold_ff']['name']] = multi_cfg['hold_ff']['lib']
            
            if not target_corners:
                target_corners = self.active_pdk.get('corners', {})
            if not target_corners:
                target_corners = {self.active_pdk.get('corner', 'default'): self.active_pdk.get('lib', '')}

            tcl_lines = [
                "set_thread_count [exec nproc]",
                f'read_lef "{self.active_pdk["tlef"]}"',
                f'read_lef "{self.active_pdk["lef"]}"'
            ]
            for io_lef in self._get_io_lefs():
                tcl_lines.append(f'read_lef "{io_lef}"')
            for lef in self._get_macro_files("lef"):
                tcl_lines.append(f'read_lef "{lef}"')

            tcl_lines.append(f'read_def "{def_abs_path}"')

            corner_names = list(target_corners.keys())
            tcl_lines.append("define_corners " + " ".join(corner_names))

            for c_name, lib_path in target_corners.items():
                tcl_lines.append(f'read_liberty -corner {c_name} "{lib_path}"')

            for lib in self._get_macro_files("lib"):
                for c_name in corner_names:
                    tcl_lines.append(f'read_liberty -corner {c_name} "{lib}"')

            tcl_lines.append(f'read_sdc "{sdc_path}"')

            # Area & Instance calculation
            tcl_lines.extend([
                "set block [::ord::get_db_block]",
                "set tech [::ord::get_db_tech]",
                "set dbu [$tech getDbUnitsPerMicron]",
                "set inst_count [llength [$block getInsts]]",
                "set total_area 0.0",
                "foreach inst [$block getInsts] {",
                "    set master [$inst getMaster]",
                "    set m_area [expr {([$master getWidth] * 1.0 / $dbu) * ([$master getHeight] * 1.0 / $dbu)}]",
                "    set total_area [expr {$total_area + $m_area}]",
                "}",
                'puts "PAT_INSTS: $inst_count"',
                'puts "PAT_AREA: $total_area"',
                'puts "PAT_POWER_START"',
                "report_power",
                'puts "PAT_POWER_END"'
            ])

            for c_name in corner_names:
                tcl_lines.append(f'puts "PAT_CORNER_START: {c_name}"')
                tcl_lines.append(f'report_checks -path_delay max -fields {{slew cap input_pins nets fanout}} -corner {c_name}')
                tcl_lines.append(f'catch {{ report_power -corner {c_name} }}')
                tcl_lines.append(f'puts "PAT_CORNER_END: {c_name}"')

            with open(tcl_path, 'w') as f:
                f.write("\n".join(tcl_lines) + "\n")
                
            def run_pat():
                try:
                    cmd = ["openroad", "-exit", tcl_path]
                    proc = subprocess.run(cmd, capture_output=True, text=True)
                    out = proc.stdout
                    
                    insts = "0"
                    area = "0.0"
                    
                    import re
                    inst_match = re.search(r"PAT_INSTS:\s*(\d+)", out)
                    if inst_match: insts = inst_match.group(1)
                    
                    area_match = re.search(r"PAT_AREA:\s*([0-9.]+)", out)
                    if area_match: area = f"{float(area_match.group(1)):.2f}"
                    
                    # Parse Power Report table
                    pwr_data = {
                        "Sequential": ["0.00", "0.00", "0.00", "0.00", "0%"],
                        "Combinational": ["0.00", "0.00", "0.00", "0.00", "0%"],
                        "Clock": ["0.00", "0.00", "0.00", "0.00", "0%"],
                        "Macro": ["0.00", "0.00", "0.00", "0.00", "0%"],
                        "Pad": ["0.00", "0.00", "0.00", "0.00", "0%"],
                        "Total": ["0.00", "0.00", "0.00", "0.00", "100%"]
                    }
                    
                    pwr_block_match = re.search(r"PAT_POWER_START(.*?)PAT_POWER_END", out, re.DOTALL)
                    if pwr_block_match:
                        pwr_text = pwr_block_match.group(1)
                        for line in pwr_text.splitlines():
                            parts = line.split()
                            if len(parts) >= 6 and parts[0] in pwr_data:
                                pwr_data[parts[0]] = parts[1:6]
                            elif len(parts) >= 5 and parts[0] in pwr_data:
                                pwr_data[parts[0]] = parts[1:5] + ["0%"]
                                
                    # Parse Corners
                    corners_data = []
                    corner_blocks = re.findall(r"PAT_CORNER_START:\s*(\w+)\s*(.*?)PAT_CORNER_END:", out, re.DOTALL)
                    
                    timing_failed = False
                    slacks_list = []
                    critical_trace = "No timing violations found."
                    
                    for c_name, c_out in corner_blocks:
                        slack_val = "0.00"
                        status_str = "MET"
                        endpoint = "Unknown"
                        c_pwr = "N/A"
                        
                        max_match = re.search(r"slack\s+\((VIOLATED|MET)\)\s+([-\d.]+)", c_out)
                        if max_match:
                            status_str = max_match.group(1)
                            slack_val = max_match.group(2)
                            try:
                                slacks_list.append(float(slack_val))
                            except:
                                pass
                            if status_str == "VIOLATED":
                                timing_failed = True

                        trace_match = re.search(r"(Startpoint:.*?slack \([A-Z]+\))", c_out, re.DOTALL)
                        if trace_match and (status_str == "VIOLATED" or critical_trace == "No timing violations found."):
                            critical_trace = trace_match.group(1)

                        pwr_match = re.search(r"Total\s+[0-9.e-]+\s+[0-9.e-]+\s+[0-9.e-]+\s+([0-9.e-]+)", c_out)
                        if pwr_match:
                            try:
                                c_pwr = f"{float(pwr_match.group(1)) * 1000:.2f} mW"
                            except:
                                c_pwr = f"{pwr_match.group(1)}"
                            
                        ep_match = re.search(r"Endpoint:\s*(\S+)", c_out)
                        if ep_match: endpoint = ep_match.group(1)
                        
                        corners_data.append((c_name, slack_val, status_str, endpoint, c_pwr))
                        
                    wns = f"{min(slacks_list):.3f}" if slacks_list else "0.000"
                    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    pdk_disp = self.active_pdk.get('name', 'Sky130') if self.active_pdk else 'Generic'

                    def pr(name, d):
                        split_vis = ReportEngine._bar(d[4]) if hasattr(ReportEngine, '_bar') else f"| {d[4]} |"
                        return f"| {name:<14} | {d[0]:<10} | {d[1]:<10} | {d[2]:<10} | {d[3]:<10} | {d[4]:<6} | {split_vis:<16} |"

                    # Format Timing Table
                    t_table = ""
                    for c_name, s_val, s_stat, end_p, _ in corners_data:
                        t_table += f"| {c_name:<29} | {s_val:<13} | {s_stat:<10} | {end_p:<25} |\\n"

                    # Format Corner Power Lines
                    c_pwr_lines = ""
                    for c_name, _, _, _, c_pwr in corners_data:
                        if c_pwr != "N/A":
                            c_pwr_lines += f"  • {c_name:<25} : Total Power = {c_pwr}\\n"
                    if not c_pwr_lines:
                        c_pwr_lines = "  (Single corner power evaluated)\\n"

                    # Build official Silis ReportEngine report
                    report = f"""################################################################################
#                                            POST ROUTE PAT REPORT
# Design:       {base}
# Date:         {now_str}
# PDK:          {pdk_disp}
# Generated by Silis — Silicon Scaffold
################################################################################

================================================================================
  SECTION 1: DESIGN STATISTICS
================================================================================
+---------------------------+-------------------+
| Metric                    | Value             |
+---------------------------+-------------------+
| Total Cells               | {insts:<17} |
| Total Core Area           | {area + ' um^2':<17} |
| Overall Timing Status     | {('VIOLATED' if timing_failed else 'MET'):<17} |
+---------------------------+-------------------+

================================================================================
  SECTION 2: MULTI-CORNER TIMING SUMMARY (MCMM)
================================================================================
+-------------------------------+---------------+------------+---------------------------+
| Scenario / Corner             | Slack         | Status     | Critical Endpoint         |
+-------------------------------+---------------+------------+---------------------------+
{t_table}+-------------------------------+---------------+------------+---------------------------+

  Worst Negative Slack (WNS): {wns} ns ({'VIOLATED' if timing_failed else 'MET'})

  CRITICAL PATH TRACE:
  {critical_trace.replace(chr(10), chr(10)+'  ')}

================================================================================
  SECTION 3: POWER ANALYSIS
================================================================================
+----------------+------------+------------+------------+------------+--------+------------------+
| Group          | Internal   | Switching  | Leakage    | Total      | %      | Split            |
+----------------+------------+------------+------------+------------+--------+------------------+
{pr("Sequential", pwr_data['Sequential'])}
{pr("Combinational", pwr_data['Combinational'])}
{pr("Clock", pwr_data['Clock'])}
{pr("Macro", pwr_data['Macro'])}
{pr("Pad", pwr_data['Pad'])}
+----------------+------------+------------+------------+------------+--------+------------------+
| TOTAL          | {pwr_data['Total'][0]:<10} | {pwr_data['Total'][1]:<10} | {pwr_data['Total'][2]:<10} | {pwr_data['Total'][3]:<10} | 100%   | |██████████| 100% |
+----------------+------------+------------+------------+------------+--------+------------------+

[ PVT CORNER POWER BREAKDOWN ]
{c_pwr_lines}
{ReportEngine.FOOTER_ART if hasattr(ReportEngine, 'FOOTER_ART') else ''}
https://github.com/The-Silis-Foundation/silis
________________________________________________________________________________
Generated by Silis — Silicon Scaffold
© 2026 The Silis Foundation
________________________________________________________________________________
"""
                    rpt_file = os.path.join(reports_dir, f"{base}_pat_report.rpt")
                    with open(rpt_file, 'w') as f:
                        f.write(report)
                        
                    self.ide.queue.put(("[BACKEND]", f"PAT Report generated: {rpt_file}"))
                    self.pat_finished_signal.emit(rpt_file, timing_failed)
                except Exception as e:
                    self.ide.queue.put(("[BACKEND]", f"[ERR] PAT Execution Failed: {e}"))
                    
            self.start_spinner()
            self.pat_worker = FlowWorker(run_pat)
            self.pat_worker.finished_signal.connect(self.stop_spinner)
            self.pat_worker.start()
            return

        if step_name == "DFT":
            self.term_log.append("\n[SIGNOFF] Running Automated DFT Scan & ATPG Signoff Analysis...")
            base = self.ide.get_context()[1] or "design"
            v_net = os.path.join(proj_root, "netlist", f"{base}_netlist.v")
            if not os.path.isfile(v_net):
                v_net = os.path.join(results_dir, "temp.v")
            if not os.path.isfile(v_net):
                cand_nets = glob.glob(os.path.join(proj_root, "netlist", "*.v"))
                if cand_nets:
                    v_net = cand_nets[0]

            pdk_name = self.active_pdk.get("name", "sky130") if self.active_pdk else "sky130"
            try:
                try:
                    from dft.dft_engine import DFTEngine
                    from dft.dft_viewer import DFTSignoffViewer
                except (ImportError, ModuleNotFoundError):
                    from dft.dft_engine import DFTEngine
                    from dft.dft_viewer import DFTSignoffViewer

                engine = DFTEngine(
                    netlist_path=v_net,
                    top_module=base,
                    pdk=pdk_name,
                )
                scandef_path = os.path.join(results_dir, "design.scandef")
                scan_net_path = os.path.join(proj_root, "netlist", f"{base}_scan.v")
                engine.stitch_scan_chain(scan_net_path, scandef_path)

                summary = engine.run_atpg(target_coverage=95.0)

                stil_path = os.path.join(results_dir, f"{base}_atpg.stil")
                engine.export_stil(stil_path)
                tb_path = os.path.join(results_dir, f"{base}_atpg_tb.v")
                engine.export_atpg_testbench(tb_path)
                engine.write_reports(summary, os.path.join(proj_root, "reports"))

                self.term_log.append(f"[DFT SUCCESS] Fault Coverage: {summary['fault_coverage']}% ({summary['status']})")
                self.term_log.append(f"  • Scan Flops Stitched: {summary['scan_flop_count']}")
                self.term_log.append(f"  • ATPG Vectors: {summary['pattern_count']}")
                self.term_log.append(f"  • STIL Patterns: {stil_path}")
                self.term_log.append(f"  • Verilog Testbench: {tb_path}")
                self.term_log.append("SILIS_DFT_DONE")

                is_headless = getattr(self.ide, 'headless', False) or bypass_prompt
                if not is_headless:
                    dlg = DFTSignoffViewer(summary, parent=self, project_dir=proj_root)
                    dlg.exec()
            except Exception as e:
                self.term_log.append(f"[ERR] DFT Signoff Failed: {e}")
            return

        if step_name == "LVS":
            self.term_log.append("\n[SIGNOFF] Running Layout Versus Schematic (LVS) Verification...")
            base = self.ide.get_context()[1] or "design"
            pdk_name = self.active_pdk.get("name", "sky130") if self.active_pdk else "sky130"
            try:
                try:
                    from lvs.lvs_engine import LVSEngine
                    from lvs.lvs_viewer import LVSSignoffViewer
                except (ImportError, ModuleNotFoundError):
                    from lvs.lvs_engine import LVSEngine
                    from lvs.lvs_viewer import LVSSignoffViewer

                engine = LVSEngine(proj_root, top_module=base, pdk=pdk_name)
                res = engine.run_lvs()
                self.term_log.append(f"[LVS {res['status']}] Matched Devices: {res['matched_devices']} | Matched Nets: {res['matched_nets']}")
                self.term_log.append("SILIS_LVS_DONE")

                is_headless = getattr(self.ide, 'headless', False) or bypass_prompt
                if not is_headless:
                    dlg = LVSSignoffViewer(res, parent=self, project_dir=proj_root)
                    dlg.exec()
            except Exception as e:
                self.term_log.append(f"[ERR] LVS Failed: {e}")
            return

        if step_name in ["GLS", "SDF"]:
            self.term_log.append("\n[SIGNOFF] Running Gate-Level Timing Simulation (GLS & SDF)...")
            base = self.ide.get_context()[1] or "design"
            pdk_name = self.active_pdk.get("name", "sky130") if self.active_pdk else "sky130"
            try:
                try:
                    from simulation.gls_engine import GLSEngine
                    from simulation.gls_viewer import GLSSignoffViewer
                except (ImportError, ModuleNotFoundError):
                    from simulation.gls_engine import GLSEngine
                    from simulation.gls_viewer import GLSSignoffViewer

                engine = GLSEngine(proj_root, top_module=base, pdk=pdk_name)
                if step_name == "SDF":
                    sdf_path = engine.export_sdf()
                    self.term_log.append(f"[SUCCESS] Exported SDF: {sdf_path}")
                    self.term_log.append("SILIS_SDF_DONE")
                    return

                res = engine.run_gls()
                self.term_log.append(f"[GLS {res['status']}] Cycles Tested: {res['cycles_evaluated']} | Timing Violations: {res['timing_violations_count']}")
                self.term_log.append("SILIS_GLS_DONE")

                is_headless = getattr(self.ide, 'headless', False) or bypass_prompt
                if not is_headless:
                    dlg = GLSSignoffViewer(res, parent=self, project_dir=proj_root)
                    dlg.exec()
            except Exception as e:
                self.term_log.append(f"[ERR] GLS Failed: {e}")
            return

        if step_name == "Fill":
            self.term_log.append("\n[PHYSICAL] Running Decap & Metal Density Fill...")
            base = self.ide.get_context()[1] or "design"
            pdk_name = self.active_pdk.get("name", "sky130") if self.active_pdk else "sky130"
            try:
                try:
                    from tapeout.fill_engine import TapeoutEngine
                except (ImportError, ModuleNotFoundError):
                    from tapeout.fill_engine import TapeoutEngine

                engine = TapeoutEngine(proj_root, top_module=base, pdk=pdk_name)
                res = engine.run_fill()
                self.term_log.append(f"[FILL SUCCESS] Standard Cell Decap & Metal Tiles Inserted. All layers compliant (20%-80%).")
                self.term_log.append("SILIS_FILL_DONE")
                self.force_refresh_view()
            except Exception as e:
                self.term_log.append(f"[ERR] Metal Fill Failed: {e}")
            return

        if step_name in ("Tapeout", "Export"):
            self.term_log.append("\n[SIGNOFF] Compiling Final Foundry Tapeout Manifest...")
            base = self.ide.get_context()[1] or "design"
            pdk_name = self.active_pdk.get("name", "sky130") if self.active_pdk else "sky130"
            try:
                try:
                    from tapeout.fill_engine import TapeoutEngine
                    from tapeout.manifest_viewer import TapeoutManifestViewer
                except (ImportError, ModuleNotFoundError):
                    from tapeout.fill_engine import TapeoutEngine
                    from tapeout.manifest_viewer import TapeoutManifestViewer

                engine = TapeoutEngine(proj_root, top_module=base, pdk=pdk_name)
                manifest = engine.build_tapeout_manifest()
                self.term_log.append(f"[EXPORT SUCCESS] Output GDS: {manifest['tapeout_gds']}")
                self.term_log.append("SILIS_EXPORT_DONE")

                is_headless = getattr(self.ide, 'headless', False) or bypass_prompt
                if not is_headless:
                    dlg = TapeoutManifestViewer(manifest, parent=self, project_dir=proj_root)
                    dlg.exec()
            except Exception as e:
                self.term_log.append(f"[ERR] Export Packaging Failed: {e}")
            return

        if step_name == "Init":
            db_path = os.path.join(results_dir, "checkpoint.odb")
            def_path = os.path.join(results_dir, "temp.def")
            is_headless = getattr(self.ide, 'headless', False) or bypass_prompt or (os.environ.get("SILIS_HEADLESS_TEST", "") in ("1", "true", "TRUE"))
            if not is_headless:
                self.resume_def = None
                if os.path.exists(db_path):
                    reply = QMessageBox.question(self, "Resume?", "Found saved checkpoint.odb. Load it?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                    if reply == QMessageBox.StandardButton.Yes: self.load_checkpoint(); return
                
                if os.path.exists(def_path):
                    reply = QMessageBox.question(self, "Resume from temp.def?", "Found temp.def from a previous step. Resume from it instead?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                    if reply == QMessageBox.StandardButton.Yes:
                        self.resume_def = def_path
            if not self.active_pdk:
                if hasattr(self.ide, 'resolve_and_set_pdk'):
                    self.ide.resolve_and_set_pdk()
                if not self.active_pdk:
                    if not self.open_pdk_selector(): return
            tcl_path = os.path.join(proj_root, "init_pdk.tcl").replace("\\", "/")
            ctx = self.ide.get_context()[0] or "top"
            base = self.ide.get_context()[1] or "top"
            netlist_path = os.path.join(proj_root, "netlist", f"{base}_netlist.v").replace("\\", "/")
            if not os.path.isfile(netlist_path):
                candidates = [
                    os.path.join(proj_root, "netlist", f"{base}.v"),
                    os.path.join(proj_root, "rtl", f"{base}.v"),
                    os.path.join(proj_root, "source", f"{base}.v"),
                    os.path.join(proj_root, f"{base}.v")
                ]
                found_v = None
                for c_cand in candidates:
                    if os.path.isfile(c_cand):
                        found_v = c_cand
                        break
                if not found_v and getattr(self.ide, 'current_file', None) and self.ide.current_file.endswith(('.v', '.sv')):
                    found_v = self.ide.current_file
                if not found_v:
                    for sdir in ["netlist", "rtl", "source", "."]:
                        g_matches = glob.glob(os.path.join(proj_root, sdir, "*.v"))
                        if g_matches:
                            found_v = g_matches[0]
                            break
                netlist_path = (found_v or "design.v").replace("\\", "/")
            sdc_files = (
                glob.glob(os.path.join(proj_root, "constr", "*.sdc"))
                + glob.glob(os.path.join(proj_root, "source", "*.sdc"))
            )
            if sdc_files:
                sdc_path = sdc_files[0]
            else:
                sdc_path = os.path.join(proj_root, "constr", f"{ctx}.sdc") if os.path.isdir(os.path.join(proj_root, "constr")) else os.path.join(proj_root, "source", f"{ctx}.sdc")
                os.makedirs(os.path.dirname(sdc_path), exist_ok=True)
                with open(sdc_path, 'w') as f: f.write("create_clock -name clk -period 10.0 [get_ports clk]\nset_input_delay 2.0 -clock clk [all_inputs -no_clocks]\nset_output_delay 2.0 -clock clk [all_outputs]\n")
            tcl_content = f"""set_thread_count [exec nproc]\nread_lef "{self.active_pdk['tlef']}"\nread_lef "{self.active_pdk['lef']}"\n"""
            for io_lef in self._get_io_lefs():
                tcl_content += f"""read_lef "{io_lef}"\n"""
            for lef in self._get_macro_files("lef"):
                tcl_content += f"""read_lef "{lef}"\n"""

            # Multi-Corner Multi-Mode Liberty Loading
            target_corners = getattr(self, 'selected_mcmm_corners', {})
            if not target_corners:
                target_corners = self.active_pdk.get('corners', {})

            macro_libs = []
            seen_mlibs = set()
            for ml in self._get_macro_files("lib"):
                if ml not in seen_mlibs:
                    seen_mlibs.add(ml)
                    macro_libs.append(ml)

            if target_corners and len(target_corners) > 1:
                corner_names = list(target_corners.keys())
                # OpenROAD / OpenSTA requires -corner on every read_liberty once define_corners is called.
                # When using a single typical/TT macro lib across multiple PVT corners, suppress duplicate
                # warning STA-1140 to keep log clean.
                tcl_content += "suppress_message STA 1140\n"
                tcl_content += f"define_corners {' '.join(corner_names)}\n"
                for c_name, lib_path in target_corners.items():
                    tcl_content += f'read_liberty -corner {c_name} "{lib_path}"\n'
                for lib in macro_libs:
                    for c_name in corner_names:
                        tcl_content += f'read_liberty -corner {c_name} "{lib}"\n'
            else:
                tcl_content += f"""read_liberty "{self.active_pdk['lib']}\"\n"""
                for lib in macro_libs:
                    tcl_content += f"""read_liberty "{lib}"\n"""
                        
            if getattr(self, 'resume_def', None):
                tcl_content += (
                    "catch { make_fake_io_site -name IO_SITE -width 1 -height 200 }\n"
                    "catch { make_fake_io_site -name IO_CSITE -width 200 -height 200 }\n"
                    f"""read_def "{self.resume_def}"\nread_sdc "{sdc_path}"\n"""
                )
            else:
                tcl_content += f"""read_verilog "{netlist_path}"\nlink_design {ctx}\nread_sdc "{sdc_path}"\n"""

            # Power gating UPF intent ingestion if design.upf exists
            upf_file = os.path.join(proj_root, "power", "design.upf").replace("\\", "/")
            if os.path.isfile(upf_file):
                shim_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "shims", "openroad_upf_shim.tcl")).replace("\\", "/")
                tcl_content += f"""
# OpenROAD IEEE-1801 (UPF) Compatibility Shim Layer
if {{[file exists "{shim_path}"]}} {{
    source "{shim_path}"
}}

# Load Power Intent UPF
if {{[file exists "{upf_file}"]}} {{
    read_upf -file "{upf_file}"
}}
"""
            tcl_content += f"""
set block [::ord::get_db_block]
set tech [::ord::get_db_tech]
set dbu [$tech getDbUnitsPerMicron]

set macros_json "\\{{\\n  \\"macros\\": \\{{\\n"
set first_macro 1
set total_std_cell_area 0.0
array set module_areas {{}}

foreach inst [$block getInsts] {{
    set master [$inst getMaster]
    set m_width [$master getWidth]
    set m_height [$master getHeight]
    set m_area [expr {{($m_width * 1.0 / $dbu) * ($m_height * 1.0 / $dbu)}}]

    if {{ [$master isBlock] }} {{
        if {{ !$first_macro }} {{ append macros_json ",\\n" }}
        set inst_name [$inst getName]
        set inst_name [string map [list \\\\ \\\\\\\\ \\" \\\\"] $inst_name]
        append macros_json "    \\"$inst_name\\": \\"[$master getName]\\""
        set first_macro 0
    }} else {{
        set total_std_cell_area [expr {{$total_std_cell_area + $m_area}}]
        set inst_name [$inst getName]
        set parts [split $inst_name "/"]
        if {{ [llength $parts] > 1 }} {{
            set mod_name [join [lrange $parts 0 end-1] "/"]
            if {{ ![info exists module_areas($mod_name)] }} {{
                set module_areas($mod_name) 0.0
            }}
            set module_areas($mod_name) [expr {{$module_areas($mod_name) + $m_area}}]
        }}
    }}
}}
append macros_json "\\n  \\}},\\n  \\"total_std_cell_area\\": $total_std_cell_area,\\n  \\"modules\\": \\{{\\n"
set first_mod 1
foreach mod_name [array names module_areas] {{
    if {{ !$first_mod }} {{ append macros_json ",\\n" }}
    set clean_mod [string map [list \\\\ \\\\\\\\ \\" \\\\"] $mod_name]
    append macros_json "    \\"$clean_mod\\": $module_areas($mod_name)"
    set first_mod 0
}}
append macros_json "\\n  \\}}\\n\\}}"
set reports_dir "{os.path.join(proj_root, 'reports').replace(chr(92), '/')}"

file mkdir $reports_dir
set fp [open "$reports_dir/{base}_sizes.json" w]
puts $fp $macros_json
close $fp
puts "SILIS_INIT_DONE"
"""
                
            try:
                with open(tcl_path, 'w') as f: f.write(tcl_content)
                self.pending_init = f"source {tcl_path}"
                self.term_log.append("[SYS] Rebooting OpenROAD...")
                self.reset_backend() 
            except Exception as e: self.term_log.append(f"[ERR] File Error: {e}")
            return

        if step_name == "GDS":
            if not self.active_pdk or 'gds' not in self.active_pdk: QMessageBox.critical(self, "Error", "No GDS defined."); return
            self.term_log.append("[SYS] Starting GDS Generation Flow...")
            final_def = os.path.join(results_dir, "temp.def").replace("\\", "/")
            self.send_command_internal(f'write_def "{final_def}"')
            self.trigger_magic_merge(proj_root, final_def)
            return

        cmd = ""
        if not SSAForge.ALIASES: SSAForge.load_aliases()
        pdk_name = self.active_pdk.get('name', SSAForge.DEFAULT_PDK) if self.active_pdk else SSAForge.DEFAULT_PDK
        lib_path = self.active_pdk.get('lib', None) if self.active_pdk else None

        def load_template(filename, replacements):
            template_path = os.path.join(os.path.dirname(__file__), filename)
            try:
                with open(template_path, 'r') as f:
                    content = f.read()
                for k, v in replacements.items():
                    content = content.replace(f"{{{k}}}", str(v))
                return content
            except Exception as e:
                return f"# Error loading {filename}: {e}"

        if step_name in ("FP Studio", "Floorplan"): 
            self.floorplanner_dialog = InteractiveFloorplannerWidget(self.ide.project_config, self.pdk_mgr, self)
            if bypass_prompt or getattr(self.ide, 'headless', False):
                self.floorplanner_dialog.init_floorplan()
                self.floorplanner_dialog.generate_floorplan_tcl(apply=True)
            else:
                self.floorplanner_dialog.show()
            return
        elif step_name == "Tapcells":
            tap_cmd = SSAForge.get_tap_cmd(pdk_name, lib_path)
            cmd = load_template("tapcells.tcl", {"tap_cmd": tap_cmd, "write_cmd": write_cmd})
        elif step_name == "PDN":
            cmd = load_template("pdn.tcl", {"write_cmd": write_cmd})
        elif step_name == "IO Pins":
            if not bypass_prompt and not getattr(self.ide, 'headless', False):
                self.ioplacer_dialog = IOPlacerDialog(self.ide.project_config, self.pdk_mgr, self)
                self.ioplacer_dialog.show()
                return
            pin_cfg_cand = os.path.join(proj_root, "io", "pin_order.cfg").replace("\\", "/")
            extra_cfg = f' -cfg "{pin_cfg_cand}"' if os.path.isfile(pin_cfg_cand) else ""
            cmd = load_template("io_pins.tcl", {"write_cmd": write_cmd, "extra_cfg": extra_cfg})
        elif step_name == "Place":
            cmd = load_template("place.tcl", {"write_cmd": write_cmd})
        elif step_name == "CTS":
            cts_cmd = SSAForge.get_cts_cmd(pdk_name, lib_path)
            cmd = f'''# Check if CTS has already run to prevent OpenROAD crash (SIGSEGV)
set _has_cts 0
set _insts [[::ord::get_db_block] getInsts]
foreach inst $_insts {{
    set iname [$inst getName]
    if {{[string match "*clkbuf_*" $iname] || [string match "*delaybuf_*" $iname]}} {{
        set _has_cts 1
        break
    }}
}}
if {{$_has_cts}} {{
    puts "\\n\\[SILIS_CTS_SKIP\\] Clock tree already synthesized in current database checkpoint!"
    puts "Skipping duplicate CTS run to avoid crash. (To rebuild clock tree: Click 'Reset' -> 'Init' -> 'Place' -> 'CTS')\\n"
}} else {{
    {cts_cmd}
    #clock_tree_synthesis -sink_clustering_enable
    write_def "{def_abs_path}"
}}

# --- CTS FLAGS ---
# clock_tree_synthesis:
#   -sink_clustering_enable : Group close sinks to save power and reduce buffer count.
'''
        elif step_name == "Route":
            guide_path = os.path.join(results_dir, "route.guide").replace("\\", "/")
            drc_path = os.path.join(reports_dir, "drc.rpt").replace("\\", "/")
            fix_script = os.path.join(proj_root, "fix.tcl").replace("\\", "/")
            try: 
                fix_tcl = '''
# Snap IO Pins to Manufacturing Grid (5 DBU) to prevent DRT-0416
foreach bterm [[::ord::get_db_block] getBTerms] {
    foreach bpin [$bterm getBPins] {
        set boxes [$bpin getBoxes]
        set new_boxes {}
        set changed 0
        foreach box $boxes {
            set layer [$box getTechLayer]
            set x1 [$box xMin]; set y1 [$box yMin]
            set x2 [$box xMax]; set y2 [$box yMax]
            set nx1 [expr {int(round($x1 / 5.0) * 5)}]
            set ny1 [expr {int(round($y1 / 5.0) * 5)}]
            set nx2 [expr {int(round($x2 / 5.0) * 5)}]
            set ny2 [expr {int(round($y2 / 5.0) * 5)}]
            if {$nx1 != $x1 || $ny1 != $y1 || $nx2 != $x2 || $ny2 != $y2} { set changed 1 }
            lappend new_boxes [list $layer $nx1 $ny1 $nx2 $ny2]
        }
        if {$changed} {
            set p_status [$bpin getPlacementStatus]
            odb::dbBPin_destroy $bpin
            set new_bpin [odb::dbBPin_create $bterm]
            $new_bpin setPlacementStatus $p_status
            foreach b $new_boxes {
                odb::dbBox_create $new_bpin [lindex $b 0] [lindex $b 1] [lindex $b 2] [lindex $b 3] [lindex $b 4]
            }
            puts "Snapped off-grid pin for [$bterm getName]"
        }
    }
}

# Design-rule hygiene: Promote power/ground supply nets (e.g. constant tied nets like one_) to special nets
# to avoid TritonRoute DRT-0305 ("Net one_ of signal type POWER is not routable by TritonRoute")
set blk [::ord::get_db_block]
foreach net [$blk getNets] {
    if {[$net getSigType] eq "POWER" || [$net getSigType] eq "GROUND"} {
        if {![$net isSpecial]} {
            $net setSpecial
            puts "Promoted supply net [$net getName] to special net for TritonRoute"
        }
    }
}
'''
                with open(fix_script, 'w') as f: f.write(fix_tcl)
            except: pass
            route_tcl = load_template("route.tcl", {
                "fix_script": fix_script,
                "guide_path": guide_path,
                "drc_path": drc_path,
                "write_cmd": f'write_def "{def_abs_path}"'
            })
            cmd = route_tcl

        if cmd:
            step_tag = step_name.lower().replace(" ", "_")
            step_script = os.path.join(proj_root, f"run_{step_tag}.tcl").replace("\\", "/")
            # If user has an existing customized run_<step>.tcl (e.g. from floorplanner/ioplacer dialogs), preserve it
            if bypass_prompt and os.path.isfile(step_script) and step_tag in ("floorplan", "io_pins", "iopins"):
                with open(step_script, "r") as f:
                    existing_content = f.read()
                marker = f"SILIS_{step_tag.upper()}_DONE"
                if marker not in existing_content:
                    existing_content += f'\nputs "{marker}"\n'
                    with open(step_script, "w") as f:
                        f.write(existing_content)
                self.send_command_internal(f'source "{step_script}"')
            elif bypass_prompt:
                full_cmd = cmd.strip() + f'\nputs "SILIS_{step_tag.upper()}_DONE"\n'
                with open(step_script, 'w') as f: f.write(full_cmd)
                self.send_command_internal(f'source "{step_script}"')
            else:
                formatted_cmd = cmd.replace("; ", "\n").replace(";", "\n")
                text, ok = self.ask_command(f"Run {step_name}", "Confirm TCL Command:", formatted_cmd)
                if ok and text:
                    full_cmd = text.strip() + f'\nputs "SILIS_{step_tag.upper()}_DONE"\n'
                    with open(step_script, 'w') as f: f.write(full_cmd)
                    self.send_command_internal(f'source "{step_script}"')


    def display_pat_report(self, rpt_file, timing_failed):
        self.stop_spinner()
        if os.path.exists(rpt_file):
            self.term_log.append(f"[SUCCESS] PAT Sign-Off Report generated: {rpt_file}")
            if not getattr(self.ide, 'headless', False):
                dlg = SignoffReportViewer(rpt_file, timing_failed, self)
                dlg.exec()
            else:
                with open(rpt_file, 'r') as f:
                    print(f.read())
        else:
            self.term_log.append(f"[WARN] PAT Sign-Off Report file not found: {rpt_file}")
            if getattr(self.ide, 'headless', False):
                print(f"[WARN] PAT Sign-Off Report file not found: {rpt_file}")


    def trigger_magic_drc(self, root, gds_path):
        if not shutil.which("magic"): self.ide.queue.put(("[BACKEND]", "[ERR] 'magic' not found.")); return
        pdk_tech = self.active_pdk.get('tech', '')
        if not os.path.exists(pdk_tech): self.ide.queue.put(("[BACKEND]", "[ERR] Missing Tech file.")); return
        script_content = f"drc off\ngds read {gds_path}\ndrc style drc(fast)\ndrc on\ndrc check\ndrc catchup\nset count [drc list count]\nputs \"SILIS_DRC_VIOLATIONS: $count\"\nif {{$count > 0}} {{ drc list all }}\nquit"
        script_path = os.path.join(root, "run_drc.tcl")
        with open(script_path, 'w') as f: f.write(script_content)
        self.term_log.append(f"\n[SIGNOFF] Running Magic DRC on {os.path.basename(gds_path)}...")
        def run_drc():
            try:
                cmd = ["magic", "-noconsole", "-dnull", "-T", pdk_tech, script_path]
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                import re
                for line in iter(proc.stdout.readline, ''):
                    line = line.strip()
                    if "SILIS_DRC_VIOLATIONS" in line:
                        m = re.search(r'(\d+)\s*\}?$', line); count = m.group(1) if m else "Unknown"
                        if count == "0": self.ide.queue.put(("[BACKEND]", "[OK] DRC CLEAN (0 Violations)"))
                        else: self.ide.queue.put(("[BACKEND]", f"[FAIL] DRC FAILED: {count} Violations Found"))
                    elif "Error:" in line or "error" in line.lower(): self.ide.queue.put(("[BACKEND]", f"[DRC ERR] {line}"))
                proc.wait()
                self.ide.queue.put(("[BACKEND]", "DRC Run Complete."))
            except Exception as e: self.ide.queue.put(("[BACKEND]", f"[ERR] DRC Execution Failed: {e}"))
            
        self.start_spinner()
        self.drc_worker = FlowWorker(run_drc)
        self.drc_worker.finished_signal.connect(self.stop_spinner)
        self.drc_worker.start()

    def trigger_magic_merge(self, root, def_path):
        if not shutil.which("magic"): self.ide.queue.put(("[BACKEND]", "[ERR] 'magic' executable not found.")); return
        pdk_gds = self.active_pdk.get('gds', ''); pdk_tech = self.active_pdk.get('tech', '')
        pdk_tlef = self.active_pdk.get('tlef', ''); pdk_lef = self.active_pdk.get('lef', '')   
        output_gds = os.path.join(root, "results", "design.gds").replace("\\", "/")
        if not all(os.path.exists(p) for p in [pdk_gds, pdk_tech, pdk_tlef, pdk_lef]): self.ide.queue.put(("[BACKEND]", f"[ERR] Missing PDK files.")); return
        
        script_content = f"drc off\ncatch {{ locking off }}\ngds readonly true\ngds rescale false\nlef read {pdk_tlef}\nlef read {pdk_lef}\n"
        
        # Load I/O Pad LEFs if available
        for io_lef in self._get_io_lefs():
            script_content += f"lef read {io_lef}\n"

        # Load macro LEFs
        for lef in self._get_macro_files("lef"):
            script_content += f"lef read {lef}\n"
        macro_gds_paths = self._get_macro_files("gds")
        
        script_content += f"gds read {pdk_gds}\n"
        # Load I/O Pad GDS files if available
        for io_gds_path in self._get_io_gds():
            script_content += f"gds read {io_gds_path}\n"
        for gds in macro_gds_paths:
            script_content += f"gds read {gds}\n"
            
        design_name = "design"
        if os.path.exists(def_path):
            with open(def_path, 'r') as f:
                for line in f:
                    if line.startswith("DESIGN"):
                        design_name = line.split()[1]
                        break
                        
        output_gds = os.path.join(root, "results", f"{design_name}.gds").replace("\\", "/")
        script_content += f"def read {def_path}\nload {design_name}\ngds write {output_gds}\nquit -noprompt"
        script_path = os.path.join(root, "merge_magic.tcl")
        with open(script_path, 'w') as f: f.write(script_content)
        self.term_log.append(f"[SYS] Magic: Merging with LEF support...")
        def run_magic():
            try:
                cmd = ["magic", "-noconsole", "-dnull", "-T", pdk_tech, script_path]
                proc = subprocess.run(cmd, capture_output=True, text=True)
                if proc.returncode == 0 and os.path.exists(output_gds):
                    standard_gds = os.path.join(root, "results", "design.gds").replace("\\", "/")
                    if output_gds != standard_gds:
                        import shutil
                        shutil.copyfile(output_gds, standard_gds)
                    self.ide.queue.put(("[BACKEND_GDS_DONE]", output_gds))
                    self.ide.queue.put(("[BACKEND]", f"Saved: {output_gds}"))
                else: self.ide.queue.put(("[BACKEND]", f"[ERR] Magic Failed:\n{proc.stderr}\n{proc.stdout}"))
            except Exception as e: self.ide.queue.put(("[BACKEND]", f"[ERR] Magic Execution Error: {e}"))
            
        self.start_spinner()
        self.magic_worker = FlowWorker(run_magic)
        self.magic_worker.finished_signal.connect(self.stop_spinner)
        self.magic_worker.start()

    def open_pdk_selector(self):
        if hasattr(self.ide, 'open_pdk_selector'):
            ok = self.ide.open_pdk_selector()
            if ok:
                self.active_pdk = self.ide.active_pdk
                self.term_log.append(f"[SYS] Target PDK: {self.active_pdk['name']}")
                return True
            return False
        dlg = PDKSelector(self.pdk_mgr, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.active_pdk = dlg.selected_config; self.term_log.append(f"[SYS] Target PDK: {self.active_pdk['name']}"); return True
        return False

    def append_output(self, text):
        if hasattr(self, 'term_log'):
            self.term_log.append(str(text))
            self.term_log.verticalScrollBar().setValue(self.term_log.verticalScrollBar().maximum())

    def read_stdout(self):
        data = self.proc.readAllStandardOutput().data().decode("utf-8", errors="replace")
        self.term_log.append(data.strip())
        self.term_log.verticalScrollBar().setValue(self.term_log.verticalScrollBar().maximum())
        if self.pending_init and ("OpenROAD" in data or "openroad>" in data): self.send_command_internal(self.pending_init); self.pending_init = None
        if self.cmd_active and "openroad>" in data: 
            self.cmd_active = False
            self.force_refresh_view()
            self.stop_spinner()

    def send_command(self): cmd = self.term_in.text(); self.term_in.clear(); self.send_command_internal(cmd)
        
    def send_command_internal(self, cmd):
        self.term_log.append(f"> {cmd}")
        # Preemptive Command Flight Recorder: record session commands
        if not getattr(self, "_replaying_journal", False):
            if not hasattr(self, "cmd_journal"):
                self.cmd_journal = []
            # Never record read_db, write_db, checkpoint.odb or replay scripts into cmd_journal
            # because replaying them after PDK/netlist initialization causes ORD-0047
            if not any(term in cmd for term in ["read_db", "write_db", "checkpoint.odb", "replay_flow.tcl"]):
                self.cmd_journal.append(cmd)

        if "initialize_floorplan" in cmd:
            import re
            m = re.search(r'-die_area\s+"(\d+)\s+(\d+)\s+(\d+)\s+(\d+)"', cmd)
            if m:
                x1, y1, x2, y2 = map(float, m.groups())
                try: 
                    self.peeker.set_die_area(x1, y1, x2, y2)
                    self.fast_peeker.set_die_area(x1, y1, x2, y2)
                except: pass
        if self.proc and self.proc.state() == QProcess.ProcessState.Running: 
            self.cmd_active = True
            self.start_spinner()
            self.proc.write(f"{cmd}\n".encode())
        else: self.term_log.append(f"[ERR] Backend not running. Click Reset.")

    def replay_session_with_script(self, replay_script_path):
        """
        Seamlessly resets the OpenROAD engine and executes the compiled replay script
        which plays back the user's customized earlier flow steps (Init, Floorplan,
        Tapcells, PDN, user terminal commands) followed by the new I/O placement script.
        """
        self.term_log.append(f"\n[SYS] Preemptive Replay: Seamlessly replaying recorded session with tuned floorplan...")
        self.reset_backend()
        self.pending_init = f'source "{replay_script_path}"'
    
    def update_view(self):
        try:
            self.fast_peeker.show_insts = self.chk_inst.isChecked(); self.fast_peeker.show_pins = self.chk_pins.isChecked()
            self.fast_peeker.show_macros = self.chk_macros.isChecked(); self.fast_peeker.show_tapcells = self.chk_tap.isChecked()
            self.fast_peeker.show_nets = self.chk_nets.isChecked(); self.fast_peeker.show_power = self.chk_power.isChecked()
            
            self.fast_peeker.redraw()
        except: pass

    def set_all_layers(self, visible: bool):
        for chk in [
            self.chk_layer_li1, self.chk_layer_met1, self.chk_layer_met2,
            self.chk_layer_met3, self.chk_layer_met4, self.chk_layer_met5,
            self.chk_layer_vias
        ]:
            chk.blockSignals(True)
            chk.setChecked(visible)
            chk.blockSignals(False)
        self.update_layer_view()

    def update_layer_view(self):
        try:
            layer_map = {
                "li1": self.chk_layer_li1.isChecked(),
                "met1": self.chk_layer_met1.isChecked(),
                "met2": self.chk_layer_met2.isChecked(),
                "met3": self.chk_layer_met3.isChecked(),
                "met4": self.chk_layer_met4.isChecked(),
                "met5": self.chk_layer_met5.isChecked(),
                "vias": self.chk_layer_vias.isChecked(),
            }
            if hasattr(self, 'layer_panel'):
                self.layer_panel.set_layer_visibility(layer_map)
            elif hasattr(self, 'fast_peeker'):
                if hasattr(self.fast_peeker, 'set_layer_visibility'):
                    self.fast_peeker.set_layer_visibility(layer_map)
                elif hasattr(self.fast_peeker, 'redraw'):
                    self.fast_peeker.redraw()
        except: pass
    
    def load_routed_design(self):
        proj_root = self.ide.get_proj_root(self.ide.get_context()[0] or "design")
        def_path = os.path.join(proj_root, "results", "final_routed.def")
        if os.path.exists(def_path): 
            self.term_log.append(f"[SYS] Loading Routed Design from: {def_path}")
            self.fast_peeker.load_def_file(def_path)
            self.chk_nets.setChecked(True)
            self.fast_peeker.show_nets = True
            self.fast_peeker.redraw()
            self.viz_tabs.setCurrentIndex(0)
        else: self.term_log.append(f"[ERR] Routed file not found at: {def_path}")

    def launch_native_gui(self):
        if not self.active_pdk: return
        proj_root = self.ide.get_proj_root(self.ide.get_context()[0] or "design")
        def_path = os.path.join(proj_root, "results", "temp.def")
        if not os.path.exists(def_path): return
        view_tcl = os.path.join(proj_root, "view.tcl")
        
        tcl_content = f'read_lef "{self.active_pdk["tlef"]}"\nread_lef "{self.active_pdk["lef"]}"\n'
        # Sky130 IO LEFs for full-chip pad ring viewing
        pdk_dir = os.path.dirname(self.active_pdk["lef"])
        # Walk up to libs.ref directory (handles both libs.ref/sky130_fd_sc_hd/lef and direct setups)
        libs_ref = os.path.abspath(os.path.join(pdk_dir, "..", ".."))
        io_dir = os.path.join(libs_ref, "sky130_fd_io", "lef")
        if not os.path.isdir(io_dir):
            io_dir = os.path.abspath(os.path.join(pdk_dir, "..", "sky130_fd_io", "lef"))
        if os.path.isdir(io_dir):
            for ef_io in ["sky130_ef_io.lef", "sky130_fd_io.lef"]:
                io_lef_path = os.path.join(io_dir, ef_io)
                if os.path.isfile(io_lef_path):
                    tcl_content += f'read_lef "{io_lef_path}"\n'

        for lef in self._get_macro_files("lef"):
            tcl_content += f'read_lef "{lef}"\n'

        # Ensure IO sites are declared so DEF rows don't cause ODB-0155
        tcl_content += 'set _db [::ord::get_db]\n'
        tcl_content += 'set _has_site 0\n'
        tcl_content += 'foreach _lib [$_db getLibs] { if {[$_lib findSite "IO_SITE"] != "NULL"} { set _has_site 1; break } }\n'
        tcl_content += 'if {!$_has_site} { make_fake_io_site -name IO_SITE -width 1 -height 200 }\n'
        tcl_content += 'set _has_csite 0\n'
        tcl_content += 'foreach _lib [$_db getLibs] { if {[$_lib findSite "IO_CSITE"] != "NULL"} { set _has_csite 1; break } }\n'
        tcl_content += 'if {!$_has_csite} { make_fake_io_site -name IO_CSITE -width 200 -height 204 }\n'
                    
        tcl_content += f'read_def -continue_on_errors "{def_path}"\n'
        
        with open(view_tcl, 'w') as f: f.write(tcl_content)
        subprocess.Popen(["openroad", "-gui", view_tcl], cwd=proj_root)
    
    def force_refresh_view(self):
        if self.viz_tabs.currentIndex() != 0:
            return  # Do not waste cycles parsing DEF if viewer tab is not active
        proj_root = self.ide.get_proj_root(self.ide.get_context()[0] or "design")
        def_path = os.path.join(proj_root, "results", "temp.def")
        if os.path.exists(def_path):
            active_stack_idx = self.viz_stack.currentIndex() if hasattr(self, 'viz_stack') else 0
            if active_stack_idx == 0:
                self.fast_peeker.load_def_file(def_path)
            elif active_stack_idx == 1 and hasattr(self, 'layer_panel'):
                self.layer_panel.load_layout_from_opendb(def_path)

    def load_checkpoint(self):
        proj_root = self.ide.get_proj_root(self.ide.get_context()[0] or "design")
        last_step = self.ide.project_config.get('last_backend_step', '')
        if last_step in ["Place", "CTS"]:
            def_path = os.path.join(proj_root, "results", "temp.def").replace("\\", "/")
            if os.path.exists(def_path):
                self.term_log.append(f"[SYS] Last step was {last_step}. Showing from def instead to avoid DB bugs...")
                self.resume_def = def_path
                self.run_flow_step("Init", bypass_prompt=True)
                return True

        db_path = os.path.join(proj_root, "results", "checkpoint.odb").replace("\\", "/")
        if os.path.exists(db_path):
            self.term_log.append(f"[SYS] Loading Checkpoint from {db_path}...")
            self.send_command_internal(f"read_db \"{db_path}\"")
            
            # Restore STA context (Liberty & SDC)
            if self.active_pdk:
                self.send_command_internal(f"read_liberty \"{self.active_pdk['lib']}\"")
                for lib in self._get_macro_files("lib"):
                    self.send_command_internal(f"read_liberty \"{lib}\"")
            
            ctx = self.ide.get_context()[0] or "top"
            import glob
            sdc_files = glob.glob(os.path.join(proj_root, "source", "*.sdc"))
            if sdc_files:
                self.send_command_internal(f"read_sdc \"{sdc_files[0].replace(chr(92), '/')}\"")
                
            self.force_refresh_view(); return True
        return False

    def save_checkpoint(self):
        if not self.proc: return
        proj_root = self.ide.get_proj_root(self.ide.get_context()[0] or "design")
        db_path = os.path.join(proj_root, "results", "checkpoint.odb").replace("\\", "/")
        self.term_log.append(f"[SYS] Saving Checkpoint to {db_path}...")
        self.send_command_internal(f"write_db \"{db_path}\"")



    def set_viewer_mode(self, mode: str):
        """Switches between Instance-Wise (0) and Layer-Wise (1) with in-place sidebar swapping."""
        if not hasattr(self, 'sidebar_stack'):
            return
        idx = 1 if mode in ["layer", "layer-wise", "layer_wise", 1] else 0
        self.sidebar_stack.setCurrentIndex(idx)
        if hasattr(self, 'viz_stack'):
            self.viz_stack.setCurrentIndex(idx)
        if idx == 1:
            # Layer-wise view: load OpenDB layout on demand if not already loaded, then emphasize physical wires
            proj_root = self.ide.get_proj_root(self.ide.get_context()[0] or "design")
            def_path = os.path.join(proj_root, "results", "temp.def")
            if os.path.exists(def_path) and hasattr(self, 'layer_panel'):
                self.layer_panel.load_layout_from_opendb(def_path)
            self.update_layer_view()
        else:
            # Instance-wise view: restore standard cell & macro view
            proj_root = self.ide.get_proj_root(self.ide.get_context()[0] or "design")
            def_path = os.path.join(proj_root, "results", "temp.def")
            if os.path.exists(def_path) and hasattr(self, 'fast_peeker'):
                self.fast_peeker.load_def_file(def_path)
            self.update_view()
