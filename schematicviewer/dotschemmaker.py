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

        read_cmd = "".join([f"read_verilog {s}; " for s in self.src_files])
        os.makedirs(os.path.join(self.root, "results"), exist_ok=True)
        out_prefix = os.path.join(self.root, "results", f"schem_{self.target_module}_{self.mode}")
        
        try:
            if self.mode in ["top", "block"]:
                json_file = out_prefix + ".json"
                if os.path.exists(json_file): os.remove(json_file)
                # prep flattens processes and prepares for structural extraction without destroying blackboxes
                yosys_script = f"{read_cmd} hierarchy -top {self.target_module}; prep; write_json {json_file}"
                
                self.log.emit(f"Extracting structural JSON for {self.target_module}...", "SYS")
                subprocess.run(f"yosys -p '{yosys_script}'", shell=True, cwd=self.root, capture_output=True, text=True)
                
                if os.path.exists(json_file):
                    self.finished.emit(json_file, self.target_module, self.mode)
                    self.log.emit(f"Block Diagram Ready ({self.target_module}).", "SYS")
                else:
                    self.log.emit("Yosys failed to generate JSON netlist.", "ERR")
                    
            elif self.mode == "gate":
                if not shutil.which("dot"):
                    self.log.emit("Graphviz ('dot') not found for Gate-Level render!", "ERR")
                    return
                
                dot_file = out_prefix + ".dot"
                svg_file = out_prefix + ".svg"
                if os.path.exists(dot_file): os.remove(dot_file)
                
                lib_cmd = f"-liberty {self.pdk_lib}" if self.pdk_lib else ""
                yosys_script = f"{read_cmd} hierarchy -top {self.target_module}; synth; dfflibmap {lib_cmd}; abc {lib_cmd}; show -notitle -colors 2 -width -stretch -format dot -prefix {out_prefix}"
                
                self.log.emit(f"Synthesizing GATE view for {self.target_module}...", "SYS")
                subprocess.run(f"yosys -p '{yosys_script}'", shell=True, cwd=self.root, capture_output=True, text=True)
                
                if os.path.exists(dot_file):
                    self.log.emit("Squarifying and Rendering SVG...", "SYS")
                    # Use unflatten to break up massive horizontal parallel structures and force a squarer aspect ratio
                    subprocess.run(f"unflatten -f -l 4 -c 4 {dot_file} | dot -Tsvg -o {svg_file} -Gsplines=ortho", shell=True, cwd=self.root)
                    if os.path.exists(svg_file):
                        self.finished.emit(svg_file, self.target_module, self.mode)
                        self.log.emit(f"Gate Schematic Ready ({self.target_module}).", "SYS")
                    else:
                        self.log.emit("Graphviz failed to convert DOT to SVG.", "ERR")
                else:
                    self.log.emit("Yosys failed to generate Gate graph.", "ERR")
                    
        except Exception as e:
            self.log.emit(f"Schematic Engine Crash: {e}", "ERR")
