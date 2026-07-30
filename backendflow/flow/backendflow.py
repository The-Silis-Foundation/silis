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
        self.peeker = SiliconPeeker()
        self.peeker.ide = self.ide
        self.fast_peeker = FastSiliconPeeker(self.ide)
        self.gds3d_port = GDS3DPort(self.ide) # [NEW] 3D Viewer Port
        
        self.def_ctrl_widget = QWidget()
        def_layout = QVBoxLayout(self.def_ctrl_widget); def_layout.setContentsMargins(0,0,0,0)
        
        self.chk_inst = QCheckBox("Cells"); self.chk_inst.setChecked(True)
        self.chk_macros = QCheckBox("Macros"); self.chk_macros.setChecked(True)
        self.chk_pins = QCheckBox("Pins"); self.chk_pins.setChecked(True)
        self.chk_nets = QCheckBox("Nets"); self.chk_nets.setChecked(False)
        self.chk_power = QCheckBox("Power"); self.chk_power.setChecked(True)
        
        self.btn_heat = QPushButton("Heatmap"); self.btn_heat.setCheckable(True)
        self.btn_heat.setStyleSheet("QPushButton:checked { background-color: #ffcccc; color: red; border: 1px solid red; }")
        
        def_layout.addWidget(QLabel("<b>DEF Layers</b>"))
        def_layout.addWidget(self.chk_inst); def_layout.addWidget(self.chk_macros); def_layout.addWidget(self.chk_pins)
        def_layout.addWidget(self.chk_nets); def_layout.addWidget(self.chk_power)
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
        self.signoff_steps = ["Antenna", "STA", "DRC"] 
        
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
        self.viz_tabs.addTab(self.peeker, "Simplified Viewer")
        self.viz_tabs.addTab(self.gds3d_port, "GDS View (3D)")
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

    def run_flow_step(self, step_name):
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
            self.term_log.append("\n[SIGNOFF] Running Signoff Timing Analysis...")
            lib_cmd = f"read_liberty \"{self.active_pdk['lib']}\""
            cmd = f"{lib_cmd}\nreport_checks -path_delay max -format full_clock_expanded -fields {{slew cap input_pins fanout}} -digits 4\nreport_worst_slack -max\nreport_tns\nreport_wns"
            self.send_command_internal(cmd)
            return

        if step_name == "DRC":
            if not self.active_pdk or 'gds' not in self.active_pdk: QMessageBox.critical(self, "Error", "PDK GDS Required."); return
            gds_file = os.path.join(results_dir, "design.gds")
            if not os.path.exists(gds_file): self.term_log.append("[ERR] Generate GDS first!"); return
            self.trigger_magic_drc(proj_root, gds_file)
            return

        if step_name == "Init":
            db_path = os.path.join(results_dir, "checkpoint.odb")
            if os.path.exists(db_path):
                reply = QMessageBox.question(self, "Resume?", "Found saved checkpoint. Load it?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.Yes: self.load_checkpoint(); return
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
            tcl_content = f"""read_lef "{self.active_pdk['tlef']}"\nread_lef "{self.active_pdk['lef']}"\n"""
            
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
set macros_json "\\{{\\n  \\"macros\\": \\{{\\n"
set first 1
foreach inst [[::ord::get_db_block] getInsts] {{
    if {{ [[$inst getMaster] isBlock] }} {{
        if {{ !$first }} {{ append macros_json ",\\n" }}
        set inst_name [$inst getName]
        set inst_name [string map [list \\\\ \\\\\\\\ \\" \\\\"] $inst_name]
        append macros_json "    \\"$inst_name\\": \\"[[$inst getMaster] getName]\\""
        set first 0
    }}
}}
append macros_json "\\n  \\}}\\n\\}}"
set reports_dir "{os.path.join(proj_root, 'reports').replace(chr(92), '/')}"
file mkdir $reports_dir
set fp [open "$reports_dir/{base}_sizes.json" w]
puts $fp $macros_json
close $fp
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
            cmd = load_template("cts.tcl", {"cts_cmd": cts_cmd, "write_cmd": write_cmd})
        elif step_name == "Route":
            guide_path = os.path.join(results_dir, "route.guide").replace("\\", "/")
            drc_path = os.path.join(reports_dir, "drc.rpt").replace("\\", "/")
            fix_script = os.path.join(proj_root, "fix.tcl").replace("\\", "/")
            try: 
                with open(fix_script, 'w') as f: f.write("set db [ord::get_db]; set chip [$db getChip]; set block [$chip getBlock]; set net_names {zero_ one_ logic0 logic1}; foreach name $net_names { set net [$block findNet $name]; if {$net != \"NULL\"} { $net setSigType \"SIGNAL\" } }")
            except: pass
            cmd = load_template("route.tcl", {"fix_script": fix_script, "guide_path": guide_path, "drc_path": drc_path, "write_cmd": write_cmd})

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
        threading.Thread(target=run_drc, daemon=True).start()

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
        threading.Thread(target=run_magic, daemon=True).start()

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
        if self.cmd_active and "openroad>" in data: self.cmd_active = False; self.force_refresh_view()

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
        if self.proc and self.proc.state() == QProcess.ProcessState.Running: self.cmd_active = True; self.proc.write(f"{cmd}\n".encode())
        else: self.term_log.append(f"[ERR] Backend not running. Click Reset.")
    
    def update_view(self):
        try:
            self.peeker.show_insts = self.chk_inst.isChecked(); self.peeker.show_pins = self.chk_pins.isChecked()
            self.peeker.show_macros = self.chk_macros.isChecked()
            self.peeker.show_nets = self.chk_nets.isChecked(); self.peeker.show_power = self.chk_power.isChecked()
            
            self.fast_peeker.show_insts = self.chk_inst.isChecked(); self.fast_peeker.show_pins = self.chk_pins.isChecked()
            self.fast_peeker.show_macros = self.chk_macros.isChecked()
            self.fast_peeker.show_nets = self.chk_nets.isChecked(); self.fast_peeker.show_power = self.chk_power.isChecked()
            
            if hasattr(self, 'btn_heat'): 
                self.peeker.show_heatmap = self.btn_heat.isChecked()
                
            self.peeker.redraw()
            self.fast_peeker.redraw()
        except: pass
    
    def load_routed_design(self):
        proj_root = self.ide.get_proj_root(self.ide.get_context()[0] or "design")
        def_path = os.path.join(proj_root, "results", "final_routed.def")
        if os.path.exists(def_path): 
            self.term_log.append(f"[SYS] Loading Routed Design from: {def_path}")
            self.peeker.load_def_file(def_path); self.fast_peeker.load_def_file(def_path)
            self.chk_nets.setChecked(True)
            self.peeker.show_nets = True; self.fast_peeker.show_nets = True
            self.peeker.redraw(); self.fast_peeker.redraw()
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
            self.peeker.load_def_file(def_path)
            self.fast_peeker.load_def_file(def_path)

    def load_checkpoint(self):
        proj_root = self.ide.get_proj_root(self.ide.get_context()[0] or "design")
        db_path = os.path.join(proj_root, "results", "checkpoint.odb").replace("\\", "/")
        if os.path.exists(db_path):
            self.term_log.append(f"[SYS] Loading Checkpoint from {db_path}...")
            self.send_command_internal(f"read_db \"{db_path}\"")
            self.force_refresh_view(); return True
        return False

    def save_checkpoint(self):
        if not self.proc: return
        proj_root = self.ide.get_proj_root(self.ide.get_context()[0] or "design")
        db_path = os.path.join(proj_root, "results", "checkpoint.odb").replace("\\", "/")
        self.term_log.append(f"[SYS] Saving Checkpoint to {db_path}...")
        self.send_command_internal(f"write_db \"{db_path}\"")


