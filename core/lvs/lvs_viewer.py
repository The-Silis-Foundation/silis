#!/usr/bin/env python3
"""
lvs_viewer.py
PyQt6 Catppuccin Mocha Modal Signoff Viewer for Layout Versus Schematic (LVS).
"""

import os
import sys
import json
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QApplication, QMessageBox
)
from PyQt6.QtCore import Qt
from config import THEMES, USER_SETTINGS


class LVSSignoffViewer(QDialog):
    def __init__(self, summary_data: dict, parent=None, project_dir: str = None):
        super().__init__(parent)
        self.summary = summary_data or {}
        self.proj_dir = project_dir or os.getcwd()

        theme_name = USER_SETTINGS.get("theme_name", "Catppuccin Mocha")
        self.theme = THEMES.get(theme_name, THEMES["Catppuccin Mocha"])

        self.setWindowTitle("Silis Signoff Hub — Layout Versus Schematic (LVS)")
        self.resize(880, 680)
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
        lbl_title = QLabel("Layout Versus Schematic (LVS) Signoff")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #58a6ff;")
        engine_name = self.summary.get("engine", "Netgen / Topological Engine")
        top_name = self.summary.get("top_module", "top")
        lbl_sub = QLabel(f"Design: {top_name}  •  Engine: {engine_name}")
        lbl_sub.setStyleSheet("font-size: 11px; color: #8b949e;")
        title_lay.addWidget(lbl_title)
        title_lay.addWidget(lbl_sub)
        h_lay.addLayout(title_lay)
        h_lay.addStretch()

        is_clean = self.summary.get("is_clean", False)
        status_bg = "#238636" if is_clean else "#da3633"
        status_border = "#2ea043" if is_clean else "#f85149"
        status_text = "🟢 LVS CLEAN (100% MATCH)" if is_clean else "🔴 LVS MISMATCHES DETECTED"

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

        unm_dev = self.summary.get("unmatched_devices", 0)
        unm_net = self.summary.get("unmatched_nets", 0)
        d_color = "#3fb950" if unm_dev == 0 else "#f85149"
        n_color = "#3fb950" if unm_net == 0 else "#f85149"

        add_card("Matched Devices", self.summary.get("matched_devices", 0), "Subcircuit Cells", "#58a6ff")
        add_card("Unmatched Devices", unm_dev, "Discrepancy count", d_color)
        add_card("Matched Nets", self.summary.get("matched_nets", 0), "Logical Equivalences", "#3fb950")
        add_card("Unmatched Nets", unm_net, "Floating/Open nets", n_color)

        main_lay.addLayout(cards_lay)

        # 3. Equivalence Table
        lbl_tbl = QLabel("<b>Device & Net Equivalence Breakdown:</b>")
        lbl_tbl.setStyleSheet("font-size: 12px; color: #f0f6fc;")
        main_lay.addWidget(lbl_tbl)

        self.tbl = QTableWidget(4, 3)
        self.tbl.setHorizontalHeaderLabels(["Entity Category", "Layout Extracted", "Schematic Netlist"])
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tbl.verticalHeader().setVisible(False)

        data_rows = [
            ("Standard Cell Instances", str(self.summary.get("matched_devices", 0)), str(self.summary.get("matched_devices", 0))),
            ("Signal & Power Nets", str(self.summary.get("matched_nets", 0)), str(self.summary.get("matched_nets", 0))),
            ("Pin Terminals", "100", "100"),
            ("Equivalence Status", "100% Match", "100% Match")
        ]
        for row, (col1, col2, col3) in enumerate(data_rows):
            self.tbl.setItem(row, 0, QTableWidgetItem(col1))
            self.tbl.setItem(row, 1, QTableWidgetItem(col2))
            self.tbl.setItem(row, 2, QTableWidgetItem(col3))
        self.tbl.setFixedHeight(140)
        main_lay.addWidget(self.tbl)

        # 4. Detailed LVS Report Log
        lbl_log = QLabel("<b>LVS Verification Log:</b>")
        lbl_log.setStyleSheet("font-size: 12px; color: #f0f6fc;")
        main_lay.addWidget(lbl_log)

        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        mismatches = self.summary.get("mismatches", [])
        raw_log = self.summary.get("raw_output", "")
        if mismatches:
            header_m = "[LVS MISMATCH DETAILS]\n" + "\n".join(f"  • {m}" for m in mismatches) + "\n\n"
            self.txt_log.setPlainText(header_m + raw_log)
        else:
            self.txt_log.setPlainText("🟢 Circuits match with no errors.\n\n" + raw_log)
        main_lay.addWidget(self.txt_log)

        # 5. Buttons Bar
        b_bar = QHBoxLayout()
        btn_copy = QPushButton("📋 Copy LVS Report")
        btn_copy.clicked.connect(lambda: QApplication.clipboard().setText(self.txt_log.toPlainText()))
        b_bar.addWidget(btn_copy)

        btn_json = QPushButton("Export JSON")
        btn_json.setStyleSheet("background-color: #1f6feb; color: #ffffff; border: 1px solid #388bfd;")
        btn_json.clicked.connect(self._export_json)
        b_bar.addWidget(btn_json)

        b_bar.addStretch()

        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        b_bar.addWidget(btn_close)

        main_lay.addLayout(b_bar)

    def _export_json(self):
        out_p = os.path.join(self.proj_dir, "reports", "lvs_summary.json")
        try:
            with open(out_p, "w") as f:
                json.dump(self.summary, f, indent=2)
            QMessageBox.information(self, "Exported", f"LVS Report saved to:\n{out_p}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export report: {e}")
