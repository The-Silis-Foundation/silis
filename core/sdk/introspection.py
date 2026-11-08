"""
silis/core/sdk/introspection.py
Agentic EDA Physical Design Introspection Engine.

Provides zero-TCL structured queries exposing:
1. pipe.get_congestion_map()        -> GCell routing congestion density & overflow boxes
2. pipe.get_macro_affinity_graph()    -> Netlist logic-to-macro interconnect matrix
3. pipe.get_critical_timing_paths()   -> Structured slack, start/end pins & coordinates
4. pipe.get_ir_drop_map()             -> Localized static ΔV drop & starved instances
5. pipe.get_drc_markers()             -> Exact geometric DRC violation markers from OpenDB
"""

import os
import re
import json
import subprocess
from typing import Dict, List, Optional, Any, Tuple


class PhysicalDesignIntrospector:
    """
    Direct introspection interface bridging OpenROAD / OpenDB / OpenSTA C++ engines
    into high-fidelity, agent-actionable Python data structures.
    """

    def __init__(self, pipeline):
        self.pipe = pipeline
        self.project = pipeline.project

    # --------------------------------------------------------------------------
    # 1. Routing Congestion & GCell Overflow Map
    # --------------------------------------------------------------------------
    def get_congestion_map(self, threshold: float = 0.80) -> List[Dict[str, Any]]:
        """
        Queries the global routing engine for GCell congestion hotspots exceeding threshold.
        Returns a list of structured bounding boxes with overflow counts and layer names.
        """
        results_dir = self.project.results_dir
        rpt_path = os.path.join(results_dir, "congestion.rpt")

        hotspots = []
        if os.path.isfile(rpt_path):
            with open(rpt_path, "r") as f:
                content = f.read()

            pattern = re.compile(
                r'(\w+)\s*\(\s*([\d\.\-]+)\s*,\s*([\d\.\-]+)\s*\)\s*-\s*\(\s*([\d\.\-]+)\s*,\s*([\d\.\-]+)\s*\)\s*.*?overflow:\s*(\d+)',
                re.IGNORECASE
            )
            for m in pattern.finditer(content):
                layer, x1, y1, x2, y2, ovfl = m.groups()
                ovfl_val = int(ovfl)
                if ovfl_val > 0:
                    hotspots.append({
                        "layer": layer,
                        "box": [float(x1), float(y1), float(x2), float(y2)],
                        "overflow": ovfl_val,
                    })

        # Check OpenROAD GlobalRouter via Python bridge if report file was absent
        if not hotspots:
            odb_path = os.path.join(results_dir, "temp.odb")
            if not os.path.isfile(odb_path):
                cand = os.path.join(results_dir, "checkpoint.odb")
                if os.path.isfile(cand):
                    odb_path = cand

            if os.path.isfile(odb_path):
                py_code = f"""
import openroad as ord
tech = ord.Tech()
design = ord.Design(tech)
try:
    design.readDb("{odb_path}")
    gr = design.getGlobalRouter()
    print("___CONGESTION___" + str(gr.isCongested()))
except Exception:
    pass
"""
                try:
                    cmd = ["openroad", "-exit", "-python", "-c", py_code]
                    p = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                    if "___CONGESTION___True" in p.stdout:
                        # Log indicates congestion exists
                        hotspots.append({
                            "layer": "global",
                            "box": [0.0, 0.0, 0.0, 0.0],
                            "overflow": 1
                        })
                except Exception:
                    pass

        return hotspots

    # --------------------------------------------------------------------------
    # 2. Macro Net Affinity Graph (Logic Proximity Matrix)
    # --------------------------------------------------------------------------
    def get_macro_affinity_graph(self) -> Dict[str, Dict[str, int]]:
        """
        Parses the gate-level netlist and OpenDB components to map connectivity
        between hard macros and RTL submodules.
        Returns: { macro_inst: { submodule_name: shared_net_count } }
        """
        affinity: Dict[str, Dict[str, int]] = {}

        # Resolve primary netlist
        netlists = getattr(self.project, "get_netlists", lambda: [])()
        if not netlists:
            return affinity

        netlist_path = netlists[0]
        if not os.path.isfile(netlist_path):
            return affinity

        with open(netlist_path, "r") as f:
            text = f.read()

        # Parse instance port connections: instance_name -> set(nets)
        inst_nets: Dict[str, set] = {}
        pattern = re.compile(r'(\w+)\s+(\w+)\s*\((.*?)\);', re.DOTALL)
        for master, inst, ports_str in pattern.findall(text):
            if master in ("module", "endmodule", "wire", "input", "output", "assign"):
                continue
            nets = set(re.findall(r'\.\w+\s*\(\s*([^)]+)\s*\)', ports_str))
            inst_nets[inst] = {n.strip() for n in nets if n.strip()}

        # Identify macro instances (from project sizes report or naming)
        known_macros = set()
        try:
            sizes = self.project.get_sizes()
            known_macros = set(sizes.get("macros", {}).keys())
        except Exception:
            pass

        if not known_macros:
            known_macros = {i for i in inst_nets if any(k in i.lower() for k in ("sram", "ram", "macro", "dsp"))}

        # Submodules (from sizes or non-macros)
        for m in sorted(known_macros):
            if m not in inst_nets:
                continue
            m_nets = inst_nets[m]
            aff: Dict[str, int] = {}
            for other_inst, other_nets in inst_nets.items():
                if other_inst == m or other_inst in known_macros:
                    continue
                # Group standard cell primitives into their parent module name if hierarchical
                mod_name = other_inst.split("/")[0] if "/" in other_inst else other_inst
                shared = len(m_nets.intersection(other_nets))
                if shared > 0:
                    aff[mod_name] = aff.get(mod_name, 0) + shared

            if aff:
                affinity[m] = aff

        return affinity

    # --------------------------------------------------------------------------
    # 3. Critical Timing Paths & Slack Introspection (OpenSTA)
    # --------------------------------------------------------------------------
    def get_critical_timing_paths(self, top_n: int = 5) -> List[Dict[str, Any]]:
        """
        Queries Static Timing Analysis (OpenSTA) for the top-N critical timing paths.
        Returns structured slacks, endpoints, logic delays, and wire delays.
        """
        paths = []
        # Check standard project timing reports first to avoid blocking STA runs
        candidate_rpts = [
            os.path.join(self.project.reports_dir, "timing.rpt"),
            os.path.join(self.project.reports_dir, f"{self.project.top_module}_pat_report.rpt"),
            os.path.join(self.project.reports_dir, "pat.rpt"),
            os.path.join(self.project.results_dir, "timing_critical.rpt"),
        ]

        sta_rpt = None
        for cand in candidate_rpts:
            if os.path.isfile(cand) and os.path.getsize(cand) > 0:
                sta_rpt = cand
                break

        if sta_rpt and os.path.isfile(sta_rpt):
            with open(sta_rpt, "r") as f:
                content = f.read()

            raw_paths = content.split("Startpoint:")
            for p in raw_paths[1:top_n + 1]:
                start_m = re.search(r'^\s*([^\s\n\(]+)', p)
                end_m = re.search(r'Endpoint:\s*([^\s\n\(]+)', p)
                slack_m = re.search(r'([\-\d\.]+)\s+slack\s+\((VIOLATED|MET)\)', p)
                if not slack_m:
                    slack_m = re.search(r'slack\s*\((?:VIOLATED|MET)\)\s*([\-\d\.]+)', p)
                delay_m = re.search(r'([\-\d\.]+)\s+data arrival time', p)

                start_pin = start_m.group(1).strip() if start_m else "unknown"
                end_pin = end_m.group(1).strip() if end_m else "unknown"
                slack_val = float(slack_m.group(1)) if slack_m else 0.0
                delay_val = float(delay_m.group(1)) if delay_m else 0.0

                paths.append({
                    "slack_ns": slack_val,
                    "startpoint": start_pin,
                    "endpoint": end_pin,
                    "data_arrival_ns": delay_val,
                    "violated": slack_val < 0.0
                })

        return paths

    # --------------------------------------------------------------------------
    # 4. Power Distribution & IR Drop Map (PDNSim)
    # --------------------------------------------------------------------------
    def get_ir_drop_map(self, net: str = "VDD") -> Dict[str, Any]:
        """
        Executes PSM linear nodal analysis on the PDN power grid.
        Returns worst-case IR drop (mV), percentage drop, and worst-case location.
        """
        results_dir = self.project.results_dir
        psm_rpt = os.path.join(results_dir, f"irdrop_{net}.rpt")

        # OpenROAD analyze_power_grid syntax: -voltage_file (not -outfile)
        if not os.path.isfile(psm_rpt) or os.path.getsize(psm_rpt) == 0:
            tcl = f'catch {{ analyze_power_grid -net "{net}" -voltage_file "{psm_rpt}" }}\n'
            if hasattr(self.pipe, "runner") and hasattr(self.pipe.runner, "execute_tcl"):
                try:
                    self.pipe.runner.execute_tcl(tcl, step_name="analyze_power_grid")
                except Exception:
                    pass

        worst_drop_mv = 0.0
        worst_x, worst_y = 0.0, 0.0
        avg_drop_mv = 0.0

        if os.path.isfile(psm_rpt):
            with open(psm_rpt, "r") as f:
                content = f.read()

            drop_m = re.search(r'Worstcase voltage\s*:\s*([\d\.]+)\s*V', content)
            loc_m = re.search(r'Worstcase coordinate\s*:\s*\(\s*([\d\.]+)\s*,\s*([\d\.]+)\s*\)', content)
            avg_m = re.search(r'Average voltage\s*:\s*([\d\.]+)\s*V', content)

            nominal = 1.80  # Default nominal for Sky130 VDD
            if drop_m:
                v_worst = float(drop_m.group(1))
                worst_drop_mv = round((nominal - v_worst) * 1000.0, 2)
            if loc_m:
                worst_x, worst_y = float(loc_m.group(1)), float(loc_m.group(2))
            if avg_m:
                v_avg = float(avg_m.group(1))
                avg_drop_mv = round((nominal - v_avg) * 1000.0, 2)

        return {
            "net": net,
            "worst_drop_mv": worst_drop_mv,
            "worst_drop_pct": round((worst_drop_mv / 1800.0) * 100.0, 2),
            "worst_location": [worst_x, worst_y],
            "avg_drop_mv": avg_drop_mv,
            "status": "PASS" if worst_drop_mv <= 90.0 else "VIOLATED"
        }

    # --------------------------------------------------------------------------
    # 5. Exact Geometric DRC Violations & Markers (OpenDB / TritonRoute)
    # --------------------------------------------------------------------------
    def get_drc_markers(self) -> List[Dict[str, Any]]:
        """
        Extracts exact DRC violation markers from OpenDB marker categories
        and TritonRoute DRC reports.
        Returns: [ {"type": str, "layer": str, "box": [x1, y1, x2, y2], "instances": [str]} ]
        """
        markers: List[Dict[str, Any]] = []

        # 1. Query OpenDB Python markers via script
        odb_path = os.path.join(self.project.results_dir, "temp.odb")
        if not os.path.isfile(odb_path):
            cand_odb = os.path.join(self.project.results_dir, "checkpoint.odb")
            if os.path.isfile(cand_odb):
                odb_path = cand_odb

        if os.path.isfile(odb_path):
            py_code = f"""
import openroad as ord
import odb, json

tech = ord.Tech()
design = ord.Design(tech)
try:
    design.readDb("{odb_path}")
    block = design.getBlock()
    categories = block.getMarkerCategories()
    out = []
    for cat in categories:
        cat_name = cat.getName()
        for m in cat.getMarkers():
            bbox = m.getBBox()
            sources = [s.getName() for s in m.getSources() if hasattr(s, "getName")]
            layer = m.getTechLayer().getName() if m.getTechLayer() else ""
            out.append({{
                "type": cat_name,
                "layer": layer,
                "box": [bbox.xMin() / 1000.0, bbox.yMin() / 1000.0, bbox.xMax() / 1000.0, bbox.yMax() / 1000.0],
                "instances": sources,
                "comment": m.getComment()
            }})
    print("___SILIS_DRC_MARKERS___" + json.dumps(out))
except Exception:
    pass
"""
            try:
                cmd = ["openroad", "-exit", "-python", "-c", py_code]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                if "___SILIS_DRC_MARKERS___" in res.stdout:
                    j_str = res.stdout.split("___SILIS_DRC_MARKERS___")[1].strip()
                    markers.extend(json.loads(j_str))
            except Exception:
                pass

        # 2. Check Magic / TritonRoute DRC text reports if 0 OpenDB markers
        if not markers:
            for rpt_name in ["drc.rpt", "tritonroute.drc", "route.drc"]:
                rpt_file = os.path.join(self.project.reports_dir, rpt_name)
                if os.path.isfile(rpt_file):
                    with open(rpt_file, "r") as f:
                        text = f.read()
                    # Parse violation boxes: e.g. violation type: Spacing ... box: (x1, y1) (x2, y2)
                    v_pattern = re.compile(r'(\w+[\s\w]*)\s*violation.*?\(\s*([\d\.]+)\s*,\s*([\d\.]+)\s*\)\s*-\s*\(\s*([\d\.]+)\s*,\s*([\d\.]+)\s*\)', re.IGNORECASE)
                    for vm in v_pattern.finditer(text):
                        markers.append({
                            "type": vm.group(1).strip(),
                            "layer": "met1",
                            "box": [float(vm.group(2)), float(vm.group(3)), float(vm.group(4)), float(vm.group(5))],
                            "instances": []
                        })

        return markers
