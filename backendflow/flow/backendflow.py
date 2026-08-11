import os
import subprocess
import time
import shutil
import glob
import threading
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from backendflow.siliconpeeker.peeker import SiliconPeeker, FastSiliconPeeker
from backendflow.gdsviewer.gds3d import GDS3DPort
from pdkmanagers.pdk.manager import SSAForge
from config import USER_SETTINGS, THEMES
from editor.editor import ScintillaEditor
from backendflow.floorplanner.floorplanner import InteractiveFloorplannerWidget

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
        
        self.btn_launch = QPushButton("🚀 Launch Embedded C++ Viewer")
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
        viewer_exe = "/home/jerome/silis/backendflow/def_viewer_cpp/build/silis_def_viewer"
        if not os.path.exists(viewer_exe):
            self.info_label.setText("❌ Missing C++ Viewer Executable!")
            self.info_label.setStyleSheet("color: #ff7b72;")
            return

        self.btn_launch.setEnabled(False)
        self.btn_launch.setText("Binding to OS...")

        self.proc = QProcess(self)
        self.proc.readyReadStandardOutput.connect(self.handle_stdout)
        self.proc.start(viewer_exe)

    def handle_stdout(self):
        if not self.proc: return
        data = self.proc.readAllStandardOutput().data().decode()
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
        self.btn_launch.setText("🚀 Launch Embedded C++ Viewer")
        self.btn_launch.setEnabled(True)
        self.info_label.show()
        self.info_label.setText("Viewer closed. Ready to launch again.")
        self.info_label.setStyleSheet("color: #8b949e;")

    def closeEvent(self, event):
        self.kill_viewer()
        super().closeEvent(event)

class BackendWidget(QWidget):
    def __init__(self, parent_ide):
        super().__init__(parent_ide)
        self.ide = parent_ide 
        self.pdk_mgr = parent_ide.pdk_mgr
        self.active_pdk = parent_ide.active_pdk
        
        # --- 1. INITIALIZE WIDGETS ---
        self.fast_peeker = FastSiliconPeeker(self.ide)
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
        
        self.btn_heat = QPushButton("Heatmap"); self.btn_heat.setCheckable(True)
        self.btn_heat.setStyleSheet("QPushButton:checked { background-color: #ffcccc; color: red; border: 1px solid red; }")
        
        def_layout.addWidget(QLabel("<b>DEF Layers</b>"))
        def_layout.addWidget(self.chk_inst); def_layout.addWidget(self.chk_macros); def_layout.addWidget(self.chk_tap)
        def_layout.addWidget(self.chk_pins); def_layout.addWidget(self.chk_nets); def_layout.addWidget(self.chk_power)
        def_layout.addSpacing(10); def_layout.addWidget(QLabel("<b>Overlay</b>"))
        def_layout.addWidget(self.btn_heat); def_layout.addStretch()



        # [UPDATE] Added Magic GUI Button
        self.btn_gui = QPushButton("Native GUI (OpenROAD)")
        self.btn_magic = QPushButton("✨ Magic GUI")
        self.btn_magic.setStyleSheet("color: #5a32a3; font-weight: bold;") # Magic purple branding
        
        self.btn_ref = QPushButton("Refresh View")
        self.btn_load = QPushButton("📂 Load Routed")
        
        self.term_log = QTextEdit(); self.term_log.setReadOnly(True)
        self.term_log.setStyleSheet("font-family: Consolas; border: none;")
        self.term_in = QLineEdit(); self.term_in.setPlaceholderText("Enter TCL command...")
        self.term_in.setStyleSheet("font-family: Consolas; padding: 5px; border-top: 1px solid gray;")

        # --- 2. LAYOUT ---
        self.layout = QVBoxLayout(self); self.layout.setContentsMargins(0,0,0,0)
        
        self.ribbon = QFrame(); self.ribbon.setStyleSheet("border-bottom: 1px solid gray;"); self.ribbon.setFixedHeight(40) 
        r_lay = QHBoxLayout(self.ribbon); r_lay.setContentsMargins(5,2,5,2)
        
        self.steps = ["Init", "Floorplan", "Tapcells", "PDN", "IO Pins", "Place", "CTS", "Route", "GDS"]
        self.signoff_steps = ["Antenna", "STA", "DRC", "PAT"] 
        
        for step in self.steps:
            btn = QPushButton(step); btn.setStyleSheet("padding: 2px; font-weight: bold; font-size: 11px;")
            btn.clicked.connect(lambda _, s=step: self.run_flow_step(s))
            r_lay.addWidget(btn)
            
        line = QFrame(); line.setFrameShape(QFrame.Shape.VLine); line.setFrameShadow(QFrame.Shadow.Sunken)
        r_lay.addWidget(line)
        
        for step in self.signoff_steps:
            btn = QPushButton(step); btn.setStyleSheet("padding: 2px; font-weight: bold; font-size: 11px; color: #880000;")
            btn.clicked.connect(lambda _, s=step: self.run_flow_step(s))
            r_lay.addWidget(btn)

        r_lay.addStretch()
        btn_rst = QPushButton("🔄 Reset"); btn_rst.clicked.connect(self.reset_backend); r_lay.addWidget(btn_rst)
        btn_cfg = QPushButton("⚙ PDK Config"); btn_cfg.clicked.connect(self.open_pdk_selector); r_lay.addWidget(btn_cfg)
        self.layout.addWidget(self.ribbon)
        
        v_split = QSplitter(Qt.Orientation.Vertical)
        h_widget = QWidget(); h_lay = QHBoxLayout(h_widget); h_lay.setContentsMargins(0,0,0,0); h_lay.setSpacing(0)
        
        sidebar = QFrame(); sidebar.setFixedWidth(140); sidebar.setStyleSheet("border-right: 1px solid gray;")
        s_lay = QVBoxLayout(sidebar); s_lay.setContentsMargins(5,10,5,10)
        s_lay.addWidget(self.def_ctrl_widget)
        
        # [UPDATE] Add buttons to sidebar
        s_lay.addWidget(self.btn_gui)
        s_lay.addWidget(self.btn_magic)
        s_lay.addWidget(self.btn_ref)
        s_lay.addWidget(self.btn_load)
        h_lay.addWidget(sidebar)
        
        self.viz_tabs = QTabWidget(); self.viz_tabs.setTabPosition(QTabWidget.TabPosition.South)
        self.viz_tabs.addTab(self.fast_peeker, "Fast Layout Viewer")
        self.viz_tabs.addTab(self.gds3d_port, "GDS View (3D)")
        
        # --- NEW: CLOCK TREE VIEWER ---
        import sys
        sys.path.append("/home/jerome/silis/clocktreeviewer/build")
        try:
            import clocktree_engine
            from PyQt6 import sip
            self.clock_engine = clocktree_engine.ClockTreeViewerCore()
            ptr = self.clock_engine.get_ptr()
            self.native_clock_view = sip.wrapinstance(ptr, QWidget)
            self.viz_tabs.addTab(self.native_clock_view, "Clock Tree")
        except Exception as e:
            err_lbl = QLabel(f"Failed to load C++ ClockTreeViewer:\n{e}")
            self.viz_tabs.addTab(err_lbl, "Clock Tree")
            
        h_lay.addWidget(self.viz_tabs)
        
        v_split.addWidget(h_widget)
        
        term_widget = QWidget(); t_lay = QVBoxLayout(term_widget); t_lay.setContentsMargins(0,0,0,0)
        t_lay.addWidget(self.term_log); t_lay.addWidget(self.term_in)
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
        self.btn_heat.toggled.connect(self.update_view)
        
        self.btn_gui.clicked.connect(self.launch_native_gui)
        self.btn_magic.clicked.connect(self.launch_magic_gui) 
        self.btn_ref.clicked.connect(self.force_refresh_view)
        self.btn_load.clicked.connect(self.load_routed_design)
        
        self.viz_tabs.currentChanged.connect(self.on_tab_changed)
        self.term_in.returnPressed.connect(self.send_command)

        # --- 4. STARTUP ---
        self.proc = None
        self.pending_init = None
        self.cmd_active = False
        
        self.reset_backend() 
        self.viz_tabs.setCurrentIndex(0)

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
        if index == 0:
            # Tab 0: DEF Live Floorplan
            self.def_ctrl_widget.setVisible(True)
            
        elif index == 1:
            # Tab 1: 3D GDS Viewer
            self.def_ctrl_widget.setVisible(False)
            # The sidebar is now completely hidden for the 3D view to maximize screen space!
        else:
            self.term_log.append(f"[ERR] GDS not found. Run 'GDS' step first.")

    def run_flow_step(self, step_name, bypass_prompt=False):
        proj_root = self.ide.get_proj_root(self.ide.get_context()[0] or "design")
        results_dir = os.path.join(proj_root, "results"); os.makedirs(results_dir, exist_ok=True)
        reports_dir = os.path.join(proj_root, "reports"); os.makedirs(reports_dir, exist_ok=True)
        def_abs_path = os.path.join(results_dir, "temp.def").replace("\\", "/")
        write_cmd = f"write_def \"{def_abs_path}\""

        if step_name == "Antenna":
            self.term_log.append("\n[SIGNOFF] Running Antenna Check...")
            self.send_command_internal("check_antennas -report_file reports/antenna.rpt; puts \"Antenna Violations: [check_antennas]\"")
            return

        if step_name == "STA":
            if not self.active_pdk: QMessageBox.critical(self, "Error", "PDK not active."); return
            self.term_log.append("\n[SIGNOFF] Extracting Full Clock Topology via C++ STA Engine...")
            
            # Use our custom C++ OpenSTA engine to extract the graph!
            import sys
            sys.path.append("/home/jerome/silis/synthengine/build")
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
                            # Switch to Clock Tree tab (index 3)
                            self.viz_tabs.setCurrentIndex(3)
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
            corners = self.active_pdk['corners']
            
            # Build TCL script
            tcl_content = f"set_thread_count [exec nproc]\\n"
            tcl_content += f"read_lef \\\"{self.active_pdk['tlef']}\\\"\\n"
            tcl_content += f"read_lef \\\"{self.active_pdk['lef']}\\\"\\n"
            
            # Read macros if any
            macros = self.ide.project_config.get('macros', [])
            if macros:
                volare_base = self.active_pdk.get('lib', '').split("libs.ref")[0]
                for lef in glob.glob(os.path.join(volare_base, "libs.ref", "*", "lef", "*.lef")):
                    if os.path.basename(lef).replace('.lef', '') in macros:
                        tcl_content += f"read_lef \\\"{lef}\\\"\\n"

            tcl_content += f"read_def \\\"{def_abs_path}\\\"\\n"
            
            corner_names = list(corners.keys())
            tcl_content += f"define_corners " + " ".join(corner_names) + "\\n"
            
            for c_name, lib_path in corners.items():
                tcl_content += f"read_liberty -corner {c_name} \\\"{lib_path}\\\"\\n"
                
            if macros:
                for lib in glob.glob(os.path.join(volare_base, "libs.ref", "*", "lib", "*.lib")):
                    name = os.path.basename(lib).replace('.lib', '')
                    if any(m in name for m in macros):
                        # Add macro lib to all corners for simplicity
                        for c_name in corner_names:
                            tcl_content += f"read_liberty -corner {c_name} \\\"{lib}\\\"\\n"
                            
            tcl_content += f"read_sdc \\\"{sdc_path}\\\"\\n"
            
            # Setup RC for corners if possible
            # We skip explicit RC corners for now since they are tied to set_layer_rc commands
            
            # Area calculation
            tcl_content += "set block [::ord::get_db_block]\\n"
            tcl_content += "set tech [::ord::get_db_tech]\\n"
            tcl_content += "set dbu [$tech getDbUnitsPerMicron]\\n"
            tcl_content += "set total_area 0.0\\n"
            tcl_content += "foreach inst [$block getInsts] {\\n"
            tcl_content += "    set master [$inst getMaster]\\n"
            tcl_content += "    set m_area [expr {([$master getWidth] * 1.0 / $dbu) * ([$master getHeight] * 1.0 / $dbu)}]\\n"
            tcl_content += "    set total_area [expr {$total_area + $m_area}]\\n"
            tcl_content += "}\\n"
            tcl_content += "puts \\\"PAT_AREA: $total_area\\\"\\n"
            
            tcl_content += "puts \\\"PAT_POWER_START\\\"\\n"
            tcl_content += "report_power\\n"
            tcl_content += "puts \\\"PAT_POWER_END\\\"\\n"
            
            for c_name in corner_names:
                tcl_content += f"puts \\\"PAT_CORNER_START: {c_name}\\\"\\n"
                tcl_content += f"report_checks -path_delay max -corner {c_name}\\n"
                tcl_content += f"puts \\\"PAT_CORNER_END: {c_name}\\\"\\n"
                
            with open(tcl_path, 'w') as f:
                f.write(tcl_content.replace('\\\\n', '\\n').replace('\\\\\\"', '\\"'))
                
            def run_pat():
                try:
                    cmd = ["openroad", "-exit", tcl_path]
                    proc = subprocess.run(cmd, capture_output=True, text=True)
                    out = proc.stdout
                    
                    area = "0.0"
                    power = "0.0"
                    
                    import re
                    area_match = re.search(r"PAT_AREA:\s*([0-9.]+)", out)
                    if area_match: area = f"{float(area_match.group(1)):.0f}"
                    
                    power_match = re.search(r"Total\s+[0-9.e-]+\s+[0-9.e-]+\s+[0-9.e-]+\s+([0-9.e-]+)", out)
                    if power_match:
                        # Convert power from whatever unit OpenSTA uses to mW (OpenSTA default is often W)
                        # Actually just extract the raw number
                        try:
                            p = float(power_match.group(1)) * 1000 # Assuming W -> mW
                            power = f"{p:.2f}"
                        except:
                            power = power_match.group(1)
                            
                    corners_data = []
                    corner_blocks = re.findall(r"PAT_CORNER_START:\s*(\w+)\s*(.*?)PAT_CORNER_END:", out, re.DOTALL)
                    
                    timing_failed = False
                    
                    for c_name, c_out in corner_blocks:
                        slack = "N/A"
                        endpoint = "N/A"
                        
                        slack_match = re.search(r"slack\s+\(VIOLATED\)\s+([-\d.]+)", c_out)
                        if slack_match:
                            slack = slack_match.group(1)
                            timing_failed = True
                        else:
                            slack_match = re.search(r"slack\s+\(MET\)\s+([-\d.]+)", c_out)
                            if slack_match: slack = slack_match.group(1)
                            
                        ep_match = re.search(r"Endpoint:\s*(\S+)", c_out)
                        if ep_match: endpoint = ep_match.group(1)
                        
                        corners_data.append((c_name, slack, endpoint))
                        
                    report = f"Area - {area} µm²\\n"
                    report += f"Timing - {'Failed' if timing_failed else 'Passed'}\\n"
                    report += f"Power - {power} mW\\n\\n"
                    
                    for i, (c_name, slack, endpoint) in enumerate(corners_data):
                        report += f"{c_name}\\n"
                        report += f"Slack\\n{slack}\\n"
                        report += f"Worst Endpoint\\n{endpoint}\\n"
                        if i < len(corners_data) - 1:
                            report += "────────────────────\\n"
                            
                    rpt_file = os.path.join(reports_dir, f"{base}_pat_report.rpt")
                    with open(rpt_file, 'w') as f:
                        f.write(report.replace('\\\\n', '\\n'))
                        
                    self.ide.queue.put(("[BACKEND]", f"PAT Report generated: {rpt_file}"))
                except Exception as e:
                    self.ide.queue.put(("[BACKEND]", f"[ERR] PAT Execution Failed: {e}"))
                    
            self.start_spinner()
            self.pat_worker = FlowWorker(run_pat)
            self.pat_worker.finished_signal.connect(self.stop_spinner)
            self.pat_worker.start()
            return

        if step_name == "Init":
            db_path = os.path.join(results_dir, "checkpoint.odb")
            def_path = os.path.join(results_dir, "temp.def")
            if not bypass_prompt:
                self.resume_def = None
                if os.path.exists(db_path):
                    reply = QMessageBox.question(self, "Resume?", "Found saved checkpoint.odb. Load it?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                    if reply == QMessageBox.StandardButton.Yes: self.load_checkpoint(); return
                
                if os.path.exists(def_path):
                    reply = QMessageBox.question(self, "Resume from temp.def?", "Found temp.def from a previous step. Resume from it instead?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                    if reply == QMessageBox.StandardButton.Yes: self.resume_def = def_path.replace("\\", "/")

            if not self.active_pdk: 
                 if not self.open_pdk_selector(): return
            tcl_path = os.path.join(proj_root, "init_pdk.tcl").replace("\\", "/")
            ctx = self.ide.get_context()[0] or "top"
            base = self.ide.get_context()[1] or "top"
            netlist_path = os.path.join(proj_root, "netlist", f"{base}_netlist.v").replace("\\", "/")
            if not os.path.exists(netlist_path): netlist_path = (self.ide.current_file or "design.v").replace("\\", "/")
            sdc_files = glob.glob(os.path.join(proj_root, "source", "*.sdc"))
            if sdc_files:
                sdc_path = sdc_files[0]
            else:
                sdc_path = os.path.join(proj_root, "source", f"{ctx}.sdc")
                os.makedirs(os.path.dirname(sdc_path), exist_ok=True)
                with open(sdc_path, 'w') as f: f.write("create_clock -name clk -period 10.0 [get_ports clk]\nset_input_delay 2.0 -clock clk [all_inputs]\nset_output_delay 2.0 -clock clk [all_outputs]\n")
            tcl_content = f"""set_thread_count [exec nproc]\nread_lef "{self.active_pdk['tlef']}"\nread_lef "{self.active_pdk['lef']}"\n"""
            
            macros = self.ide.project_config.get('macros', [])
            if macros:
                lib_path = self.active_pdk.get('lib', '')
                volare_base = lib_path.split("libs.ref")[0]
                lef_search = os.path.join(volare_base, "libs.ref", "*", "lef", "*.lef")
                lib_search = os.path.join(volare_base, "libs.ref", "*", "lib", "*.lib")
                
                for lef in glob.glob(lef_search):
                    name = os.path.basename(lef).replace('.lef', '')
                    if name in macros:
                        tcl_content += f"""read_lef "{lef}"\n"""
                        
            tcl_content += f"""read_liberty "{self.active_pdk['lib']}\"\n"""
            if macros:
                for lib in glob.glob(lib_search):
                    name = os.path.basename(lib).replace('.lib', '')
                    # handle typical .lib naming which might have extensions like __tt_025C_1v80.lib
                    if any(m in name for m in macros):
                        tcl_content += f"""read_liberty "{lib}"\n"""
                        
            tcl_content += f"""read_verilog "{netlist_path}"\nlink_design {ctx}\nread_sdc "{sdc_path}"\n"""
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
"""
            if getattr(self, 'resume_def', None):
                tcl_content += f'\nread_def "{self.resume_def}"\n'
                
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
            self.send_command_internal(f"write_def \"{final_def}\"")
            QTimer.singleShot(2000, lambda: self.trigger_magic_merge(proj_root, final_def))
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

        if step_name == "Floorplan": 
            self.floorplanner_dialog = InteractiveFloorplannerWidget(self.ide.project_config, self.pdk_mgr, self)
            self.floorplanner_dialog.show()
            return
        elif step_name == "Tapcells":
            tap_cmd = SSAForge.get_tap_cmd(pdk_name, lib_path)
            cmd = load_template("tapcells.tcl", {"tap_cmd": tap_cmd, "write_cmd": write_cmd})
        elif step_name == "PDN":
            cmd = load_template("pdn.tcl", {"write_cmd": write_cmd})
        elif step_name == "IO Pins":
            cmd = load_template("io_pins.tcl", {"write_cmd": write_cmd})
        elif step_name == "Place":
            cmd = load_template("place.tcl", {"write_cmd": write_cmd})
        elif step_name == "CTS":
            cts_cmd = SSAForge.get_cts_cmd(pdk_name, lib_path)
            cmd = f'''{cts_cmd}
#clock_tree_synthesis -sink_clustering_enable
write_def "{def_abs_path}"

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
# 1. Fix Rogue Power Nets
foreach net [[::ord::get_db_block] getNets] { 
    set type [$net getSigType]
    set name [$net getName]
    if {($type == "POWER" || $type == "GROUND") && $name != "VDD" && $name != "VSS"} { 
        $net setSigType "SIGNAL"
        puts "Fixed rogue power net $name"
    } 
}

# 2. Snap IO Pins to Manufacturing Grid (5 DBU) to prevent DRT-0416
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
'''
                with open(fix_script, 'w') as f: f.write(fix_tcl)
            except: pass
            cmd = f'''source "{fix_script}"
global_route -guide_file "{guide_path}" -congestion_iterations 50 -verbose
#global_route -congestion_iterations 100
detailed_route -output_drc "{drc_path}"
#detailed_route -bottom_routing_layer met1 -top_routing_layer met5
write_def "{def_abs_path}"

# --- ROUTING FLAGS ---
# global_route:
#   -congestion_iterations <N> : How aggressively the router tries to fix congestion (higher = slower but better).
# detailed_route:
#   -bottom_routing_layer / -top_routing_layer : Restrict routing to specific layers.
'''

        if cmd:
            # Format the command string nicely into multiple lines for the dialog
            cmd = cmd.replace("; ", "\n").replace(";", "\n")
            text, ok = self.ask_command(f"Run {step_name}", "Confirm TCL Command:", cmd)
            if ok and text: self.send_command_internal(text)

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
                        if count == "0": self.ide.queue.put(("[BACKEND]", "🟢 DRC CLEAN (0 Violations)"))
                        else: self.ide.queue.put(("[BACKEND]", f"🔴 DRC FAILED: {count} Violations Found"))
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
        
        script_content = f"drc off\nlocking off\ngds readonly true\ngds rescale false\nlef read {pdk_tlef}\nlef read {pdk_lef}\n"
        
        # Load macro LEFs
        macros = self.ide.project_config.get('macros', [])
        macro_gds_paths = []
        if macros:
            volare_base = self.active_pdk.get('lib', '').split("libs.ref")[0]
            import glob
            for lef in glob.glob(os.path.join(volare_base, "libs.ref", "*", "lef", "*.lef")):
                name = os.path.basename(lef).replace('.lef', '')
                if name in macros:
                    script_content += f"lef read {lef}\n"
            for gds in glob.glob(os.path.join(volare_base, "libs.ref", "*", "gds", "*.gds")):
                name = os.path.basename(gds).replace('.gds', '')
                if name in macros:
                    macro_gds_paths.append(gds)
        
        script_content += f"gds read {pdk_gds}\n"
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
                    self.ide.queue.put(("[BACKEND_GDS_DONE]", output_gds))
                    self.ide.queue.put(("[BACKEND]", f"Saved: {output_gds}"))
                else: self.ide.queue.put(("[BACKEND]", f"[ERR] Magic Failed:\n{proc.stderr}\n{proc.stdout}"))
            except Exception as e: self.ide.queue.put(("[BACKEND]", f"[ERR] Magic Execution Error: {e}"))
            
        self.start_spinner()
        self.magic_worker = FlowWorker(run_magic)
        self.magic_worker.finished_signal.connect(self.stop_spinner)
        self.magic_worker.start()

    def open_pdk_selector(self):
        dlg = PDKSelector(self.pdk_mgr, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.active_pdk = dlg.selected_config; self.term_log.append(f"[SYS] Target PDK: {self.active_pdk['name']}"); return True
        return False

    def read_stdout(self):
        data = self.proc.readAllStandardOutput().data().decode()
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
    
    def update_view(self):
        try:
            self.fast_peeker.show_insts = self.chk_inst.isChecked(); self.fast_peeker.show_pins = self.chk_pins.isChecked()
            self.fast_peeker.show_macros = self.chk_macros.isChecked(); self.fast_peeker.show_tapcells = self.chk_tap.isChecked()
            self.fast_peeker.show_nets = self.chk_nets.isChecked(); self.fast_peeker.show_power = self.chk_power.isChecked()
            
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
        
        macros = self.ide.project_config.get('macros', [])
        if macros:
            volare_base = self.active_pdk.get('lib', '').split("libs.ref")[0]
            import glob
            for lef in glob.glob(os.path.join(volare_base, "libs.ref", "*", "lef", "*.lef")):
                name = os.path.basename(lef).replace('.lef', '')
                if name in macros:
                    tcl_content += f'read_lef "{lef}"\n'
                    
        tcl_content += f'read_def "{def_path}"\n'
        
        with open(view_tcl, 'w') as f: f.write(tcl_content)
        subprocess.Popen(["openroad", "-gui", view_tcl], cwd=proj_root)
    
    def force_refresh_view(self):
        proj_root = self.ide.get_proj_root(self.ide.get_context()[0] or "design")
        def_path = os.path.join(proj_root, "results", "temp.def")
        if os.path.exists(def_path): 
            self.fast_peeker.load_def_file(def_path)

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
                macros = self.ide.project_config.get('macros', [])
                if macros:
                    lib_path = self.active_pdk.get('lib', '')
                    volare_base = lib_path.split("libs.ref")[0]
                    lib_search = os.path.join(volare_base, "libs.ref", "*", "lib", "*.lib")
                    import glob
                    for lib in glob.glob(lib_search):
                        name = os.path.basename(lib).replace('.lib', '')
                        if any(m in name for m in macros):
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


