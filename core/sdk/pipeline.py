"""
silis/sdk/pipeline.py
Programmatic Headless Execution Pipeline for Silis ASIC Flow.
Wraps HeadlessASICRunner, SilisIDE, and BackendWidget with fine-grained Python controls,
explicit Qt event loop pumping, step sequencing, and signoff verification.
"""

import os
import sys
import time
from typing import Dict, List, Optional, Tuple, Any, Union

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QCoreApplication

# Ensure offscreen platform is set before any Qt widget instantiation if headless
if "QT_QPA_PLATFORM" not in os.environ:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"

try:
    from cli_flow import HeadlessASICRunner
except ImportError:
    from core.cli.flow import HeadlessASICRunner
from .project import Project
from .report import (
    SynthesisReport,
    SignoffReport,
    DRCReport,
    DFTSignoffReport,
    GLSSignoffReport,
    LVSSignoffReport,
    TapeoutManifestReport,
)


class Pipeline:
    """
    High-level programmatic ASIC pipeline for Silis.
    Provides methods for synthesis, PnR steps, GDS stream-out, and signoff.
    """

    FLOW_STEPS = [
        "synthesis",
        "init",
        "floorplan",
        "tapcells",
        "pdn",
        "iopins",
        "place",
        "cts",
        "route",
        "gds",
        "fill",
        "signoff",
        "dft",
        "lvs",
        "gls",
        "tapeout",
    ]

    STEP_ALIASES = {
        "synth": "synthesis",
        "fp": "floorplan",
        "io_pins": "iopins",
        "pins": "iopins",
        "clock": "cts",
        "routing": "route",
        "stream": "gds",
        "pat": "signoff",
        "sta": "signoff",
        "drc": "signoff",
        "atpg": "dft",
        "scan": "dft",
        "decap": "fill",
        "density": "fill",
        "sdf": "gls",
        "manifest": "tapeout",
    }

    def __init__(
        self,
        project_or_path: Optional[Union[Project, str]] = None,
        headless: bool = True,
    ):
        if headless:
            os.environ["QT_QPA_PLATFORM"] = "offscreen"

        # 1. Resolve Project
        if isinstance(project_or_path, Project):
            self.project = project_or_path
        else:
            self.project = Project.load(project_or_path)

        # 2. Ensure QApplication exists
        self.app = QApplication.instance()
        if not self.app:
            self.app = QApplication(
                ["silis", "-platform", "offscreen" if headless else "xcb"]
            )

        # 3. Instantiate Runner
        self.runner = HeadlessASICRunner(self.project.proj_file)
        self.ide = self.runner.ide
        self.backend = self.runner.backend

        # In-memory SDC builder (SCINT Phase 2)
        from .sdc import SDCBuilder
        self.sdc = SDCBuilder(design_name=self.project.top_module)

        # OpenROAD OpenDB Query & Inspection Engine
        from .opendb_bridge import OpenDBBridge
        self.db = OpenDBBridge(self)

    def process_events(self, iterations: int = 10, delay_ms: int = 5) -> None:
        """Pumps Qt event loop so QProcess, QThread, and timer events are processed."""
        if not self.app:
            return
        for _ in range(iterations):
            self.app.processEvents()
            if delay_ms > 0:
                time.sleep(delay_ms / 1000.0)

    # --------------------------------------------------------------------------
    # Flow Step Methods
    # --------------------------------------------------------------------------
    def synthesis(
        self,
        tcl: Optional[str] = None,
        corner: Optional[str] = "tt",
        mcmm: Optional[Dict[str, str]] = None,
        dft: bool = False,
        flatten: bool = False,
    ) -> SynthesisReport:
        """Runs frontend RTL synthesis, scan insertion (if dft=True), and technology mapping."""
        self.runner.run_synthesis(tcl_arg=tcl, dft=dft, flatten=flatten, corner=corner, mcmm=mcmm)
        self.process_events()
        return self.project.get_synthesis_report()

    # Alias
    synth = synthesis

    def init(self, tcl: Optional[str] = None) -> bool:
        """Initializes OpenROAD, links PDK LEF/LIBs, and reads the synthesized netlist."""
        res = self.runner.run_init(tcl_arg=tcl)
        self.process_events()
        if hasattr(self.project, "_cached_sizes"):
            self.project._cached_sizes = None
        return bool(res)

    def floorplan(
        self,
        tcl: Optional[str] = None,
        die_area: Optional[Tuple[float, float, float, float]] = None,
        core_margin: Union[float, Tuple[float, float, float, float]] = 20.0,
        macros: Optional[List[Dict[str, Any]]] = None,
        regions: Optional[List[Dict[str, Any]]] = None,
        blockages: Optional[List[Any]] = None,
        # SCINT Phase 3: Auto Macro Placer
        auto_macro_placer: Optional[str] = None,
        macro_halo: Tuple[float, float] = (10.0, 10.0),
        macro_channel: Tuple[float, float] = (15.0, 15.0),
        mpl_max_levels: Optional[int] = None,
        mpl_min_instances: Optional[int] = None,
        mpl_max_instances: Optional[int] = None,
        mpl_min_macros: Optional[int] = None,
        mpl_max_macros: Optional[int] = None,
        mpl_bus_planning: bool = False,
        mpl_target_dead_space: Optional[float] = None,
        mpl_wirelength_weight: Optional[float] = None,
        mpl_area_weight: Optional[float] = None,
    ) -> bool:
        """
        Configures chip die bounds, core utilization, macro placement, halos, blockages, and regions.
        Supports automated macro placement modes: 'hierarchical' (OpenROAD rtl_macro_placer),
        'openroad' (TritonMacroPlace), or 'peripheral' (Silis geometric solver).
        """
        if not tcl and (die_area or macros or regions or blockages or auto_macro_placer):
            from backendflow.floorplanner.floorplanner import generate_floorplan_tcl_from_data
            pdk_name = self.project.pdk if hasattr(self.project, "pdk") else "sky130"
            if isinstance(die_area, str):
                norm_die = [float(x) for x in die_area.replace('"', '').replace(',', ' ').split()]
            elif die_area:
                norm_die = [float(x) for x in die_area]
            else:
                norm_die = [0.0, 0.0, 2000.0, 2000.0]

            # Format blockages
            clean_blocks = []
            if blockages:
                for b in blockages:
                    if isinstance(b, dict):
                        clean_blocks.append(b)
                    elif isinstance(b, (list, tuple)) and len(b) == 4:
                        clean_blocks.append({"box": list(b), "soft": False})

            # Check if peripheral auto macro placer requested
            resolved_macros = macros or []
            if auto_macro_placer == "peripheral" and not resolved_macros:
                try:
                    from backendflow.floorplanner.floorplanner import compute_peripheral_macro_placement
                    # Detect discovered macros from project
                    all_macros = [{"inst_name": m} for m in getattr(self.project, "macros", [])]
                    die_w = norm_die[2] - norm_die[0]
                    die_h = norm_die[3] - norm_die[1]
                    _, _, placed = compute_peripheral_macro_placement(
                        all_macros, die_w=die_w, die_h=die_h, margins=core_margin
                    )
                    resolved_macros = placed
                except Exception as e:
                    pass

            tcl = generate_floorplan_tcl_from_data(
                die_area=norm_die,
                core_margin=core_margin,
                macros=resolved_macros,
                regions=regions or [],
                blockages=clean_blocks,
                pdk_name=pdk_name,
            )

            # Append automated macro placer commands if hierarchical or openroad
            if auto_macro_placer in ("hierarchical", "rtl_macro_placer", "openroad", "macro_placement"):
                tcl += "\n# === SCINT: OpenROAD Hierarchical RTL Macro Placer ===\n"
                tcl += "make_tracks\n"
                tcl += "set mpl_args [list \\\n"
                tcl += f"    -halo_width {macro_halo[0]} \\\n"
                tcl += f"    -halo_height {macro_halo[1]} \\\n"
                tcl += "    -report_directory reports/rtlmp \\\n"
                if mpl_max_levels is not None:
                    tcl += f"    -max_num_level {mpl_max_levels} \\\n"
                if mpl_min_instances is not None:
                    tcl += f"    -min_num_inst {mpl_min_instances} \\\n"
                if mpl_max_instances is not None:
                    tcl += f"    -max_num_inst {mpl_max_instances} \\\n"
                if mpl_min_macros is not None:
                    tcl += f"    -min_num_macro {mpl_min_macros} \\\n"
                if mpl_max_macros is not None:
                    tcl += f"    -max_num_macro {mpl_max_macros} \\\n"
                if mpl_target_dead_space is not None:
                    tcl += f"    -target_dead_space {mpl_target_dead_space} \\\n"
                if mpl_area_weight is not None:
                    tcl += f"    -area_weight {mpl_area_weight} \\\n"
                if mpl_wirelength_weight is not None:
                    tcl += f"    -wirelength_weight {mpl_wirelength_weight} \\\n"
                tcl += "]\n"
                if mpl_bus_planning:
                    tcl += "lappend mpl_args -bus_planning\n"
                tcl += "catch { rtl_macro_placer {*}$mpl_args }\n"

            # Ensure final DEF is exported
            def_path = os.path.join(self.project.results_dir, "temp.def").replace("\\", "/")
            tcl += f'\nwrite_def "{def_path}"\n'

        if not getattr(self.runner, "_design_loaded", False):
            self.init()

        res = self.runner.run_floorplan(
            tcl_arg=tcl,
            die_area=die_area,
            core_margin=core_margin,
            macros=macros,
            regions=regions,
            blockages=blockages,
        )
        self.process_events()
        return bool(res)

    def place_macro(
        self,
        inst: str,
        at: Tuple[float, float],
        orient: str = "R0",
        halo: Union[float, Tuple[float, float], Tuple[float, float, float, float]] = 10.0,
    ) -> Dict[str, Any]:
        """
        Creates a clean, validated macro placement dictionary.
        Accepts scalar halo (e.g. halo=10.0 expanded to 4 edges).
        """
        if isinstance(halo, (int, float)):
            norm_halo = (float(halo), float(halo), float(halo), float(halo))
        elif len(halo) == 2:
            norm_halo = (float(halo[0]), float(halo[1]), float(halo[0]), float(halo[1]))
        else:
            norm_halo = tuple(float(x) for x in halo)

        return {
            "inst": inst,
            "pos": (float(at[0]), float(at[1])),
            "orient": orient,
            "halo": norm_halo,
        }

    def add_fence(
        self,
        module: str,
        box: Optional[Union[Tuple[float, float, float, float], List[float]]] = None,
        origin: Optional[Tuple[float, float]] = None,
        density: float = 0.50,
        aspect_ratio: float = 1.0,
        halo: Optional[Union[float, Tuple[float, float, float, float]]] = None,
    ) -> Dict[str, Any]:
        """
        Creates a clean fence region dictionary.
        If box is not provided, automatically derives optimal bounding box from module cell area.
        """
        if box is None:
            ox, oy = origin if origin else (0.0, 0.0)
            box = self.suggest_box(
                module=module,
                origin=(ox, oy),
                target_density=density,
                aspect_ratio=aspect_ratio,
            )

        res = {
            "module": module,
            "box": list(box),
            "is_fence": True,
            "density": density,
        }
        if halo is not None:
            if isinstance(halo, (int, float)):
                res["halo"] = [float(halo)] * 4
            elif len(halo) == 4:
                res["halo"] = list(halo)
        return res

    def add_region(
        self,
        module: str,
        box: Optional[Union[Tuple[float, float, float, float], List[float]]] = None,
        origin: Optional[Tuple[float, float]] = None,
        density: float = 0.50,
        aspect_ratio: float = 1.0,
        halo: Optional[Union[float, Tuple[float, float, float, float]]] = None,
    ) -> Dict[str, Any]:
        """
        Creates an inclusive region dictionary.
        If box is not provided, automatically derives optimal bounding box from module cell area.
        """
        if box is None:
            ox, oy = origin if origin else (0.0, 0.0)
            box = self.suggest_box(
                module=module,
                origin=(ox, oy),
                target_density=density,
                aspect_ratio=aspect_ratio,
            )

        res = {
            "module": module,
            "box": list(box),
            "is_fence": False,
            "type": "inclusive",
            "density": density,
        }
        if halo is not None:
            if isinstance(halo, (int, float)):
                res["halo"] = [float(halo)] * 4
            elif len(halo) == 4:
                res["halo"] = list(halo)
        return res

    def auto_place_regions(
        self,
        die_area: Optional[Tuple[float, float, float, float]] = None,
        core_margin: Union[float, Tuple[float, float, float, float]] = 20.0,
        macros: Optional[List[Dict[str, Any]]] = None,
        regions: Optional[List[Dict[str, Any]]] = None,
        blockages: Optional[List[Any]] = None,
        target_density: float = 0.70,
        min_cutoff_pct: float = 15.0,
        force_place_all: bool = True,
        force_auto_shape: bool = True,
        as_fence: bool = False,
        common_halo: float = 10.0,
        seed: int = 42,
        w_r2m: float = 1.0,
        w_r2r: float = 1.0,
        w_r2io: float = 1.0,
        allow_non_rectangular: bool = True,
    ) -> Dict[str, Any]:
        """
        Executes hierarchical auto region placement using the Silis geometric & affinity solver.
        Automatically scales qualifying modules exceeding min_cutoff_pct to target_density,
        performs site row snapping, obstacle repulsion, and returns placed region definitions.
        """
        from backendflow.floorplanner.region_autoplacer import auto_place_regions as _solve_regions

        if isinstance(die_area, str):
            norm_die = [float(x) for x in die_area.replace('"', '').replace(',', ' ').split()]
        elif die_area:
            norm_die = [float(x) for x in die_area]
        else:
            norm_die = [0.0, 0.0, 2000.0, 2000.0]

        if isinstance(core_margin, (int, float)):
            c_margin = [float(core_margin)] * 4
        elif len(core_margin) == 4:
            c_margin = list(core_margin)
        else:
            c_margin = [20.0, 20.0, 20.0, 20.0]

        core_x1 = norm_die[0] + c_margin[0]
        core_y1 = norm_die[1] + c_margin[2]
        core_x2 = norm_die[2] - c_margin[1]
        core_y2 = norm_die[3] - c_margin[3]

        sizes_data = self.get_sizes()

        # Netlist path detection
        proj_root = getattr(self.project, "root_dir", getattr(self.project, "project_dir", ""))
        base = getattr(self.project, "top_module", "top")
        netlist_path = os.path.join(proj_root, "netlist", f"{base}_netlist.v")
        if not os.path.isfile(netlist_path):
            netlist_path = os.path.join(proj_root, "source", f"{base}.v")

        return _solve_regions(
            core_rect=(core_x1, core_y1, core_x2, core_y2),
            die_rect=norm_die,
            macros=macros or [],
            regions=regions or [],
            blockages=blockages or [],
            netlist_path=netlist_path if os.path.isfile(netlist_path) else None,
            target_density=target_density,
            min_cutoff_pct=min_cutoff_pct,
            force_place_all=force_place_all,
            force_auto_shape=force_auto_shape,
            as_fence=as_fence,
            common_halo=common_halo,
            sizes_data=sizes_data,
            seed=seed,
            w_r2m=w_r2m,
            w_r2r=w_r2r,
            w_r2io=w_r2io,
            allow_non_rectangular=allow_non_rectangular,
        )

    def auto_shape_regions(
        self,
        module_names: Optional[List[str]] = None,
        target_density: float = 0.70,
        min_cutoff_pct: float = 3.0,
        core_margin: Union[float, Tuple[float, float, float, float]] = 15.0,
        as_fence: bool = False,
    ) -> Dict[str, Any]:
        """
        Convenience method to auto-shape and auto-place inclusive floorplanning regions.
        If module_names is provided, explicitly shapes those modules at target_density.
        Applies a default contribution cutoff of 3% for automatic subtree qualifying.
        """
        regions = []
        if module_names:
            for m in module_names:
                regions.append({"module": m, "density": target_density, "is_fence": as_fence})

        # Query current die area if already initialized
        die = self.db.die_area
        if die == (0.0, 0.0, 0.0, 0.0):
            die = (0.0, 0.0, 2000.0, 2000.0)

        res = self.auto_place_regions(
            die_area=die,
            core_margin=core_margin,
            regions=regions,
            target_density=target_density,
            min_cutoff_pct=min_cutoff_pct,
            force_place_all=True,
            force_auto_shape=True,
            as_fence=as_fence,
        )

        # Apply placed regions to OpenROAD floorplan
        placed_list = res.get("regions", [])
        if placed_list:
            tcl_lines = []
            for r in placed_list:
                m_name = r.get("module")
                box = r.get("box", [0, 0, 0, 0])
                if m_name and box:
                    tcl_lines.append(f'catch {{ create_region -name "reg_{m_name}" -region {{{box[0]} {box[1]} {box[2]} {box[3]}}} }}')
                    tcl_lines.append(f'catch {{ assign_region -name "reg_{m_name}" [get_cells "{m_name}"] }}')
            if tcl_lines:
                def_path = os.path.join(self.project.results_dir, "temp.def").replace("\\", "/")
                tcl_lines.append(f'write_def "{def_path}"')
                self.runner.execute_tcl("\n".join(tcl_lines) + "\n", "auto_shape_regions")
                self.process_events()

        return res

    def add_blockage(
        self,
        box: Union[Tuple[float, float, float, float], List[float]],
        soft: bool = True,
    ) -> Dict[str, Any]:
        """Creates a placement/routing blockage dictionary."""
        return {"box": list(box), "soft": soft}

    def tapcells(
        self,
        tcl: Optional[str] = None,
        distance: int = 14,
        endcap_cpp: int = 1,
        tapcell: Optional[str] = None,
        endcap: Optional[str] = None,
    ) -> bool:
        """Inserts welltap and endcap cells according to PDK DRC spacing rules."""
        if not tcl and (distance != 14 or endcap_cpp != 1 or tapcell or endcap):
            def_path = os.path.join(self.project.results_dir, "temp.def").replace("\\", "/")
            tap_str = f"-tapcell {tapcell} " if tapcell else ""
            end_str = f"-endcap {endcap} " if endcap else ""
            tcl = f"tapcell -endcap_cpp {endcap_cpp} -distance {distance} {tap_str}{end_str}\nwrite_def \"{def_path}\"\n"
        res = self.runner.run_step("tapcells", tcl_arg=tcl)
        self.process_events()
        return bool(res)

    def pdn(self, tcl: Optional[str] = None) -> bool:
        """Synthesizes VDD and VSS power grid straps and rails."""
        res = self.runner.run_step("pdn", tcl_arg=tcl)
        self.process_events()
        return bool(res)

    def iopins(
        self,
        tcl: Optional[str] = None,
        hor_layers: str = "met3",
        ver_layers: str = "met4",
        corner_avoidance: float = 5.0,
        min_distance: float = 1.0,
        pin_constraints: Optional[List[Dict[str, Any]]] = None,
        random: bool = False,
        exclude_left: bool = False,
        exclude_right: bool = False,
        exclude_top: bool = False,
        exclude_bottom: bool = False,
    ) -> bool:
        """Places IO pins along peripheral die tracks with grid alignment, constraints, and exclusion flags."""
        if not tcl:
            def_path = os.path.join(self.project.results_dir, "temp.def").replace("\\", "/")
            lines = [
                "set tech [::ord::get_db_tech]",
                f'if {{[$tech findLayer "{hor_layers}"] eq "NULL"}} {{ set io_hor "Metal3"; set io_ver "Metal4" }} else {{ set io_hor "{hor_layers}"; set io_ver "{ver_layers}" }}',
            ]
            if pin_constraints:
                for pc in pin_constraints:
                    pins = pc.get("pins") or pc.get("names") or []
                    pin_str = " ".join(pins) if isinstance(pins, (list, tuple)) else str(pins)
                    reg = pc.get("region") or pc.get("side") or ""
                    reg_flag = f"-region {reg}" if reg else ""
                    lines.append(f"set_io_pin_constraint -pin_names {{{pin_str}}} {reg_flag}")

            cmd = "place_pins -hor_layers $io_hor -ver_layers $io_ver"
            if corner_avoidance > 0:
                cmd += f" -corner_avoidance {corner_avoidance}"
            if min_distance > 0:
                cmd += f" -min_distance {min_distance}"
            if random:
                cmd += " -random"
            if exclude_left:
                cmd += " -exclude left"
            if exclude_right:
                cmd += " -exclude right"
            if exclude_top:
                cmd += " -exclude top"
            if exclude_bottom:
                cmd += " -exclude bottom"
            lines.append(cmd)
            lines.append(f'write_def "{def_path}"')
            tcl = "\n".join(lines) + "\n"

        res = self.runner.run_step("iopins", tcl_arg=tcl)
        self.process_events()
        return bool(res)

    def place(
        self,
        tcl: Optional[str] = None,
        density: float = 0.50,
        pad_left: int = 2,
        pad_right: int = 2,
        timing_driven: bool = True,
    ) -> bool:
        """Executes global placement, timing-driven optimization, and detailed placement."""
        if not tcl and (density != 0.50 or pad_left != 2 or pad_right != 2 or not timing_driven):
            def_path = os.path.join(self.project.results_dir, "temp.def").replace("\\", "/")
            tflag = "-timing_driven" if timing_driven else ""
            tcl = f"""global_placement -density {density} -pad_left {pad_left} -pad_right {pad_right} {tflag}
detailed_placement
check_placement
write_def "{def_path}"
"""
        res = self.runner.run_step("place", tcl_arg=tcl)
        self.process_events()
        return bool(res)

    def cts(
        self,
        tcl: Optional[str] = None,
        root_buf: Optional[str] = None,
        buf_list: Optional[Union[str, List[str]]] = None,
        sink_clustering: bool = True,
    ) -> bool:
        """Synthesizes balanced clock tree network with clock buffer insertion."""
        if not tcl and (root_buf or buf_list or sink_clustering):
            def_path = os.path.join(self.project.results_dir, "temp.def").replace("\\", "/")
            bufs = " ".join(buf_list) if isinstance(buf_list, (list, tuple)) else (buf_list or "")
            b_flag = f'-buf_list "{bufs}" ' if bufs else ""
            r_flag = f'-root_buf "{root_buf}" ' if root_buf else ""
            c_flag = "-sink_clustering_enable " if sink_clustering else ""
            tcl = f"""set tech [::ord::get_db_tech]
if {{[$tech findLayer "met2"] ne "NULL"}} {{
    catch {{ set_wire_rc -layer met2 }}
    catch {{ estimate_parasitics -placement }}
}}
clock_tree_synthesis {b_flag}{r_flag}{c_flag}
catch {{ repair_clock_nets }}
catch {{ repair_timing -setup -hold }}
detailed_placement
check_placement
write_def "{def_path}"
"""
        res = self.runner.run_step("cts", tcl_arg=tcl)
        self.process_events()
        return bool(res)

    def route(
        self,
        tcl: Optional[str] = None,
        congestion_iterations: int = 60,
        bottom_layer: str = "met1",
        top_layer: str = "met5",
        layer_adjustments: Optional[Dict[str, float]] = None,
    ) -> bool:
        """Runs global routing (FastRoute) and detailed routing (TritonRoute)."""
        if not tcl:
            def_path = os.path.join(self.project.results_dir, "temp.def").replace("\\", "/")
            fix_path = os.path.join(self.project.root_dir, "fix.tcl").replace("\\", "/")
            lines = []
            if os.path.isfile(os.path.join(self.project.root_dir, "fix.tcl")):
                lines.append(f'source "{fix_path}"')

            # Fix DRT-0305: TritonRoute crashes if regular nets are marked as POWER/GROUND.
            lines.append("""foreach net [[::ord::get_db_block] getNets] {
    set type [$net getSigType]
    set name [$net getName]
    if {($type == "POWER" || $type == "GROUND") && $name != "VDD" && $name != "VSS"} {
        $net setSigType "SIGNAL"
    }
}""")

            adj = layer_adjustments if layer_adjustments is not None else {"met1": 0.5, "met2": 0.3, "met3": 0.2}
            if adj:
                lines.append("set tech [::ord::get_db_tech]")
                lines.append(f'if {{[$tech findLayer "{bottom_layer}"] ne "NULL"}} {{')
                lines.append(f'    catch {{ set_routing_layers -signal {bottom_layer}-{top_layer} }}')
                for l, val in adj.items():
                    lines.append(f'    catch {{ set_global_routing_layer_adjustment {l} {val} }}')
                lines.append("}")

            guide_path = os.path.join(self.project.results_dir, "route.guide").replace("\\", "/")
            drc_path = os.path.join(self.project.reports_dir, "drc.rpt").replace("\\", "/")
            lines.append(
                f'catch {{ global_route -guide_file "{guide_path}" -congestion_iterations {congestion_iterations} -verbose }}'
            )
            lines.append(
                f'detailed_route -output_drc "{drc_path}"'
            )
            lines.append(f'write_def "{def_path}"')
            tcl = "\n".join(lines) + "\n"

        res = self.runner.run_step("route", tcl_arg=tcl)
        self.process_events()
        return bool(res)

    def fill(self, tcl: Optional[str] = None) -> bool:
        """Inserts decap & standard cell filler cells and checks metal layer densities."""
        res = self.runner.run_step("fill", tcl_arg=tcl)
        self.process_events()
        return bool(res)

    def gds(self, tcl: Optional[str] = None) -> bool:
        """Streams out physical layout into standard GDSII using Magic."""
        res = self.runner.run_step("gds", tcl_arg=tcl)
        self.process_events()
        return bool(res)

    def signoff(self, step: str = "pat", tcl: Optional[str] = None) -> Any:
        """
        Executes final verification and signoff checks:
        step can be 'pat' (multi-corner timing/power), 'drc', 'antenna', 'dft', 'lvs', 'gls', or 'tapeout'.
        Returns the corresponding parsed SignoffReport object.
        """
        clean_step = step.lower().strip()
        if clean_step in ["pat", "sta", "timing"]:
            self.runner.run_step("sta", tcl_arg=tcl)
            self.process_events()
            return self.project.get_signoff_report()
        elif clean_step == "drc":
            self.runner.run_step("drc", tcl_arg=tcl)
            self.process_events()
            return self.project.get_drc_report()
        elif clean_step == "antenna":
            self.runner.run_step("antenna", tcl_arg=tcl)
            self.process_events()
            return True
        elif clean_step in ["dft", "atpg", "scan"]:
            self.runner.run_step("DFT", tcl_arg=tcl)
            self.process_events()
            return self.project.get_dft_report()
        elif clean_step in ["lvs", "run_lvs"]:
            self.runner.run_step("LVS", tcl_arg=tcl)
            self.process_events()
            return self.project.get_lvs_report()
        elif clean_step in ["gls", "run_gls", "simulation"]:
            self.runner.run_step("GLS", tcl_arg=tcl)
            self.process_events()
            return self.project.get_gls_report()
        elif clean_step in ["tapeout", "manifest", "packaging"]:
            self.runner.run_step("Tapeout", tcl_arg=tcl)
            self.process_events()
            return self.project.get_tapeout_report()
        else:
            res = self.runner.run_step(step, tcl_arg=tcl)
            self.process_events()
            return bool(res)

    def dft(self, tcl: Optional[str] = None) -> DFTSignoffReport:
        """Executes full DFT scan chain stitching and ATPG signoff analysis. Returns DFTSignoffReport."""
        return self.signoff("dft", tcl=tcl)

    def lvs(self, tcl: Optional[str] = None) -> LVSSignoffReport:
        """Executes Layout Versus Schematic (LVS) comparison. Returns LVSSignoffReport."""
        return self.signoff("lvs", tcl=tcl)

    def gls(self, tcl: Optional[str] = None) -> GLSSignoffReport:
        """Executes Gate-Level Simulation (GLS) with SDF timing back-annotation. Returns GLSSignoffReport."""
        return self.signoff("gls", tcl=tcl)

    def export_sdf(self) -> str:
        """Exports Standard Delay Format (SDF) timing file from physical design."""
        self.runner.run_step("sdf")
        self.process_events()
        sdf_path = os.path.join(self.project.results_dir, f"{self.project.top_module}.sdf")
        return sdf_path

    def tapeout(self, tcl: Optional[str] = None) -> TapeoutManifestReport:
        """Packages final foundry tapeout GDS and generates signoff checklist manifest."""
        return self.signoff("tapeout", tcl=tcl)

    def export_macro(
        self,
        macro_name: Optional[str] = None,
        pdk_name: str = "sky130",
        corners: Optional[List[Tuple[str, str, int, str]]] = None,
        def_path: Optional[str] = None,
        gds_path: Optional[str] = None,
        verilog_path: Optional[str] = None,
        sdc_path: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Exports the current physical design as a foundry-grade Hard Macro Package
        (Abstract LEF, Multi-corner Liberty models, GDSII, Verilog stub, SPICE CDL,
        SDC, and Datasheet) conforming to SkyWater 130nm foundry standards.
        Deposits the package in ~/.silis/macrocache/<pdk>/<macro_name>/
        and returns a dictionary of artifact paths.
        """
        from backendflow.macro_exporter import run_macro_package_export

        target_name = macro_name or self.project.top_module
        project_root = self.project.root_dir

        if not def_path:
            cand_defs = [
                os.path.join(self.project.results_dir, f"{target_name}.def"),
                os.path.join(self.project.results_dir, "temp.def"),
                self.project.get_def() or "",
            ]
            def_path = next((p for p in cand_defs if p and os.path.isfile(p)), None)

        if not gds_path:
            cand_gds = [
                os.path.join(self.project.results_dir, f"{target_name}.gds"),
                os.path.join(self.project.results_dir, "design.gds"),
                os.path.join(self.project.results_dir, "temp.gds"),
                self.project.get_gds() or "",
            ]
            gds_path = next((p for p in cand_gds if p and os.path.isfile(p)), None)

        if not verilog_path:
            cand_v = [
                os.path.join(self.project.results_dir, "temp.v"),
                self.project.get_netlist() or "",
            ]
            verilog_path = next((p for p in cand_v if p and os.path.isfile(p)), None)

        if not sdc_path:
            sdcs = self.project.get_sdc_files()
            sdc_path = sdcs[0] if sdcs else None

        cache_dir = run_macro_package_export(
            project_root=project_root,
            macro_name=target_name,
            pdk_name=pdk_name,
            corners=corners,
            def_path=def_path,
            gds_path=gds_path,
            verilog_path=verilog_path,
            sdc_path=sdc_path,
        )

        return {
            "macro_name": target_name,
            "cache_dir": cache_dir,
            "lef": os.path.join(cache_dir, f"{target_name}.lef"),
            "gds": os.path.join(cache_dir, f"{target_name}.gds"),
            "stub_v": os.path.join(cache_dir, f"{target_name}.v"),
            "sim_v": os.path.join(cache_dir, f"{target_name}.sim.v"),
            "spice": os.path.join(cache_dir, f"{target_name}.spice"),
            "sdc": os.path.join(cache_dir, f"{target_name}.sdc"),
            "lib_tt": os.path.join(cache_dir, "lib", f"{target_name}__tt_025C_1v80.lib"),
        }

    # --------------------------------------------------------------------------
    # Flow Sequencing & Execution Control
    # --------------------------------------------------------------------------
    def _normalize_step(self, step: str) -> str:
        s = step.lower().strip()
        return self.STEP_ALIASES.get(s, s)

    def run_step(self, step_name: str, **kwargs) -> bool:
        """Dispatches an individual step by name."""
        norm = self._normalize_step(step_name)
        if norm == "synthesis":
            return self.synthesis(tcl=kwargs.get("tcl"))
        elif norm == "init":
            return self.init(tcl=kwargs.get("tcl"))
        elif norm == "floorplan":
            return self.floorplan(
                tcl=kwargs.get("tcl"),
                die_area=kwargs.get("die_area"),
                core_margin=kwargs.get("core_margin", 20.0),
                macros=kwargs.get("macros"),
                regions=kwargs.get("regions"),
                blockages=kwargs.get("blockages"),
            )
        elif norm == "tapcells":
            return self.tapcells(tcl=kwargs.get("tcl"))
        elif norm == "pdn":
            return self.pdn(tcl=kwargs.get("tcl"))
        elif norm == "iopins":
            return self.iopins(tcl=kwargs.get("tcl"))
        elif norm == "place":
            return self.place(tcl=kwargs.get("tcl"))
        elif norm == "cts":
            return self.cts(tcl=kwargs.get("tcl"))
        elif norm == "route":
            return self.route(tcl=kwargs.get("tcl"))
        elif norm == "fill":
            return self.fill(tcl=kwargs.get("tcl"))
        elif norm == "gds":
            return self.gds(tcl=kwargs.get("tcl"))
        elif norm == "signoff":
            sub = kwargs.get("substep", "pat")
            return self.signoff(step=sub, tcl=kwargs.get("tcl"))
        elif norm == "dft":
            res = self.dft(tcl=kwargs.get("tcl"))
            return res.is_clean if hasattr(res, "is_clean") else bool(res)
        elif norm == "lvs":
            res = self.lvs(tcl=kwargs.get("tcl"))
            return res.is_clean if hasattr(res, "is_clean") else bool(res)
        elif norm == "gls":
            res = self.gls(tcl=kwargs.get("tcl"))
            return res.is_clean if hasattr(res, "is_clean") else bool(res)
        elif norm == "tapeout":
            res = self.tapeout(tcl=kwargs.get("tcl"))
            return res.tapeout_ready if hasattr(res, "tapeout_ready") else bool(res)
        else:
            return self.runner.run_step(step_name, tcl_arg=kwargs.get("tcl"))

    def run_until(self, target_step: str, **kwargs) -> bool:
        """
        Executes flow steps sequentially starting from 'synthesis' up to and
        including target_step. Halts immediately on failure.
        """
        target_norm = self._normalize_step(target_step)
        if target_norm not in self.FLOW_STEPS:
            raise ValueError(f"Unknown step: '{target_step}'. Valid steps: {self.FLOW_STEPS}")

        end_idx = self.FLOW_STEPS.index(target_norm)
        steps_to_run = self.FLOW_STEPS[: end_idx + 1]

        for s in steps_to_run:
            print(f"\n[PIPELINE] >>> Executing Step: {s.upper()} <<<")
            ok = self.run_step(s, **kwargs)
            if not ok:
                print(f"[PIPELINE ERR] Step '{s}' failed. Aborting run_until.")
                return False
        return True

    def run_from(self, start_step: str, end_step: str, **kwargs) -> bool:
        """
        Executes flow steps sequentially from start_step to end_step (inclusive).
        Halts immediately if any step fails.
        """
        start_norm = self._normalize_step(start_step)
        end_norm = self._normalize_step(end_step)

        if start_norm not in self.FLOW_STEPS:
            raise ValueError(f"Unknown start step: '{start_step}'")
        if end_norm not in self.FLOW_STEPS:
            raise ValueError(f"Unknown end step: '{end_step}'")

        s_idx = self.FLOW_STEPS.index(start_norm)
        e_idx = self.FLOW_STEPS.index(end_norm)

        if s_idx > e_idx:
            raise ValueError(f"Start step '{start_step}' is after end step '{end_step}'")

        steps_to_run = self.FLOW_STEPS[s_idx : e_idx + 1]
        for s in steps_to_run:
            print(f"\n[PIPELINE] >>> Executing Step: {s.upper()} <<<")
            ok = self.run_step(s, **kwargs)
            if not ok:
                print(f"[PIPELINE ERR] Step '{s}' failed. Aborting run_from.")
                return False
        return True

    def run_all(self, **kwargs) -> bool:
        """Executes full ASIC flow end-to-end: synthesis through signoff."""
        return self.run_from("synthesis", "signoff", **kwargs)

    # --------------------------------------------------------------------------
    # Report & Metric Queries
    # --------------------------------------------------------------------------
    def get_synthesis_report(self) -> SynthesisReport:
        """Retrieves parsed post-synthesis report."""
        return self.project.get_synthesis_report()

    def get_signoff_report(self) -> SignoffReport:
        """Retrieves parsed post-route PAT signoff report."""
        return self.project.get_signoff_report()

    def get_drc_report(self) -> DRCReport:
        """Retrieves parsed DRC verification report."""
        return self.project.get_drc_report()

    def get_dft_report(self) -> DFTSignoffReport:
        """Retrieves parsed DFT scan chain and fault coverage report."""
        return self.project.get_dft_report()

    def get_lvs_report(self) -> LVSSignoffReport:
        """Retrieves parsed LVS signoff report."""
        return self.project.get_lvs_report()

    def get_gls_report(self) -> GLSSignoffReport:
        """Retrieves parsed Gate-Level Simulation (GLS) signoff report."""
        return self.project.get_gls_report()

    def get_tapeout_report(self) -> TapeoutManifestReport:
        """Retrieves parsed Foundry Tapeout checklist manifest report."""
        return self.project.get_tapeout_report()

    def get_reports(self) -> Dict[str, Any]:
        """Returns all parsed reports for the pipeline project."""
        return self.project.get_reports()

    # --------------------------------------------------------------------------
    # Floorplanning & Area Enquiry Engine
    # --------------------------------------------------------------------------
    def get_sizes(self, refresh: bool = False) -> Dict[str, Any]:
        """Returns design sizes JSON containing total cell area and module breakdown."""
        return self.project.get_sizes(refresh=refresh)

    def get_modules(self, refresh: bool = False) -> List[str]:
        """Returns list of hierarchical module instance names."""
        return self.project.get_modules(refresh=refresh)

    def get_module_area(self, module: str = "core", refresh: bool = False) -> float:
        """Returns standard cell area in um^2 for module or core."""
        return self.project.get_module_area(module=module, refresh=refresh)

    def get_utilization(
        self,
        module_or_region: Union[str, Dict[str, Any]],
        area: Optional[Union[float, int, Tuple[float, float], Tuple[float, float, float, float], List[float]]] = None,
        refresh: bool = False,
    ) -> float:
        """
        Calculates and returns cell utilization (0.0 to 1.0+) for a module or region.
        Supports both (module, area/box) and region_dict directly.
        """
        return self.project.get_utilization(
            module_or_region=module_or_region, area=area, refresh=refresh
        )

    enquire_utilization = get_utilization

    def get_required_area(
        self,
        module: str = "core",
        target_density: float = 0.40,
        refresh: bool = False,
    ) -> float:
        """Returns required physical area in um^2 for target density."""
        return self.project.get_required_area(
            module=module, target_density=target_density, refresh=refresh
        )

    def suggest_box(
        self,
        module: str = "core",
        origin: Tuple[float, float] = (0.0, 0.0),
        target_density: float = 0.40,
        aspect_ratio: float = 1.0,
        grid_snap: float = 0.005,
        refresh: bool = False,
    ) -> List[float]:
        """Calculates optimal [x1, y1, x2, y2] bounding box for target density and aspect ratio."""
        return self.project.suggest_box(
            module=module,
            origin=origin,
            target_density=target_density,
            aspect_ratio=aspect_ratio,
            grid_snap=grid_snap,
            refresh=refresh,
        )

    # --------------------------------------------------------------------------
    # Multi-Language Lowering & Formal Verification (SCINT Phase 4)
    # --------------------------------------------------------------------------
    def convert(
        self,
        src: Union[str, List[str]],
        src_lang: Optional[str] = None,
        out: Optional[str] = None,
        std: str = "08",
        fsynopsys: bool = False,
        use_latches: bool = False,
        hls_top: Optional[str] = None,
        hls_memory_policy: str = "NO_BRAM",
        hls_channels: int = 1,
    ) -> str:
        """
        Lowers source HDL/HLS code (SystemVerilog, VHDL-2008, C/C++) to standard synthesizable Verilog.
        Automatically adds the converted Verilog file to project.rtl_files.
        """
        import subprocess
        import shutil

        sources = [src] if isinstance(src, str) else list(src)
        first_src = sources[0]
        base_name = os.path.splitext(os.path.basename(first_src))[0]

        if not out:
            out = os.path.join(self.project.netlist_dir, f"{base_name}_converted.v")
        out = os.path.abspath(out)
        os.makedirs(os.path.dirname(out), exist_ok=True)

        # Detect language
        ext = os.path.splitext(first_src)[1].lower()
        lang = src_lang.lower() if src_lang else ("sv" if ext in (".sv", ".svh") else ("vhdl" if ext in (".vhd", ".vhdl") else ("c" if ext in (".c", ".cpp") else "v")))

        if lang == "sv":
            sv2v_bin = shutil.which("sv2v") or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "third-party", "bin", "sv2v")
            if not shutil.which(sv2v_bin) and not os.path.isfile(sv2v_bin):
                raise FileNotFoundError("sv2v executable not found in PATH or silis/third-party/bin/sv2v")
            cmd = [sv2v_bin] + sources + [f"--write={out}"]
            subprocess.run(cmd, check=True)
        elif lang == "vhdl":
            ghdl_bin = shutil.which("ghdl") or "ghdl"
            top_mod = hls_top or self.project.top_module
            cmd = [ghdl_bin, "--synth", f"--std={std}", "--out=verilog", "--no-formal"]
            if fsynopsys:
                cmd.append("-fsynopsys")
            if use_latches:
                cmd.append("--latches")
            cmd += ["-e", top_mod] + sources
            with open(out, "w") as f_out:
                subprocess.run(cmd, stdout=f_out, check=True)
        elif lang == "c":
            bambu_bin = shutil.which("bambu") or "bambu"
            if not shutil.which(bambu_bin):
                raise FileNotFoundError("Bambu HLS executable not found in PATH")
            top_fn = hls_top or self.project.top_module
            cmd = [
                bambu_bin,
                f"--top-fname={top_fn}",
                f"--memory-allocation-policy={hls_memory_policy}",
                f"--channels-number={hls_channels}",
                f"--output-fname={out}",
            ] + sources
            subprocess.run(cmd, check=True)
        else:
            raise ValueError(f"Unsupported conversion language: {lang}")

        if out not in self.project.rtl_files:
            self.project.rtl_files.append(out)

        return out

    def formal(
        self,
        properties: str,
        engine: str = "smtbmc",
        mode: str = "prove",
        depth: int = 20,
    ) -> bool:
        """
        Executes formal property verification using SymbiYosys (SBY).
        """
        import subprocess
        import shutil

        sby_bin = shutil.which("sby") or "sby"
        if not shutil.which(sby_bin):
            raise FileNotFoundError("SymbiYosys ('sby') executable not found in PATH")

        sby_dir = os.path.join(self.project.reports_dir, "formal")
        os.makedirs(sby_dir, exist_ok=True)
        sby_file = os.path.join(sby_dir, f"{self.project.top_module}.sby")

        sby_content = f"""[options]
mode {mode}
depth {depth}

[engines]
{engine}

[script]
"""
        for f in self.project.rtl_files:
            sby_content += f"read -sv {f}\n"
        sby_content += f"""read -sv {os.path.abspath(properties)}
prep -top {self.project.top_module}

[files]
{os.path.abspath(properties)}
"""
        for f in self.project.rtl_files:
            sby_content += f"{os.path.abspath(f)}\n"

        with open(sby_file, "w") as f:
            f.write(sby_content)

        proc = subprocess.run([sby_bin, "-f", sby_file], cwd=sby_dir, capture_output=True, text=True)
        return proc.returncode == 0

    # --------------------------------------------------------------------------
    # Lifecycle & Context Management
    # --------------------------------------------------------------------------
    def close(self) -> None:
        """Gracefully closes child OpenROAD processes and flushes events."""
        if hasattr(self, "runner") and self.runner:
            try:
                self.runner.close()
            except Exception:
                pass
        self.process_events(iterations=5, delay_ms=2)

    def __enter__(self) -> "Pipeline":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    def __repr__(self) -> str:
        return f"<Pipeline project='{self.project.name}' top='{self.project.top_module}'>"
