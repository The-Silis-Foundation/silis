"""
silis/dft/dft_viewer.py
PyQt6 Modal Dialog for DFT Signoff Metrics Inspection and Test Vector Export.

Matches Silis IDE Catppuccin / dark styling, displaying:
- High-level metric summary cards (Fault Coverage %, Scan Flops, Patterns, Test Time)
- Fault breakdown table (DT, UT, AU, UD)
- Quick action buttons (View Full Report, Export STIL, Export Verilog TB, Close)
"""

import os
import json
from typing import Optional, Dict, Any

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QWidget,
    QFrame,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QTextEdit,
    QFileDialog,
    QMessageBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont


class DFTSignoffViewer(QDialog):
    """
    Modal signoff viewer displaying comprehensive DFT scan & ATPG metrics.
    """

    def __init__(
        self,
        summary_dict_or_path: Any,
        parent: Optional[QWidget] = None,
        project_dir: Optional[str] = None,
    ):
        super().__init__(parent)
        self.project_dir = project_dir or os.getcwd()
        self.metrics: Dict[str, Any] = {}
        self.report_path: Optional[str] = None

        if isinstance(summary_dict_or_path, str):
            if os.path.isfile(summary_dict_or_path):
                self.report_path = summary_dict_or_path
                try:
                    with open(summary_dict_or_path, "r") as f:
                        if summary_dict_or_path.endswith(".json"):
                            self.metrics = json.load(f)
                        else:
                            # It's a text report, parse key numbers
                            content = f.read()
                            self.metrics = self._parse_txt_report(content)
                except Exception as e:
                    print(f"[DFT Viewer] Failed to parse report: {e}")
        elif isinstance(summary_dict_or_path, dict):
            self.metrics = summary_dict_or_path

        self._init_ui()

    def _parse_txt_report(self, text: str) -> Dict[str, Any]:
        """Fallback simple parser for .rpt text files."""
        res = {
            "fault_coverage": 95.0,
            "scan_flop_count": 0,
            "pattern_count": 0,
            "estimated_test_time_ms": 0.0,
            "detected_faults": 0,
            "total_faults": 0,
            "untestable_faults": 0,
            "macro_clamped_faults": 0,
            "undetected_faults": 0,
            "status": "PASS",
        }
        m_cov = re.search(r"FINAL FAULT COVERAGE\s*:\s*([\d\.]+)", text)
        if m_cov:
            res["fault_coverage"] = float(m_cov.group(1))
        m_flops = re.search(r"Total Scan Flip-Flops\s*\|\s*(\d+)", text)
        if m_flops:
            res["scan_flop_count"] = int(m_flops.group(1))
        m_pats = re.search(r"TOTAL TEST PATTERNS\s*:\s*(\d+)", text)
        if m_pats:
            res["pattern_count"] = int(m_pats.group(1))
        m_time = re.search(r"ESTIMATED TEST TIME\s*:\s*([\d\.]+)", text)
        if m_time:
            res["estimated_test_time_ms"] = float(m_time.group(1))
        return res

    def _init_ui(self):
        self.setWindowTitle(f"Silis DFT & ATPG Signoff — {self.metrics.get('top_module', 'Design')}")
        self.setMinimumSize(780, 560)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMinMaxButtonsHint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Header Title
        title_lbl = QLabel("Design-for-Testability (DFT) & ATPG Signoff Analysis")
        title_lbl.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title_lbl.setStyleSheet("color: #58a6ff;")
        layout.addWidget(title_lbl)

        # 1. Metric Cards Grid
        grid_card = QGridLayout()
        grid_card.setSpacing(10)

        cov = self.metrics.get("fault_coverage", 0.0)
        cov_color = "#3fb950" if cov >= 95.0 else ("#d29922" if cov >= 90.0 else "#f85149")

        card_cov = self._create_card("Fault Coverage", f"{cov:.2f} %", cov_color)
        card_flops = self._create_card("Scan Flops", str(self.metrics.get("scan_flop_count", 0)), "#58a6ff")
        card_pats = self._create_card("Test Vectors", str(self.metrics.get("pattern_count", 0)), "#79c0ff")
        card_time = self._create_card("Estimated Test Time", f"{self.metrics.get('estimated_test_time_ms', 0.0)} ms", "#38bdf8")

        grid_card.addWidget(card_cov, 0, 0)
        grid_card.addWidget(card_flops, 0, 1)
        grid_card.addWidget(card_pats, 0, 2)
        grid_card.addWidget(card_time, 0, 3)
        layout.addLayout(grid_card)

        # 2. Detailed Breakdown Table
        lbl_tbl = QLabel("<b>Fault Classification & Testability Breakdown:</b>")
        lbl_tbl.setStyleSheet("font-size: 12px; color: #f0f6fc;")
        layout.addWidget(lbl_tbl)

        self.table = QTableWidget(5, 3)
        self.table.setHorizontalHeaderLabels(["Fault Category", "Count", "Percentage"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)

        tot = max(self.metrics.get("total_faults", 1), 1)
        dt = self.metrics.get("detected_faults", 0)
        ud = self.metrics.get("undetected_faults", 0)
        ut = self.metrics.get("untestable_faults", 0)
        au = self.metrics.get("macro_clamped_faults", 0)

        rows = [
            ("Detected Faults (DT)", dt, (dt / tot) * 100.0, "#3fb950"),
            ("Untestable / Tied Nodes (UT)", ut, (ut / tot) * 100.0, "#d29922"),
            ("Macro Clamped Nodes (AU)", au, (au / tot) * 100.0, "#58a6ff"),
            ("Undetected Faults (UD)", ud, (ud / tot) * 100.0, "#f85149" if ud > 0 else "#3fb950"),
            ("Total Enumerate Faults", tot, 100.0, "#f0f6fc"),
        ]

        for i, (name, cnt, pct, col) in enumerate(rows):
            item_name = QTableWidgetItem(name)
            item_cnt = QTableWidgetItem(str(cnt))
            item_cnt.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_pct = QTableWidgetItem(f"{pct:.2f} %")
            item_pct.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_name.setForeground(Qt.GlobalColor.white)
            self.table.setItem(i, 0, item_name)
            self.table.setItem(i, 1, item_cnt)
            self.table.setItem(i, 2, item_pct)

        layout.addWidget(self.table)

        # 3. Action Buttons Bar
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(8)

        btn_view_rpt = QPushButton("📄 View Report")
        btn_view_rpt.clicked.connect(self._on_view_report)
        btn_bar.addWidget(btn_view_rpt)

        btn_export_stil = QPushButton("💾 Export STIL (.stil)")
        btn_export_stil.setStyleSheet("background-color: #1f6feb; color: #ffffff; border: 1px solid #388bfd;")
        btn_export_stil.clicked.connect(self._on_export_stil)
        btn_bar.addWidget(btn_export_stil)

        btn_export_tb = QPushButton("🛠 Export Verilog TB (.v)")
        btn_export_tb.setStyleSheet("background-color: #238636; color: #ffffff; border: 1px solid #2ea043;")
        btn_export_tb.clicked.connect(self._on_export_tb)
        btn_bar.addWidget(btn_export_tb)

        btn_bar.addStretch()

        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        btn_bar.addWidget(btn_close)

        layout.addLayout(btn_bar)

    def _create_card(self, title: str, value: str, val_color: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(4)

        lbl_t = QLabel(title.upper())
        lbl_t.setStyleSheet("color: #8b949e; font-size: 10px; font-weight: bold; letter-spacing: 0.5px;")
        lay.addWidget(lbl_t)

        lbl_v = QLabel(value)
        lbl_v.setStyleSheet(f"color: {val_color}; font-size: 20px; font-weight: bold;")
        lay.addWidget(lbl_v)
        return card

    def _on_view_report(self):
        """Displays full text report in a preview modal."""
        rpt_text = "No report file available."
        rpt_file = self.report_path
        if not rpt_file and self.project_dir:
            cand = os.path.join(self.project_dir, "reports", "dft_summary.rpt")
            if os.path.isfile(cand):
                rpt_file = cand

        if rpt_file and os.path.isfile(rpt_file):
            with open(rpt_file, "r") as f:
                rpt_text = f.read()

        dlg = QDialog(self)
        dlg.setWindowTitle("DFT Summary Report Preview")
        dlg.resize(700, 500)
        dlg.setStyleSheet("QDialog { background-color: #0d1117; color: #f0f6fc; }")
        lay = QVBoxLayout(dlg)
        te = QTextEdit(dlg)
        te.setReadOnly(True)
        te.setStyleSheet("background: #090d13; color: #f0f6fc; font-family: Consolas; border: 1px solid #30363d; border-radius: 6px; padding: 8px;")
        te.setPlainText(rpt_text)
        lay.addWidget(te)
        dlg.exec()

    def _on_export_stil(self):
        dest, _ = QFileDialog.getSaveFileName(
            self, "Save STIL Pattern File", os.path.join(self.project_dir, "atpg_patterns.stil"), "STIL Files (*.stil)"
        )
        if dest:
            src = os.path.join(self.project_dir, "results", f"{self.metrics.get('top_module', 'design')}_atpg.stil")
            if os.path.isfile(src):
                import shutil
                shutil.copy2(src, dest)
                QMessageBox.information(self, "Export Success", f"Saved STIL pattern file to:\n{dest}")
            else:
                QMessageBox.warning(self, "Export Notice", f"Source STIL file not generated yet at:\n{src}")

    def _on_export_tb(self):
        dest, _ = QFileDialog.getSaveFileName(
            self, "Save ATPG Verilog Testbench", os.path.join(self.project_dir, "atpg_tb.v"), "Verilog Files (*.v)"
        )
        if dest:
            src = os.path.join(self.project_dir, "results", f"{self.metrics.get('top_module', 'design')}_atpg_tb.v")
            if os.path.isfile(src):
                import shutil
                shutil.copy2(src, dest)
                QMessageBox.information(self, "Export Success", f"Saved ATPG testbench to:\n{dest}")
            else:
                QMessageBox.warning(self, "Export Notice", f"Source testbench not generated yet at:\n{src}")
