"""
silis/sdk/sc_bridge.py
SCINT: SiliconCompiler ↔ Silis Integration Bridge.

Phases implemented here:
    Phase 0: SilisSCPDKAdapter (auto PDK resolution)
    Phase 1: from_sc() / to_sc() (bi-directional translator)
    Phase 1: SilisDirectoryAdapter (filesystem convention bridge)
"""

import os
import sys
import shutil
import logging
import json
from typing import Optional, Dict, Any, List

log = logging.getLogger("silis.sc_bridge")

# Mapping: SiliconCompiler canonical names -> Silis SSAForge PDK names
_SC_TO_SILIS_PDK = {
    "skywater130": "sky130",
    "sky130": "sky130",
    "ihp130": "ihp130",
    "gf180": "gf180",
    "gf180mcu": "gf180",
    "asap7": "asap7",
    "freepdk45": "freepdk45",
}


def _get_silis_pdk_root() -> str:
    """Absolute path to silis/third-party/pdks/"""
    return os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "third-party", "pdks")
    )


class SilisSCPDKAdapter:
    """
    Bridges SiliconCompiler's PDK schema to Silis's SSAForge / Volare PDK store.
    """

    def __init__(self, pdk_name: str):
        self.sc_pdk_name = pdk_name
        self.silis_pdk_name = _SC_TO_SILIS_PDK.get(pdk_name.lower(), pdk_name)
        self.pdk_root = os.path.join(_get_silis_pdk_root(), self._resolve_pdk_dir())
        self._config: Dict[str, Any] = {}
        self._load_from_ssaforge()

    def _resolve_pdk_dir(self) -> str:
        name_map = {
            "sky130": "sky130A",
            "gf180": "gf180mcuD",
            "ihp130": "ihp130_sg13g2",
            "asap7": "asap7",
            "freepdk45": "FreePDK45",
        }
        return name_map.get(self.silis_pdk_name, self.silis_pdk_name)

    def _load_from_ssaforge(self):
        try:
            from pdkmanagers.pdk.manager import PDKManager
            mgr = PDKManager()
            matched = None
            for c in mgr.configs:
                cname = c.get("name", "").lower()
                if self.silis_pdk_name in cname and c.get("tlef") and c.get("lib"):
                    matched = c
                    break
            if not matched:
                for c in mgr.configs:
                    cname = c.get("name", "").lower()
                    if self.silis_pdk_name in cname:
                        matched = c
                        break
            if matched:
                self._config = dict(matched)
                return
        except Exception as e:
            log.warning(f"SilisSCPDKAdapter: PDKManager lookup failed: {e}")

        # Direct filesystem fallback
        pdk_dir = self.pdk_root
        if os.path.isdir(pdk_dir):
            import glob
            tlef = glob.glob(os.path.join(pdk_dir, "**", "*.tlef"), recursive=True)
            lef = glob.glob(os.path.join(pdk_dir, "**", "*.lef"), recursive=True)
            lib = glob.glob(os.path.join(pdk_dir, "**", "*.lib"), recursive=True)
            self._config = {
                "name": self.silis_pdk_name,
                "tlef": tlef[0] if tlef else "",
                "lef": lef[0] if lef else "",
                "lib": lib[0] if lib else "",
            }

    def inject_into_sc_chip(self, chip) -> None:
        """Injects resolved PDK file paths into an SC chip instance."""
        if not self._config:
            return

        tlef = self._config.get("tlef")
        lib = self._config.get("lib")
        pdk_name = self.sc_pdk_name

        try:
            if tlef and os.path.exists(tlef):
                chip.set("pdk", pdk_name, "aprtech", "openroad", "*", "*", "lef", tlef)
            if lib and os.path.exists(lib):
                chip.set("library", "*", "nldm", "*", "lib", lib)
        except Exception as e:
            log.warning(f"SilisSCPDKAdapter.inject_into_sc_chip: {e}")

    @property
    def available(self) -> bool:
        return bool(self._config.get("tlef") and self._config.get("lib"))

    def to_silis_config(self) -> Dict[str, Any]:
        return dict(self._config)


def _require_sc():
    try:
        import siliconcompiler # noqa
    except ImportError:
        raise ImportError(
            "SiliconCompiler is not available. Ensure silis/third-party/siliconcompiler/ exists."
        )


class SilisDirectoryAdapter:
    """
    Synchronizes checkpoint DEF, GDS, and report artifacts between
    SC's nested step directory tree and Silis's unified results/ directory.
    """

    def __init__(self, chip, silis_project_root: str):
        self.chip = chip
        self.project_root = os.path.abspath(silis_project_root)
        self.results_dir = os.path.join(self.project_root, "results")
        self.netlist_dir = os.path.join(self.project_root, "netlist")
        self.reports_dir = os.path.join(self.project_root, "reports")
        os.makedirs(self.results_dir, exist_ok=True)
        os.makedirs(self.netlist_dir, exist_ok=True)
        os.makedirs(self.reports_dir, exist_ok=True)

    def locate_latest_sc_def(self) -> Optional[str]:
        """
        Traverses SC's jobdir to locate the latest DEF checkpoint.
        Checks steps in reverse chronological flow order.
        """
        try:
            from siliconcompiler.utils.paths import workdir
        except Exception:
            return None

        priority_steps = [
            "detailedroute", "route", "globalroute",
            "cts", "detailedplace", "place",
            "globalplace", "floorplan", "init_floorplan"
        ]
        design = getattr(self.chip, "name", None) or getattr(self.chip, "design", "top")
        for step in priority_steps:
            try:
                wdir = workdir(self.chip, step=step, index="0")
                cand = os.path.join(wdir, "outputs", f"{design}.def")
                if os.path.isfile(cand):
                    return cand
            except Exception:
                continue
        return None

    def locate_latest_sc_netlist(self) -> Optional[str]:
        """Traverses SC's jobdir to locate the latest synthesized gate netlist."""
        try:
            from siliconcompiler.utils.paths import workdir
        except Exception:
            return None
        priority_steps = ["syn", "synthesis", "syn_asic"]
        design = getattr(self.chip, "name", None) or getattr(self.chip, "design", "top")
        for step in priority_steps:
            try:
                wdir = workdir(self.chip, step=step, index="0")
                for cand_name in [f"{design}.vg", f"{design}.v", f"{design}_netlist.v"]:
                    cand = os.path.join(wdir, "outputs", cand_name)
                    if os.path.isfile(cand):
                        return cand
            except Exception:
                continue
        return None

    def sync_sc_to_silis(self) -> Optional[str]:
        """
        Finds the latest DEF and netlist from SC and links/copies them into
        the Silis project results/ and netlist/ directories.
        """
        design = getattr(self.chip, "name", None) or getattr(self.chip, "design", "top")
        sc_net = self.locate_latest_sc_netlist()
        if sc_net:
            dest_net = os.path.join(self.netlist_dir, f"{design}_netlist.v")
            try:
                shutil.copyfile(sc_net, dest_net)
            except Exception:
                pass

        sc_def = self.locate_latest_sc_def()
        if not sc_def:
            return None
        target_def = os.path.join(self.results_dir, "temp.def")
        if os.path.exists(target_def) or os.path.islink(target_def):
            try:
                os.remove(target_def)
            except Exception:
                pass
        try:
            os.symlink(sc_def, target_def)
        except OSError:
            shutil.copyfile(sc_def, target_def)
        return target_def

    def sync_silis_to_sc(self, target_step: str = "detailedplace") -> Optional[str]:
        """
        Copies <silis_project>/results/temp.def into SC's previous step output directory.
        """
        try:
            from siliconcompiler.utils.paths import workdir
        except Exception:
            return None

        source_def = os.path.join(self.results_dir, "temp.def")
        if not os.path.isfile(source_def):
            return None

        design = getattr(self.chip, "name", None) or getattr(self.chip, "design", "top")
        try:
            pred_wdir = workdir(self.chip, step="floorplan", index="0")
            out_dir = os.path.join(pred_wdir, "outputs")
            os.makedirs(out_dir, exist_ok=True)
            dest_def = os.path.join(out_dir, f"{design}.def")
            shutil.copyfile(source_def, dest_def)
            return dest_def
        except Exception as e:
            log.warning(f"SilisDirectoryAdapter.sync_silis_to_sc failed: {e}")
            return None


def from_sc(chip, work_dir: Optional[str] = None):
    """
    Translates a SiliconCompiler Project or ASIC object into an initialized Silis Pipeline.
    """
    _require_sc()
    from sdk.pipeline import Pipeline
    from sdk.project import Project
    from sdk.sdc import SDCBuilder

    design = getattr(chip, "name", None) or getattr(chip, "design", None)
    if not design:
        raise ValueError("SiliconCompiler chip must have a top design name set.")

    # 1. PDK Resolution
    sc_pdk = ""
    try:
        sc_pdk = chip.get("option", "pdk")
    except Exception:
        pass
    pdk_adapter = SilisSCPDKAdapter(sc_pdk or "sky130")
    silis_pdk = pdk_adapter.silis_pdk_name

    # 2. Work directory setup
    if not work_dir:
        try:
            from siliconcompiler.utils.paths import jobdir
            work_dir = os.path.join(jobdir(chip), "silis_handoff")
        except Exception:
            work_dir = os.path.abspath(f"silis_handoff_{design}")
    os.makedirs(work_dir, exist_ok=True)

    # 3. Harvest RTL Sources
    rtl_files = []
    # Check modern SC 0.35+ Design filesets
    try:
        if hasattr(chip, "get_filesets"):
            for d_obj, fset in chip.get_filesets():
                if fset in ["rtl", "verilog", "v", "sv", "vhdl"]:
                    try:
                        files = d_obj.get_file(fileset=fset)
                        if files:
                            rtl_files.extend(files)
                    except Exception:
                        pass
    except Exception:
        pass

    # Fallback to legacy SC find_files schema
    if not rtl_files:
        for filetype in ["v", "verilog", "sv", "systemverilog", "vhdl", "vhd"]:
            try:
                files = chip.find_files("input", "rtl", filetype, step="*", index="*")
                if files:
                    rtl_files.extend(files)
            except Exception:
                pass

    # 4. Harvest Macros and Libraries
    macros = []
    try:
        if hasattr(chip, "get_filesets"):
            for d_obj, fset in chip.get_filesets():
                if fset in ["macro", "macros", "lef", "lib"]:
                    try:
                        m_files = d_obj.get_file(fileset=fset)
                        for mf in m_files:
                            m_name = os.path.splitext(os.path.basename(mf))[0]
                            if m_name not in macros:
                                macros.append(m_name)
                    except Exception:
                        pass
    except Exception:
        pass

    # Also detect macros from RTL stubs if any (e.g. sky130_sram_*)
    for rf in rtl_files:
        base_rf = os.path.basename(rf)
        if "sram" in base_rf.lower() or "macro" in base_rf.lower():
            m_cand = os.path.splitext(base_rf)[0].replace("_stub", "")
            if m_cand not in macros:
                macros.append(m_cand)

    # 5. Construct synthetic .silisproj
    proj_config = {
        "project_name": design,
        "top_module": design,
        "pdk": silis_pdk,
        "rtl_files": rtl_files,
        "macros": macros,
        "auto_sdc": False,
        "vhdl_std": "08",
    }
    proj_file = os.path.join(work_dir, "silis.silisproj")
    with open(proj_file, "w") as f:
        json.dump(proj_config, f, indent=2)

    # 6. Instantiate Project & Pipeline
    silis_proj = Project(proj_file)
    pipe = Pipeline(silis_proj)

    # 7. Translate Timing Constraints to in-memory SDCBuilder & write initial SDC
    pipe.sdc = SDCBuilder.from_sc_chip(chip)
    sdc_path = os.path.join(silis_proj.source_dir, f"{design}.sdc")
    if not os.path.isfile(sdc_path):
        if not pipe.sdc.clocks:
            pipe.sdc.create_clock(name="clk", period=10.0, pin="clk")
        pipe.sdc.write(sdc_path)

    # 8. Checkpoint DEF synchronization
    adapter = SilisDirectoryAdapter(chip, work_dir)
    target_def = adapter.sync_sc_to_silis()
    if target_def:
        log.info(f"[SCINT] Linked SC checkpoint DEF -> {target_def}")

    pipe._sc_chip = chip
    pipe._sc_adapter = adapter

    return pipe


def to_sc(pipe):
    """
    Translates a Silis Pipeline instance into an hydrated SiliconCompiler ASIC chip.
    """
    _require_sc()
    import siliconcompiler as sc

    proj = pipe.project
    chip = getattr(pipe, "_sc_chip", None)
    if chip is None:
        try:
            from siliconcompiler import Design, ASIC
            d = Design(proj.top_module)
            for rtl in proj.rtl_files:
                try:
                    d.add_file(rtl, fileset="rtl")
                except Exception:
                    pass
            chip = ASIC(d)
            if proj.rtl_files:
                try:
                    chip.add_fileset("rtl")
                except Exception:
                    pass
            try:
                sc_pdk_name = "skywater130" if "sky130" in proj.pdk.lower() else proj.pdk
                chip.set_pdk(sc_pdk_name)
            except Exception:
                pass
        except Exception:
            chip = sc.ASIC(proj.top_module)
            try:
                chip.set_pdk(proj.pdk)
            except Exception:
                pass

    # Export in-memory SDC if configured
    if hasattr(pipe, "sdc") and pipe.sdc and pipe.sdc.clocks:
        sdc_path = os.path.join(proj.results_dir, f"{proj.top_module}.sdc")
        pipe.sdc.write(sdc_path)
        try:
            # Modern Design fileset
            if hasattr(chip, "design") and hasattr(chip.design, "add_file"):
                chip.design.add_file(sdc_path, fileset="sdc")
                chip.add_fileset("sdc")
        except Exception:
            try:
                chip.input(sdc_path)
            except Exception:
                pass

    # Sync DEF back to SC
    adapter = getattr(pipe, "_sc_adapter", None) or SilisDirectoryAdapter(chip, proj.root_dir)
    adapter.sync_silis_to_sc(target_step="detailedplace")

    return chip
