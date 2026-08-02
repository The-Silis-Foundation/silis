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
        self.log.emit(f"Extracting structural JSON for {self.module_name}...", "INFO")
        
        build_dir = os.path.join(self.root, "build")
        os.makedirs(build_dir, exist_ok=True)
        out_path = os.path.join(build_dir, f"structural_{self.module_name}.json")
        
        script_path = os.path.join(build_dir, "temp_synth.ys")
        with open(script_path, "w") as f:
            vhdl_files = [s for s in self.src if s.endswith('.vhd') or s.endswith('.vhdl')]
            vlog_files = [s for s in self.src if not (s.endswith('.vhd') or s.endswith('.vhdl'))]
            vhdl_files = sorted(vhdl_files, key=lambda x: 0 if any(k in os.path.basename(x).lower() for k in ['pack', 'pkg', 'type', 'const']) else 1)
            
            if vhdl_files:
                f.write("plugin -i ghdl;\n")
                work_lib = os.path.basename(self.root)
                if "neorv32" in self.root.lower() or "neorv32" in work_lib.lower():
                    work_lib = "neorv32"
                f.write(f"ghdl --work={work_lib} {' '.join(vhdl_files)} -e {self.module_name};\n")
                
            for s in vlog_files:
                if s.endswith(".sv"):
                    f.write(f"read_verilog -sv {s}\n")
                else:
                    f.write(f"read_verilog {s}\n")
            
            f.write(f"hierarchy -top {self.module_name}\n")
            
            if self.mode == "gate" and self.pdk_lib:
                f.write(f"synth -top {self.module_name}\n")
                f.write(f"dfflibmap -liberty {self.pdk_lib}\n")
                f.write(f"abc -liberty {self.pdk_lib}\n")
            else:
                f.write(f"prep -top {self.module_name}\n")
                
            f.write(f"write_json {out_path}\n")
            
        process = QProcess()
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        process.start("yosys", ["-q", script_path])
        process.waitForFinished(-1)
        
        if process.exitCode() == 0 and os.path.exists(out_path):
            self.log.emit(f"Block Diagram Ready ({self.module_name}).", "INFO")
            self.finished.emit(out_path, self.module_name, self.mode)
        else:
            self.log.emit("Yosys synthesis failed.", "ERR")
