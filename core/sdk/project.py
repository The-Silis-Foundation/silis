"""
silis/sdk/project.py
Silis ASIC Project Model and Discovery Engine.
Provides programmatic loading, PDK and macro discovery, design file locating,
and automated report binding for Silis projects.
"""

import os
import sys
import glob
import json
import shutil
from typing import Dict, List, Optional, Tuple, Any, Union

try:
    from cli.flow import find_project_file
    from cli.project import run_cli_init, create_project_structure, resolve_pdk_name
except ImportError:
    try:
        from cli_flow import find_project_file
        from cli_project import run_cli_init, create_project_structure, resolve_pdk_name
    except ImportError:
        from core.cli.flow import find_project_file
        from core.cli.project import run_cli_init, create_project_structure, resolve_pdk_name
import project_registry
from pdkmanagers.pdk.manager import PDKManager
from .report import SynthesisReport, SignoffReport, DRCReport, DFTSignoffReport


class Project:
    """
    Programmatic abstraction of a Silis ASIC Project (.silisproj).
    Handles configuration parsing, file discovery, macro binding, and report extraction.
    """

    def __init__(self, path_or_name: Optional[str] = None):
        # 1. Resolve Project File
        proj_file = find_project_file(path_or_name)
        if not proj_file:
            # Check within standard silis/projects folder
            repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if path_or_name:
                cand = os.path.join(repo_root, "projects", path_or_name, "silis.silisproj")
                if os.path.isfile(cand):
                    proj_file = os.path.abspath(cand)
                else:
                    cand_dir = os.path.join(repo_root, "projects", path_or_name)
                    if os.path.isdir(cand_dir):
                        for f in os.listdir(cand_dir):
                            if f.endswith(".silisproj"):
                                proj_file = os.path.abspath(os.path.join(cand_dir, f))
                                break

        if not proj_file or not os.path.isfile(proj_file):
            raise FileNotFoundError(
                f"Could not locate a valid Silis project from: '{path_or_name}'. "
                f"Ensure silis.silisproj exists or provide a registered project name/path."
            )

        self.proj_file = os.path.abspath(proj_file)
        self.root_dir = os.path.dirname(self.proj_file)

        # 2. Register project in global registry
        try:
            project_registry.register_project(self.proj_file)
        except Exception:
            pass

        # 3. Parse Configuration
        with open(self.proj_file, "r") as f:
            self.config: Dict[str, Any] = json.load(f)

        self.name: str = self.config.get("project_name", os.path.basename(self.root_dir))
        self.top_module: str = self.config.get("top_module", self.name)
        self.pdk: str = resolve_pdk_name(self.config.get("pdk", "sky130"))
        self.macros: List[str] = list(self.config.get("macros", []))
        self.auto_sdc: bool = bool(self.config.get("auto_sdc", False))
        self.vhdl_std: str = self.config.get("vhdl_std", "08")
        self.vhdl_work: str = self.config.get("vhdl_work", "neorv32" if "neorv32" in self.name.lower() or "gemm" in self.name.lower() else "work")

        # Standard project layout directories (rtl/, tb/, constr/ preferred, source/ legacy fallback)
        self.rtl_dir = os.path.join(self.root_dir, "rtl")
        self.tb_dir = os.path.join(self.root_dir, "tb")
        self.constr_dir = os.path.join(self.root_dir, "constr")
        self.power_dir = os.path.join(self.root_dir, "power")
        self.io_dir = os.path.join(self.root_dir, "io")
        self.source_dir = self.rtl_dir if os.path.isdir(self.rtl_dir) else os.path.join(self.root_dir, "source")
        self.netlist_dir = os.path.join(self.root_dir, "netlist")
        self.reports_dir = os.path.join(self.root_dir, "reports")
        self.results_dir = os.path.join(self.root_dir, "results")

        # Resolve configured files (support relative to project root)
        self.rtl_files: List[str] = self._resolve_paths(self.config.get("rtl_files", []))
        self.sdc_files: List[str] = self._resolve_paths(self.config.get("sdc_files", []))
        self.tb_files: List[str] = self._resolve_paths(self.config.get("tb_files", []))
        self.upf_file: Optional[str] = self._resolve_single_path(self.config.get("upf_file") or self.config.get("power_intent"))
        self.pin_order_file: Optional[str] = self._resolve_single_path(self.config.get("pin_order_file") or self.config.get("io_pin_cfg"))

        # Strongly-typed Silis physical & electrical subsystems (lazy-initialized)
        self._floorplan = None
        self._power_network = None
        self._timing_graph = None
        self._layout = None

    def get_floorplan(self):
        """Returns the strongly-typed Floorplan entity for physical placement."""
        if self._floorplan is None:
            from .floorplan import Floorplan
            self._floorplan = Floorplan(project=self)
        return self._floorplan

    def get_power_network(self):
        """Returns the strongly-typed IEEE 1801 UPF PowerNetwork coordinator."""
        if self._power_network is None:
            from .power import PowerNetwork
            self._power_network = PowerNetwork(project=self)
        return self._power_network

    @property
    def power_network(self):
        """Property returning the PowerNetwork coordinator for idiomatic project.power_network access."""
        return self.get_power_network()

    def get_timing_graph(self):
        """Returns the live in-memory TimingGraph for on-the-fly static timing slack inspection."""
        if self._timing_graph is None:
            from .timing import TimingGraph
            self._timing_graph = TimingGraph(project=self)
        return self._timing_graph

    def get_layout(self):
        """Returns the in-memory Layout engine for real-time physical change analysis."""
        if self._layout is None:
            from .layout import Layout
            self._layout = Layout(project=self)
        return self._layout

    @property
    def layout(self):
        """Property returning the Layout engine for idiomatic proj.layout access."""
        return self.get_layout()

    def view_layers(self, show: bool = True, detach: Optional[bool] = None, **kwargs):
        """Launches the C++ OpenROAD Native Layer Viewer for this project's layout."""
        return self.get_layout().view_layers(show=show, detach=detach, **kwargs)

    @property
    def db(self):
        """Returns the OpenDBBridge query engine for direct in-memory OpenROAD database introspection."""
        if not hasattr(self, "_db") or self._db is None:
            from .opendb_bridge import OpenDBBridge
            self._db = OpenDBBridge(self)
        return self._db

    def _resolve_single_path(self, path: Optional[str]) -> Optional[str]:
        if not path:
            return None
        if os.path.isabs(path):
            return path
        return os.path.abspath(os.path.join(self.root_dir, path))

    def _resolve_paths(self, paths: List[str]) -> List[str]:
        resolved = []
        for p in paths:
            if not p:
                continue
            if os.path.isabs(p):
                resolved.append(p)
            else:
                resolved.append(os.path.abspath(os.path.join(self.root_dir, p)))
        return resolved

    # --------------------------------------------------------------------------
    # Discovery Methods
    # --------------------------------------------------------------------------
    def get_rtl_files(self) -> List[str]:
        """Discovers existing RTL source files from config and rtl/ or source/ directory."""
        existing = [p for p in self.rtl_files if os.path.isfile(p)]
        if not existing:
            existing_set = set(existing)
            search_dirs = [d for d in [self.rtl_dir, self.source_dir] if os.path.isdir(d)]
            for sdir in search_dirs:
                for pat in ("*.v", "*.sv", "*.vhd", "*.vhdl"):
                    for f in glob.glob(os.path.join(sdir, pat)):
                        bname = os.path.basename(f).lower()
                        if not any(x in bname for x in ["tb_", "_tb", "test_"]):
                            if f not in existing_set:
                                existing.append(f)
                                existing_set.add(f)
        return existing

    def is_vhdl(self) -> bool:
        """Returns True if the project contains any VHDL source files."""
        return len(self.get_vhdl_files()) > 0

    def get_vhdl_files(self) -> List[str]:
        """Discovers existing VHDL source files (*.vhd, *.vhdl)."""
        return [f for f in self.get_rtl_files() if f.endswith(".vhd") or f.endswith(".vhdl")]

    def get_verilog_files(self) -> List[str]:
        """Discovers existing Verilog source files (*.v, *.sv)."""
        return [f for f in self.get_rtl_files() if not (f.endswith(".vhd") or f.endswith(".vhdl"))]

    def get_sdc_files(self) -> List[str]:
        """Discovers existing SDC timing constraint files."""
        existing = [p for p in self.sdc_files if os.path.isfile(p)]
        if not existing:
            existing_set = set(existing)
            search_dirs = [d for d in [self.constr_dir, self.rtl_dir, self.source_dir] if os.path.isdir(d)]
            for sdir in search_dirs:
                for f in glob.glob(os.path.join(sdir, "*.sdc")):
                    if f not in existing_set:
                        existing.append(f)
                        existing_set.add(f)
        return existing

    def get_upf_file(self) -> Optional[str]:
        """Discovers existing UPF power intent specification file."""
        if self.upf_file and os.path.isfile(self.upf_file):
            return self.upf_file
        candidates = [
            os.path.join(self.power_dir, "design.upf"),
            os.path.join(self.power_dir, f"{self.name}.upf"),
            os.path.join(self.constr_dir, "design.upf"),
            os.path.join(self.root_dir, "design.upf"),
            os.path.join(self.root_dir, f"{self.name}.upf"),
        ]
        if os.path.isdir(self.power_dir):
            candidates.extend(glob.glob(os.path.join(self.power_dir, "*.upf")))
        candidates.extend(glob.glob(os.path.join(self.root_dir, "*.upf")))
        for c in candidates:
            if os.path.isfile(c) and os.path.getsize(c) > 0:
                return c
        return None

    def get_power_domains(self) -> List[Any]:
        """Returns parsed power_domain objects from the project UPF file."""
        from backendflow.power.upf_engine import parse_upf, power_domain
        upf_f = self.get_upf_file()
        if upf_f:
            return parse_upf(upf_f)
        return [power_domain(name="PD_TOP", is_top=True, voltage=1.80, gated=False)]

    def get_pin_order_file(self) -> Optional[str]:
        """Discovers existing I/O pin / pad ordering configuration file."""
        if self.pin_order_file and os.path.isfile(self.pin_order_file):
            return self.pin_order_file
        candidates = [
            os.path.join(self.io_dir, "pin_order.cfg"),
            os.path.join(self.io_dir, "pad_list.io"),
            os.path.join(self.constr_dir, "pin_order.cfg"),
            os.path.join(self.root_dir, "pin_order.cfg")
        ]
        if os.path.isdir(self.io_dir):
            candidates.extend(glob.glob(os.path.join(self.io_dir, "*.cfg")) + glob.glob(os.path.join(self.io_dir, "*.io")))
        for c in candidates:
            if os.path.isfile(c) and os.path.getsize(c) > 0:
                return c
        return None

    def get_tb_files(self) -> List[str]:
        """Discovers existing testbench files."""
        existing = [p for p in self.tb_files if os.path.isfile(p)]
        if not existing:
            existing_set = set(existing)
            search_dirs = [d for d in [self.tb_dir, self.rtl_dir, self.source_dir] if os.path.isdir(d)]
            for sdir in search_dirs:
                for pat in ("*.v", "*.sv", "*.py", "*.vhd", "*.vhdl"):
                    for f in glob.glob(os.path.join(sdir, pat)):
                        bname = os.path.basename(f).lower()
                        if any(x in bname for x in ["tb_", "_tb", "test_"]) or sdir == self.tb_dir:
                            if f not in existing_set:
                                existing.append(f)
                                existing_set.add(f)
        return existing

    def get_netlists(self) -> List[str]:
        """Returns all synthesized Verilog netlists in netlist/ directory."""
        if not os.path.isdir(self.netlist_dir):
            return []
        netlists = glob.glob(os.path.join(self.netlist_dir, "*.v")) + glob.glob(
            os.path.join(self.netlist_dir, "*.sv")
        )
        return sorted(netlists)

    def get_netlist(self) -> Optional[str]:
        """Returns primary synthesized netlist path or None."""
        preferred = os.path.join(self.netlist_dir, f"{self.top_module}_netlist.v")
        if os.path.isfile(preferred):
            return preferred
        netlists = self.get_netlists()
        return netlists[0] if netlists else None

    def get_defs(self) -> List[str]:
        """Returns all layout DEF files in results/ and root."""
        defs = []
        if os.path.isdir(self.results_dir):
            defs.extend(glob.glob(os.path.join(self.results_dir, "*.def")))
        defs.extend(glob.glob(os.path.join(self.root_dir, "*.def")))
        return sorted(list(set(defs)))

    def get_def(self) -> Optional[str]:
        """Returns primary DEF file (temp.def or latest)."""
        temp_def = os.path.join(self.results_dir, "temp.def")
        if os.path.isfile(temp_def):
            return temp_def
        defs = self.get_defs()
        if defs:
            # Return most recently modified DEF
            return max(defs, key=os.path.getmtime)
        return None

    def get_gds_files(self) -> List[str]:
        """Returns all stream GDSII files in results/."""
        if not os.path.isdir(self.results_dir):
            return []
        gds = glob.glob(os.path.join(self.results_dir, "*.gds")) + glob.glob(
            os.path.join(self.results_dir, "*.GDS")
        )
        return sorted(list(set(gds)))

    def get_gds(self) -> Optional[str]:
        """Returns primary GDS file (design.gds or <top>.gds)."""
        cands = [
            os.path.join(self.results_dir, "design.gds"),
            os.path.join(self.results_dir, f"{self.top_module}.gds"),
        ]
        for c in cands:
            if os.path.isfile(c):
                return c
        gds_files = self.get_gds_files()
        return gds_files[0] if gds_files else None

    def get_odbs(self) -> List[str]:
        """Returns all OpenROAD database checkpoints (*.odb) in results/."""
        if not os.path.isdir(self.results_dir):
            return []
        return sorted(glob.glob(os.path.join(self.results_dir, "*.odb")))

    def get_vcd_files(self) -> List[str]:
        """Returns waveform VCD files in project."""
        vcds = glob.glob(os.path.join(self.root_dir, "*.vcd"))
        if os.path.isdir(self.results_dir):
            vcds.extend(glob.glob(os.path.join(self.results_dir, "*.vcd")))
        return sorted(list(set(vcds)))

    def get_macro_lefs_and_libs(self) -> Tuple[List[str], List[str]]:
        """Locates LEF and Liberty LIB files for all hard macros in the project."""
        macro_lefs: List[str] = []
        macro_libs: List[str] = []
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        search_dirs = [
            self.root_dir,
            self.source_dir,
            os.path.join(repo_root, "third-party", "pdks"),
        ]
        env_pdk = os.environ.get("PDK_ROOT")
        if env_pdk and env_pdk not in search_dirs:
            search_dirs.append(env_pdk)

        if self.macros:
            for m in self.macros:
                lef_found = False
                lib_found = False
                for d in search_dirs:
                    if not os.path.exists(d):
                        continue
                    if not lef_found:
                        for lef_cand in glob.glob(os.path.join(d, "**", f"{m}.lef"), recursive=True):
                            if os.path.isfile(lef_cand):
                                macro_lefs.append(lef_cand)
                                lef_found = True
                                break
                    if not lib_found:
                        for lib_cand in glob.glob(os.path.join(d, "**", f"{m}*.lib"), recursive=True):
                            if os.path.isfile(lib_cand):
                                macro_libs.append(lib_cand)
                                lib_found = True
                                break
                    if lef_found and lib_found:
                        break

        # Check if project uses UPF power switches, and ensure power_switch.lef is loaded
        pds = self.get_power_domains()
        has_switches = any(getattr(p, "gated", False) or getattr(p, "power_switch_master", None) is not None for p in pds)
        if has_switches:
            pdk_info = self.get_pdk_info()
            if pdk_info and "lef" in pdk_info:
                pdk_root = pdk_info["lef"].split("libs.ref")[0]
                sw_cand = os.path.join(pdk_root, "libs.ref", "sky130_power_switch", "lef", "power_switch.lef")
                if os.path.isfile(sw_cand) and sw_cand not in macro_lefs:
                    macro_lefs.append(sw_cand)

        return macro_lefs, macro_libs

    def get_pdk_info(self) -> Optional[Dict[str, Any]]:
        """Finds configured PDK files (tlef, lef, lib, tech, gds) matching target PDK."""
        pdk_mgr = PDKManager()
        pdk_name = self.pdk.lower()
        candidates = [
            p
            for p in pdk_mgr.configs
            if pdk_name in p["name"].lower() or pdk_name in p.get("family", "").lower()
        ]
        candidates_with_gds = [p for p in candidates if p.get("gds") and p.get("tech")]
        if candidates_with_gds:
            return candidates_with_gds[0]
        elif candidates:
            return candidates[0]
        elif pdk_mgr.configs:
            return pdk_mgr.configs[0]
        return None

    # --------------------------------------------------------------------------
    # Report Accessors
    # --------------------------------------------------------------------------
    def get_synthesis_report(self) -> SynthesisReport:
        """Loads and returns the SynthesisReport for this project."""
        return SynthesisReport.load(self.reports_dir, design_name=self.top_module)

    def get_signoff_report(self) -> SignoffReport:
        """Loads and returns the SignoffReport (PAT) for this project."""
        return SignoffReport.load(self.reports_dir, design_name=self.top_module)

    def get_drc_report(self) -> DRCReport:
        """Loads and returns the DRCReport for this project."""
        return DRCReport.load(self.reports_dir, results_dir=self.results_dir)

    def get_antenna_report(self) -> Any:
        """Loads and returns the AntennaSignoffReport for this project."""
        from sdk.report import AntennaSignoffReport
        return AntennaSignoffReport.load(self.reports_dir, design_name=self.top_module)

    def get_dft_report(self) -> DFTSignoffReport:
        """Loads and returns the DFTSignoffReport for this project."""
        return DFTSignoffReport.load(self.reports_dir, design_name=self.top_module)

    def get_lvs_report(self) -> Any:
        """Loads and returns the LVSSignoffReport for this project."""
        from sdk.report import LVSSignoffReport
        return LVSSignoffReport.load(self.reports_dir, design_name=self.top_module)

    def get_gls_report(self) -> Any:
        """Loads and returns the GLSSignoffReport for this project."""
        from sdk.report import GLSSignoffReport
        return GLSSignoffReport.load(self.reports_dir, design_name=self.top_module)

    def get_tapeout_report(self) -> Any:
        """Loads and returns the TapeoutManifestReport for this project."""
        from sdk.report import TapeoutManifestReport
        return TapeoutManifestReport.load(self.reports_dir, design_name=self.top_module)

    def get_reports(self) -> Dict[str, Any]:
        """
        Discovers and parses all project reports.
        Returns a dictionary containing SynthesisReport, SignoffReport, DRCReport,
        DFTSignoffReport, LVSSignoffReport, GLSSignoffReport, TapeoutManifestReport,
        and paths to all raw report files.
        """
        raw_files = []
        if os.path.isdir(self.reports_dir):
            raw_files = [
                os.path.join(self.reports_dir, f) for f in os.listdir(self.reports_dir)
            ]

        return {
            "synthesis": self.get_synthesis_report(),
            "signoff": self.get_signoff_report(),
            "drc": self.get_drc_report(),
            "dft": self.get_dft_report(),
            "lvs": self.get_lvs_report(),
            "gls": self.get_gls_report(),
            "tapeout": self.get_tapeout_report(),
            "report_files": sorted(raw_files),
        }

    # --------------------------------------------------------------------------
    # Floorplanning & Area Enquiry Engine
    # --------------------------------------------------------------------------
    def get_sizes(self, refresh: bool = False) -> Dict[str, Any]:
        """
        Discovers, parses, and caches the design sizes JSON ({top_module}_sizes.json).
        Contains total standard cell area, per-module areas, and macro instances.
        """
        if hasattr(self, "_cached_sizes") and self._cached_sizes is not None and not refresh:
            return self._cached_sizes

        sizes_path = os.path.join(self.reports_dir, f"{self.top_module}_sizes.json")
        if not os.path.isfile(sizes_path):
            # Fallback search for any *_sizes.json in reports/
            if os.path.isdir(self.reports_dir):
                cands = glob.glob(os.path.join(self.reports_dir, "*_sizes.json"))
                if cands:
                    sizes_path = cands[0]

        if not os.path.isfile(sizes_path):
            raise FileNotFoundError(
                f"Design sizes report not found at '{sizes_path}'. "
                f"Please run 'pipe.init()' or backend initialization first to extract cell sizes."
            )

        with open(sizes_path, "r") as f:
            self._cached_sizes = json.load(f)

        return self._cached_sizes

    def get_modules(self, refresh: bool = False) -> List[str]:
        """Returns a list of all hierarchical module instance names discovered in the netlist."""
        sizes = self.get_sizes(refresh=refresh)
        return sorted(list(sizes.get("modules", {}).keys()))

    def get_module_area(self, module: str = "core", refresh: bool = False) -> float:
        """
        Returns the standard cell area in um^2 for a specific module or the entire core.
        Passing 'core', 'top', 'all', or '' queries total_std_cell_area.
        """
        sizes = self.get_sizes(refresh=refresh)
        total_std_cell_area = float(sizes.get("total_std_cell_area", 0.0))

        mod_key = module.strip() if module else ""
        if mod_key.lower() in ("core", "top", "all", ""):
            return total_std_cell_area

        modules = sizes.get("modules", {})
        # 1. Exact match
        if mod_key in modules:
            return float(modules[mod_key])

        # 2. Normalized match (replace / with _)
        norm_key = mod_key.replace("/", "_")
        for k, v in modules.items():
            if k.replace("/", "_") == norm_key:
                return float(v)

        # 3. Suffix match (e.g. 'alu' matches 'core_complex/cpu/alu')
        matches = [k for k in modules if k == mod_key or k.endswith(f"/{mod_key}") or k.endswith(f"_{mod_key}")]
        if len(matches) == 1:
            return float(modules[matches[0]])
        elif len(matches) > 1:
            # If multiple, prefer exact basename match
            exact_base = [k for k in matches if k.split("/")[-1] == mod_key or k.split("_")[-1] == mod_key]
            if len(exact_base) == 1:
                return float(modules[exact_base[0]])
            raise KeyError(
                f"Ambiguous module name '{module}'. Matches: {matches}. Please specify full hierarchical path."
            )

        avail = ", ".join(sorted(modules.keys())[:10])
        extra = f" (and {len(modules)-10} more)" if len(modules) > 10 else ""
        raise KeyError(
            f"Module '{module}' not found in sizes report. Available modules: [{avail}{extra}]"
        )

    def get_utilization(
        self,
        module_or_region: Union[str, Dict[str, Any]],
        area: Optional[Union[float, int, Tuple[float, float], Tuple[float, float, float, float], List[float]]] = None,
        macros: Optional[List[Any]] = None,
        refresh: bool = False,
    ) -> float:
        """
        Calculates and returns cell utilization (0.0 to 1.0+) for a module or region.
        Accurately accounts for hard macros occupying space inside the region:
          effective_free_area = total_area - sum(macro_area)
          utilization = cell_area / effective_free_area
        """
        # Parse Style B (region dictionary)
        reg_dict = module_or_region if isinstance(module_or_region, dict) else {}
        if reg_dict:
            mod_name = reg_dict.get("module") or reg_dict.get("module_name") or reg_dict.get("name") or "core"
            if area is None:
                area = reg_dict.get("box") or reg_dict.get("rect")
                if area is None and "w" in reg_dict and "h" in reg_dict:
                    area = (reg_dict["w"], reg_dict["h"])
            if macros is None:
                macros = reg_dict.get("macros") or reg_dict.get("insts")
        else:
            mod_name = str(module_or_region)

        if area is None:
            raise ValueError(
                "Area must be specified either as 2nd argument or inside region dict under 'box' or 'rect'."
            )

        # Compute numerical area in um^2
        if isinstance(area, (int, float)):
            num_area = float(area)
        elif isinstance(area, (list, tuple)):
            if len(area) == 2:
                num_area = float(area[0]) * float(area[1])
            elif len(area) == 4:
                w = abs(float(area[2]) - float(area[0]))
                h = abs(float(area[3]) - float(area[1]))
                num_area = w * h
            else:
                raise ValueError(
                    f"Area sequence must have length 2 (w, h) or 4 (x1, y1, x2, y2), got {area}"
                )
        else:
            raise TypeError(f"Unsupported area type: {type(area)}")

        if num_area <= 0:
            raise ValueError(f"Calculated area must be strictly positive, got {num_area} um^2.")

        # Account for hard macros occupying the region cavity
        macro_area = 0.0
        if macros:
            macro_sizes = {}
            try:
                sizes = self.get_sizes(refresh=refresh)
                macro_sizes = sizes.get("macros", {})
            except Exception:
                pass
            for m in macros:
                if isinstance(m, dict):
                    mw = float(m.get("w") or m.get("width") or 0.0)
                    mh = float(m.get("h") or m.get("height") or 0.0)
                    if mw > 0 and mh > 0:
                        macro_area += (mw * mh)
                    else:
                        m_cell = m.get("cell") or m.get("master")
                        if m_cell and m_cell in macro_sizes:
                            macro_area += (macro_sizes[m_cell][0] * macro_sizes[m_cell][1])
                elif isinstance(m, str) and m in macro_sizes:
                    macro_area += (macro_sizes[m][0] * macro_sizes[m][1])

        eff_area = max(1.0, num_area - macro_area)
        cell_area = self.get_module_area(mod_name, refresh=refresh)
        return cell_area / eff_area

    enquire_utilization = get_utilization

    def get_required_area(
        self,
        module: str = "core",
        target_density: float = 0.40,
        macro_area: float = 0.0,
        refresh: bool = False,
    ) -> float:
        """
        Returns the required physical area in um^2 to achieve target_density (0.0 to 1.0)
        for the given module or core, taking internal macros into account:
          total_required_area = (cell_area / target_density) + macro_area
        """
        if target_density <= 0 or target_density > 1.0:
            raise ValueError(f"target_density must be in range (0.0, 1.0], got {target_density}")
        cell_area = self.get_module_area(module, refresh=refresh)
        return (cell_area / target_density) + float(macro_area)

    def suggest_box(
        self,
        module: str = "core",
        origin: Tuple[float, float] = (0.0, 0.0),
        target_density: float = 0.40,
        macro_area: float = 0.0,
        aspect_ratio: float = 1.0,
        grid_snap: float = 0.005,
        refresh: bool = False,
    ) -> List[float]:
        """
        Calculates and returns an optimal bounding box [x1, y1, x2, y2] starting at origin
        to achieve target_density with the given aspect_ratio (width / height), taking macros into account:
          total_area = (cell_area / target_density) + macro_area
        Coordinates are snapped to PDK manufacturing grid.
        """
        import math
        try:
            req_area = self.get_required_area(module, target_density=target_density, macro_area=macro_area, refresh=refresh)
        except FileNotFoundError:
            req_area = 100.0 + float(macro_area)

        if req_area <= 0:
            req_area = 100.0
        if aspect_ratio <= 0:
            raise ValueError(f"aspect_ratio must be positive, got {aspect_ratio}")

        h = math.sqrt(req_area / aspect_ratio)
        w = h * aspect_ratio

        def _snap(val: float) -> float:
            return round(round(val / grid_snap) * grid_snap, 3)

        x1 = _snap(origin[0])
        y1 = _snap(origin[1])
        x2 = _snap(x1 + w)
        y2 = _snap(y1 + h)
        return [x1, y1, x2, y2]

    # --------------------------------------------------------------------------
    # Mutation & Serialization
    # --------------------------------------------------------------------------
    def add_macro(
        self,
        macro_name: str,
        lef: Optional[str] = None,
        lib: Optional[str] = None,
        gds: Optional[str] = None,
    ) -> None:
        """Registers a hard macro in the project, optionally copying LEF, LIB, and GDS into rtl/ or source/."""
        if macro_name not in self.macros:
            self.macros.append(macro_name)
        target_dir = self.rtl_dir if os.path.isdir(self.rtl_dir) else self.source_dir
        if lef and os.path.isfile(lef):
            dest_lef = os.path.join(target_dir, os.path.basename(lef))
            if os.path.abspath(lef) != os.path.abspath(dest_lef):
                shutil.copy2(lef, dest_lef)
        if lib and os.path.isfile(lib):
            dest_lib = os.path.join(target_dir, os.path.basename(lib))
            if os.path.abspath(lib) != os.path.abspath(dest_lib):
                shutil.copy2(lib, dest_lib)
        if gds and os.path.isfile(gds):
            dest_gds = os.path.join(target_dir, os.path.basename(gds))
            if os.path.abspath(gds) != os.path.abspath(dest_gds):
                shutil.copy2(gds, dest_gds)
        self.save()

    def add_rtl(self, *paths: str) -> None:
        """Adds RTL source files to the project."""
        for p in paths:
            ap = os.path.abspath(p)
            if ap not in self.rtl_files:
                self.rtl_files.append(ap)
        self.save()

    def add_tb(self, *paths: str) -> None:
        """Adds testbench files to the project."""
        for p in paths:
            ap = os.path.abspath(p)
            if ap not in self.tb_files:
                self.tb_files.append(ap)
        self.save()

    def add_sdc(self, *paths: str) -> None:
        """Adds SDC constraint files to the project."""
        for p in paths:
            ap = os.path.abspath(p)
            if ap not in self.sdc_files:
                self.sdc_files.append(ap)
        self.save()

    def save(self, path: Optional[str] = None) -> str:
        """Saves project configuration to .silisproj file."""
        target_file = path or self.proj_file
        self.config["project_name"] = self.name
        self.config["top_module"] = self.top_module
        self.config["pdk"] = self.pdk
        self.config["macros"] = self.macros
        self.config["auto_sdc"] = self.auto_sdc
        self.config["rtl_files"] = self.rtl_files
        self.config["sdc_files"] = self.sdc_files
        self.config["tb_files"] = self.tb_files
        if hasattr(self, "upf_file") and self.upf_file:
            self.config["upf_file"] = self.upf_file
        if hasattr(self, "pin_order_file") and self.pin_order_file:
            self.config["pin_order_file"] = self.pin_order_file

        with open(target_file, "w") as f:
            json.dump(self.config, f, indent=4)
        return target_file

    def import_macro(
        self,
        macro_name: str,
        lef: Optional[str] = None,
        lib: Optional[str] = None,
        gds: Optional[str] = None,
        generate_stub: bool = True,
    ) -> str:
        """
        Imports a hard macro into the project.
        Copies LEF, LIB, and GDS assets, optionally extracts pin signatures to generate
        a black-box Verilog stub in rtl/<macro_name>_stub.v, and updates .silisproj.
        """
        self.add_macro(macro_name, lef=lef, lib=lib, gds=gds)
        target_dir = self.rtl_dir if os.path.isdir(self.rtl_dir) else self.source_dir
        os.makedirs(target_dir, exist_ok=True)
        stub_path = os.path.join(target_dir, f"{macro_name}_stub.v")

        if generate_stub and not os.path.isfile(stub_path):
            # Parse LEF if provided to build accurate Verilog stub port list
            ports_str = ""
            lef_cand = lef or os.path.join(target_dir, f"{macro_name}.lef")
            if lef_cand and os.path.isfile(lef_cand):
                try:
                    with open(lef_cand, "r", errors="ignore") as lf:
                        lcontent = lf.read()
                    # Find macro pin names and directions
                    pin_matches = re.findall(r'PIN\s+(\S+).*?DIRECTION\s+(\S+)\s*;.*?END\s+\1', lcontent, re.DOTALL)
                    if pin_matches:
                        port_lines = []
                        for pname, pdir in pin_matches:
                            pdir_v = pdir.lower()
                            if pdir_v in ("input", "output", "inout"):
                                port_lines.append(f"    {pdir_v} {pname}")
                        if port_lines:
                            ports_str = ",\n".join(port_lines)
                except Exception:
                    pass

            if not ports_str:
                ports_str = "    // Empty black-box port signature\n"

            content = (
                f"`timescale 1ns / 1ps\n"
                f"module {macro_name} (\n"
                f"{ports_str}\n"
                f");\n"
                f"    // Black-box stub auto-generated by Silis SDK\n"
                f"endmodule\n"
            )
            with open(stub_path, "w", encoding="utf-8") as sf:
                sf.write(content)

        if os.path.isfile(stub_path):
            if stub_path not in self.rtl_files:
                self.rtl_files.append(stub_path)
            self.save()

        return stub_path

    def import_upf(self, path: str, copy: bool = True) -> str:
        """
        Imports an IEEE 1801 UPF or CPF power intent file into the project.
        Copies the file to power/<filename>, sets upf_file in the project manifest, and saves.
        """
        if not os.path.isfile(path):
            raise FileNotFoundError(f"UPF file not found: {path}")

        os.makedirs(self.power_dir, exist_ok=True)
        dest = os.path.join(self.power_dir, os.path.basename(path)) if copy else os.path.abspath(path)
        if copy and os.path.abspath(path) != os.path.abspath(dest):
            shutil.copy2(path, dest)

        self.upf_file = dest
        self.config["upf_file"] = os.path.relpath(dest, self.root_dir)
        self.save()
        return dest

    def set_power_domain_supply_type(self, domain_name: str, supply_type: str) -> None:
        """
        Configures the physical power supply type for a power domain:
        - "Always-On" (Top-level core supply mesh)
        - "Internally Gated" (Switched from top VDD via PMU control and power switch headers)
        - "Dedicated External Pad" (Fed directly from dedicated periphery I/O pad)
        """
        session_file = os.path.join(self.root_dir, ".silis_fp_session.json")
        if os.path.isfile(session_file):
            try:
                with open(session_file, "r") as f:
                    sdata = json.load(f)
                updated = False
                for pd in sdata.get("power_domains", []):
                    if pd.get("domain_name") == domain_name:
                        pd["domain_type"] = supply_type
                        updated = True
                if updated:
                    with open(session_file, "w") as f:
                        json.dump(sdata, f, indent=2)
            except Exception:
                pass

    def import_io_config(self, path: str, copy: bool = True) -> str:
        """
        Imports an I/O pin ordering configuration into io/<filename>.
        Creates an automatic timestamped backup if an existing configuration is present.
        """
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Pin config file not found: {path}")

        os.makedirs(self.io_dir, exist_ok=True)
        dest = os.path.join(self.io_dir, os.path.basename(path)) if copy else os.path.abspath(path)
        if copy and os.path.isfile(dest) and os.path.abspath(path) != os.path.abspath(dest):
            import datetime
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            shutil.copy2(dest, f"{dest}.bak.{ts}")
            shutil.copy2(path, dest)
        elif copy and os.path.abspath(path) != os.path.abspath(dest):
            shutil.copy2(path, dest)

        self.pin_order_file = dest
        self.config["pin_order_file"] = os.path.relpath(dest, self.root_dir)
        self.save()
        return dest

    def to_dict(self) -> Dict[str, Any]:
        """Returns project configuration dictionary."""
        return dict(self.config)

    def summary(self) -> str:
        """Returns a high-level overview string of project status."""
        net = self.get_netlist()
        layout_def = self.get_def()
        gds = self.get_gds()
        reports = self.get_reports()

        return (
            f"===================================================================\n"
            f" SILIS PROJECT: {self.name} (Top: {self.top_module})\n"
            f" Target Silicon PDK: {self.pdk}\n"
            f" Workspace: {self.root_dir}\n"
            f"===================================================================\n"
            f" • RTL Sources:     {len(self.get_rtl_files())} files\n"
            f" • Hard Macros:     {len(self.macros)} ({', '.join(self.macros) if self.macros else 'None'})\n"
            f" • Netlist:         {os.path.basename(net) if net else 'Not generated'}\n"
            f" • Layout DEF:      {os.path.basename(layout_def) if layout_def else 'Not generated'}\n"
            f" • GDSII Stream:    {os.path.basename(gds) if gds else 'Not generated'}\n"
            f" • Synthesis Slack: {reports['synthesis'].wns} ns ({reports['synthesis'].status})\n"
            f" • Signoff Slack:   {reports['signoff'].wns} ns ({reports['signoff'].timing_status})\n"
            f" • DRC Violations:  {reports['drc'].violations_count} ({'CLEAN' if reports['drc'].is_clean else 'FAILED'})\n"
            f"==================================================================="
        )

    # --------------------------------------------------------------------------
    # Static Factories
    # --------------------------------------------------------------------------
    @classmethod
    def load(cls, path_or_name: Optional[str] = None) -> "Project":
        """Loads and returns a Project instance."""
        return cls(path_or_name)

    @classmethod
    def create(
        cls,
        name: str,
        top: Optional[str] = None,
        pdk: str = "sky130",
        loc: Optional[str] = None,
        rtl: Optional[List[str]] = None,
        tb: Optional[List[str]] = None,
        sdc: Optional[List[str]] = None,
        macros: Optional[List[str]] = None,
    ) -> "Project":
        """
        Creates a new Silis ASIC project workspace with standard directory layout
        and silis.silisproj metadata.
        """
        proj_file = run_cli_init(
            name=name,
            top=top,
            pdk=pdk,
            loc=loc,
            rtl=rtl,
            tb=tb,
            sdc=sdc,
            macros=macros,
        )
        return cls.load(proj_file)

    def __repr__(self) -> str:
        return (
            f"<Project name='{self.name}' top='{self.top_module}' "
            f"pdk='{self.pdk}' at '{self.root_dir}'>"
        )
