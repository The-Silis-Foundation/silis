import os
import glob
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtCore import QProcess

class YosysStructuralWorker(QThread):
    log = pyqtSignal(str, str)
    finished = pyqtSignal(str, str, str)

    def __init__(self, root, src, module_name, mode, pdk_lib=None):
        super().__init__()
        self.root = root
        self.src = src
        self.module_name = module_name
        self.mode = mode
        self.pdk_lib = pdk_lib

    def run(self):
        build_dir = os.path.join(self.root, "build")
        os.makedirs(build_dir, exist_ok=True)
        suffix = f"_{self.mode}" if self.mode == "gate" else ""
        out_path = os.path.join(build_dir, f"structural_{self.module_name}{suffix}.json")

        # Fast netlist cache check: return instantly if sources have not changed
        if os.path.exists(out_path):
            json_mtime = os.path.getmtime(out_path)
            src_mtimes = [os.path.getmtime(s) for s in self.src if os.path.exists(s)]
            if src_mtimes and json_mtime >= max(src_mtimes):
                self.log.emit(f"Block Diagram Ready ({self.module_name}) [Cached].", "INFO")
                self.finished.emit(out_path, self.module_name, self.mode)
                return

        self.log.emit(f"Extracting structural JSON for {self.module_name}...", "INFO")
        
        # Verify target module exists in sources; auto-resolve top if specified module_name is missing
        import re
        target_mod = self.module_name
        found_mods = []
        for s in self.src:
            if os.path.exists(s):
                try:
                    with open(s, 'r', errors='ignore') as sf:
                        found_mods.extend(re.findall(r'\b(?:module|entity)\s+([a-zA-Z_][a-zA-Z0-9_$]*)', sf.read()))
                except Exception:
                    pass

        if found_mods and target_mod not in found_mods:
            # Module name mismatch (e.g. project name was used instead of module name)
            self.log.emit(f"Module '{target_mod}' not found in sources; auto-selecting '{found_mods[0]}'.", "WARN")
            target_mod = found_mods[0]
            out_path = os.path.join(build_dir, f"structural_{target_mod}{suffix}.json")
            if os.path.exists(out_path):
                json_mtime = os.path.getmtime(out_path)
                src_mtimes = [os.path.getmtime(s) for s in self.src if os.path.exists(s)]
                if src_mtimes and json_mtime >= max(src_mtimes):
                    self.log.emit(f"Block Diagram Ready ({target_mod}) [Cached].", "INFO")
                    self.finished.emit(out_path, target_mod, self.mode)
                    return

        script_path = os.path.join(build_dir, "temp_synth.ys")
        with open(script_path, "w") as f:
            vhdl_files = [s for s in self.src if s.endswith('.vhd') or s.endswith('.vhdl')]
            vlog_files = [s for s in self.src if not (s.endswith('.vhd') or s.endswith('.vhdl'))]
            vhdl_files = sorted(vhdl_files, key=lambda x: 0 if any(k in os.path.basename(x).lower() for k in ['pack', 'pkg', 'type', 'const']) else 1)
            
            if vhdl_files:
                plugin_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "third-party", "plugins", "ghdl.so"))
                if os.path.exists(plugin_path):
                    f.write(f"plugin -i {plugin_path};\n")
                else:
                    f.write("plugin -i ghdl;\n")
                work_lib = os.path.basename(self.root)
                if any("neorv32" in str(x).lower() for x in [self.root, target_mod, work_lib] + vhdl_files):
                    work_lib = "neorv32"
                f.write(f"ghdl --work={work_lib} {' '.join(vhdl_files)} -e {target_mod};\n")
                
            for s in vlog_files:
                if s.endswith(".sv"):
                    f.write(f"read_verilog -sv {s}\n")
                else:
                    f.write(f"read_verilog {s}\n")
            
            f.write(f"hierarchy -top {target_mod}\n")
            # Always generate architectural block schematic with prep
            f.write(f"prep -top {target_mod}\n")
            f.write(f"write_json {out_path}\n")
            
        # Locate yosys executable: prefer bundled/third-party/bin/yosys, then PATH
        yosys_bin = "yosys"
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        bundled_yosys = os.path.join(repo_root, "third-party", "bin", "yosys")
        if os.path.isfile(bundled_yosys) and os.access(bundled_yosys, os.X_OK):
            yosys_bin = bundled_yosys

        process = QProcess()
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        process.start(yosys_bin, ["-q", script_path])
        process.waitForFinished(-1)
        
        if process.exitCode() == 0 and os.path.exists(out_path):
            self.log.emit(f"Block Diagram Ready ({target_mod}).", "INFO")
            self.finished.emit(out_path, target_mod, self.mode)
        else:
            self.log.emit("Yosys synthesis failed.", "ERR")
