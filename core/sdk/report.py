"""
silis/sdk/report.py
Silis ASIC Report Analysis and Parsing Layer.
Exposes SynthesisReport, SignoffReport, and DRCReport.
"""

import os
import re
import json
from typing import Dict, List, Optional, Tuple, Any

from synthesisscripts.synthesisthread import ReportEngine


class SynthesisReport:
    """
    Structured post-synthesis metrics and timing analysis.
    Parses area.rpt, timing.rpt, power.rpt, and synthesis.log via ReportEngine.
    """

    def __init__(
        self,
        metrics: Optional[Dict[str, Any]] = None,
        report_dir: Optional[str] = None,
        raw_text: Optional[str] = None,
        design_name: str = "design",
    ):
        self.report_dir = os.path.abspath(report_dir) if report_dir else None
        self.design_name = design_name
        self.metrics = metrics or {}
        self.raw_text = raw_text or ""

        # Extracted fields
        self.status: str = self.metrics.get("status", "UNKNOWN")
        try:
            self.cells: int = int(self.metrics.get("cells", 0))
        except (ValueError, TypeError):
            self.cells = 0

        try:
            self.area: float = float(self.metrics.get("area", 0.0))
        except (ValueError, TypeError):
            self.area = 0.0

        self.wires: str = str(self.metrics.get("wires", "Unknown"))
        self.bits: str = str(self.metrics.get("bits", "Unknown"))

        try:
            self.wns: float = float(self.metrics.get("wns", 0.0))
        except (ValueError, TypeError):
            self.wns = 0.0

        self.critical_path_trace: str = self.metrics.get("critical_path_trace", "")
        self.errors: List[str] = list(self.metrics.get("errors", []))
        self.timing_groups: List[Tuple[str, str, str, str]] = list(
            self.metrics.get("timing_groups", [])
        )
        self.cell_list: List[Tuple[str, int]] = list(self.metrics.get("cell_list", []))

        # Power breakdown: [Internal, Switching, Leakage, Total, %]
        self.pwr_seq: List[str] = list(self.metrics.get("pwr_seq", ["0", "0", "0", "0", "0%"]))
        self.pwr_comb: List[str] = list(self.metrics.get("pwr_comb", ["0", "0", "0", "0", "0%"]))
        self.pwr_clk: List[str] = list(self.metrics.get("pwr_clk", ["0", "0", "0", "0", "0%"]))
        self.pwr_mac: List[str] = list(self.metrics.get("pwr_mac", ["0", "0", "0", "0", "0%"]))
        self.pwr_pad: List[str] = list(self.metrics.get("pwr_pad", ["0", "0", "0", "0", "0%"]))
        self.pwr_tot: List[str] = list(self.metrics.get("pwr_tot", ["0", "0", "0", "0", "100%"]))
        self.pwr_pct: List[str] = list(self.metrics.get("pwr_pct", ["0%", "0%", "0%"]))

    @property
    def is_clean(self) -> bool:
        """Returns True if timing was met and status is not FAILED/VIOLATED."""
        return self.status == "MET" and self.wns >= 0.0

    @property
    def total_power(self) -> str:
        """Returns total power string if available."""
        if len(self.pwr_tot) >= 4:
            return self.pwr_tot[3]
        return "0.00"

    def summary(self, design_name: Optional[str] = None) -> str:
        """Generates comprehensive ASCII report matching Silis standard formatting."""
        d_name = design_name or self.design_name
        return ReportEngine.generate_report(self.metrics, design_name=d_name)

    @classmethod
    def load(cls, path_or_dir: str, design_name: str = "design") -> "SynthesisReport":
        """Loads and parses synthesis report files from a directory or path."""
        target_dir = path_or_dir
        if os.path.isfile(target_dir):
            target_dir = os.path.dirname(target_dir)

        target_dir = os.path.abspath(target_dir)
        metrics = ReportEngine.parse_files(target_dir)
        return cls(metrics=metrics, report_dir=target_dir, design_name=design_name)

    def __repr__(self) -> str:
        return (
            f"<SynthesisReport status='{self.status}' cells={self.cells} "
            f"area={self.area:.2f}um^2 wns={self.wns:.3f}ns clean={self.is_clean}>"
        )


class SignoffReport:
    """
    Post-route Power, Area, and Timing (PAT) signoff report parser.
    Parses <top>_pat_report.rpt generated after routing and multi-corner timing.
    """

    def __init__(
        self,
        file_path: Optional[str] = None,
        design: str = "unknown",
        date: str = "",
        pdk: str = "",
        cells: int = 0,
        core_area: float = 0.0,
        timing_status: str = "UNKNOWN",
        wns: float = 0.0,
        critical_path_trace: str = "",
        timing_groups: Optional[List[Dict[str, str]]] = None,
        power_table: Optional[Dict[str, Dict[str, str]]] = None,
        raw_text: str = "",
    ):
        self.file_path = os.path.abspath(file_path) if file_path else None
        self.design = design
        self.date = date
        self.pdk = pdk
        self.cells = cells
        self.core_area = core_area
        self.timing_status = timing_status
        self.wns = wns
        self.critical_path_trace = critical_path_trace
        self.timing_groups = timing_groups or []
        self.power_table = power_table or {}
        self.raw_text = raw_text

    @property
    def is_clean(self) -> bool:
        """Returns True if overall timing is MET and WNS >= 0.0."""
        return self.timing_status == "MET" and self.wns >= 0.0

    @property
    def total_power(self) -> str:
        """Returns total power from power table if parsed."""
        if "TOTAL" in self.power_table:
            return self.power_table["TOTAL"].get("total", "0.00")
        return "0.00"

    @property
    def total_power_mw(self) -> str:
        """Alias for total_power."""
        return self.total_power

    @property
    def area(self) -> float:
        """Alias for core_area."""
        return self.core_area

    @property
    def critical_endpoint(self) -> str:
        """Alias for critical_path_trace."""
        return self.critical_path_trace

    def summary(self) -> str:
        """Returns full raw or formatted PAT report string."""
        if self.raw_text:
            return self.raw_text
        return (
            f"Signoff PAT Report: {self.design}\n"
            f"PDK: {self.pdk} | Timing: {self.timing_status} | WNS: {self.wns} ns\n"
            f"Cells: {self.cells} | Core Area: {self.core_area} um^2"
        )

    @classmethod
    def load(cls, path_or_dir: str, design_name: Optional[str] = None) -> "SignoffReport":
        """
        Loads and parses a PAT signoff report from a file or directory.
        If a directory is given, searches for *_pat_report.rpt.
        """
        rpt_path = None
        if os.path.isdir(path_or_dir):
            if design_name:
                cand = os.path.join(path_or_dir, f"{design_name}_pat_report.rpt")
                if os.path.isfile(cand):
                    rpt_path = cand
            if not rpt_path:
                for f in os.listdir(path_or_dir):
                    if f.endswith("_pat_report.rpt") or f == "pat_report.rpt":
                        rpt_path = os.path.join(path_or_dir, f)
                        break
        elif os.path.isfile(path_or_dir):
            rpt_path = path_or_dir

        if not rpt_path or not os.path.exists(rpt_path):
            return cls(file_path=rpt_path, design=design_name or "unknown")

        with open(rpt_path, "r", errors="ignore") as f:
            content = f.read()

        return cls.parse_text(content, file_path=rpt_path, design_name=design_name)

    @classmethod
    def parse_text(
        cls, content: str, file_path: Optional[str] = None, design_name: Optional[str] = None
    ) -> "SignoffReport":
        design = design_name or "unknown"
        m_des = re.search(r"#\s*Design:\s*(\S+)", content)
        if m_des:
            design = m_des.group(1).strip()

        date_val = ""
        m_date = re.search(r"#\s*Date:\s*(.+)", content)
        if m_date:
            date_val = m_date.group(1).strip()

        pdk_val = ""
        m_pdk = re.search(r"#\s*PDK:\s*(\S+)", content)
        if m_pdk:
            pdk_val = m_pdk.group(1).strip()

        cells_val = 0
        m_cells = re.search(r"\|\s*Total Cells\s*\|\s*(\d+)", content)
        if m_cells:
            cells_val = int(m_cells.group(1))

        area_val = 0.0
        m_area = re.search(r"\|\s*Total Core Area\s*\|\s*([\d\.]+)", content)
        if m_area:
            area_val = float(m_area.group(1))

        timing_status = "UNKNOWN"
        m_status = re.search(r"\|\s*Overall Timing Status\s*\|\s*(\w+)", content)
        if m_status:
            timing_status = m_status.group(1).strip()

        wns_val = 0.0
        num_pattern = r"[-+]?(?:(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?|inf|-inf|nan|-nan)"
        m_wns = re.search(rf"Worst Negative Slack \(WNS\):\s*({num_pattern})\s*ns\s*\((\w+)\)", content, re.IGNORECASE)
        if m_wns:
            wns_val = float(m_wns.group(1))
            if timing_status == "UNKNOWN":
                timing_status = m_wns.group(2).strip()

        # Critical path trace
        crit_trace = ""
        m_trace = re.search(r"CRITICAL PATH TRACE:\s*\n(.*?)(?=\n={10,}|\Z)", content, re.DOTALL)
        if m_trace:
            crit_trace = m_trace.group(1).strip()

        # Timing scenarios / groups
        timing_groups = []
        sec2 = re.search(
            r"SECTION 2:.*?TIMING SUMMARY.*?\n\+[-+]+\+.*?\n(.*?)(?=\n\s*Worst Negative Slack)",
            content,
            re.DOTALL,
        )
        if sec2:
            for row in sec2.group(1).split("\n"):
                if "|" in row and not row.startswith("+"):
                    parts = [p.strip() for p in row.split("|")[1:-1]]
                    if len(parts) >= 4 and parts[0] and not parts[0].startswith("Scenario"):
                        timing_groups.append({
                            "scenario": parts[0],
                            "slack": parts[1],
                            "status": parts[2],
                            "endpoint": parts[3],
                        })

        # Power table
        power_table: Dict[str, Dict[str, str]] = {}
        sec3 = re.search(
            r"SECTION 3: POWER ANALYSIS.*?\n\+[-+]+\+.*?\n(.*?)(?=\n\+[-+]+\+\s*\n\s*\[ PVT|\Z)",
            content,
            re.DOTALL,
        )
        if sec3:
            for row in sec3.group(1).split("\n"):
                if "|" in row and not row.startswith("+"):
                    cols = [c.strip() for c in row.split("|")[1:-1]]
                    if len(cols) >= 5 and cols[0] and not cols[0].startswith("Group"):
                        grp_name = cols[0]
                        power_table[grp_name] = {
                            "internal": cols[1] if len(cols) > 1 else "0.0",
                            "switching": cols[2] if len(cols) > 2 else "0.0",
                            "leakage": cols[3] if len(cols) > 3 else "0.0",
                            "total": cols[4] if len(cols) > 4 else "0.0",
                            "pct": cols[5] if len(cols) > 5 else "0%",
                        }

        return cls(
            file_path=file_path,
            design=design,
            date=date_val,
            pdk=pdk_val,
            cells=cells_val,
            core_area=area_val,
            timing_status=timing_status,
            wns=wns_val,
            critical_path_trace=crit_trace,
            timing_groups=timing_groups,
            power_table=power_table,
            raw_text=content,
        )

    def __repr__(self) -> str:
        return (
            f"<SignoffReport design='{self.design}' status='{self.timing_status}' "
            f"wns={self.wns:.3f}ns cells={self.cells} core_area={self.core_area:.2f}um^2 clean={self.is_clean}>"
        )


class DRCReport:
    """
    Design Rule Checking (DRC) report parser.
    Parses Magic DRC or OpenROAD TritonRoute DRC reports.
    """

    def __init__(
        self,
        file_path: Optional[str] = None,
        violations_count: int = 0,
        violations: Optional[List[str]] = None,
        raw_text: str = "",
        tool: str = "DRC",
    ):
        self.file_path = os.path.abspath(file_path) if file_path else None
        self.violations_count = violations_count
        self.violations = violations or []
        self.raw_text = raw_text
        self.tool = tool

    @property
    def is_clean(self) -> bool:
        """Returns True if there are 0 DRC violations."""
        return self.violations_count == 0

    def summary(self) -> str:
        """Returns a concise DRC status summary."""
        status_sym = "🟢 CLEAN" if self.is_clean else f"🔴 FAILED ({self.violations_count} Violations)"
        summary_str = f"[{self.tool} Sign-off] Status: {status_sym}\nReport File: {self.file_path}\n"
        if self.violations:
            summary_str += "Violations:\n"
            for v in self.violations[:20]:
                summary_str += f"  • {v}\n"
            if len(self.violations) > 20:
                summary_str += f"  ... and {len(self.violations) - 20} more violations\n"
        return summary_str

    @classmethod
    def load(cls, path_or_dir: str, results_dir: Optional[str] = None) -> "DRCReport":
        """
        Loads DRC report from a specific file path or discovers standard DRC files
        in reports/ or results/ directories (e.g. drc.rpt, route_drc.rpt, antenna.rpt).
        """
        rpt_cand = None
        if os.path.isfile(path_or_dir):
            rpt_cand = path_or_dir
        elif os.path.isdir(path_or_dir):
            # Check candidate names in report dir
            cands = ["drc.rpt", "route_drc.rpt", "antenna.rpt"]
            for c in cands:
                p = os.path.join(path_or_dir, c)
                if os.path.isfile(p):
                    rpt_cand = p
                    break

            # Check results_dir fallback
            if not rpt_cand and results_dir and os.path.isdir(results_dir):
                for c in ["route_drc.rpt", "drc.rpt"]:
                    p = os.path.join(results_dir, c)
                    if os.path.isfile(p):
                        rpt_cand = p
                        break

        if not rpt_cand or not os.path.exists(rpt_cand):
            return cls(file_path=rpt_cand, violations_count=0, tool="DRC")

        with open(rpt_cand, "r", errors="ignore") as f:
            content = f.read()

        return cls.parse_text(content, file_path=rpt_cand)

    @classmethod
    def parse_text(cls, content: str, file_path: Optional[str] = None) -> "DRCReport":
        tool = "DRC"
        lines = [line.strip() for line in content.split("\n") if line.strip()]

        if not lines:
            # Empty DRC report indicates 0 violations
            return cls(file_path=file_path, violations_count=0, violations=[], raw_text=content, tool=tool)

        # 1. Check Magic DRC format: SILIS_DRC_VIOLATIONS: <n>
        m_magic = re.search(r"SILIS_DRC_VIOLATIONS:\s*(\d+)", content)
        if m_magic:
            v_count = int(m_magic.group(1))
            tool = "Magic DRC"
            viols = [l for l in lines if not l.startswith("SILIS_DRC") and ("violation" in l.lower() or "error" in l.lower())]
            return cls(file_path=file_path, violations_count=v_count, violations=viols, raw_text=content, tool=tool)

        # 2. Check OpenROAD TritonRoute DRC format: "total violations: <n>" or "violation type: ..."
        m_drt = re.search(r"total violations:\s*(\d+)", content, re.IGNORECASE)
        viols = []
        for line in lines:
            if line.lower().startswith("violation type:") or "violation" in line.lower():
                viols.append(line)

        if m_drt:
            v_count = int(m_drt.group(1))
            tool = "OpenROAD Route DRC"
            return cls(file_path=file_path, violations_count=v_count, violations=viols, raw_text=content, tool=tool)

        # 3. Check antenna violations format: "Antenna Violations: <n>"
        m_ant = re.search(r"Antenna Violations:\s*(\d+)", content)
        if m_ant:
            v_count = int(m_ant.group(1))
            tool = "Antenna DRC"
            return cls(file_path=file_path, violations_count=v_count, violations=viols, raw_text=content, tool=tool)

        # Fallback: Count non-empty violation lines
        v_count = len(viols)
        return cls(file_path=file_path, violations_count=v_count, violations=viols, raw_text=content, tool=tool)

    def __repr__(self) -> str:
        return f"<DRCReport tool='{self.tool}' violations={self.violations_count} clean={self.is_clean}>"


class DFTSignoffReport:
    """
    Structured DFT and ATPG Signoff metrics.
    Parses reports/dft_summary.rpt and reports/dft_summary.json.
    """

    def __init__(
        self,
        file_path: Optional[str] = None,
        top_module: str = "design",
        pdk: str = "sky130",
        fault_coverage: float = 0.0,
        scan_flop_count: int = 0,
        scan_chain_count: int = 1,
        pattern_count: int = 0,
        total_faults: int = 0,
        detected_faults: int = 0,
        undetected_faults: int = 0,
        untestable_faults: int = 0,
        macro_clamped_faults: int = 0,
        estimated_test_time_ms: float = 0.0,
        status: str = "UNKNOWN",
        raw_text: str = "",
    ):
        self.file_path = file_path
        self.top_module = top_module
        self.pdk = pdk
        self.fault_coverage = fault_coverage
        self.scan_flop_count = scan_flop_count
        self.scan_chain_count = scan_chain_count
        self.pattern_count = pattern_count
        self.total_faults = total_faults
        self.detected_faults = detected_faults
        self.undetected_faults = undetected_faults
        self.untestable_faults = untestable_faults
        self.macro_clamped_faults = macro_clamped_faults
        self.estimated_test_time_ms = estimated_test_time_ms
        self.status = status
        self.raw_text = raw_text

    @property
    def is_clean(self) -> bool:
        return self.status == "PASS" and self.fault_coverage >= 95.0

    @classmethod
    def load(cls, path_or_dir: str, design_name: Optional[str] = None) -> "DFTSignoffReport":
        json_cand = None
        rpt_cand = None
        if os.path.isdir(path_or_dir):
            j = os.path.join(path_or_dir, "dft_summary.json")
            r = os.path.join(path_or_dir, "dft_summary.rpt")
            if os.path.isfile(j): json_cand = j
            if os.path.isfile(r): rpt_cand = r
        elif os.path.isfile(path_or_dir):
            if path_or_dir.endswith(".json"): json_cand = path_or_dir
            else: rpt_cand = path_or_dir

        if json_cand and os.path.isfile(json_cand):
            import json
            with open(json_cand, "r") as f:
                d = json.load(f)
            return cls(
                file_path=json_cand,
                top_module=d.get("top_module", design_name or "design"),
                pdk=d.get("pdk", "sky130"),
                fault_coverage=d.get("fault_coverage", 0.0),
                scan_flop_count=d.get("scan_flop_count", 0),
                scan_chain_count=d.get("scan_chain_count", 1),
                pattern_count=d.get("pattern_count", 0),
                total_faults=d.get("total_faults", 0),
                detected_faults=d.get("detected_faults", 0),
                undetected_faults=d.get("undetected_faults", 0),
                untestable_faults=d.get("untestable_faults", 0),
                macro_clamped_faults=d.get("macro_clamped_faults", 0),
                estimated_test_time_ms=d.get("estimated_test_time_ms", 0.0),
                status=d.get("status", "PASS"),
            )
        elif rpt_cand and os.path.isfile(rpt_cand):
            with open(rpt_cand, "r") as f:
                content = f.read()
            cov = 95.0
            m_c = re.search(r"FINAL FAULT COVERAGE\s*:\s*([\d\.]+)", content)
            if m_c: cov = float(m_c.group(1))
            return cls(
                file_path=rpt_cand,
                top_module=design_name or "design",
                fault_coverage=cov,
                status="PASS" if cov >= 95.0 else "WARN",
                raw_text=content,
            )

        return cls(top_module=design_name or "design")

    def __repr__(self) -> str:
        return f"<DFTSignoffReport coverage={self.fault_coverage}% scan_flops={self.scan_flop_count} patterns={self.pattern_count} status='{self.status}'>"


class GLSSignoffReport:
    """
    Gate-Level Simulation (GLS) signoff report parser.
    Parses gls_summary.json or gls.rpt generated after post-layout timing simulation.
    """

    def __init__(
        self,
        file_path: Optional[str] = None,
        top_module: str = "top",
        status: str = "UNKNOWN",
        duration_sec: float = 0.0,
        cycles_evaluated: int = 0,
        timing_violations_count: int = 0,
        timing_violations: Optional[List[str]] = None,
        sdf_file: Optional[str] = None,
        vcd_file: Optional[str] = None,
        raw_text: str = "",
    ):
        self.file_path = os.path.abspath(file_path) if file_path else None
        self.top_module = top_module
        self.status = status
        self.duration_sec = duration_sec
        self.cycles_evaluated = cycles_evaluated
        self.timing_violations_count = timing_violations_count
        self.timing_violations = timing_violations or []
        self.sdf_file = sdf_file
        self.vcd_file = vcd_file
        self.raw_text = raw_text

    @property
    def is_clean(self) -> bool:
        return self.status == "PASS" and self.timing_violations_count == 0

    @classmethod
    def load(cls, path_or_dir: str, design_name: Optional[str] = None) -> "GLSSignoffReport":
        json_cand = None
        rpt_cand = None
        if os.path.isdir(path_or_dir):
            j = os.path.join(path_or_dir, "gls_summary.json")
            r = os.path.join(path_or_dir, "gls.rpt")
            if os.path.isfile(j): json_cand = j
            if os.path.isfile(r): rpt_cand = r
        elif os.path.isfile(path_or_dir):
            if path_or_dir.endswith(".json"): json_cand = path_or_dir
            else: rpt_cand = path_or_dir

        if json_cand and os.path.isfile(json_cand):
            with open(json_cand, "r") as f:
                d = json.load(f)
            return cls(
                file_path=json_cand,
                top_module=d.get("top_module", design_name or "top"),
                status=d.get("status", "PASS"),
                duration_sec=d.get("duration_sec", 0.0),
                cycles_evaluated=d.get("cycles_evaluated", 0),
                timing_violations_count=d.get("timing_violations_count", 0),
                timing_violations=d.get("timing_violations", []),
                sdf_file=d.get("sdf_file"),
                vcd_file=d.get("vcd_file"),
            )
        elif rpt_cand and os.path.isfile(rpt_cand):
            with open(rpt_cand, "r") as f:
                content = f.read()
            is_pass = "PASSED" in content
            return cls(
                file_path=rpt_cand,
                top_module=design_name or "top",
                status="PASS" if is_pass else "FAIL",
                raw_text=content,
            )

        return cls(top_module=design_name or "top")

    def __repr__(self) -> str:
        return f"<GLSSignoffReport status='{self.status}' cycles={self.cycles_evaluated} violations={self.timing_violations_count}>"


class LVSSignoffReport:
    """
    Layout Versus Schematic (LVS) signoff report parser.
    Parses lvs_summary.json or lvs.rpt generated after Magic extraction and Netgen comparison.
    """

    def __init__(
        self,
        file_path: Optional[str] = None,
        top_module: str = "top",
        engine: str = "Netgen / Topological",
        status: str = "UNKNOWN",
        is_clean: bool = False,
        matched_devices: int = 0,
        unmatched_devices: int = 0,
        matched_nets: int = 0,
        unmatched_nets: int = 0,
        unmatched_pins: int = 0,
        mismatches: Optional[List[str]] = None,
        layout_spice: Optional[str] = None,
        schematic_spice: Optional[str] = None,
        duration_sec: float = 0.0,
        raw_text: str = "",
    ):
        self.file_path = os.path.abspath(file_path) if file_path else None
        self.top_module = top_module
        self.engine = engine
        self.status = status
        self.is_clean = is_clean
        self.matched_devices = matched_devices
        self.unmatched_devices = unmatched_devices
        self.matched_nets = matched_nets
        self.unmatched_nets = unmatched_nets
        self.unmatched_pins = unmatched_pins
        self.mismatches = mismatches or []
        self.layout_spice = layout_spice
        self.schematic_spice = schematic_spice
        self.duration_sec = duration_sec
        self.raw_text = raw_text

    @classmethod
    def load(cls, path_or_dir: str, design_name: Optional[str] = None) -> "LVSSignoffReport":
        json_cand = None
        rpt_cand = None
        if os.path.isdir(path_or_dir):
            j = os.path.join(path_or_dir, "lvs_summary.json")
            r = os.path.join(path_or_dir, "lvs.rpt")
            if os.path.isfile(j): json_cand = j
            if os.path.isfile(r): rpt_cand = r
        elif os.path.isfile(path_or_dir):
            if path_or_dir.endswith(".json"): json_cand = path_or_dir
            else: rpt_cand = path_or_dir

        if json_cand and os.path.isfile(json_cand):
            with open(json_cand, "r") as f:
                d = json.load(f)
            return cls(
                file_path=json_cand,
                top_module=d.get("top_module", design_name or "top"),
                engine=d.get("engine", "Netgen / Topological"),
                status=d.get("status", "PASS"),
                is_clean=d.get("is_clean", False),
                matched_devices=d.get("matched_devices", 0),
                unmatched_devices=d.get("unmatched_devices", 0),
                matched_nets=d.get("matched_nets", 0),
                unmatched_nets=d.get("unmatched_nets", 0),
                unmatched_pins=d.get("unmatched_pins", 0),
                mismatches=d.get("mismatches", []),
                layout_spice=d.get("layout_spice"),
                schematic_spice=d.get("schematic_spice"),
                duration_sec=d.get("duration_sec", 0.0),
            )
        elif rpt_cand and os.path.isfile(rpt_cand):
            with open(rpt_cand, "r") as f:
                content = f.read()
            clean = "CLEAN" in content or "match with no errors" in content
            return cls(
                file_path=rpt_cand,
                top_module=design_name or "top",
                status="PASS" if clean else "FAIL",
                is_clean=clean,
                raw_text=content,
            )

        return cls(top_module=design_name or "top")

    def __repr__(self) -> str:
        return f"<LVSSignoffReport status='{self.status}' is_clean={self.is_clean} matched_devs={self.matched_devices} matched_nets={self.matched_nets}>"


class TapeoutManifestReport:
    """
    Final foundry tapeout manifest report parser.
    Parses tapeout_manifest.json or tapeout.rpt verifying complete foundry checklist.
    """

    def __init__(
        self,
        file_path: Optional[str] = None,
        top_module: str = "top",
        pdk: str = "sky130",
        tapeout_gds: Optional[str] = None,
        tapeout_ready: bool = False,
        signoffs: Optional[Dict[str, Any]] = None,
        raw_text: str = "",
    ):
        self.file_path = os.path.abspath(file_path) if file_path else None
        self.top_module = top_module
        self.pdk = pdk
        self.tapeout_gds = tapeout_gds
        self.tapeout_ready = tapeout_ready
        self.signoffs = signoffs or {}
        self.raw_text = raw_text

    @property
    def drc_pass(self) -> bool:
        return self.signoffs.get("drc", {}).get("status") == "PASS"

    @property
    def lvs_pass(self) -> bool:
        return self.signoffs.get("lvs", {}).get("status") == "PASS"

    @property
    def dft_pass(self) -> bool:
        return self.signoffs.get("dft", {}).get("status") == "PASS"

    @property
    def timing_pass(self) -> bool:
        return self.signoffs.get("timing_pat", {}).get("status") == "PASS"

    @property
    def gls_pass(self) -> bool:
        return self.signoffs.get("gls", {}).get("status") == "PASS"

    @property
    def gds_path(self) -> Optional[str]:
        return self.tapeout_gds

    @classmethod
    def load(cls, path_or_dir: str, design_name: Optional[str] = None) -> "TapeoutManifestReport":
        json_cand = None
        rpt_cand = None
        if os.path.isdir(path_or_dir):
            j = os.path.join(path_or_dir, "tapeout_manifest.json")
            r = os.path.join(path_or_dir, "tapeout.rpt")
            if os.path.isfile(j): json_cand = j
            if os.path.isfile(r): rpt_cand = r
        elif os.path.isfile(path_or_dir):
            if path_or_dir.endswith(".json"): json_cand = path_or_dir
            else: rpt_cand = path_or_dir

        if json_cand and os.path.isfile(json_cand):
            with open(json_cand, "r") as f:
                d = json.load(f)
            return cls(
                file_path=json_cand,
                top_module=d.get("top_module", design_name or "top"),
                pdk=d.get("pdk", "sky130"),
                tapeout_gds=d.get("tapeout_gds"),
                tapeout_ready=d.get("tapeout_ready", False),
                signoffs=d.get("signoffs", {}),
            )
        elif rpt_cand and os.path.isfile(rpt_cand):
            with open(rpt_cand, "r") as f:
                content = f.read()
            ready = "100% READY" in content
            return cls(
                file_path=rpt_cand,
                top_module=design_name or "top",
                tapeout_ready=ready,
                raw_text=content,
            )

        return cls(top_module=design_name or "top")

    def __repr__(self) -> str:
        return f"<TapeoutManifestReport ready={self.tapeout_ready} gds='{self.tapeout_gds}' DRC={self.drc_pass} LVS={self.lvs_pass} DFT={self.dft_pass}>"


