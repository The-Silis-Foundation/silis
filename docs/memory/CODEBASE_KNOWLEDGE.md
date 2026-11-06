# Silis ASIC EDA Master Architectural Knowledge Base
*Machine-readable, densely-indexed reference strictly scoped to `silis/`.*

---

## 1. Top-Level Core SDK Classes & Methods

### `class Pipeline` (silis/core/sdk/pipeline.py:359)
> High-level programmatic ASIC pipeline for Silis.
Provides methods for synthesis, PnR steps, GDS stream-out, and signoff.

| Method | Arguments | File Line | Description |
|---|---|---|---|
| `__init__` | `(self, project_or_path, headless)` | [`L403`](silis/core/sdk/pipeline.py#L403) | - |
| `process_events` | `(self, iterations, delay_ms)` | [`L437`](silis/core/sdk/pipeline.py#L437) | Pumps Qt event loop so QProcess, QThread, and timer events are processed. |
| `synthesis` | `(self, tcl, corner, mcmm, dft, flatten)` | [`L449`](silis/core/sdk/pipeline.py#L449) | Runs frontend RTL synthesis, scan insertion (if dft=True), and technology mapping. |
| `init` | `(self, tcl)` | [`L469`](silis/core/sdk/pipeline.py#L469) | Initializes OpenROAD, links PDK LEF/LIBs, and reads the synthesized netlist. |
| `spec_floorplan` | `(self, die_area, core_margin, macros, regions, blockages, power_domains, site, auto_macro_placer, macro_halo, macro_channel, check_collisions, strict_collisions)` | [`L531`](silis/core/sdk/pipeline.py#L531) | Declaratively specifies chip die bounds, core utilization, macro placement, halos, blockages, and regions. |
| `spec_iopins` | `(self, mode, pad_strategy, pad_ring_margin, upf_aware, supply_pairs_per_edge, edge_assignments, pin_target, hor_layers, ver_layers, corner_avoidance, min_distance, pin_constraints, pin_order_file)` | [`L571`](silis/core/sdk/pipeline.py#L571) | Declaratively specifies IO pad ring or peripheral pin placement. |
| `spec_pdn` | `(self, enable_ring, ring_width, ring_spacing, ring_offset, ring_h_layer, ring_v_layer, enable_trunks, trunk_layer, trunk_width)` | [`L610`](silis/core/sdk/pipeline.py#L610) | Declaratively specifies the PDN mesh, core power rings, and dedicated pad trunk synthesis parameters. |
| `spec_tapcells` | `(self, distance, tapcell_master, endcap_cpp, endcap_master)` | [`L641`](silis/core/sdk/pipeline.py#L641) | Declaratively specifies tapcell and endcap insertion parameters. |
| `spec_power_switches` | `(self, cell_master, columns, pitch_um, domains, adaptive_placement)` | [`L662`](silis/core/sdk/pipeline.py#L662) | Declaratively specifies physical power switch column synthesis in gated domains. |
| `spec_level_shifters` | `(self, cell_master, rules)` | [`L690`](silis/core/sdk/pipeline.py#L690) | Declaratively specifies level shifter cell synthesis on domain boundary cuts. |
| `run_fps` | `(self, tcl_out_path)` | [`L707`](silis/core/sdk/pipeline.py#L707) | Unified FloorPlan Synthesis (FPS) Orchestrator. |
| `floorplan` | `(self, tcl, die_area, core_margin, macros, regions, blockages, power_domains, power_domain_affinity, check_collisions, strict_collisions, auto_macro_placer, macro_halo, macro_channel, mpl_max_levels, mpl_min_instances, mpl_max_instances, mpl_min_macros, mpl_max_macros, mpl_bus_planning, mpl_target_dead_space, mpl_wirelength_weight, mpl_area_weight)` | [`L1313`](silis/core/sdk/pipeline.py#L1313) | Configures chip die bounds, core utilization, macro placement, halos, blockages, and regions. |
| `place_macro` | `(self, inst, at, orient, halo)` | [`L1586`](silis/core/sdk/pipeline.py#L1586) | Creates a clean, validated macro placement dictionary. |
| `add_fence` | `(self, module, box, origin, density, aspect_ratio, halo)` | [`L1612`](silis/core/sdk/pipeline.py#L1612) | Creates a clean fence region dictionary. |
| `add_region` | `(self, module, box, origin, density, aspect_ratio, halo)` | [`L1647`](silis/core/sdk/pipeline.py#L1647) | Creates an inclusive region dictionary. |
| `auto_place_regions` | `(self, die_area, core_margin, macros, regions, blockages, target_density, min_cutoff_pct, force_place_all, force_auto_shape, as_fence, common_halo, seed, w_r2m, w_r2r, w_r2io, allow_non_rectangular)` | [`L1683`](silis/core/sdk/pipeline.py#L1683) | Executes hierarchical auto region placement using the Silis geometric & affinity solver. |
| `auto_shape_regions` | `(self, module_names, target_density, min_cutoff_pct, core_margin, as_fence)` | [`L1762`](silis/core/sdk/pipeline.py#L1762) | Convenience method to auto-shape and auto-place inclusive floorplanning regions. |
| `add_blockage` | `(self, box, soft)` | [`L1814`](silis/core/sdk/pipeline.py#L1814) | Creates a placement/routing blockage dictionary. |
| `tapcells` | `(self, tcl, distance, endcap_cpp, tapcell, endcap)` | [`L1822`](silis/core/sdk/pipeline.py#L1822) | Inserts welltap and endcap cells according to PDK DRC spacing rules. |
| `configure_power_domain_supply` | `(self, domain_name, supply_type)` | [`L1846`](silis/core/sdk/pipeline.py#L1846) | Configures the power supply architecture for a power domain: |
| `pdn` | `(self, tcl, enable_ring, ring_width, ring_spacing, ring_offset, ring_h_layer, ring_v_layer, enable_trunks, trunk_layer, trunk_width)` | [`L1857`](silis/core/sdk/pipeline.py#L1857) | Synthesizes VDD and VSS power grid straps, peripheral power ring, and targeted pad trunk bridges. |
| `iopins` | `(self, tcl, mode, pad_strategy, pad_ring_margin, upf_aware, supply_pairs_per_edge, edge_assignments, pin_target, hor_layers, ver_layers, corner_avoidance, min_distance, pin_constraints, pin_order_file, random, exclude_left, exclude_right, exclude_top, exclude_bottom)` | [`L2252`](silis/core/sdk/pipeline.py#L2252) | Places IO pins or full-chip pad ring along die perimeter. |
| `place` | `(self, tcl, density, pad_left, pad_right, timing_driven, init_density_penalty)` | [`L2688`](silis/core/sdk/pipeline.py#L2688) | Executes global placement, timing-driven optimization, and detailed placement. |
| `cts` | `(self, tcl, root_buf, buf_list, sink_clustering)` | [`L2783`](silis/core/sdk/pipeline.py#L2783) | Synthesizes balanced clock tree network with clock buffer insertion. |
| `route` | `(self, tcl, congestion_iterations, allow_congestion, bottom_layer, top_layer, layer_adjustments)` | [`L2828`](silis/core/sdk/pipeline.py#L2828) | Runs global routing (FastRoute) and detailed routing (TritonRoute). |
| `fill` | `(self, tcl)` | [`L2908`](silis/core/sdk/pipeline.py#L2908) | Inserts decap & standard cell filler cells and checks metal layer densities. |
| `gds` | `(self, tcl)` | [`L2923`](silis/core/sdk/pipeline.py#L2923) | Streams out physical layout into standard GDSII using Magic. |
| `signoff` | `(self, step, tcl)` | [`L2945`](silis/core/sdk/pipeline.py#L2945) | Executes final verification and signoff checks: |
| `dft` | `(self, tcl)` | [`L2989`](silis/core/sdk/pipeline.py#L2989) | Executes full DFT scan chain stitching and ATPG signoff analysis. Returns DFTSignoffReport. |
| `lvs` | `(self, tcl)` | [`L2993`](silis/core/sdk/pipeline.py#L2993) | Executes Layout Versus Schematic (LVS) comparison. Returns LVSSignoffReport. |
| `gls` | `(self, tcl)` | [`L2997`](silis/core/sdk/pipeline.py#L2997) | Executes Gate-Level Simulation (GLS) with SDF timing back-annotation. Returns GLSSignoffReport. |
| `simulate` | `(self, trace_format, coverage, threads, timeout_sec)` | [`L3001`](silis/core/sdk/pipeline.py#L3001) | Executes high-speed cycle-accurate SystemVerilog / UVM simulation using Verilator. |
| `lint` | `(self)` | [`L3093`](silis/core/sdk/pipeline.py#L3093) | Runs fast static linting across project RTL using bundled Verilator. |
| `export_sdf` | `(self)` | [`L3118`](silis/core/sdk/pipeline.py#L3118) | Exports Standard Delay Format (SDF) timing file from physical design. |
| `tapeout` | `(self, tcl)` | [`L3125`](silis/core/sdk/pipeline.py#L3125) | Packages final foundry tapeout GDS and generates signoff checklist manifest. |
| `export_macro` | `(self, macro_name, pdk_name, corners, def_path, gds_path, verilog_path, sdc_path)` | [`L3129`](silis/core/sdk/pipeline.py#L3129) | Exports the current physical design as a foundry-grade Hard Macro Package |
| `run_step` | `(self, step_name)` | [`L3209`](silis/core/sdk/pipeline.py#L3209) | Dispatches an individual step by name. |
| `run_until` | `(self, target_step)` | [`L3259`](silis/core/sdk/pipeline.py#L3259) | Executes flow steps sequentially starting from 'synthesis' up to and |
| `run_from` | `(self, start_step, end_step)` | [`L3279`](silis/core/sdk/pipeline.py#L3279) | Executes flow steps sequentially from start_step to end_step (inclusive). |
| `run_all` | `(self)` | [`L3307`](silis/core/sdk/pipeline.py#L3307) | Executes full ASIC flow end-to-end: synthesis through signoff. |
| `get_synthesis_report` | `(self)` | [`L3314`](silis/core/sdk/pipeline.py#L3314) | Retrieves parsed post-synthesis report. |
| `get_signoff_report` | `(self)` | [`L3318`](silis/core/sdk/pipeline.py#L3318) | Retrieves parsed post-route PAT signoff report. |
| `get_drc_report` | `(self)` | [`L3322`](silis/core/sdk/pipeline.py#L3322) | Retrieves parsed DRC verification report. |
| `get_dft_report` | `(self)` | [`L3326`](silis/core/sdk/pipeline.py#L3326) | Retrieves parsed DFT scan chain and fault coverage report. |
| `get_lvs_report` | `(self)` | [`L3330`](silis/core/sdk/pipeline.py#L3330) | Retrieves parsed LVS signoff report. |
| `get_gls_report` | `(self)` | [`L3334`](silis/core/sdk/pipeline.py#L3334) | Retrieves parsed Gate-Level Simulation (GLS) signoff report. |
| `get_tapeout_report` | `(self)` | [`L3338`](silis/core/sdk/pipeline.py#L3338) | Retrieves parsed Foundry Tapeout checklist manifest report. |
| `get_reports` | `(self)` | [`L3342`](silis/core/sdk/pipeline.py#L3342) | Returns all parsed reports for the pipeline project. |
| `get_sizes` | `(self, refresh)` | [`L3349`](silis/core/sdk/pipeline.py#L3349) | Returns design sizes JSON containing total cell area and module breakdown. |
| `get_modules` | `(self, refresh)` | [`L3353`](silis/core/sdk/pipeline.py#L3353) | Returns list of hierarchical module instance names. |
| `get_module_area` | `(self, module, refresh)` | [`L3357`](silis/core/sdk/pipeline.py#L3357) | Returns standard cell area in um^2 for module or core. |
| `get_utilization` | `(self, module_or_region, area, refresh)` | [`L3361`](silis/core/sdk/pipeline.py#L3361) | Calculates and returns cell utilization (0.0 to 1.0+) for a module or region. |
| `get_required_area` | `(self, module, target_density, refresh)` | [`L3377`](silis/core/sdk/pipeline.py#L3377) | Returns required physical area in um^2 for target density. |
| `suggest_box` | `(self, module, origin, target_density, aspect_ratio, grid_snap, refresh)` | [`L3388`](silis/core/sdk/pipeline.py#L3388) | Calculates optimal [x1, y1, x2, y2] bounding box for target density and aspect ratio. |
| `convert` | `(self, src, src_lang, out, std, fsynopsys, use_latches, hls_top, hls_memory_policy, hls_channels)` | [`L3410`](silis/core/sdk/pipeline.py#L3410) | Lowers source HDL/HLS code (SystemVerilog, VHDL-2008, C/C++) to standard synthesizable Verilog. |
| `formal` | `(self, properties, engine, mode, depth)` | [`L3480`](silis/core/sdk/pipeline.py#L3480) | Executes formal property verification using SymbiYosys (SBY). |
| `get_heatmap` | `(self, heatmap_type, grid_size, def_path)` | [`L3530`](silis/core/sdk/pipeline.py#L3530) | Calculates and returns physical heatmap data directly as a NumPy array. |
| `compute_minimum_die_for_pads` | `(self, num_pads, core_w, core_h, strategy, target_aspect, pad_margin, min_pitch)` | [`L3703`](silis/core/sdk/pipeline.py#L3703) | Calculates the minimum PDK-legal die dimensions and per-edge pad allocations |
| `optimize_die` | `(self, target_density, padring, strategy, pad_margin)` | [`L3770`](silis/core/sdk/pipeline.py#L3770) | Optimizes core and die dimensions based on synthesized standard cell area |
| `apply_clock_ndr` | `(self, rule_name, min_layer, max_layer, clock_nets)` | [`L3812`](silis/core/sdk/pipeline.py#L3812) | Applies Non-Default Routing (NDR) rules to clock trees. |
| `repair_clock_buffers` | `(self)` | [`L3832`](silis/core/sdk/pipeline.py#L3832) | Repairs and balances clock buffer chains in OpenROAD. |
| `repair_antennas` | `(self, iterations, diode_cell)` | [`L3839`](silis/core/sdk/pipeline.py#L3839) | Inserts antenna diodes on long gate routing nets. |
| `save_checkpoint` | `(self, tag)` | [`L3856`](silis/core/sdk/pipeline.py#L3856) | Saves current layout and database checkpoint to results/{tag}.odb and results/{tag}.def. |
| `load_checkpoint` | `(self, tag)` | [`L3881`](silis/core/sdk/pipeline.py#L3881) | Loads a previously saved database checkpoint from results/{tag}.odb. |
| `close` | `(self)` | [`L3897`](silis/core/sdk/pipeline.py#L3897) | Gracefully closes child OpenROAD processes and flushes events. |
| `__enter__` | `(self)` | [`L3916`](silis/core/sdk/pipeline.py#L3916) | - |
| `__exit__` | `(self, exc_type, exc_val, exc_tb)` | [`L3919`](silis/core/sdk/pipeline.py#L3919) | - |

### `class Project` (silis/core/sdk/project.py:30)
> Programmatic abstraction of a Silis ASIC Project (.silisproj).
Handles configuration parsing, file discovery, macro binding, and report extraction.

| Method | Arguments | File Line | Description |
|---|---|---|---|
| `__init__` | `(self, path_or_name)` | [`L36`](silis/core/sdk/project.py#L36) | - |
| `get_floorplan` | `(self)` | [`L105`](silis/core/sdk/project.py#L105) | Returns the strongly-typed Floorplan entity for physical placement. |
| `get_power_network` | `(self)` | [`L112`](silis/core/sdk/project.py#L112) | Returns the strongly-typed IEEE 1801 UPF PowerNetwork coordinator. |
| `power_network` | `(self)` | [`L120`](silis/core/sdk/project.py#L120) | Property returning the PowerNetwork coordinator for idiomatic project.power_network access. |
| `get_timing_graph` | `(self)` | [`L124`](silis/core/sdk/project.py#L124) | Returns the live in-memory TimingGraph for on-the-fly static timing slack inspection. |
| `get_layout` | `(self)` | [`L131`](silis/core/sdk/project.py#L131) | Returns the in-memory Layout engine for real-time physical change analysis. |
| `layout` | `(self)` | [`L139`](silis/core/sdk/project.py#L139) | Property returning the Layout engine for idiomatic proj.layout access. |
| `view_layers` | `(self, show, detach)` | [`L143`](silis/core/sdk/project.py#L143) | Launches the C++ OpenROAD Native Layer Viewer for this project's layout. |
| `db` | `(self)` | [`L148`](silis/core/sdk/project.py#L148) | Returns the OpenDBBridge query engine for direct in-memory OpenROAD database introspection. |
| `get_rtl_files` | `(self)` | [`L176`](silis/core/sdk/project.py#L176) | Discovers existing RTL source files from config and rtl/ or source/ directory. |
| `is_vhdl` | `(self)` | [`L192`](silis/core/sdk/project.py#L192) | Returns True if the project contains any VHDL source files. |
| `get_vhdl_files` | `(self)` | [`L196`](silis/core/sdk/project.py#L196) | Discovers existing VHDL source files (*.vhd, *.vhdl). |
| `get_verilog_files` | `(self)` | [`L200`](silis/core/sdk/project.py#L200) | Discovers existing Verilog source files (*.v, *.sv). |
| `get_sdc_files` | `(self)` | [`L204`](silis/core/sdk/project.py#L204) | Discovers existing SDC timing constraint files. |
| `get_upf_file` | `(self)` | [`L217`](silis/core/sdk/project.py#L217) | Discovers existing UPF power intent specification file. |
| `get_power_domains` | `(self)` | [`L236`](silis/core/sdk/project.py#L236) | Returns parsed power_domain objects from the project UPF file. |
| `get_pin_order_file` | `(self)` | [`L244`](silis/core/sdk/project.py#L244) | Discovers existing I/O pin / pad ordering configuration file. |
| `get_tb_files` | `(self)` | [`L261`](silis/core/sdk/project.py#L261) | Discovers existing testbench files. |
| `get_netlists` | `(self)` | [`L277`](silis/core/sdk/project.py#L277) | Returns all synthesized Verilog netlists in netlist/ directory. |
| `get_netlist` | `(self)` | [`L286`](silis/core/sdk/project.py#L286) | Returns primary synthesized netlist path or None. |
| `get_defs` | `(self)` | [`L294`](silis/core/sdk/project.py#L294) | Returns all layout DEF files in results/ and root. |
| `get_def` | `(self)` | [`L302`](silis/core/sdk/project.py#L302) | Returns primary DEF file (temp.def or latest). |
| `get_gds_files` | `(self)` | [`L313`](silis/core/sdk/project.py#L313) | Returns all stream GDSII files in results/. |
| `get_gds` | `(self)` | [`L322`](silis/core/sdk/project.py#L322) | Returns primary GDS file (design.gds or <top>.gds). |
| `get_odbs` | `(self)` | [`L334`](silis/core/sdk/project.py#L334) | Returns all OpenROAD database checkpoints (*.odb) in results/. |
| `get_vcd_files` | `(self)` | [`L340`](silis/core/sdk/project.py#L340) | Returns waveform VCD files in project. |
| `get_macro_lefs_and_libs` | `(self)` | [`L347`](silis/core/sdk/project.py#L347) | Locates LEF and Liberty LIB files for all hard macros in the project. |
| `get_pdk_info` | `(self)` | [`L396`](silis/core/sdk/project.py#L396) | Finds configured PDK files (tlef, lef, lib, tech, gds) matching target PDK. |
| `get_synthesis_report` | `(self)` | [`L417`](silis/core/sdk/project.py#L417) | Loads and returns the SynthesisReport for this project. |
| `get_signoff_report` | `(self)` | [`L421`](silis/core/sdk/project.py#L421) | Loads and returns the SignoffReport (PAT) for this project. |
| `get_drc_report` | `(self)` | [`L425`](silis/core/sdk/project.py#L425) | Loads and returns the DRCReport for this project. |
| `get_antenna_report` | `(self)` | [`L429`](silis/core/sdk/project.py#L429) | Loads and returns the AntennaSignoffReport for this project. |
| `get_dft_report` | `(self)` | [`L434`](silis/core/sdk/project.py#L434) | Loads and returns the DFTSignoffReport for this project. |
| `get_lvs_report` | `(self)` | [`L438`](silis/core/sdk/project.py#L438) | Loads and returns the LVSSignoffReport for this project. |
| `get_gls_report` | `(self)` | [`L443`](silis/core/sdk/project.py#L443) | Loads and returns the GLSSignoffReport for this project. |
| `get_tapeout_report` | `(self)` | [`L448`](silis/core/sdk/project.py#L448) | Loads and returns the TapeoutManifestReport for this project. |
| `get_reports` | `(self)` | [`L453`](silis/core/sdk/project.py#L453) | Discovers and parses all project reports. |
| `get_sizes` | `(self, refresh)` | [`L480`](silis/core/sdk/project.py#L480) | Discovers, parses, and caches the design sizes JSON ({top_module}_sizes.json). |
| `get_modules` | `(self, refresh)` | [`L507`](silis/core/sdk/project.py#L507) | Returns a list of all hierarchical module instance names discovered in the netlist. |
| `get_module_area` | `(self, module, refresh)` | [`L512`](silis/core/sdk/project.py#L512) | Returns the standard cell area in um^2 for a specific module or the entire core. |
| `get_utilization` | `(self, module_or_region, area, macros, refresh)` | [`L554`](silis/core/sdk/project.py#L554) | Calculates and returns cell utilization (0.0 to 1.0+) for a module or region. |
| `get_required_area` | `(self, module, target_density, macro_area, refresh)` | [`L633`](silis/core/sdk/project.py#L633) | Returns the required physical area in um^2 to achieve target_density (0.0 to 1.0) |
| `suggest_box` | `(self, module, origin, target_density, macro_area, aspect_ratio, grid_snap, refresh)` | [`L650`](silis/core/sdk/project.py#L650) | Calculates and returns an optimal bounding box [x1, y1, x2, y2] starting at origin |
| `add_macro` | `(self, macro_name, lef, lib, gds)` | [`L692`](silis/core/sdk/project.py#L692) | Registers a hard macro in the project, optionally copying LEF, LIB, and GDS into rtl/ or source/. |
| `add_rtl` | `(self)` | [`L717`](silis/core/sdk/project.py#L717) | Adds RTL source files to the project. |
| `add_tb` | `(self)` | [`L725`](silis/core/sdk/project.py#L725) | Adds testbench files to the project. |
| `add_sdc` | `(self)` | [`L733`](silis/core/sdk/project.py#L733) | Adds SDC constraint files to the project. |
| `save` | `(self, path)` | [`L741`](silis/core/sdk/project.py#L741) | Saves project configuration to .silisproj file. |
| `import_macro` | `(self, macro_name, lef, lib, gds, generate_stub)` | [`L761`](silis/core/sdk/project.py#L761) | Imports a hard macro into the project. |
| `import_upf` | `(self, path, copy)` | [`L821`](silis/core/sdk/project.py#L821) | Imports an IEEE 1801 UPF or CPF power intent file into the project. |
| `set_power_domain_supply_type` | `(self, domain_name, supply_type)` | [`L839`](silis/core/sdk/project.py#L839) | Configures the physical power supply type for a power domain: |
| `import_io_config` | `(self, path, copy)` | [`L862`](silis/core/sdk/project.py#L862) | Imports an I/O pin ordering configuration into io/<filename>. |
| `to_dict` | `(self)` | [`L885`](silis/core/sdk/project.py#L885) | Returns project configuration dictionary. |
| `summary` | `(self)` | [`L889`](silis/core/sdk/project.py#L889) | Returns a high-level overview string of project status. |
| `load` | `(cls, path_or_name)` | [`L917`](silis/core/sdk/project.py#L917) | Loads and returns a Project instance. |
| `create` | `(cls, name, top, pdk, loc, rtl, tb, sdc, macros)` | [`L922`](silis/core/sdk/project.py#L922) | Creates a new Silis ASIC project workspace with standard directory layout |

### `class Floorplan` (silis/core/sdk/floorplan.py:144)
> Authoritative physical floorplan representation:
Die boundary, core rectangle, manufacturing grid quantization, and macro arrangement.

| Method | Arguments | File Line | Description |
|---|---|---|---|
| `__init__` | `(self, project)` | [`L149`](silis/core/sdk/floorplan.py#L149) | - |
| `set_die_dimensions` | `(self, width, height, margins)` | [`L170`](silis/core/sdk/floorplan.py#L170) | Sets die bounds with defensive dimension assertions. |
| `get_die_bbox` | `(self)` | [`L189`](silis/core/sdk/floorplan.py#L189) | - |
| `get_core_bbox` | `(self)` | [`L192`](silis/core/sdk/floorplan.py#L192) | - |
| `get_core_dimensions` | `(self)` | [`L200`](silis/core/sdk/floorplan.py#L200) | - |
| `add_macro` | `(self, name, master, x, y, width, height, orientation, halo)` | [`L204`](silis/core/sdk/floorplan.py#L204) | Adds a macro instance to the physical floorplan context with dynamic site row snapping. |
| `get_macro` | `(self, name)` | [`L233`](silis/core/sdk/floorplan.py#L233) | - |
| `get_macros` | `(self)` | [`L236`](silis/core/sdk/floorplan.py#L236) | - |
| `check_collisions` | `(self)` | [`L239`](silis/core/sdk/floorplan.py#L239) | Sweep-and-prune macro-to-macro keepout collision verification. |
| `verify_legal_placement` | `(self)` | [`L275`](silis/core/sdk/floorplan.py#L275) | Executes pre-flight DRC checks: |

### `class MacroInstance` (silis/core/sdk/floorplan.py:71)
> Physical macro block representation with exact bounding box, halo keepout,
orientation, and terminal locations.

| Method | Arguments | File Line | Description |
|---|---|---|---|
| `__init__` | `(self, name, master, x, y, width, height, orientation, halo, parent_floorplan)` | [`L76`](silis/core/sdk/floorplan.py#L76) | - |
| `move_to` | `(self, x, y)` | [`L98`](silis/core/sdk/floorplan.py#L98) | Moves macro origin with manufacturing grid quantization and dynamic site row snapping. |
| `set_orientation` | `(self, orient)` | [`L108`](silis/core/sdk/floorplan.py#L108) | - |
| `set_halo` | `(self, left, right, top, bottom)` | [`L113`](silis/core/sdk/floorplan.py#L113) | - |
| `get_bbox` | `(self)` | [`L118`](silis/core/sdk/floorplan.py#L118) | Returns exact physical bounding box (x1, y1, x2, y2) in microns. |
| `get_halo_bbox` | `(self)` | [`L122`](silis/core/sdk/floorplan.py#L122) | Returns physical bounding box including keepout halo margins (x1, y1, x2, y2). |
| `overlaps` | `(self, other)` | [`L131`](silis/core/sdk/floorplan.py#L131) | Collision invariant: BoundingBox(M_i + Halo_i) intersect BoundingBox(M_j + Halo_j) == empty. |

### `class PowerNetwork` (silis/core/sdk/power.py:143)
> IEEE 1801 multi-voltage architecture coordinator.
Validates domain exclusivities, level shifter mandates, and power intent completeness.

| Method | Arguments | File Line | Description |
|---|---|---|---|
| `__init__` | `(self, project)` | [`L148`](silis/core/sdk/power.py#L148) | - |
| `create_domain` | `(self, name, primary_voltage, elements)` | [`L178`](silis/core/sdk/power.py#L178) | - |
| `get_domain` | `(self, name)` | [`L185`](silis/core/sdk/power.py#L185) | - |
| `get_domains` | `(self)` | [`L188`](silis/core/sdk/power.py#L188) | - |
| `verify_power_intent` | `(self)` | [`L191`](silis/core/sdk/power.py#L191) | Validates IEEE 1801 verification rules: |

### `class PowerDomain` (silis/core/backendflow/floorplanner/power_domain_manager.py:24)
> Represents a physical or logical power domain.

| Method | Arguments | File Line | Description |
|---|---|---|---|
| `is_top` | `(self)` | [`L27`](silis/core/backendflow/floorplanner/power_domain_manager.py#L27) | - |
| `__init__` | `(self, name, voltage, domain_type, parent_domain, pmu_instance, elements, switch_topology, switch_pitch, enable_srpg, iso_en, sleep_en, sleep_ack, tapcell_type, site_type, row_height, enable_physical_switch)` | [`L30`](silis/core/backendflow/floorplanner/power_domain_manager.py#L30) | - |
| `to_dict` | `(self)` | [`L68`](silis/core/backendflow/floorplanner/power_domain_manager.py#L68) | - |
| `from_dict` | `(cls, data)` | [`L90`](silis/core/backendflow/floorplanner/power_domain_manager.py#L90) | - |

### `class TimingGraph` (silis/core/sdk/timing.py:32)
> Live Static Timing Graph wrapping OpenROAD / OpenSTA.
Queries timing slack and transitions directly in memory.

| Method | Arguments | File Line | Description |
|---|---|---|---|
| `__init__` | `(self, project)` | [`L37`](silis/core/sdk/timing.py#L37) | - |
| `invalidate_cache` | `(self)` | [`L65`](silis/core/sdk/timing.py#L65) | Invalidates all cached timing slacks and WNS/TNS metrics. |
| `wns` | `(self)` | [`L73`](silis/core/sdk/timing.py#L73) | Worst Negative Slack in nanoseconds. |
| `tns` | `(self)` | [`L78`](silis/core/sdk/timing.py#L78) | Total Negative Slack in nanoseconds. |
| `query_live_metrics` | `(self, force_refresh)` | [`L82`](silis/core/sdk/timing.py#L82) | Queries WNS and TNS from the active OpenROAD runtime. |
| `get_wns` | `(self, corner)` | [`L166`](silis/core/sdk/timing.py#L166) | Returns Worst Negative Slack in nanoseconds (negative indicates violation). |
| `get_tns` | `(self, corner)` | [`L171`](silis/core/sdk/timing.py#L171) | Returns Total Negative Slack in nanoseconds. |
| `get_pin_slack` | `(self, pin_name, delay_type)` | [`L176`](silis/core/sdk/timing.py#L176) | Queries on-the-fly static timing slack for an individual instance terminal. |
| `get_equivalent_cells` | `(self, master_name)` | [`L211`](silis/core/sdk/timing.py#L211) | Returns sizing alternatives for cell driver optimization (e.g. buf_1 -> buf_2, buf_4, buf_8). |

### `class Layout` (silis/core/sdk/layout.py:24)
> Authoritative In-Memory Physical Design Layout Engine.
Exposes real-time instance coordinate mutation, boundary inspection,
and net connectivity graphs.

| Method | Arguments | File Line | Description |
|---|---|---|---|
| `__init__` | `(self, project)` | [`L30`](silis/core/sdk/layout.py#L30) | - |
| `get_instances` | `(self)` | [`L55`](silis/core/sdk/layout.py#L55) | Returns all physical standard cell and macro instances in the active design. |
| `find_instance` | `(self, name)` | [`L60`](silis/core/sdk/layout.py#L60) | Finds an instance by hierarchical name. |
| `set_instance_location` | `(self, name, x, y, orientation)` | [`L65`](silis/core/sdk/layout.py#L65) | Mutates the instance location directly in the in-memory layout representation |
| `die_area` | `(self)` | [`L80`](silis/core/sdk/layout.py#L80) | Returns die boundary [x1, y1, x2, y2] in microns. |
| `core_area` | `(self)` | [`L85`](silis/core/sdk/layout.py#L85) | Returns core boundary [x1, y1, x2, y2] in microns. |
| `utilization` | `(self)` | [`L90`](silis/core/sdk/layout.py#L90) | Returns standard cell core area utilization percentage. |
| `get_die_area` | `(self)` | [`L94`](silis/core/sdk/layout.py#L94) | Returns die boundary [x1, y1, x2, y2] in microns. |
| `get_core_area` | `(self)` | [`L99`](silis/core/sdk/layout.py#L99) | Returns core boundary [x1, y1, x2, y2] in microns. |
| `get_utilization` | `(self)` | [`L104`](silis/core/sdk/layout.py#L104) | Returns standard cell core area utilization percentage. |
| `get_pins` | `(self)` | [`L109`](silis/core/sdk/layout.py#L109) | Returns top-level I/O boundary pins. |
| `view` | `(self, show, detach, layer_view)` | [`L114`](silis/core/sdk/layout.py#L114) | Interactive visualization of the physical layout directly from SDK. |
| `view_layers` | `(self, show, detach)` | [`L145`](silis/core/sdk/layout.py#L145) | Convenience method to launch the C++ OpenROAD Layer Viewer directly. |

## 2. Floorplanner & Physical Flow Architecture

### `class InteractiveFloorplannerWidget` (silis/core/backendflow/floorplanner/floorplanner.py:1445)
> Silis Floorplan & Power Studio (FPS)
Unified ASIC Floorplanning, Multi-Domain Power Intent (IEEE-1801 UPF),
and I/O Pad/Pin Co-Optimization Workbench.

- **Key Methods**: _get_project_context, __init__, _init_top_menu_bar, _init_layout_and_splitters, _setup_keyboard_shortcuts, keyPressEvent, reject, closeEvent, toggle_hud_visibility, _trigger_autosave, _do_transactional_autosave, _serialize_session_state, save_session, save_snapshot_as, load_session, revert_to_saved, verify_netlist_integrity, on_reset_from_netlist, select_all_canvas, clear_selection, delete_selected_entities, fit_core, toggle_halos_visibility, scan_narrow_corridors, open_die_core_setup_dialog

### `class HeadlessASICRunner` (silis/core/cli/flow.py:106)
- **Key Methods**: __init__, close, __del__, _streaming_read_stdout, _ensure_backend_running, execute_tcl, _wait_for_backend, run_synthesis, _get_io_lefs, _get_macro_lefs_and_libs, ensure_design_loaded, run_init, run_floorplan, run_step, run_fill, run_lvs, run_gls, export_sdf, run_tapeout

### `class BackendWidget` (silis/core/backendflow/flow/backendflow.py:224)
- **Key Methods**: __init__, load_custom_odb, load_custom_def, run_psm_integrity_check, run_bondpad_studio, apply_clock_ndr, repair_clock_buffers, repair_antenna_violations, launch_gds3d_view, run_signoff_pipeline, _on_signoff_pipeline_failed, _on_signoff_pipeline_succeeded, _on_signoff_pipeline_finished, _get_io_lefs, _get_io_gds, _get_macro_files, update_spinner, start_spinner, stop_spinner, launch_magic_gui, ask_command, kill_active_backend_process, reset_backend, on_tab_changed, run_flow_step

### `class ReportEngine` (silis/core/synthesisscripts/synthesisthread.py:13)
> Parses generated report files for robust metric extraction.

- **Key Methods**: parse_files, _bar, generate_markdown_report, generate_report

## 3. Floorplan & Macro Core Helper Functions

| Function | File Line | Summary |
|---|---|---|
| `generate_floorplan_tcl_from_data` | [`silis/core/backendflow/floorplanner/floorplanner.py:L7745`](silis/core/backendflow/floorplanner/floorplanner.py#L7745) | Headless & programmatic ASIC floorplan TCL generator. |
| `compute_peripheral_macro_placement` | [`silis/core/backendflow/floorplanner/floorplanner.py:L7575`](silis/core/backendflow/floorplanner/floorplanner.py#L7575) | Computes strict non-overlapping peripheral macro placement for all macros. |
| `check_floorplan_collisions` | [`silis/core/sdk/pipeline.py:L69`](silis/core/sdk/pipeline.py#L69) | Performs comprehensive 2D geometric collision and containment checks between: |

## 4. OpenROAD TCL Shims & Floorplan Commands

| TCL Command / Proc | File Line | Arguments |
|---|---|---|
| `NULL` | [`silis/core/backendflow/shims/openroad_upf_shim.tcl:L3`](silis/core/backendflow/shims/openroad_upf_shim.tcl#L3) | `args` |
| `_silis_get_mfg_grid` | [`silis/core/backendflow/floorplanner/silis_fp.tcl:L6`](silis/core/backendflow/floorplanner/silis_fp.tcl#L6) | `` |
| `_silis_get_site_row_height` | [`silis/core/backendflow/floorplanner/silis_fp.tcl:L16`](silis/core/backendflow/floorplanner/silis_fp.tcl#L16) | `` |
| `_silis_snap` | [`silis/core/backendflow/floorplanner/silis_fp.tcl:L33`](silis/core/backendflow/floorplanner/silis_fp.tcl#L33) | `val` |
| `_silis_snap_row_y` | [`silis/core/backendflow/floorplanner/silis_fp.tcl:L39`](silis/core/backendflow/floorplanner/silis_fp.tcl#L39) | `val` |
| `add_power_state` | [`silis/core/backendflow/shims/openroad_upf_shim.tcl:L44`](silis/core/backendflow/shims/openroad_upf_shim.tcl#L44) | `args` |
| `add_pst_state` | [`silis/core/backendflow/shims/openroad_upf_shim.tcl:L46`](silis/core/backendflow/shims/openroad_upf_shim.tcl#L46) | `args` |
| `connect_supply_net` | [`silis/core/backendflow/shims/openroad_upf_shim.tcl:L35`](silis/core/backendflow/shims/openroad_upf_shim.tcl#L35) | `args` |
| `create_fence` | [`silis/core/backendflow/floorplanner/silis_fp.tcl:L52`](silis/core/backendflow/floorplanner/silis_fp.tcl#L52) | `args` |
| `create_power_domain` | [`silis/core/backendflow/shims/openroad_upf_shim.tcl:L56`](silis/core/backendflow/shims/openroad_upf_shim.tcl#L56) | `name args` |
| `create_power_switch` | [`silis/core/backendflow/shims/openroad_upf_shim.tcl:L84`](silis/core/backendflow/shims/openroad_upf_shim.tcl#L84) | `name args` |
| `create_pst` | [`silis/core/backendflow/shims/openroad_upf_shim.tcl:L45`](silis/core/backendflow/shims/openroad_upf_shim.tcl#L45) | `args` |
| `create_region` | [`silis/core/backendflow/floorplanner/silis_fp.tcl:L93`](silis/core/backendflow/floorplanner/silis_fp.tcl#L93) | `args` |
| `create_supply_net` | [`silis/core/backendflow/shims/openroad_upf_shim.tcl:L33`](silis/core/backendflow/shims/openroad_upf_shim.tcl#L33) | `args` |
| `create_supply_port` | [`silis/core/backendflow/shims/openroad_upf_shim.tcl:L32`](silis/core/backendflow/shims/openroad_upf_shim.tcl#L32) | `args` |
| `create_supply_set` | [`silis/core/backendflow/shims/openroad_upf_shim.tcl:L36`](silis/core/backendflow/shims/openroad_upf_shim.tcl#L36) | `args` |
| `describe_state_model` | [`silis/core/backendflow/shims/openroad_upf_shim.tcl:L47`](silis/core/backendflow/shims/openroad_upf_shim.tcl#L47) | `args` |
| `gds` | [`silis/examples/cpp_macro_to_sv_chip/chip_top_proj/run_cts.tcl:L35`](silis/examples/cpp_macro_to_sv_chip/chip_top_proj/run_cts.tcl#L35) | `args` |
| `init` | [`silis/examples/cpp_macro_to_sv_chip/chip_top_proj/run_cts.tcl:L11`](silis/examples/cpp_macro_to_sv_chip/chip_top_proj/run_cts.tcl#L11) | `args` |
| `iopins` | [`silis/examples/cpp_macro_to_sv_chip/chip_top_proj/run_cts.tcl:L30`](silis/examples/cpp_macro_to_sv_chip/chip_top_proj/run_cts.tcl#L30) | `args` |
| `pdn` | [`silis/examples/cpp_macro_to_sv_chip/chip_top_proj/run_cts.tcl:L22`](silis/examples/cpp_macro_to_sv_chip/chip_top_proj/run_cts.tcl#L22) | `args` |
| `place_macro` | [`silis/core/backendflow/floorplanner/silis_fp.tcl:L261`](silis/core/backendflow/floorplanner/silis_fp.tcl#L261) | `args` |
| `set_design_attributes` | [`silis/core/backendflow/shims/openroad_upf_shim.tcl:L28`](silis/core/backendflow/shims/openroad_upf_shim.tcl#L28) | `args` |
| `set_domain_supply_net` | [`silis/core/backendflow/shims/openroad_upf_shim.tcl:L34`](silis/core/backendflow/shims/openroad_upf_shim.tcl#L34) | `args` |
| `set_isolation` | [`silis/core/backendflow/shims/openroad_upf_shim.tcl:L164`](silis/core/backendflow/shims/openroad_upf_shim.tcl#L164) | `name args` |
| `set_isolation_control` | [`silis/core/backendflow/shims/openroad_upf_shim.tcl:L39`](silis/core/backendflow/shims/openroad_upf_shim.tcl#L39) | `args` |
| `set_retention` | [`silis/core/backendflow/shims/openroad_upf_shim.tcl:L40`](silis/core/backendflow/shims/openroad_upf_shim.tcl#L40) | `args` |
| `set_retention_control` | [`silis/core/backendflow/shims/openroad_upf_shim.tcl:L41`](silis/core/backendflow/shims/openroad_upf_shim.tcl#L41) | `args` |
| `set_scope` | [`silis/core/backendflow/shims/openroad_upf_shim.tcl:L29`](silis/core/backendflow/shims/openroad_upf_shim.tcl#L29) | `args` |
| `synth` | [`silis/examples/cpp_macro_to_sv_chip/chip_top_proj/run_cts.tcl:L4`](silis/examples/cpp_macro_to_sv_chip/chip_top_proj/run_cts.tcl#L4) | `args` |
| `tapcells` | [`silis/examples/cpp_macro_to_sv_chip/chip_top_proj/run_cts.tcl:L17`](silis/examples/cpp_macro_to_sv_chip/chip_top_proj/run_cts.tcl#L17) | `args` |
| `upf_version` | [`silis/core/backendflow/shims/openroad_upf_shim.tcl:L27`](silis/core/backendflow/shims/openroad_upf_shim.tcl#L27) | `args` |
