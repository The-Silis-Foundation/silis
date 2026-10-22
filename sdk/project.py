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

from cli_flow import find_project_file
from cli_project import run_cli_init, create_project_structure, resolve_pdk_name
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

        # Standard project layout directories
        self.source_dir = os.path.join(self.root_dir, "source")
        self.netlist_dir = os.path.join(self.root_dir, "netlist")
        self.reports_dir = os.path.join(self.root_dir, "reports")
        self.results_dir = os.path.join(self.root_dir, "results")

        # Resolve configured files (support relative to project root)
        self.rtl_files: List[str] = self._resolve_paths(self.config.get("rtl_files", []))
        self.sdc_files: List[str] = self._resolve_paths(self.config.get("sdc_files", []))
        self.tb_files: List[str] = self._resolve_paths(self.config.get("tb_files", []))

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
        """Discovers existing RTL source files from config and source/ directory."""
        existing = [p for p in self.rtl_files if os.path.isfile(p)]
        if not existing and os.path.isdir(self.source_dir):
            for pat in ("*.v", "*.sv", "*.vhd", "*.vhdl"):
                for f in glob.glob(os.path.join(self.source_dir, pat)):
                    bname = os.path.basename(f).lower()
                    if not any(x in bname for x in ["tb_", "_tb", "test_"]):
                        existing.append(f)
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
        if not existing and os.path.isdir(self.source_dir):
            existing = glob.glob(os.path.join(self.source_dir, "*.sdc"))
        return existing

    def get_tb_files(self) -> List[str]:
        """Discovers existing testbench files."""
        existing = [p for p in self.tb_files if os.path.isfile(p)]
        if not existing and os.path.isdir(self.source_dir):
            for pat in ("*.v", "*.sv"):
                for f in glob.glob(os.path.join(self.source_dir, pat)):
                    bname = os.path.basename(f).lower()
                    if any(x in bname for x in ["tb_", "_tb", "test_"]):
                        existing.append(f)
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
        if not self.macros:
            return macro_lefs, macro_libs

        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        search_dirs = [
            self.root_dir,
            self.source_dir,
            os.path.join(repo_root, "third-party", "pdks"),
        ]
        env_pdk = os.environ.get("PDK_ROOT")
        if env_pdk and env_pdk not in search_dirs:
            search_dirs.append(env_pdk)

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

    def get_dft_report(self) -> DFTSignoffReport:
        """Loads and returns the DFTSignoffReport for this project."""
        return DFTSignoffReport.load(self.reports_dir, design_name=self.top_module)

    def get_lvs_report(self) -> Any:
        """Loads and returns the LVSSignoffReport for this project."""
        from silis.sdk.report import LVSSignoffReport
        return LVSSignoffReport.load(self.reports_dir, design_name=self.top_module)

    def get_gls_report(self) -> Any:
        """Loads and returns the GLSSignoffReport for this project."""
        from silis.sdk.report import GLSSignoffReport
        return GLSSignoffReport.load(self.reports_dir, design_name=self.top_module)

    def get_tapeout_report(self) -> Any:
        """Loads and returns the TapeoutManifestReport for this project."""
        from silis.sdk.report import TapeoutManifestReport
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
        refresh: bool = False,
    ) -> float:
        """
        Calculates and returns cell utilization (0.0 to 1.0+) for a module or region.

        Supports two fluent calling styles:
          Style A: get_utilization("u_execution_core", area=[600, 1300, 1000, 1700])
          Style B: get_utilization(region_dict)  # extracts 'module' and 'box'

        Area can be a float (um^2), (w, h) tuple, or [x1, y1, x2, y2] bounding box.
        """
        # Parse Style B (region dictionary)
        if isinstance(module_or_region, dict):
            r = module_or_region
            mod_name = r.get("module") or r.get("module_name") or r.get("name") or "core"
            if area is None:
                area = r.get("box") or r.get("rect")
                if area is None and "w" in r and "h" in r:
                    area = (r["w"], r["h"])
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

        cell_area = self.get_module_area(mod_name, refresh=refresh)
        return cell_area / num_area

    enquire_utilization = get_utilization

    def get_required_area(
        self,
        module: str = "core",
        target_density: float = 0.40,
        refresh: bool = False,
    ) -> float:
        """
        Returns the required physical area in um^2 to achieve target_density (0.0 to 1.0)
        for the given module or core.
        """
        if target_density <= 0 or target_density > 1.0:
            raise ValueError(f"target_density must be in range (0.0, 1.0], got {target_density}")
        cell_area = self.get_module_area(module, refresh=refresh)
        return cell_area / target_density

    def suggest_box(
        self,
        module: str = "core",
        origin: Tuple[float, float] = (0.0, 0.0),
        target_density: float = 0.40,
        aspect_ratio: float = 1.0,
        grid_snap: float = 0.005,
        refresh: bool = False,
    ) -> List[float]:
        """
        Calculates and returns an optimal bounding box [x1, y1, x2, y2] starting at origin
        to achieve target_density with the given aspect_ratio (width / height).
        Coordinates are snapped to PDK manufacturing grid.
        """
        import math
        try:
            req_area = self.get_required_area(module, target_density=target_density, refresh=refresh)
        except FileNotFoundError:
            req_area = 100.0

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
        """Registers a hard macro in the project, optionally copying LEF, LIB, and GDS into source/."""
        if macro_name not in self.macros:
            self.macros.append(macro_name)
        if lef and os.path.isfile(lef):
            dest_lef = os.path.join(self.source_dir, os.path.basename(lef))
            if os.path.abspath(lef) != os.path.abspath(dest_lef):
                shutil.copy2(lef, dest_lef)
        if lib and os.path.isfile(lib):
            dest_lib = os.path.join(self.source_dir, os.path.basename(lib))
            if os.path.abspath(lib) != os.path.abspath(dest_lib):
                shutil.copy2(lib, dest_lib)
        if gds and os.path.isfile(gds):
            dest_gds = os.path.join(self.source_dir, os.path.basename(gds))
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

        with open(target_file, "w") as f:
            json.dump(self.config, f, indent=4)
        return target_file

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
