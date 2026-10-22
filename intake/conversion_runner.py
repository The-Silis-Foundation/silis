"""
Asynchronous Conversion Worker for SILIS Intake Engine.
Executes pipe.convert() in a separate QThread with live stdout streaming.
"""

import os
import shutil
import subprocess
from PyQt6.QtCore import QThread, pyqtSignal
from typing import List


class ConversionWorker(QThread):
    progress = pyqtSignal(str)   # Output log lines
    finished = pyqtSignal(str)   # Generated Verilog path
    failed   = pyqtSignal(str)   # Error description

    def __init__(self,
                 sorted_files: List[str],
                 lang: str,
                 top_module: str,
                 out_verilog_path: str,
                 std: str = "08",
                 work_lib: str = "work"):
        super().__init__()
        self.sorted_files = sorted_files
        self.lang = lang
        self.top_module = top_module
        self.out_verilog_path = out_verilog_path
        self.std = std
        self.work_lib = work_lib

    def run(self):
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.out_verilog_path)), exist_ok=True)
            self.progress.emit(f"[INTAKE] Target language: {self.lang.upper()} | Top: {self.top_module}")
            self.progress.emit(f"[INTAKE] Output netlist: {self.out_verilog_path}")

            if self.lang == 'vhdl':
                ghdl_bin = shutil.which("ghdl") or "ghdl"
                # GHDL-mcode syntax: ghdl --synth [FLAGS] [FILES...] -e UNIT
                cmd = [
                    ghdl_bin,
                    "--synth",
                    f"--std={self.std}",
                    f"--work={self.work_lib}",
                    "--out=verilog",
                    "--no-formal",
                    "-fsynopsys",
                ] + self.sorted_files + [
                    "-e",
                    self.top_module
                ]

                self.progress.emit(f"[EXEC] {ghdl_bin} --synth --std={self.std} --work={self.work_lib} ({len(self.sorted_files)} files) -e {self.top_module}")

                with open(self.out_verilog_path, "w") as f_out:
                    proc = subprocess.Popen(
                        cmd,
                        stdout=f_out,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    _, stderr_text = proc.communicate()

                if stderr_text:
                    for line in stderr_text.strip().splitlines():
                        self.progress.emit(f"[GHDL] {line}")

                if proc.returncode != 0:
                    self.failed.emit(f"GHDL conversion failed with exit code {proc.returncode}:\n{stderr_text}")
                    return

            elif self.lang == 'sv':
                sv2v_bin = shutil.which("sv2v") or os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "third-party", "bin", "sv2v"
                )
                if not shutil.which(sv2v_bin) and not os.path.isfile(sv2v_bin):
                    # Check in yosys sv2v or standard system
                    sv2v_bin = "sv2v"

                cmd = [sv2v_bin] + self.sorted_files + [f"--write={self.out_verilog_path}"]
                self.progress.emit(f"[EXEC] {' '.join(cmd[:8])} ...")

                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True
                )
                stdout_text, _ = proc.communicate()
                if stdout_text:
                    for line in stdout_text.strip().splitlines():
                        self.progress.emit(f"[SV2V] {line}")

                if proc.returncode != 0:
                    self.failed.emit(f"sv2v conversion failed with exit code {proc.returncode}")
                    return

            else:
                # Verilog passthrough / concatenation
                with open(self.out_verilog_path, "w") as f_out:
                    for f in self.sorted_files:
                        with open(f, "r", errors="ignore") as f_in:
                            f_out.write(f"// --- Source: {os.path.basename(f)} ---\n")
                            f_out.write(f_in.read() + "\n\n")

            self.progress.emit(f"[SUCCESS] Transpiled Verilog created: {self.out_verilog_path}")
            self.finished.emit(self.out_verilog_path)

        except Exception as e:
            self.failed.emit(str(e))
