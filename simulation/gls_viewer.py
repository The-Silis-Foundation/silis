#!/usr/bin/env python3
"""
gls_viewer.py
PyQt6 Catppuccin Mocha Modal Signoff Viewer for Gate-Level Simulation (GLS).
"""

import os
import sys
import json
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QTextEdit, QScrollArea, QWidget, QApplication, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from config import THEMES, USER_SETTINGS


class GLSSignoffViewer(QDialog):
    view_waveforms_requested = pyqtSignal(str)

    def __init__(self, summary_data: dict, parent=None, project_dir: str = None):
        super().__init__(parent)
        self.summary = summary_data or {}
        self.proj_dir = project_dir or os.getcwd()

        theme_name = USER_SETTINGS.get("theme_name", "Catppuccin Mocha")
        self.theme = THEMES.get(theme_name, THEMES["Catppuccin Mocha"])

        self.setWindowTitle("Silis Signoff Hub — Gate-Level Simulation (GLS)")
        self.resize(850, 680)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMinMaxButtonsHint)
        self._init_ui()

    def _init_ui(self):
        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(20, 20, 20, 20)
        main_lay.setSpacing(14)

        # 1. Header Banner
        h_frame = QFrame()
        h_frame.setStyleSheet("background-color: #161b22; border-radius: 8px; border: 1px solid #30363d;")
        h_lay = QHBoxLayout(h_frame)
        h_lay.setContentsMargins(16, 12, 16, 12)

        title_lay = QVBoxLayout()
        lbl_title = QLabel("Gate-Level Timing Simulation (GLS) Signoff")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #58a6ff;")
        top_name = self.summary.get("top_module", "top")
        lbl_sub = QLabel(f"Design: {top_name}  •  IEEE 1497 SDF Timing Back-Annotation")
        lbl_sub.setStyleSheet("font-size: 11px; color: #8b949e;")
        title_lay.addWidget(lbl_title)
        title_lay.addWidget(lbl_sub)
        h_lay.addLayout(title_lay)
        h_lay.addStretch()

        is_pass = self.summary.get("status") == "PASS"
        status_bg = "#238636" if is_pass else "#da3633"
        status_border = "#2ea043" if is_pass else "#f85149"
        status_text = "🟢 GLS PASSED" if is_pass else "🔴 GLS FAILED"

        lbl_badge = QLabel(f" {status_text} ")
        lbl_badge.setStyleSheet(f"""
            background-color: {status_bg};
            color: #ffffff;
            font-weight: bold;
            font-size: 12px;
            border-radius: 6px;
            border: 1px solid {status_border};
            padding: 6px 14px;
        """)
        h_lay.addWidget(lbl_badge)
        main_lay.addWidget(h_frame)

        # 2. Key Metrics Cards
        cards_lay = QHBoxLayout()
        cards_lay.setSpacing(12)

        def add_card(label, val, sub, color="#58a6ff"):
            c = QFrame()
            c.setStyleSheet("background-color: #161b22; border-radius: 8px; border: 1px solid #30363d;")
            cl = QVBoxLayout(c)
            cl.setContentsMargins(14, 12, 14, 12)
            l1 = QLabel(label.upper()); l1.setStyleSheet("font-size: 10px; font-weight: bold; color: #8b949e; letter-spacing: 0.5px;")
            l2 = QLabel(str(val)); l2.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {color};")
            l3 = QLabel(sub); l3.setStyleSheet("font-size: 10px; color: #6e7681;")
            cl.addWidget(l1); cl.addWidget(l2); cl.addWidget(l3)
            cards_lay.addWidget(c)

        v_count = self.summary.get("timing_violations_count", 0)
        v_color = "#3fb950" if v_count == 0 else "#f85149"

        add_card("Cycles Tested", self.summary.get("cycles_evaluated", 0), "Testbench Cycles", "#58a6ff")
        add_card("Timing Violations", v_count, "$setup / $hold errors", v_color)
        add_card("Simulation Time", f"{self.summary.get('duration_sec', 0.0)}s", "Elapsed Run Time", "#79c0ff")
        add_card("Timing Mode", "TYPICAL (1.8V)", "SDF Annotate Corner", "#38bdf8")

        main_lay.addLayout(cards_lay)

        # 3. Simulation Log & Timing Violations Tab
        lbl_log = QLabel("<b>Simulation Output Trace & Back-Annotation:</b>")
        lbl_log.setStyleSheet("font-size: 12px; color: #f0f6fc;")
        main_lay.addWidget(lbl_log)

        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        raw_log = self.summary.get("sim_stdout", "")
        violations = self.summary.get("timing_violations", [])
        if violations:
            header_viol = "[TIMING VIOLATIONS DETECTED]\n" + "\n".join(f"  • {v}" for v in violations) + "\n\n"
            self.txt_log.setPlainText(header_viol + raw_log)
        else:
            self.txt_log.setPlainText(raw_log if raw_log else "Simulation completed with zero errors.")
        main_lay.addWidget(self.txt_log)

        # 4. Action Buttons Bar
        b_bar = QHBoxLayout()
        vcd_path = self.summary.get("vcd_file")
        if vcd_path and os.path.isfile(vcd_path):
            btn_wave = QPushButton("📈 Open Waveforms in SignalPeeker")
            btn_wave.setStyleSheet("background-color: #1f6feb; color: #ffffff; border: 1px solid #388bfd; font-weight: bold;")
            btn_wave.clicked.connect(self._open_waveforms)
            b_bar.addWidget(btn_wave)

        btn_copy = QPushButton("📋 Copy Log")
        btn_copy.clicked.connect(lambda: QApplication.clipboard().setText(self.txt_log.toPlainText()))
        b_bar.addWidget(btn_copy)

        btn_json = QPushButton("Export JSON")
        btn_json.setStyleSheet("background-color: #238636; color: #ffffff; border: 1px solid #2ea043;")
        btn_json.clicked.connect(self._export_json)
        b_bar.addWidget(btn_json)

        b_bar.addStretch()

        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        b_bar.addWidget(btn_close)

        main_lay.addLayout(b_bar)

    def _open_waveforms(self):
        vcd_path = self.summary.get("vcd_file")
        if vcd_path and os.path.isfile(vcd_path):
            self.view_waveforms_requested.emit(vcd_path)
            # If parent ide has SignalPeeker tab, switch to it
            parent_ide = getattr(self.parent(), "ide", self.parent())
            if hasattr(parent_ide, "switch_world") and hasattr(parent_ide, "frontend_tabs"):
                parent_ide.switch_world(0)
                parent_ide.frontend_tabs.setCurrentIndex(1) # SignalPeeker
                if hasattr(parent_ide, "tab_waves") and hasattr(parent_ide.tab_waves, "load_vcd"):
                    parent_ide.tab_waves.load_vcd(vcd_path)
            self.accept()

    def _export_json(self):
        out_p = os.path.join(self.proj_dir, "reports", "gls_summary.json")
        try:
            with open(out_p, "w") as f:
                json.dump(self.summary, f, indent=2)
            QMessageBox.information(self, "Exported", f"GLS Report saved to:\n{out_p}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export report: {e}")
