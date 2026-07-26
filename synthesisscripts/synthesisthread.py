"""
synthesisscripts/synthesisthread.py
Synthesis dashboard, report parser, and tab widget.
"""
import os
import re
import datetime
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from terminal.terminal import HeaderFactory


class ReportEngine:
    """Parses generated report files for robust metric extraction."""

    FOOTER_ART = HeaderFactory.ASCII_ART

    @staticmethod
    def parse_files(report_dir):
        metrics = {
            "area": "Unknown", "cells": "0", "wires": "Unknown", "bits": "Unknown",
            "wns": "0.00", "status": "UNKNOWN",
            "critical_path_trace": "No path data found in timing.rpt",
            "pwr_seq": ["0", "0", "0", "0", "0%"],
            "pwr_comb": ["0", "0", "0", "0", "0%"],
            "pwr_clk": ["0", "0", "0", "0", "0%"],
            "pwr_mac": ["0", "0", "0", "0", "0%"],
            "pwr_pad": ["0", "0", "0", "0", "0%"],
            "pwr_tot": ["0", "0", "0", "0", "100%"],
            "pwr_pct": ["0%", "0%", "0%"],
            "errors": [], "timing_groups": [], "cell_list": []
        }

        # 1. PARSE YOSYS LOG
        yosys_log = os.path.join(report_dir, "synthesis.log")
        if os.path.exists(yosys_log):
            with open(yosys_log, 'r') as f:
                log_content = f.read()
                raw_cells = re.findall(r"(sky130_fd_sc_hd__\w+)\s+cells:\s+(\d+)", log_content)
                if raw_cells:
                    metrics["cell_list"] = sorted([(k, int(v)) for k, v in raw_cells], key=lambda x: x[1], reverse=True)
                for line in log_content.split('\n'):
                    if "ERROR" in line or "Warning:" in line:
                        if len(metrics["errors"]) < 10: metrics["errors"].append(line.strip())

        # 2. PARSE AREA REPORT
        area_rpt = os.path.join(report_dir, "area.rpt")
        if os.path.exists(area_rpt):
            with open(area_rpt, 'r') as f:
                content = f.read()
                m_area = re.search(r'"area":\s+([\d\.]+)', content)
                if m_area: metrics["area"] = m_area.group(1)
                m_cells = re.search(r'"num_cells":\s+(\d+)', content)
                if m_cells: metrics["cells"] = m_cells.group(1)
                m_wires = re.search(r'"num_wires":\s+(\d+)', content)
                if m_wires: metrics["wires"] = m_wires.group(1)
                m_bits = re.search(r'"num_pub_wire_bits":\s+(\d+)', content)
                if m_bits: metrics["bits"] = m_bits.group(1)

        # 3. PARSE TIMING REPORT
        timing_rpt = os.path.join(report_dir, "timing.rpt")
        if os.path.exists(timing_rpt):
            with open(timing_rpt, 'r') as f:
                content = f.read()
                trace_match = re.search(r"(Startpoint:.*?slack \([A-Z]+\))", content, re.DOTALL)
                if trace_match:
                    metrics["critical_path_trace"] = trace_match.group(1)
                slacks = re.findall(r"([-+]?\d+\.\d+)\s+slack\s+\((VIOLATED|MET)\)", content)
                if slacks:
                    worst_slack = min(slacks, key=lambda x: float(x[0]))
                    metrics["wns"] = worst_slack[0]
                    metrics["status"] = worst_slack[1]
                else:
                    metrics["status"] = "MET"
                chunks = content.split("Path Group: ")
                seen_groups = set()
                for chunk in chunks[1:]:
                    lines = chunk.strip().split('\n')
                    g_name = lines[0].strip()
                    if g_name in seen_groups: continue
                    seen_groups.add(g_name)
                    m_slack = re.search(r"([-+]?\d+\.\d+)\s+slack\s+\((VIOLATED|MET)\)", chunk)
                    m_end = re.search(r"Endpoint:\s+(\S+)", chunk)
                    if m_slack:
                        s_val = m_slack.group(1)
                        s_stat = m_slack.group(2)
                        end_p = m_end.group(1) if m_end else "Unknown"
                        metrics["timing_groups"].append((g_name, s_val, s_stat, end_p))

        # 4. PARSE POWER REPORT
        power_rpt = os.path.join(report_dir, "power.rpt")
        if os.path.exists(power_rpt):
            with open(power_rpt, 'r') as f:
                for line in f:
                    parts = line.split()
                    if not parts: continue
                    if parts[0] == "Sequential" and len(parts)>=6: metrics["pwr_seq"] = parts[1:6]
                    elif parts[0] == "Combinational" and len(parts)>=6: metrics["pwr_comb"] = parts[1:6]
                    elif parts[0] == "Clock" and len(parts)>=6: metrics["pwr_clk"] = parts[1:6]
                    elif parts[0] == "Macro" and len(parts)>=6: metrics["pwr_mac"] = parts[1:6]
                    elif parts[0] == "Pad" and len(parts)>=6: metrics["pwr_pad"] = parts[1:6]
                    elif parts[0] == "Total" and len(parts)>=6: metrics["pwr_tot"] = parts[1:6]
                    elif "%" in parts[0] and len(parts)>=3 and "Total" not in line: metrics["pwr_pct"] = parts[0:3]

        return metrics

    @staticmethod
    def _bar(pct_str):
        try:
            val = float(pct_str.strip('%'))
            blocks = int(val / 10)
            return f"|{'█'*blocks}{'-'*(10-blocks)}| {pct_str}"
        except: return "|----------| 0.0%"

    @staticmethod
    def generate_report(metrics, design_name="riscv_core"):
        now = datetime.datetime.now().strftime("%Y-%m-%d")
        def pr(name, d):
            split_vis = ReportEngine._bar(d[4])
            return f"| {name:<14} | {d[0]:<10} | {d[1]:<10} | {d[2]:<10} | {d[3]:<10} | {d[4]:<6} | {split_vis:<16} |"
        t_table = ""
        for g, s, st, end in metrics["timing_groups"]:
            t_table += f"| {g:<13} | {s:<11} | {st:<10} | {end:<25} |\n"
        c_table = ""
        total_c = int(metrics["cells"]) if int(metrics["cells"]) > 0 else 1
        for name, count in metrics["cell_list"][:15]:
            pct = (count / total_c) * 100
            c_table += f"| {name:<30} | {str(count):<6} | {pct:<4.1f}% |\n"
        rpt = f"""################################################################################
#                                            POST SYNTHESIS REPORT
# Design:       {design_name}
# Date:         {now}
# PDK:          Sky130 (High Density)
# Generated by Silis — Silicon Scaffold
################################################################################

================================================================================
  SECTION 1: DESIGN STATISTICS
================================================================================
+---------------------------+-------------------+
| Metric                    | Value             |
+---------------------------+-------------------+
| Total Cells               | {metrics['cells']:<17} |
| Total Area                | {metrics['area'] + ' um^2':<17} |
| Total Wires               | {metrics['wires']:<17} |
| Public Wire Bits          | {metrics['bits']:<17} |
+---------------------------+-------------------+

================================================================================
  SECTION 2: TIMING SUMMARY
================================================================================
+---------------+-------------+------------+---------------------------+
| Path Group    | Slack       | Status     | Critical Endpoint         |
+---------------+-------------+------------+---------------------------+
{t_table}+---------------+-------------+------------+---------------------------+

  Worst Negative Slack (WNS): {metrics['wns']} ns ({metrics['status']})

  CRITICAL PATH TRACE:
  {metrics['critical_path_trace'].replace(chr(10), chr(10)+'  ')}

================================================================================
  SECTION 3: POWER ANALYSIS
================================================================================
+----------------+------------+------------+------------+------------+--------+------------------+
| Group          | Internal   | Switching  | Leakage    | Total      | %      | Split            |
+----------------+------------+------------+------------+------------+--------+------------------+
{pr("Sequential", metrics['pwr_seq'])}
{pr("Combinational", metrics['pwr_comb'])}
{pr("Clock", metrics['pwr_clk'])}
{pr("Macro", metrics['pwr_mac'])}
{pr("Pad", metrics['pwr_pad'])}
+----------------+------------+------------+------------+------------+--------+------------------+
| TOTAL          | {metrics['pwr_tot'][0]:<10} | {metrics['pwr_tot'][1]:<10} | {metrics['pwr_tot'][2]:<10} | {metrics['pwr_tot'][3]:<10} | 100%   | |██████████| 100% |
+----------------+------------+------------+------------+------------+--------+------------------+

[ WARNINGS ]
{chr(10).join(['  ! '+e for e in metrics['errors']]) if metrics['errors'] else "  (None)"}

================================================================================
  SECTION 4: CELL UTILIZATION (Top 15)
================================================================================
+--------------------------------+--------+-------+
| Cell Name                      | Count  | %     |
+--------------------------------+--------+-------+
{c_table}+--------------------------------+--------+-------+

{ReportEngine.FOOTER_ART}
https://github.com/The-Silis-Foundation/silis
________________________________________________________________________________
Generated by Silis — Silicon Scaffold
© 2026 The Silis Foundation
________________________________________________________________________________
"""
        return rpt


class SynthesisTab(QWidget):
    def __init__(self, ide):
        super().__init__()
        self.ide = ide
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10); lay.setSpacing(15)

        # === LEFT COLUMN (LOGS) ===
        left_col = QWidget()
        l_lay = QVBoxLayout(left_col); l_lay.setContentsMargins(0,0,0,0)

        ctrl = QFrame(); ctrl.setStyleSheet("border-radius: 4px; padding: 5px; border: 1px solid gray;")
        cl = QHBoxLayout(ctrl); cl.setContentsMargins(5,5,5,5)
        self.lbl_pdk = QLabel("Active PDK: Sky130A"); self.lbl_pdk.setStyleSheet("font-weight:bold;")

        btn_style = "QPushButton { border: 1px solid gray; padding: 5px 15px; border-radius: 3px; }"
        run_style = "QPushButton { border: 1px solid gray; padding: 5px 15px; border-radius: 3px; font-weight: bold; }"

        btn_sel = QPushButton("⚙ PDK"); btn_sel.setStyleSheet(btn_style)
        btn_sel.clicked.connect(self.ide.open_pdk_selector)
        self.btn_run = QPushButton("Run Flow"); self.btn_run.setStyleSheet(run_style)
        self.btn_run.clicked.connect(self.ide.run_synthesis_flow)

        cl.addWidget(self.lbl_pdk); cl.addStretch(); cl.addWidget(btn_sel); cl.addWidget(self.btn_run)
        l_lay.addWidget(ctrl)

        self.log_tabs = QTabWidget()
        self.log_tabs.setStyleSheet("")

        self.log_main = QTextEdit(); self.log_main.setReadOnly(True)
        self.log_main.setStyleSheet("font-family:Consolas; border:none;")
        self.log_tabs.addTab(self.log_main, "Build Output")

        self.list_err = QListWidget()
        self.list_err.setStyleSheet("color:#cf222e; font-family:Consolas; border:1px solid gray; padding: 5px;")
        self.log_tabs.addTab(self.list_err, "Issues / Errors")

        l_lay.addWidget(self.log_tabs)
        lay.addWidget(left_col, stretch=2)

        # === RIGHT COLUMN (DASHBOARD) ===
        right_col = QFrame()
        right_col.setStyleSheet("border-left: 1px solid gray;")
        right_col.setFixedWidth(360)
        r_lay = QVBoxLayout(right_col)

        self.card_status = QLabel("READY")
        self.card_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.card_status.setStyleSheet("font-size:14px; font-weight:bold; padding:10px; border-radius:6px; border: 1px solid gray;")
        r_lay.addWidget(self.card_status)

        grid_w = QWidget(); grid = QGridLayout(grid_w)
        v_style = "font-weight:bold; font-size:12px;"
        grid.addWidget(QLabel("WNS (Slack):"), 0, 0); lbl = QLabel("--"); lbl.setStyleSheet(v_style); self.val_wns = lbl; grid.addWidget(lbl, 0, 1)
        grid.addWidget(QLabel("Chip Area:"), 1, 0); lbl2 = QLabel("--"); lbl2.setStyleSheet(v_style); self.val_area = lbl2; grid.addWidget(lbl2, 1, 1)
        grid.addWidget(QLabel("Gate Count:"), 2, 0); lbl3 = QLabel("--"); lbl3.setStyleSheet(v_style); self.val_gates = lbl3; grid.addWidget(lbl3, 2, 1)
        r_lay.addWidget(grid_w)

        r_lay.addWidget(QLabel("<b style='color:#24292f'>Report Preview:</b>"))
        self.preview = QTextEdit(); self.preview.setReadOnly(True)
        self.preview.setMaximumHeight(250)
        self.preview.setStyleSheet("font-family:Consolas; font-size:8pt; border:1px solid gray;")
        self.preview.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        r_lay.addWidget(self.preview)

        btn_save = QPushButton("Save .rpt File"); btn_save.setStyleSheet("border:1px solid gray; padding:5px;")
        btn_save.clicked.connect(self.save_report)
        r_lay.addWidget(btn_save)
        r_lay.addStretch()

        lay.addWidget(right_col, stretch=1)

    def update_dashboard(self):
        _, base = self.ide.get_context()
        if not base: return
        root = self.ide.get_proj_root(base)
        report_dir = os.path.join(root, "reports")

        m = ReportEngine.parse_files(report_dir)

        if m["status"] == "MET":
            self.card_status.setText("TIMING MET")
            self.card_status.setStyleSheet("background:#2da44e; color:white; font-weight:bold; padding:10px; border-radius:6px;")
        elif m["status"] == "VIOLATED":
            self.card_status.setText("TIMING FAIL")
            self.card_status.setStyleSheet("background:#cf222e; color:white; font-weight:bold; padding:10px; border-radius:6px;")

        self.val_wns.setText(f"{m['wns']} ns")
        self.val_area.setText(f"{m['area']} um^2")
        self.val_gates.setText(m['cells'])

        self.list_err.clear()
        for e in m['errors']: self.list_err.addItem(e)
        if m['errors']: self.log_tabs.setCurrentIndex(1)

        rpt = ReportEngine.generate_report(m, base or "design")
        self.preview.setPlainText(rpt)
        self.last_report = rpt

        self.ide.log_system("Generating Post Synthesis Report...", "SYS")
        print(rpt)
        self.ide.log_system("Report generated in background.", "RPT")

    def save_report(self):
        if not hasattr(self, 'last_report'): return
        _, base = self.ide.get_context()
        report_name = f"{base or 'design'}_synthesis_report.rpt"
        path, _ = QFileDialog.getSaveFileName(self, "Save PAT Report", report_name, "Report Files (*.rpt)")
        if path:
            with open(path, 'w') as f: f.write(self.last_report)
            self.ide.log_system(f"Report saved: {os.path.basename(path)}")
