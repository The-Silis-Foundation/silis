"""
Smart HDL/HLS Source Intake & Lowering Wizard (PyQt6 Dialog).
Provides folder/file ingestion, auto-language and dependency graph visualization,
top-level module confirmation, pre-check simulation, and 1-click Verilog lowering.
"""

import os
import re
from typing import List, Optional
from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QTreeWidget, QTreeWidgetItem, QComboBox, QPlainTextEdit,
    QProgressBar, QMessageBox, QFrame, QSplitter, QHeaderView
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon

from .source_scanner import scan_sources, SourceFile
from .dependency_graph import topological_sort
from .top_finder import find_top_candidates
from .port_extractor import extract_ports, PortSpec
from .conversion_runner import ConversionWorker
from .tb_runner import TBRunnerWorker


class DropZoneWidget(QFrame):
    files_dropped = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setStyleSheet("""
            QFrame {
                border: 2px dashed #44475a;
                border-radius: 8px;
                background-color: #1e1f29;
                min-height: 70px;
            }
            QFrame:hover {
                border-color: #50fa7b;
                background-color: #282a36;
            }
        """)
        layout = QVBoxLayout(self)
        self.lbl = QLabel("Drag and drop HDL folders or files here, or click 'Browse Sources...'")
        self.lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl.setStyleSheet("color: #8be9fd; font-size: 13px; font-weight: bold;")
        layout.addWidget(self.lbl)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = []
        for url in event.mimeData().urls():
            paths.append(url.toLocalFile())
        if paths:
            self.files_dropped.emit(paths)


class IntakeWizardDialog(QDialog):
    intake_completed = pyqtSignal(dict) # Emits project updates

    def __init__(self, parent=None, project_config: Optional[dict] = None):
        super().__init__(parent)
        self.project_config = project_config or {}
        self.setWindowTitle("HDL Source Intake & Lowering")
        self.resize(950, 720)
        self.setStyleSheet("""
            QDialog { background-color: #191a21; color: #f8f8f2; }
            QLabel { color: #f8f8f2; font-size: 12px; }
            QTreeWidget {
                background-color: #21222c;
                border: 1px solid #44475a;
                border-radius: 6px;
                color: #f8f8f2;
                font-family: monospace;
            }
            QTreeWidget::item:selected {
                background-color: #44475a;
                color: #50fa7b;
            }
            QComboBox {
                background-color: #282a36;
                color: #f8f8f2;
                border: 1px solid #44475a;
                border-radius: 4px;
                padding: 4px;
                min-height: 24px;
            }
            QPushButton {
                background-color: #44475a;
                color: #f8f8f2;
                border-radius: 5px;
                padding: 6px 14px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #6272a4; }
            QPlainTextEdit {
                background-color: #1e1f29;
                color: #50fa7b;
                border: 1px solid #44475a;
                border-radius: 4px;
                font-family: monospace;
            }
        """)

        self.sources: List[SourceFile] = []
        self.sorted_sources: List[SourceFile] = []
        self.converted_verilog_path = ""
        self.detected_ports: List[PortSpec] = []

        self._build_ui()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Header Title
        title_lbl = QLabel("HDL Source Intake & Lowering Engine")
        title_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #50fa7b;")
        main_layout.addWidget(title_lbl)

        # Ingestion Drop Zone + Browse
        ingest_row = QHBoxLayout()
        self.drop_zone = DropZoneWidget(self)
        self.drop_zone.files_dropped.connect(self.on_files_ingested)
        ingest_row.addWidget(self.drop_zone, 4)

        btn_browse = QPushButton("Browse Sources...")
        btn_browse.setStyleSheet("background-color: #6272a4; color: #f8f8f2; font-size: 12px;")
        btn_browse.clicked.connect(self.on_browse_clicked)
        ingest_row.addWidget(btn_browse, 1)
        main_layout.addLayout(ingest_row)

        # Configuration Bar (Language, Work Library, Standard)
        cfg_bar = QHBoxLayout()
        cfg_bar.addWidget(QLabel("Primary Dialect:"))
        self.cmb_lang = QComboBox()
        self.cmb_lang.addItems(["Auto-Detect", "VHDL-2008", "SystemVerilog", "Verilog"])
        self.cmb_lang.currentIndexChanged.connect(self.on_config_changed)
        cfg_bar.addWidget(self.cmb_lang)

        cfg_bar.addWidget(QLabel("VHDL Work Library:"))
        self.cmb_work = QComboBox()
        self.cmb_work.setEditable(True)
        self.cmb_work.addItems(["neorv32", "work"])
        cfg_bar.addWidget(self.cmb_work)

        cfg_bar.addStretch()
        self.lbl_file_count = QLabel("0 files loaded")
        self.lbl_file_count.setStyleSheet("color: #8be9fd; font-weight: bold;")
        cfg_bar.addWidget(self.lbl_file_count)
        main_layout.addLayout(cfg_bar)

        # Splitter: Tree on top, Log on bottom
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Dependency Tree
        tree_widget_container = QWidget()
        tree_layout = QVBoxLayout(tree_widget_container)
        tree_layout.setContentsMargins(0, 0, 0, 0)

        tree_header = QHBoxLayout()
        tree_header.addWidget(QLabel("Topological Dependency Hierarchy (Compilation Order):"))
        tree_layout.addLayout(tree_header)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels(["Order / Tier", "File Name", "Role / Unit", "Path"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        tree_layout.addWidget(self.tree)

        splitter.addWidget(tree_widget_container)

        # Log & Progress Console
        log_container = QWidget()
        log_layout = QVBoxLayout(log_container)
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_layout.addWidget(QLabel("Execution Console:"))
        self.txt_console = QPlainTextEdit()
        self.txt_console.setReadOnly(True)
        log_layout.addWidget(self.txt_console)
        splitter.addWidget(log_container)

        splitter.setSizes([340, 180])
        main_layout.addWidget(splitter, 1)

        # Top Entity & Clock/Reset Detection Selectors
        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("Top Entity:"))
        self.cmb_top = QComboBox()
        self.cmb_top.currentIndexChanged.connect(self.on_top_selected)
        top_row.addWidget(self.cmb_top, 2)

        top_row.addWidget(QLabel("Clock:"))
        self.cmb_clk = QComboBox()
        top_row.addWidget(self.cmb_clk, 1)

        top_row.addWidget(QLabel("Reset:"))
        self.cmb_rst = QComboBox()
        top_row.addWidget(self.cmb_rst, 1)
        main_layout.addLayout(top_row)

        # Action Buttons
        act_row = QHBoxLayout()
        self.btn_precheck = QPushButton("Run Simulation Pre-Check")
        self.btn_precheck.setEnabled(False)
        self.btn_precheck.clicked.connect(self.on_run_precheck)
        act_row.addWidget(self.btn_precheck)

        self.btn_convert = QPushButton("Convert to Verilog")
        self.btn_convert.setStyleSheet("background-color: #50fa7b; color: #282a36; font-size: 13px; font-weight: bold;")
        self.btn_convert.setEnabled(False)
        self.btn_convert.clicked.connect(self.on_run_convert)
        act_row.addWidget(self.btn_convert)

        self.btn_commit = QPushButton("Register into Project & Finish")
        self.btn_commit.setEnabled(False)
        self.btn_commit.clicked.connect(self.on_commit_and_close)
        act_row.addWidget(self.btn_commit)

        main_layout.addLayout(act_row)

    # --- Ingestion Handlers ---
    def on_browse_clicked(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select HDL Source Directory")
        if dir_path:
            self.on_files_ingested([dir_path])

    def on_files_ingested(self, paths: list):
        self.txt_console.appendPlainText(f"[SCAN] Ingesting {len(paths)} paths...")
        self.sources = scan_sources(paths)
        if not self.sources:
            QMessageBox.warning(self, "No Sources", "No valid VHDL (.vhd) or Verilog (.v/.sv) files found in selected paths.")
            return

        self.lbl_file_count.setText(f"{len(self.sources)} files loaded")
        self.rebuild_hierarchy()

    def on_config_changed(self):
        if self.sources:
            self.rebuild_hierarchy()

    def rebuild_hierarchy(self):
        # 1. Topological Sort
        self.sorted_sources = topological_sort(self.sources)

        # 2. Populate Tree
        self.tree.clear()
        for i, s in enumerate(self.sorted_sources):
            base = os.path.basename(s.path)
            role = "[TB - Excluded]" if s.is_testbench else (
                "[PKG]" if any("pkg" in u or "package" in u for u in s.declared_units) else "[RTL]"
            )
            item = QTreeWidgetItem([
                f"Tier {s.tier}" if not s.is_testbench else "Sim Only",
                base,
                f"{role} ({', '.join(s.declared_units) or 'anon'})",
                s.path
            ])
            if s.is_testbench:
                item.setForeground(0, QColor("#6272a4"))
                item.setForeground(1, QColor("#6272a4"))
            elif "[PKG]" in role:
                item.setForeground(1, QColor("#8be9fd"))
            else:
                item.setForeground(1, QColor("#f8f8f2"))

            self.tree.addTopLevelItem(item)

        # 3. Detect Top Candidates
        candidates = find_top_candidates(self.sorted_sources)
        self.cmb_top.clear()
        for cand_name, src_file, score in candidates:
            self.cmb_top.addItem(cand_name, cand_name)

        # Auto-adjust work library if neorv32 detected
        if any("neorv32" in s.path.lower() for s in self.sources):
            self.cmb_work.setCurrentText("neorv32")

        # Enable actions
        has_rtl = any(not s.is_testbench for s in self.sorted_sources)
        self.btn_convert.setEnabled(has_rtl)
        has_tb = any(s.is_testbench for s in self.sorted_sources)
        self.btn_precheck.setEnabled(has_tb)

        self.txt_console.appendPlainText(f"[OK] Structured {len(self.sorted_sources)} files across compilation tiers.")

    def on_top_selected(self):
        top_name = self.cmb_top.currentData()
        if not top_name:
            return

        # Find file containing top
        top_file = next((s for s in self.sorted_sources if top_name.lower() in [u.lower() for u in s.declared_units]), None)
        if not top_file:
            return

        # Extract Ports
        self.detected_ports = extract_ports(top_file, top_name)
        self.cmb_clk.clear()
        self.cmb_rst.clear()

        for p in self.detected_ports:
            if p.port_type == "clock":
                self.cmb_clk.addItem(p.name)
            elif p.port_type == "reset":
                self.cmb_rst.addItem(p.name)

        self.txt_console.appendPlainText(f"[PORT] Top '{top_name}' interface extracted: {len(self.detected_ports)} ports detected.")

    # --- Simulation Pre-Check ---
    def on_run_precheck(self):
        tb_file = next((s for s in self.sorted_sources if s.is_testbench), None)
        if not tb_file:
            QMessageBox.information(self, "No Testbench", "No testbench file identified in source set.")
            return

        rtl_files = [s.path for s in self.sorted_sources if not s.is_testbench]
        lang = tb_file.lang
        work_dir = os.path.join(self.project_config.get("project_root", "/tmp"), "sim")

        self.txt_console.appendPlainText(f"[SIM] Launching functional pre-check with testbench: {os.path.basename(tb_file.path)}...")
        self.btn_precheck.setEnabled(False)

        self.tb_worker = TBRunnerWorker(
            sorted_files=rtl_files,
            tb_file=tb_file.path,
            lang=lang,
            work_dir=work_dir,
            std="08"
        )
        self.tb_worker.progress.connect(self.txt_console.appendPlainText)
        self.tb_worker.finished.connect(self.on_precheck_finished)
        self.tb_worker.start()

    def on_precheck_finished(self, success: bool, vcd_path: str):
        self.btn_precheck.setEnabled(True)
        if success:
            self.txt_console.appendPlainText("[SIM] [OK] Functional verification pre-check passed!")
            if vcd_path and os.path.isfile(vcd_path):
                reply = QMessageBox.question(
                    self, "Simulation Succeeded",
                    f"Testbench simulation completed successfully.\nWaveform generated: {os.path.basename(vcd_path)}\n\nDo you want to open waveforms in the Waveform Viewer tab?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.Yes:
                    parent_ide = self.parent()
                    if parent_ide and hasattr(parent_ide, "frontend_tabs") and hasattr(parent_ide, "tab_waves"):
                        parent_ide.frontend_tabs.setCurrentIndex(1)
                        parent_ide.tab_waves.load_vcd(vcd_path)
        else:
            QMessageBox.warning(self, "Simulation Warning", "Pre-check simulation failed or had warnings. Check console log for details.")

    # --- Lowering & Conversion ---
    def on_run_convert(self):
        top_name = self.cmb_top.currentData()
        if not top_name:
            QMessageBox.warning(self, "Top Required", "Please select a top-level module.")
            return

        rtl_files = [s.path for s in self.sorted_sources if not s.is_testbench]
        lang = self.sources[0].lang
        proj_root = self.project_config.get("project_root", os.getcwd())
        out_v = os.path.join(proj_root, "netlist", f"{top_name}_converted.v")

        self.btn_convert.setEnabled(False)
        self.txt_console.appendPlainText(f"[CONVERT] Starting conversion for top '{top_name}'...")

        self.conv_worker = ConversionWorker(
            sorted_files=rtl_files,
            lang=lang,
            top_module=top_name,
            out_verilog_path=out_v,
            std="08",
            work_lib=self.cmb_work.currentText().strip() or "work"
        )
        self.conv_worker.progress.connect(self.txt_console.appendPlainText)
        self.conv_worker.finished.connect(self.on_convert_success)
        self.conv_worker.failed.connect(self.on_convert_failed)
        self.conv_worker.start()

    def on_convert_success(self, out_path: str):
        self.btn_convert.setEnabled(True)
        self.btn_commit.setEnabled(True)
        self.converted_verilog_path = out_path
        self.txt_console.appendPlainText(f"[DONE] Synthesizable Verilog successfully generated: {out_path}")
        QMessageBox.information(
            self, "Conversion Succeeded",
            f"Successfully lowered HDL sources to synthesizable Verilog netlist:\n{out_path}\n\nClick 'Register into Project & Finish' to commit."
        )

    def on_convert_failed(self, error_msg: str):
        self.btn_convert.setEnabled(True)
        self.txt_console.appendPlainText(f"[FAILED] {error_msg}")
        QMessageBox.critical(self, "Conversion Failed", f"Transpilation failed:\n{error_msg}")

    # --- Commit & Finish ---
    def on_commit_and_close(self):
        top_name = self.cmb_top.currentData()
        clk_name = self.cmb_clk.currentText()
        rst_name = self.cmb_rst.currentText()
        proj_root = self.project_config.get("project_root", os.getcwd())

        # Generate basic starter SDC if clock was found
        if clk_name and top_name:
            sdc_path = os.path.join(proj_root, "source", f"{top_name}.sdc")
            os.makedirs(os.path.dirname(sdc_path), exist_ok=True)
            sdc_lines = [
                f"# Auto-generated SDC timing constraints for {top_name}",
                f"create_clock -name clk -period 10.0 [get_ports {clk_name}]",
                "set_clock_uncertainty 0.25 [get_clocks clk]",
                "set_input_delay -clock clk 1.5 [all_inputs]",
                "set_output_delay -clock clk 1.5 [all_outputs]"
            ]
            if rst_name:
                sdc_lines.append(f"set_false_path -from [get_ports {rst_name}]")
            try:
                with open(sdc_path, "w") as f:
                    f.write("\n".join(sdc_lines) + "\n")
            except Exception:
                pass

        result_dict = {
            "top_module": top_name,
            "rtl_files": [self.converted_verilog_path] if self.converted_verilog_path else [],
            "vhdl_work": self.cmb_work.currentText().strip() or "work",
            "vhdl_std": "08",
            "ports": [p.__dict__ for p in self.detected_ports]
        }
        self.intake_completed.emit(result_dict)
        self.accept()
