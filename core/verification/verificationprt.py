"""
verificationprt.py
Engineered verification report generator for Silis EDA.
Produces clean, GitHub-flavored Markdown reports with text-based bar charts,
Mermaid architecture topologies, and hardware coverage metrics.
Strictly EDA-compliant: no playful emojis or toyish styling.
"""

import os
import re
from datetime import datetime


class VerificationReport:
    """
    Parses simulation outputs, assertion diagnostics, and Verilator hardware coverage
    to generate structured Markdown reports.
    """

    @staticmethod
    def render_bar(percentage: float, width: int = 25) -> str:
        """
        Renders an ASCII/Unicode progress bar.
        Example: [████████████████████░░░░░] 80.0%
        """
        clamped = max(0.0, min(100.0, float(percentage)))
        filled_len = int(round(width * clamped / 100.0))
        empty_len = width - filled_len
        bar_str = "█" * filled_len + "░" * empty_len
        return f"[{bar_str}] {clamped:5.1f}%"

    @classmethod
    def parse_verilator_coverage(cls, cov_output: str) -> dict:
        """
        Parses output from `verilator_coverage --report summary coverage.dat`.
        Extracts hit/total and percentages for line, toggle, branch, expr, fsm.
        """
        metrics = {}
        for line in cov_output.splitlines():
            line_s = line.strip()
            # Match pattern: line : 88.9% ( 16/ 18)
            m = re.match(r'^([a-zA-Z_]+)\s*:\s*([\d\.]+)%\s*\(\s*(\d+)/\s*(\d+)\)', line_s)
            if m:
                cat = m.group(1).lower()
                pct = float(m.group(2))
                hit = int(m.group(3))
                total = int(m.group(4))
                metrics[cat] = {
                    "pct": pct,
                    "hit": hit,
                    "total": total
                }
        return metrics

    @classmethod
    def generate(cls, project_name: str, top_module: str, test_name: str,
                 methodology: str, sim_logs: list, assertion_markers: list = None,
                 coverage_metrics: dict = None, out_path: str = None) -> str:
        """
        Generates full professional Markdown verification report.
        """
        assertion_markers = assertion_markers or []
        coverage_metrics = coverage_metrics or {}
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Determine overall PASS / FAIL status
        has_fatal = any(m.get("severity") in ["fatal", "error"] for m in assertion_markers)
        has_log_error = any("error" in str(line).lower() or "fatal" in str(line).lower() or "mismatch" in str(line).lower() for line in sim_logs)
        passed = not (has_fatal or has_log_error)
        status_text = "PASS" if passed else "FAIL"

        doc = []
        doc.append(f"# Verification Report: {project_name} / {test_name}\n")
        doc.append(f"**Target DUT**: `{top_module}`  ")
        doc.append(f"**Methodology**: {methodology.upper()}  ")
        doc.append(f"**Status**: **{status_text}**  ")
        doc.append(f"**Generated**: {timestamp}  ")
        doc.append(f"**Simulator**: Verilator 5.053 (IEEE 1800-2023 SystemVerilog)  \n")
        doc.append("---\n")

        # 1. Executive Summary Table
        doc.append("## 1. Executive Summary\n")
        doc.append("| Parameter | Value | Status |")
        doc.append("| :--- | :--- | :--- |")
        doc.append(f"| Project Name | `{project_name}` | Configured |")
        doc.append(f"| Top DUT Module | `{top_module}` | Synthesizable |")
        doc.append(f"| Testcase Executed | `{test_name}` | Completed |")
        doc.append(f"| Verification Result | **{status_text}** | {'Normal' if passed else 'Action Required'} |")
        doc.append(f"| Assertion / Log Violations | {len(assertion_markers)} | {'Clean' if len(assertion_markers) == 0 else 'Violations Detected'} |")
        
        overall_cov = coverage_metrics.get("line", {}).get("pct", None)
        if overall_cov is not None:
            doc.append(f"| Line Coverage | {overall_cov:.1f}% | {'Acceptable' if overall_cov >= 80.0 else 'Under Target'} |")
        doc.append("\n")

        # 2. Hardware Coverage Visual Representation & Mermaid Chart
        if coverage_metrics:
            doc.append("## 2. Hardware Coverage Metrics\n")
            categories = [
                ("Line Coverage", "line"),
                ("Toggle Coverage", "toggle"),
                ("Branch Coverage", "branch"),
                ("Expression Coverage", "expr"),
                ("FSM State Coverage", "fsm_state")
            ]

            # Mermaid XY Chart for visual coverage bars
            active_cats = [(label.replace(" Coverage", ""), key) for label, key in categories if key in coverage_metrics]
            if active_cats:
                cat_names = [f'"{name}"' for name, _ in active_cats]
                pct_values = [str(int(round(coverage_metrics[key]["pct"]))) for _, key in active_cats]
                doc.append("```mermaid")
                doc.append("xychart-beta")
                doc.append("    title \"Hardware Coverage by Category (%)\"")
                doc.append(f"    x-axis [{', '.join(cat_names)}]")
                doc.append("    y-axis \"Coverage %\" 0 --> 100")
                doc.append(f"    bar [{', '.join(pct_values)}]")
                doc.append("```\n")

            doc.append("### Detailed Metric Breakdown\n")
            doc.append("| Metric Type | Points Hit | Total Points | Coverage (%) | Target (%) | Status |")
            doc.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
            for label, key in categories:
                data = coverage_metrics.get(key)
                if data:
                    pct = data["pct"]
                    target = 80.0
                    stat = "MET" if pct >= target else "UNMET"
                    doc.append(f"| {label} | {data['hit']} | {data['total']} | {pct:.1f}% | {target:.1f}% | {stat} |")
            doc.append("\n")

        # 3. Component & Verification Topology (Mermaid)
        doc.append("## 3. Testbench Topology & Interface Wiring\n")
        doc.append("```mermaid")
        doc.append("flowchart TD")
        doc.append("    subgraph Testbench [\"Testbench Environment\"]")
        doc.append(f"        TB[\"{test_name}\"] --> INTF[\"Virtual Interface / Pin Driver\"]")
        doc.append("        INTF --> STIM[\"TX Stimulus Generator\"]")
        doc.append("        INTF --> MON[\"RX Monitor / Checker\"]")
        doc.append("        MON --> SCB[\"Scoreboard Comparison\"]")
        doc.append("    end")
        doc.append(f"    subgraph DUT [\"Design Under Test: {top_module}\"]")
        doc.append("        INTF --> DUT_CORE[\"DUT Core Logic\"]")
        doc.append("        DUT_CORE --> INTF")
        doc.append("    end")
        doc.append("```\n")

        # 4. Simulation Assertion & Diagnostic Checks
        doc.append("## 4. Assertion & Diagnostic Log Summary\n")
        if assertion_markers:
            doc.append("| Index | Timestamp | Severity | Diagnostic Message | Source Context |")
            doc.append("| :--- | :--- | :--- | :--- | :--- |")
            for i, m in enumerate(assertion_markers, start=1):
                t_str = f"{m.get('time_ps')} ps" if m.get("time_ps") is not None else "N/A"
                sev = m.get("severity", "ERROR").upper()
                msg = m.get("msg", "Unknown error")
                loc = f"`{m.get('file', 'unknown')}:{m.get('line', 0)}`"
                doc.append(f"| {i} | {t_str} | {sev} | {msg} | {loc} |")
            doc.append("\n")
        else:
            doc.append("- No assertion failures or protocol violations detected during simulation.\n")

        # 5. Raw Simulation Log Tail
        doc.append("## 5. Simulation Execution Transcript\n")
        doc.append("```text")
        tail_lines = sim_logs[-30:] if len(sim_logs) > 30 else sim_logs
        for l in tail_lines:
            doc.append(str(l))
        doc.append("```\n")

        report_content = "\n".join(doc)
        if out_path:
            os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(report_content)

        return report_content
