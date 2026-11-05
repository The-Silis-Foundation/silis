"""
Functional Testbench Pre-Check Runner for SILIS Intake Engine.
Executes simulation for VHDL or Verilog, dumps VCD waveforms,
and provides live status feedback.
"""

import os
import shutil
import subprocess
from PyQt6.QtCore import QThread, pyqtSignal
from typing import List


class TBRunnerWorker(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str) # (success, vcd_path)

    def __init__(self,
                 sorted_files: List[str],
                 tb_file: str,
                 lang: str,
                 work_dir: str,
                 std: str = "08"):
        super().__init__()
        self.sorted_files = sorted_files
        self.tb_file = tb_file
        self.lang = lang
        self.work_dir = work_dir
        self.std = std

    def run(self):
        try:
            os.makedirs(self.work_dir, exist_ok=True)
            vcd_path = os.path.join(self.work_dir, "tb_waves.vcd")
            self.progress.emit(f"[SIM] Setting up simulation in: {self.work_dir}")

            if self.lang == 'vhdl':
                ghdl_bin = shutil.which("ghdl") or "ghdl"
                # Step 1: Analyze
                analyze_cmd = [ghdl_bin, "-a", f"--std={self.std}", f"--workdir={self.work_dir}"] + self.sorted_files + [self.tb_file]
                self.progress.emit(f"[SIM] Analyzing VHDL sources...")
                proc = subprocess.Popen(analyze_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                out, _ = proc.communicate()
                if out:
                    for l in out.strip().splitlines():
                        self.progress.emit(f"[GHDL-A] {l}")
                if proc.returncode != 0:
                    self.finished.emit(False, "")
                    return

                # Find testbench entity name
                tb_base = os.path.splitext(os.path.basename(self.tb_file))[0]
                # Step 2: Elaborate
                elab_cmd = [ghdl_bin, "-e", f"--std={self.std}", f"--workdir={self.work_dir}", tb_base]
                self.progress.emit(f"[SIM] Elaborating {tb_base}...")
                proc = subprocess.Popen(elab_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                out, _ = proc.communicate()
                if out:
                    for l in out.strip().splitlines():
                        self.progress.emit(f"[GHDL-E] {l}")
                if proc.returncode != 0:
                    self.finished.emit(False, "")
                    return

                # Step 3: Run
                run_cmd = [ghdl_bin, "-r", f"--std={self.std}", f"--workdir={self.work_dir}", tb_base, f"--vcd={vcd_path}", "--stop-time=10us"]
                self.progress.emit(f"[SIM] Running {tb_base} with 10us limit...")
                proc = subprocess.Popen(run_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                out, _ = proc.communicate()
                if out:
                    for l in out.strip().splitlines():
                        self.progress.emit(f"[GHDL-R] {l}")

            else:
                # Verilog / SystemVerilog with iverilog
                iv_bin = shutil.which("iverilog") or "iverilog"
                vvp_bin = shutil.which("vvp") or "vvp"
                vvp_out = os.path.join(self.work_dir, "sim.vvp")

                compile_cmd = [iv_bin, "-g2012", "-o", vvp_out] + self.sorted_files + [self.tb_file]
                self.progress.emit(f"[SIM] Compiling with iverilog...")
                proc = subprocess.Popen(compile_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                out, _ = proc.communicate()
                if out:
                    for l in out.strip().splitlines():
                        self.progress.emit(f"[IVERILOG] {l}")
                if proc.returncode != 0:
                    self.finished.emit(False, "")
                    return

                self.progress.emit(f"[SIM] Executing vvp...")
                proc = subprocess.Popen([vvp_bin, vvp_out], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                out, _ = proc.communicate()
                if out:
                    for l in out.strip().splitlines():
                        self.progress.emit(f"[VVP] {l}")

            has_vcd = os.path.isfile(vcd_path) and os.path.getsize(vcd_path) > 0
            self.progress.emit(f"[SIM] Complete! Waveform generated: {has_vcd}")
            self.finished.emit(True, vcd_path if has_vcd else "")

        except Exception as e:
            self.progress.emit(f"[ERROR] Simulation failed: {e}")
            self.finished.emit(False, "")
