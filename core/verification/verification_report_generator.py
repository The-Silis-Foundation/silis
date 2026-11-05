"""
verification_report_generator.py
Generates rich GitHub-flavored Markdown verification reports for Silis EDA.
Supports pyuvm, cocotb, SystemVerilog UVM, and VHDL OSVVM simulation runs.
Formats PASS / FAIL status badges, phase execution summaries, scoreboard comparisons,
and assertion diagnostics with clickable code jump links.
"""

import os
import re
from datetime import datetime


class VerificationReportGenerator:
    """
    Parses verification logs & scoreboard outputs and produces formatted Markdown.
    """

    @classmethod
    def generate_report(cls, project_name, test_name, methodology, logs, assertion_markers=None, out_dir=None, coverage_data=None):
        """
        Generates clean Markdown verification report for Silis EDA with hardware coverage metrics.
        """
        assertion_markers = assertion_markers or []
        coverage_data = coverage_data or {}
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Determine overall PASS / FAIL status
        has_fatal = any(m.get("severity") in ["fatal", "error"] for m in assertion_markers)
        has_log_error = any("error" in str(line).lower() or "fatal" in str(line).lower() or "mismatch" in str(line).lower() for line in logs)
        passed = not (has_fatal or has_log_error)

        status_text = "PASS" if passed else "FAIL"

        md = []
        md.append(f"# Verification Test Report: {test_name}\n")
        md.append(f"- **Status**: {status_text}")
        md.append(f"- **Methodology**: {methodology.upper()}")
        md.append(f"- **Project**: {project_name}")
        md.append(f"- **Execution Time**: {timestamp}")
        md.append(f"- **Total Checks / Assertions**: {len(assertion_markers)}")
        if coverage_data.get("overall_pct") is not None:
            md.append(f"- **Hardware Coverage**: {coverage_data.get('overall_pct')}%")
        md.append("\n---\n")

        # 1. Methodology Execution Summary
        md.append("## 1. Testbench Execution Summary\n")
        md.append("| Metric | Value |")
        md.append("| :--- | :--- |")
        md.append(f"| Test Case | `{test_name}` |")
        md.append(f"| Methodology | {methodology} |")
        md.append(f"| Result | {status_text} |")
        md.append(f"| Assertion Failures | {len(assertion_markers)} |")
        if coverage_data.get("overall_pct") is not None:
            md.append(f"| Line Coverage | {coverage_data.get('line_pct', 'N/A')}% |")
            md.append(f"| Toggle Coverage | {coverage_data.get('toggle_pct', 'N/A')}% |")
        md.append("\n")

        # 2. Hardware Coverage Section
        if coverage_data:
            md.append("## 2. Hardware Coverage Analysis (Verilator)\n")
            md.append("| Metric Type | Points Hit | Total Points | Coverage % |")
            md.append("| :--- | :--- | :--- | :--- |")
            for cov_type in ["Line", "Toggle", "Branch", "User / Assertion"]:
                key = cov_type.lower().split()[0]
                hit = coverage_data.get(f"{key}_hit", "-")
                total = coverage_data.get(f"{key}_total", "-")
                pct = coverage_data.get(f"{key}_pct", "-")
                pct_str = f"{pct}%" if pct != "-" else "-"
                md.append(f"| {cov_type} | {hit} | {total} | {pct_str} |")
            md.append("\n")

        # 3. Scoreboard & Assertion Diagnostics Table
        md.append("## 3. Assertion & Verification Checks\n")
        if assertion_markers:
            md.append("| # | Timestamp | Severity | Message | Source Location |")
            md.append("| :--- | :--- | :--- | :--- | :--- |")
            for idx, m in enumerate(assertion_markers, 1):
                t_str = f"{m.get('time_ps')} ps" if m.get("time_ps") is not None else "N/A"
                sev = m.get("severity", "error").upper()
                f_path = m.get("file", "unknown")
                f_line = m.get("line", 1)
                link = f"[{os.path.basename(f_path)}:{f_line}](file://{os.path.abspath(f_path)}#L{f_line})"
                md.append(f"| {idx} | `{t_str}` | {sev} | {m.get('msg', 'Check failure')} | {link} |")
        else:
            md.append("No assertion failures or errors detected during simulation.\n")
        md.append("\n")

        # 4. Log Stream Transcript (Folded)
        md.append("## 4. Simulation Console Transcript\n")
        md.append("<details>\n<summary>Click to expand raw simulation log</summary>\n\n```text")
        for line in logs[-150:]: # last 150 lines
            md.append(str(line).rstrip())
        md.append("```\n</details>\n")

        report_content = "\n".join(md)

        # Save to reports directory
        if not out_dir:
            out_dir = os.getcwd()
        rep_dir = os.path.join(out_dir, "reports")
        os.makedirs(rep_dir, exist_ok=True)
        report_path = os.path.join(rep_dir, f"{test_name}_report.md")

        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_content)

        return report_path
