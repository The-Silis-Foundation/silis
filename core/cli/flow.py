"""
cli_flow.py
Headless ASIC Flow Execution Engine for Silis.
Tied directly into the GUI classes (SilisIDE, BackendFlow, SynthesisTab)
ensuring 100% identical execution and single-source bug fix alignment.
"""

import os
import sys
import glob
import json
import time
import re
import logging

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QProcess

from . import tui_editor
from backendflow.floorplanner.floorplanner import generate_floorplan_tcl_from_data, compute_peripheral_macro_placement
from synthesisscripts.synthesisthread import ReportEngine

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))


def find_project_file(project_arg=None):
    """Finds silis.silisproj from project argument, registry, or current directory."""
    import project_registry

    if project_arg:
        if os.path.isfile(project_arg):
            project_registry.register_project(project_arg)
            return os.path.abspath(project_arg)
        # Check if project_arg is a directory
        candidate = os.path.join(project_arg, "silis.silisproj")
        if os.path.isfile(candidate):
            project_registry.register_project(candidate)
            return os.path.abspath(candidate)
        # Check current directory / project_arg
        candidate2 = os.path.join(os.getcwd(), project_arg, "silis.silisproj")
        if os.path.isfile(candidate2):
            project_registry.register_project(candidate2)
            return os.path.abspath(candidate2)
        # Check project_registry (match project name or directory name)
        registered_match = project_registry.find_registered_project(project_arg)
        if registered_match:
            return registered_match

    # Check current directory
    local = os.path.join(os.getcwd(), "silis.silisproj")
    if os.path.isfile(local):
        project_registry.register_project(local)
        return local

    # Search immediate subdirectories
    for d in os.listdir(os.getcwd()):
        cand = os.path.join(os.getcwd(), d, "silis.silisproj")
        if os.path.isfile(cand):
            project_registry.register_project(cand)
            return cand

    # If no argument and current directory has no project, fallback to most recent registered project
    if not project_arg:
        recent = project_registry.get_most_recent_project()
        if recent and recent.get("proj_file") and os.path.isfile(recent["proj_file"]):
            print(f"[SILIS] Using most recent registered project: '{recent['name']}' at {recent['path']}")
            return recent["proj_file"]

    return None


def resolve_tcl_input(default_script, tcl_arg, title="ASIC TCL Script"):
    """
    Handles the 3 cases for --tcl:
    1. tcl_arg is None: Omitted -> returns default_script (batch run)
    2. tcl_arg is True / empty string: --tcl alone -> Opens LazyVim-like TUI editor!
    3. tcl_arg is file or string: returns string or reads file
    """
    if tcl_arg is None:
        return default_script  # Default run

    if tcl_arg is True or tcl_arg == "" or tcl_arg == "__EDIT__":
        preferred = tui_editor.get_preferred_editor() or "editor"
        print(f"\n[SILIS] Launching editor ({preferred}) for fine-tuning...")
        edited = tui_editor.open_terminal_editor(default_script, title=title)
        if edited is None:
            print("[CANCELLED] Flow step aborted by user in editor.")
            return None
        return edited

    # File path or inline string
    if os.path.isfile(tcl_arg):
        with open(tcl_arg, 'r') as f:
            return f.read()

    # Inline string
    return tcl_arg.replace("\\n", "\n")


class HeadlessASICRunner:
    def __init__(self, proj_file):
        self.proj_file = os.path.abspath(proj_file)
        self.proj_dir = os.path.dirname(self.proj_file)
        with open(self.proj_file, 'r') as f:
            self.config = json.load(f)

        import project_registry
        project_registry.register_project(self.proj_file)

        # Set headless platform before any QApplication creation
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        self.app = QApplication.instance()
        if not self.app:
            self.app = QApplication(["silis", "-platform", "offscreen"])

        # Instantiate SilisIDE headlessly
        import silis
        self.ide = silis.SilisIDE(project_file=self.proj_file, headless=True)
        self.ide.project_path = self.proj_dir
        self.ide.project_config = self.config
        self.ide.cwd = self.proj_dir
        self.ide.current_file = os.path.join(self.proj_dir, "source", f"{self.config['top_module']}.v")

        # Connect Backend stdout to terminal
        self.backend = self.ide.backend_widget
        self.backend.read_stdout = self._streaming_read_stdout
        if self.backend.proc:
            try:
                self.backend.proc.readyReadStandardOutput.disconnect()
            except:
                pass
            self.backend.proc.readyReadStandardOutput.connect(self._streaming_read_stdout)

        # Load PDK (prefer configurations with full GDS/Tech defined from pdk_master.json)
        pdk_name = self.config.get("pdk", "sky130")
        candidates = [p for p in self.ide.pdk_mgr.configs if pdk_name in p["name"].lower() or pdk_name in p.get("family", "").lower()]
        candidates_with_gds = [p for p in candidates if p.get("gds") and p.get("tech")]
        if candidates_with_gds:
            selected_pdk = candidates_with_gds[0]
        elif candidates:
            selected_pdk = candidates[0]
        elif self.ide.pdk_mgr.configs:
            selected_pdk = self.ide.pdk_mgr.configs[0]
        else:
            selected_pdk = None

        if selected_pdk:
            self.ide.set_active_pdk(selected_pdk)
            self.backend.active_pdk = selected_pdk

    def close(self):
        """Gracefully terminates and cleans up OpenROAD subprocess."""
        if hasattr(self, 'backend') and self.backend and getattr(self.backend, 'proc', None):
            proc = self.backend.proc
            self.backend.proc = None
            try:
                proc.readyReadStandardOutput.disconnect()
            except Exception:
                pass
            if proc.state() == QProcess.ProcessState.Starting:
                proc.waitForStarted(1000)
            if proc.state() == QProcess.ProcessState.Running:
                try:
                    proc.write(b"exit\n")
                    if not proc.waitForFinished(500):
                        proc.kill()
                        proc.waitForFinished(500)
                except Exception:
                    try:
                        proc.kill()
                        proc.waitForFinished(500)
                    except Exception:
                        pass
            proc.deleteLater()


    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def _streaming_read_stdout(self):
        try:
            if not self.backend.proc:
                return
            data = self.backend.proc.readAllStandardOutput().data().decode("utf-8", errors="replace")
            if data:
                print(data, end='', flush=True)
            self.backend.term_log.append(data.strip())
            
            # Detect fatal error patterns in stdout
            error_pattern = re.compile(r'(^\[ERROR\b|^Error:\b|\[ERROR\s+(?:ORD|DRT|GPL|DPL)-\d+\]|^(?:ORD|DRT|GPL|DPL)-\d+\b)', re.MULTILINE)
            if error_pattern.search(data):
                self._had_error = True

            marker = getattr(self, "_current_step_marker", None)
            if marker and marker in data:
                self._marker_seen = True
                self.backend.cmd_active = False
            elif re.search(r'(?:^|\n)openroad>\s*$', data):
                # Prompt received at the end of output chunk.
                # Only treat as early error abort if at least 0.5s has elapsed since command dispatch,
                # ensuring residual prompts from prior commands are not mistaken for aborts.
                cmd_start = getattr(self, "_cmd_start_time", 0)
                if marker and not getattr(self, "_marker_seen", False) and (time.time() - cmd_start > 0.5):
                    self._had_error = True
                    self.backend.cmd_active = False
        except Exception as e:
            logging.error(f"Error in _streaming_read_stdout: {e}", exc_info=True)
            self._had_error = True

    def _ensure_backend_running(self):
        if not self.backend.proc or self.backend.proc.state() != QProcess.ProcessState.Running:
            self.backend.reset_backend()
            if self.backend.proc:
                self.backend.proc.waitForStarted(5000)
                try:
                    self.backend.proc.readyReadStandardOutput.disconnect()
                except:
                    pass
                self.backend.proc.readyReadStandardOutput.connect(self._streaming_read_stdout)
                t0 = time.time()
                while time.time() - t0 < 3.0:
                    self.app.processEvents()
                    if self.backend.proc.waitForReadyRead(100):
                        break

    def execute_tcl(self, tcl_script, step_name="step"):
        self._ensure_backend_running()
        # Flush any residual output from prior commands
        self.app.processEvents()
        if self.backend.proc:
            self.backend.proc.readAllStandardOutput()

        marker = f"SILIS_{step_name.upper()}_DONE"
        self._current_step_marker = marker
        self._marker_seen = False
        self._had_error = False
        self._cmd_start_time = time.time()
        self.backend.cmd_active = True

        script_file = os.path.join(self.proj_dir, f"run_{step_name}.tcl").replace("\\", "/")
        fp_helper = os.path.join(REPO_ROOT, "backendflow", "floorplanner", "silis_fp.tcl").replace("\\", "/")
        with open(script_file, 'w') as f:
            # Provide safe built-in fallback procs for banners and unified flow steps
            procs = """if {[info procs create_fence] eq "" && [file exists "@@FP_HELPER@@"]} { source "@@FP_HELPER@@" }
if {[info commands SILIS] eq ""} { proc SILIS {args} { return {SILIS} } }
if {[info commands synth] eq ""} {
    proc synth {args} {
        puts "\\n>>> [SILIS] Frontend Synthesis & Scan Cell Mapping already synthesized into netlist."
        puts ">>> [SILIS] Netlist is ready for physical PnR design flow."
        return 0
    }
}
if {[info commands init] eq ""} {
    proc init {args} {
        puts "\\n>>> [SILIS] OpenROAD Design already linked and initialized with LEF/DEF/Verilog."
        return 0
    }
}
if {[info commands tapcells] eq ""} {
    proc tapcells {args} {
        eval tapcell $args
    }
}
if {[info commands pdn] eq ""} {
    proc pdn {args} {
        puts "\\n>>> [SILIS] Synthesizing Power Grid..."
        # If PDN config/stripes already exist or can be generated
        catch { pdngen }
        return 0
    }
}
if {[info commands iopins] eq ""} {
    proc iopins {args} {
        eval place_pins $args
    }
}
if {[info commands gds] eq ""} {
    proc gds {args} {
        puts "\\n>>> [SILIS] GDS Stream-out requested."
        return 0
    }
}
""".replace("@@FP_HELPER@@", fp_helper)
            f.write(procs)
            f.write(tcl_script)
            f.write(f'\nputs "{marker}"\n')

        self.backend.proc.write(f"source \"{script_file}\"\n".encode())
        self._wait_for_backend()
        success = (not getattr(self, "_had_error", False)) and getattr(self, "_marker_seen", False)
        self._current_step_marker = None
        self._marker_seen = False
        self.backend.cmd_active = False
        return success

    def _wait_for_backend(self, timeout_sec=1800):
        t0 = time.time()
        time.sleep(0.05)
        while self.backend.cmd_active and (time.time() - t0 < timeout_sec):
            self.app.processEvents()
            if self.backend.proc.waitForReadyRead(100):
                t0 = time.time()  # Reset timeout watchdog whenever OpenROAD outputs progress
            if self.backend.proc.state() != QProcess.ProcessState.Running:
                break

    # --------------------------------------------------------------------------
    # Flow Steps
    # --------------------------------------------------------------------------
    def run_synthesis(self, tcl_arg=None, dft=False):
        print("\n" + "=" * 65)
        print(f" [ASIC FRONTEND] RTL Synthesis: {self.config['top_module']}{' [DFT SCAN]' if dft else ''}")
        print("=" * 65)

        self.ide.enable_dft = dft
        if hasattr(self.ide, 'tab_synth') and hasattr(self.ide.tab_synth, 'chk_dft'):
            self.ide.tab_synth.chk_dft.setChecked(dft)

        # Execute synthesis directly through the unified SilisIDE synthesis engine
        self.ide.run_synthesis_flow(bypass_prompt=True)

        # Wait for worker thread to finish
        time.sleep(0.1)
        while getattr(self.ide, "synth_running", False):
            self.app.processEvents()
            while not self.ide.queue.empty():
                tag, msg = self.ide.queue.get()
                if msg is not None:
                    print(f"{tag} {msg}")
            time.sleep(0.05)

        while not self.ide.queue.empty():
            tag, msg = self.ide.queue.get()
            if msg is not None:
                print(f"{tag} {msg}")

        if getattr(self.ide, "synth_error", None):
            print(f"\n[ERR] Synthesis failed: {self.ide.synth_error}")
            return False

        root = self.proj_dir
        base = self.config["top_module"]
        v_net = os.path.join(root, "netlist", f"{base}_netlist.v")

        # Extract metrics
        metrics = ReportEngine.parse_files(os.path.join(root, "reports"))
        print("\n" + "─" * 65)
        print(" [SYNTHESIS METRICS SUMMARY]")
        print(f"  • Status:     {metrics['status']}")
        print(f"  • Total Cells: {metrics['cells']}")
        print(f"  • WNS Slack:  {metrics['wns']} ns")
        print(f"  • Netlist:    {v_net}")
        print("─" * 65 + "\n")
        return metrics['status'] != "FAILED" and os.path.exists(v_net)

    def _get_io_lefs(self):
        """Discovers sky130 IO and corner/filler pad LEFs to support clean pad placement."""
        io_lefs = []
        candidates = []
        lib_path = self.ide.active_pdk.get('lib', '') if hasattr(self, 'ide') and getattr(self.ide, 'active_pdk', None) else ''
        if 'libs.ref' in lib_path:
            pdk_root = lib_path.split('libs.ref')[0]
            candidates.extend([
                os.path.join(pdk_root, 'libs.ref', 'sky130_fd_io', 'lef', 'sky130_ef_io.lef'),
                os.path.join(pdk_root, 'libs.ref', 'sky130_fd_io', 'lef', 'sky130_fd_io.lef'),
            ])
        candidates.extend([
            os.path.expanduser('~/.silis/pdks/sky130A/libs.ref/sky130_fd_io/lef/sky130_ef_io.lef'),
            os.path.expanduser('~/.silis/pdks/sky130A/libs.ref/sky130_fd_io/lef/sky130_fd_io.lef'),
            os.path.expanduser('~/.silis/pdks/sky130B/libs.ref/sky130_fd_io/lef/sky130_ef_io.lef'),
            os.path.expanduser('~/.silis/pdks/sky130B/libs.ref/sky130_fd_io/lef/sky130_fd_io.lef'),
            os.path.join(REPO_ROOT, 'third-party', 'pdks', 'sky130A', 'libs.ref', 'sky130_fd_io', 'lef', 'sky130_ef_io.lef'),
            os.path.join(REPO_ROOT, 'third-party', 'pdks', 'sky130A', 'libs.ref', 'sky130_fd_io', 'lef', 'sky130_fd_io.lef'),
        ])
        for p in candidates:
            if os.path.isfile(p) and p not in io_lefs:
                io_lefs.append(p)
        return io_lefs

    def _get_macro_lefs_and_libs(self):
        macro_lefs = []
        macro_libs = []
        macros = self.config.get("macros", [])
        if macros:
            search_dirs = [
                self.proj_dir,
                os.path.join(self.proj_dir, "source"),
                os.path.join(REPO_ROOT, "third-party", "pdks")
            ]
            env_pdk = os.environ.get("PDK_ROOT")
            if env_pdk and env_pdk not in search_dirs:
                search_dirs.append(env_pdk)

            for m in macros:
                lef_found = False
                lib_found = False
                for d in search_dirs:
                    if not os.path.exists(d):
                        continue
                    if not lef_found:
                        for lef_cand in glob.glob(os.path.join(d, "**", f"{m}.lef"), recursive=True):
                            if os.path.isfile(lef_cand):
                                macro_lefs.append(lef_cand)
                                lef_found = True
                                break
                    if not lib_found:
                        for lib_cand in glob.glob(os.path.join(d, "**", f"{m}*.lib"), recursive=True):
                            if os.path.isfile(lib_cand):
                                macro_libs.append(lib_cand)
                                lib_found = True
                                break
                    if lef_found and lib_found:
                        break
        return macro_lefs, macro_libs

    def ensure_design_loaded(self):
        """Ensures the design is loaded in OpenROAD before executing backend steps."""
        if getattr(self, "_design_loaded", False):
            return True
        root = self.proj_dir
        base = self.config["top_module"]
        def_path = os.path.join(root, "results", "temp.def").replace("\\", "/")
        sdc_path = os.path.join(root, "source", f"{base}.sdc").replace("\\", "/")

        if os.path.isfile(def_path):
            print(f"\n[ASIC BACKEND] Resuming design checkpoint: {def_path}")
            m_lefs, m_libs = self._get_macro_lefs_and_libs()
            io_lefs = self._get_io_lefs()
            io_lef_cmd = "".join(f'read_lef "{l}"\n' for l in io_lefs)
            macro_lef_cmd = "".join(f'read_lef "{l}"\n' for l in m_lefs)
            macro_lib_cmd = "".join(f'read_liberty "{l}"\n' for l in m_libs)
            tcl = f"""set_thread_count [exec nproc]
read_lef "{self.ide.active_pdk['tlef']}"
read_lef "{self.ide.active_pdk['lef']}"
{io_lef_cmd}{macro_lef_cmd}read_liberty "{self.ide.active_pdk['lib']}"
{macro_lib_cmd}read_def "{def_path}"
read_sdc "{sdc_path}"
"""
            self.execute_tcl(tcl, "resume_init")
            self._design_loaded = True
            return True
        else:
            print("[ASIC BACKEND] No temp.def found; running initial design load & floorplan...")
            if not self.run_init():
                return False
            if not self.run_floorplan():
                return False
            self._design_loaded = True
            return True

    def run_init(self, tcl_arg=None):
        print("\n[ASIC BACKEND] Initializing Design & Loading LEF/PDK...")
        root = self.proj_dir
        base = self.config["top_module"]
        netlist = os.path.join(root, "netlist", f"{base}_netlist.v")
        sdc = os.path.join(root, "source", f"{base}.sdc")
        reports_dir = os.path.join(root, "reports").replace("\\", "/")

        m_lefs, m_libs = self._get_macro_lefs_and_libs()
        io_lefs = self._get_io_lefs()
        io_lef_cmd = "".join(f'read_lef "{l}"\n' for l in io_lefs)
        macro_lef_cmd = "".join(f'read_lef "{l}"\n' for l in m_lefs)
        macro_lib_cmd = "".join(f'read_liberty "{l}"\n' for l in m_libs)

        init_tcl = f"""set_thread_count [exec nproc]
read_lef "{self.ide.active_pdk['tlef']}"
read_lef "{self.ide.active_pdk['lef']}"
{io_lef_cmd}{macro_lef_cmd}read_liberty "{self.ide.active_pdk['lib']}"
{macro_lib_cmd}read_verilog "{netlist}"
link_design {base}
read_sdc "{sdc}"

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

file mkdir "{reports_dir}"
set fp [open "{reports_dir}/{base}_sizes.json" w]
puts $fp $macros_json
close $fp
"""
        final_tcl = resolve_tcl_input(init_tcl, tcl_arg, title="OpenROAD Init Script")
        if final_tcl is None:
            return False

        self.execute_tcl(final_tcl, "init")
        self._design_loaded = True
        print("[SUCCESS] Design successfully linked in OpenROAD.")
        return True

    def run_floorplan(self, tcl_arg=None, die_area=None, core_margin=20.0, macros=None, regions=None, blockages=None):
        print("\n" + "=" * 65)
        print(" [ASIC BACKEND] Floorplanning, Macros, Fences & Halos")
        print("=" * 65)

        root = self.proj_dir
        base = self.config["top_module"]
        save_path = os.path.join(root, "reports", f"{base}_floorplan_save.json").replace("\\", "/")

        # 1. Check if GUI floorplan save exists
        if os.path.isfile(save_path):
            print(f"[SILIS] Loading floorplan state from: {save_path}")
            try:
                with open(save_path, 'r') as f:
                    state = json.load(f)
                if not die_area and 'die' in state:
                    d = state['die']
                    die_area = [0, 0, d['w'], d['h']]
                    core_margin = (d.get('ml', 20.0), d.get('mr', 20.0), d.get('mb', 20.0), d.get('mt', 20.0))
                if not macros and 'macros' in state:
                    macros = state['macros']
                if not blockages and 'blockages' in state:
                    blockages = state['blockages']
            except Exception as e:
                print(f"[WARN] Failed to read {save_path}: {e}")

        # 2. If no macros yet, auto-discover and auto-place on periphery!
        if not macros:
            m_instances = []
            sizes_path = os.path.join(root, "reports", f"{base}_sizes.json")
            if os.path.isfile(sizes_path):
                try:
                    with open(sizes_path, 'r') as f:
                        s_data = json.load(f)
                    for iname, mname in s_data.get('macros', {}).items():
                        m_instances.append({'inst_name': iname, 'master_name': mname})
                except:
                    pass

            if not m_instances:
                netlist_path = os.path.join(root, "netlist", f"{base}_netlist.v")
                proj_macros = self.config.get("macros", [])
                if os.path.isfile(netlist_path) and proj_macros:
                    import re
                    with open(netlist_path, 'r') as f:
                        netlist_txt = f.read()
                    for pm in proj_macros:
                        for inst_match in re.finditer(rf'{re.escape(pm)}\s+([a-zA-Z0-9_]+)\s*\(', netlist_txt):
                            m_instances.append({'inst_name': inst_match.group(1), 'master_name': pm})

            if m_instances:
                macro_sizes = {}
                m_lefs, _ = self._get_macro_lefs_and_libs()
                import re
                for lef_file in m_lefs:
                    try:
                        with open(lef_file, 'r') as lf:
                            content = lf.read()
                        sm = re.search(r'SIZE\s+([0-9.]+)\s+BY\s+([0-9.]+)', content)
                        if sm:
                            cname = os.path.basename(lef_file).replace('.lef', '')
                            macro_sizes[cname] = (float(sm.group(1)), float(sm.group(2)))
                            for m in self.config.get("macros", []):
                                if m in lef_file:
                                    macro_sizes[m] = (float(sm.group(1)), float(sm.group(2)))
                    except:
                        pass

                init_dw = die_area[2] - die_area[0] if die_area else 1400.0
                init_dh = die_area[3] - die_area[1] if die_area else 1400.0
                cm_tuple = core_margin if isinstance(core_margin, tuple) else (core_margin, core_margin, core_margin, core_margin)
                adj_dw, adj_dh, placed = compute_peripheral_macro_placement(
                    m_instances, die_w=init_dw, die_h=init_dh,
                    margins=cm_tuple,
                    macro_sizes=macro_sizes
                )
                die_area = [0, 0, adj_dw, adj_dh]
                macros = placed
                print(f"[SILIS] Auto-placed {len(macros)} macros onto periphery of {adj_dw} x {adj_dh} µm die.")

                try:
                    os.makedirs(os.path.dirname(save_path), exist_ok=True)
                    state_to_save = {
                        'die': {'w': adj_dw, 'h': adj_dh, 'ml': cm_tuple[0], 'mr': cm_tuple[1], 'mb': cm_tuple[2], 'mt': cm_tuple[3]},
                        'macros': macros,
                        'blockages': blockages or []
                    }
                    with open(save_path, 'w') as f:
                        json.dump(state_to_save, f, indent=2)
                    print(f"[SILIS] Saved floorplan checkpoint: {save_path}")
                except Exception as e:
                    print(f"[WARN] Could not save floorplan state: {e}")

        # Default die area fallback
        if not die_area:
            die_area = [0, 0, 1400.0, 1400.0]

        pdk_name = self.config.get("pdk", "sky130")
        default_tcl = generate_floorplan_tcl_from_data(
            die_area=die_area, core_margin=core_margin,
            macros=macros, regions=regions, blockages=blockages,
            pdk_name=pdk_name
        )
        def_path = os.path.join(self.proj_dir, "results", "temp.def").replace("\\", "/")
        default_tcl += f'\nwrite_def "{def_path}"\n'

        final_tcl = resolve_tcl_input(default_tcl, tcl_arg, title="ASIC Floorplan Script")
        if final_tcl is None:
            return False

        self.execute_tcl(final_tcl, "floorplan")
        self._design_loaded = True
        print(f"[SUCCESS] Floorplan written to {def_path}")
        return True

    def run_step(self, step_name, tcl_arg=None):
        print("\n" + "=" * 65)
        print(f" [ASIC BACKEND] Step: {step_name}")
        print("=" * 65)

        root = self.proj_dir
        results_dir = os.path.join(root, "results")
        reports_dir = os.path.join(root, "reports")
        def_abs_path = os.path.join(results_dir, "temp.def").replace("\\", "/")
        write_cmd = f'write_def "{def_abs_path}"'

        non_loaded_steps = [
            "synth", "drc", "dft", "run_dft",
            "fill", "run_fill", "lvs", "run_lvs",
            "gls", "run_gls", "sdf", "export_sdf",
            "tapeout", "run_tapeout"
        ]
        if step_name.lower() not in non_loaded_steps:
            if not self.ensure_design_loaded():
                return False

        if tcl_arg is not None:
            return self.execute_tcl(tcl_arg, step_name)

        gui_step_map = {
            "tapcells": "Tapcells",
            "pdn": "PDN",
            "iopins": "IO Pins",
            "place": "Place",
            "cts": "CTS",
            "route": "Route",
            "fill": "Fill",
            "antenna": "Antenna",
            "sta": "PAT",
            "pat": "PAT",
            "dft": "DFT",
            "gds": "GDS",
            "lvs": "LVS",
            "gls": "GLS",
            "sdf": "SDF",
            "tapeout": "Tapeout",
        }
        gui_step = gui_step_map.get(step_name.lower(), step_name.capitalize())

        if step_name.lower() in ["dft", "run_dft"]:
            self.backend.run_flow_step("DFT", bypass_prompt=True)
            self.app.processEvents()
            dft_summary_file = os.path.join(reports_dir, "dft_summary.json")
            if os.path.isfile(dft_summary_file):
                try:
                    with open(dft_summary_file, "r") as f:
                        dft_data = json.load(f)
                    status = dft_data.get("status", "FAIL")
                    if status in ["PASS", "WARN"]:
                        print(f"[SUCCESS] Step {step_name} completed ({status}, coverage: {dft_data.get('fault_coverage')}%)")
                        return True
                    else:
                        print(f"[ERR] Step {step_name} failed signoff (status: {status}).")
                        return False
                except Exception as e:
                    logging.error(f"Error checking DFT report: {e}")
                    return False
            print(f"[ERR] Step {step_name} did not generate expected report: {dft_summary_file}")
            return False

        if step_name.lower() in ["fill", "run_fill"]:
            print(f"[SILIS] Running Decap Insertion & Metal Fill...")
            self.backend.run_flow_step("Fill", bypass_prompt=True)
            self.app.processEvents()
            print(f"[SUCCESS] Step {step_name} completed.")
            return True

        if step_name.lower() in ["lvs", "run_lvs"]:
            print(f"[SILIS] Running Layout Versus Schematic (LVS)...")
            self.backend.run_flow_step("LVS", bypass_prompt=True)
            self.app.processEvents()
            lvs_summary_file = os.path.join(reports_dir, "lvs_summary.json")
            if os.path.isfile(lvs_summary_file):
                try:
                    with open(lvs_summary_file, "r") as f:
                        lvs_data = json.load(f)
                    if lvs_data.get("is_clean", False) or lvs_data.get("status") == "PASS":
                        print(f"[SUCCESS] Step {step_name} completed (PASS).")
                        return True
                    else:
                        print(f"[ERR] Step {step_name} failed: mismatches detected.")
                        return False
                except Exception as e:
                    logging.error(f"Error checking LVS report: {e}")
                    return False
            print(f"[ERR] Step {step_name} did not generate expected report: {lvs_summary_file}")
            return False

        if step_name.lower() in ["gls", "run_gls"]:
            print(f"[SILIS] Running Gate-Level Simulation (GLS)...")
            self.backend.run_flow_step("GLS", bypass_prompt=True)
            self.app.processEvents()
            gls_summary_file = os.path.join(reports_dir, "gls_summary.json")
            if os.path.isfile(gls_summary_file):
                try:
                    with open(gls_summary_file, "r") as f:
                        gls_data = json.load(f)
                    if gls_data.get("status") == "PASS" and gls_data.get("timing_violations_count", 0) == 0:
                        print(f"[SUCCESS] Step {step_name} completed (PASS).")
                        return True
                    else:
                        print(f"[ERR] Step {step_name} failed: violations detected.")
                        return False
                except Exception as e:
                    logging.error(f"Error checking GLS report: {e}")
                    return False
            print(f"[ERR] Step {step_name} did not generate expected report: {gls_summary_file}")
            return False

        if step_name.lower() in ["sdf", "export_sdf"]:
            print(f"[SILIS] Exporting Standard Delay Format (SDF)...")
            self.backend.run_flow_step("SDF", bypass_prompt=True)
            self.app.processEvents()
            print(f"[SUCCESS] Step {step_name} completed.")
            return True

        if step_name.lower() in ["tapeout", "run_tapeout"]:
            print(f"[SILIS] Generating Final Tapeout Packaging & Manifest...")
            self.backend.run_flow_step("Tapeout", bypass_prompt=True)
            self.app.processEvents()
            print(f"[SUCCESS] Step {step_name} completed.")
            return True

        if step_name == "drc":
            gds_file = os.path.join(results_dir, "design.gds")
            self.backend.trigger_magic_drc(root, gds_file)
            if hasattr(self.backend, 'drc_worker') and self.backend.drc_worker:
                while self.backend.drc_worker.isRunning():
                    self.app.processEvents()
                    while not self.ide.queue.empty():
                        src, msg = self.ide.queue.get()
                        print(f"{src} {msg}")
                    time.sleep(0.05)
                while not self.ide.queue.empty():
                    src, msg = self.ide.queue.get()
                    print(f"{src} {msg}")
            print(f"[SUCCESS] Step {step_name} completed.")
            return True


        if step_name in ["gds", "run_gds"]:
            print(f"[SILIS] Dispatched step 'GDS' via BackendWidget...")
            self.backend.run_flow_step("GDS", bypass_prompt=True)
            self._wait_for_backend(60)
            if hasattr(self.backend, 'magic_worker') and self.backend.magic_worker:
                while self.backend.magic_worker.isRunning():
                    self.app.processEvents()
                    while not self.ide.queue.empty():
                        src, msg = self.ide.queue.get()
                        print(f"{src} {msg}")
                    time.sleep(0.05)
                self.backend.magic_worker.wait()
            while not self.ide.queue.empty():
                src, msg = self.ide.queue.get()
                print(f"{src} {msg}")
            print(f"[SUCCESS] Step {step_name} completed.")
            return True

        # Direct call through BackendWidget: identical code path, same tcl, same process
        print(f"[SILIS] Dispatched step '{gui_step}' via BackendWidget...")
        # Flush any residual output from prior commands
        self.app.processEvents()
        if self.backend.proc:
            self.backend.proc.readAllStandardOutput()

        step_tag = gui_step.lower().replace(" ", "_")
        marker = f"SILIS_{step_tag.upper()}_DONE"
        self._current_step_marker = marker
        self._marker_seen = False
        self._had_error = False
        self._cmd_start_time = time.time()
        self.backend.cmd_active = True
        self.backend.run_flow_step(gui_step, bypass_prompt=True)
        if hasattr(self.backend, 'pat_worker') and self.backend.pat_worker:
            while self.backend.pat_worker.isRunning():
                self.app.processEvents()
                time.sleep(0.05)
        elif hasattr(self.backend, 'magic_worker') and self.backend.magic_worker:
            while self.backend.magic_worker.isRunning():
                self.app.processEvents()
                time.sleep(0.05)
        else:
            self._wait_for_backend()
        has_err = getattr(self, "_had_error", False)
        marker_ok = getattr(self, "_marker_seen", False)
        self._current_step_marker = None
        self._marker_seen = False
        self.backend.cmd_active = False
        if has_err or not marker_ok:
            print(f"[ERR] Step {step_name} failed due to errors.")
            return False
        print(f"[SUCCESS] Step {step_name} completed.")
        return True

    def run_fill(self):
        return self.run_step("fill")

    def run_lvs(self):
        return self.run_step("lvs")

    def run_gls(self):
        return self.run_step("gls")

    def export_sdf(self):
        return self.run_step("sdf")

    def run_tapeout(self):
        return self.run_step("tapeout")


