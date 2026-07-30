import os
import subprocess
import shutil
from PyQt6.QtCore import QThread, pyqtSignal

class YosysStructuralWorker(QThread):
    finished = pyqtSignal(str, str, str)  # (out_path, module, mode)
    log = pyqtSignal(str, str)
    
    def __init__(self, root, src_files, target_module, mode, pdk_lib=None):
        super().__init__()
        self.root = root
        self.src_files = src_files
        self.target_module = target_module
        self.mode = mode # 'top', 'block', or 'gate'
        self.pdk_lib = pdk_lib

    def run(self):
        if not shutil.which("yosys"):
            self.log.emit("Yosys not found!", "ERR")
            return

        read_cmd = ""
        for s in self.src_files:
            if s.endswith(".sv"):
                read_cmd += f"read_verilog -sv {s}; "
            elif s.endswith(".vhd") or s.endswith(".vhdl"):
                read_cmd += f"ghdl {s} -e {self.target_module}; "
            else:
                read_cmd += f"read_verilog {s}; "
        os.makedirs(os.path.join(self.root, "results"), exist_ok=True)
        out_prefix = os.path.join(self.root, "results", f"schem_{self.target_module}_{self.mode}")
        
        try:
            if self.mode in ["top", "block"]:
                json_file = out_prefix + ".json"
                if os.path.exists(json_file): os.remove(json_file)
                # prep flattens processes and prepares for structural extraction without destroying blackboxes
                yosys_script = f"{read_cmd} hierarchy -top {self.target_module}; prep; write_json {json_file}"
                
                self.log.emit(f"Extracting structural JSON for {self.target_module}...", "SYS")
                res = subprocess.run(f"yosys -p '{yosys_script}'", shell=True, cwd=self.root, capture_output=True, text=True)
                
                if os.path.exists(json_file):
                    self.finished.emit(json_file, self.target_module, self.mode)
                    self.log.emit(f"Block Diagram Ready ({self.target_module}).", "SYS")
                else:
                    self.log.emit(f"Yosys failed to generate JSON netlist. Error:\n{res.stderr}", "ERR")
                    
            elif self.mode == "gate":
                json_file = out_prefix + ".json"
                if os.path.exists(json_file): os.remove(json_file)
                
                # Do not attempt to extract structural layout for PDK leaf cells
                if self.target_module.startswith("sky130_") or self.target_module.startswith("\\sky130_") or "sc_hd" in self.target_module:
                    self.log.emit(f"Skipping schematic for leaf cell: {self.target_module}", "SYS")
                    return
                
                lib_cmd = f"-liberty {self.pdk_lib}" if self.pdk_lib else ""
                yosys_script = f"{read_cmd} hierarchy -top {self.target_module}; synth; dfflibmap {lib_cmd}; abc {lib_cmd}; write_json {json_file}"
                
                self.log.emit(f"Synthesizing GATE view for {self.target_module}...", "SYS")
                res = subprocess.run(f"yosys -p '{yosys_script}'", shell=True, cwd=self.root, capture_output=True, text=True)
                
                if os.path.exists(json_file):
                    self.finished.emit(json_file, self.target_module, self.mode)
                    self.log.emit(f"Gate Schematic Ready ({self.target_module}).", "SYS")
                else:
                    self.log.emit(f"Yosys failed to generate JSON netlist. Error:\n{res.stderr}", "ERR")
                    
        except Exception as e:
            self.log.emit(f"Schematic Engine Crash: {e}", "ERR")
