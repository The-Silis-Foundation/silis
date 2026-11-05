# Silis ASIC EDA Master Architectural Knowledge Base
*Machine-readable, densely-indexed reference strictly scoped to `silis/`.*

---

## 1. Top-Level Core SDK Classes & Methods

### `class Pipeline` (silis/core/sdk/pipeline.py:348)
> High-level programmatic ASIC pipeline for Silis.
Provides methods for synthesis, PnR steps, GDS stream-out, and signoff.

| Method | Arguments | File Line | Description |
|---|---|---|---|
| `__init__` | `(self, project_or_path, headless)` | [`L392`](silis/core/sdk/pipeline.py#L392) | - |
| `process_events` | `(self, iterations, delay_ms)` | [`L426`](silis/core/sdk/pipeline.py#L426) | Pumps Qt event loop so QProcess, QThread, and timer events are processed. |
| `synthesis` | `(self, tcl, corner, mcmm, dft, flatten)` | [`L438`](silis/core/sdk/pipeline.py#L438) | Runs frontend RTL synthesis, scan insertion (if dft=True), and technology mapping. |
| `init` | `(self, tcl)` | [`L458`](silis/core/sdk/pipeline.py#L458) | Initializes OpenROAD, links PDK LEF/LIBs, and reads the synthesized netlist. |
| `floorplan` | `(self, tcl, die_area, core_margin, macros, regions, blockages, power_domains, power_domain_affinity, check_collisions, strict_collisions, auto_macro_placer, macro_halo, macro_channel, mpl_max_levels, mpl_min_instances, mpl_max_instances, mpl_min_macros, mpl_max_macros, mpl_bus_planning, mpl_target_dead_space, mpl_wirelength_weight, mpl_area_weight)` | [`L516`](silis/core/sdk/pipeline.py#L516) | Configures chip die bounds, core utilization, macro placement, halos, blockages, and regions. |
| `place_macro` | `(self, inst, at, orient, halo)` | [`L729`](silis/core/sdk/pipeline.py#L729) | Creates a clean, validated macro placement dictionary. |
| `add_fence` | `(self, module, box, origin, density, aspect_ratio, halo)` | [`L754`](silis/core/sdk/pipeline.py#L754) | Creates a clean fence region dictionary. |
| `add_region` | `(self, module, box, origin, density, aspect_ratio, halo)` | [`L789`](silis/core/sdk/pipeline.py#L789) | Creates an inclusive region dictionary. |
| `auto_place_regions` | `(self, die_area, core_margin, macros, regions, blockages, target_density, min_cutoff_pct, force_place_all, force_auto_shape, as_fence, common_halo, seed, w_r2m, w_r2r, w_r2io, allow_non_rectangular)` | [`L825`](silis/core/sdk/pipeline.py#L825) | Executes hierarchical auto region placement using the Silis geometric & affinity solver. |
| `auto_shape_regions` | `(self, module_names, target_density, min_cutoff_pct, core_margin, as_fence)` | [`L904`](silis/core/sdk/pipeline.py#L904) | Convenience method to auto-shape and auto-place inclusive floorplanning regions. |
| `add_blockage` | `(self, box, soft)` | [`L956`](silis/core/sdk/pipeline.py#L956) | Creates a placement/routing blockage dictionary. |
| `tapcells` | `(self, tcl, distance, endcap_cpp, tapcell, endcap)` | [`L964`](silis/core/sdk/pipeline.py#L964) | Inserts welltap and endcap cells according to PDK DRC spacing rules. |
| `configure_power_domain_supply` | `(self, domain_name, supply_type)` | [`L988`](silis/core/sdk/pipeline.py#L988) | Configures the power supply architecture for a power domain: |
| `pdn` | `(self, tcl, enable_ring, ring_width, ring_spacing, ring_offset, ring_h_layer, ring_v_layer, enable_trunks, trunk_layer, trunk_width)` | [`L999`](silis/core/sdk/pipeline.py#L999) | Synthesizes VDD and VSS power grid straps, peripheral power ring, and targeted pad trunk bridges. |
| `iopins` | `(self, tcl, mode, pad_strategy, pad_ring_margin, upf_aware, supply_pairs_per_edge, edge_assignments, pin_target, hor_layers, ver_layers, corner_avoidance, min_distance, pin_constraints, pin_order_file, random, exclude_left, exclude_right, exclude_top, exclude_bottom)` | [`L1479`](silis/core/sdk/pipeline.py#L1479) | Places IO pins or full-chip pad ring along die perimeter. |
| `place` | `(self, tcl, density, pad_left, pad_right, timing_driven, init_density_penalty)` | [`L1915`](silis/core/sdk/pipeline.py#L1915) | Executes global placement, timing-driven optimization, and detailed placement. |
| `cts` | `(self, tcl, root_buf, buf_list, sink_clustering)` | [`L2024`](silis/core/sdk/pipeline.py#L2024) | Synthesizes balanced clock tree network with clock buffer insertion. |
| `route` | `(self, tcl, congestion_iterations, bottom_layer, top_layer, layer_adjustments)` | [`L2069`](silis/core/sdk/pipeline.py#L2069) | Runs global routing (FastRoute) and detailed routing (TritonRoute). |
| `fill` | `(self, tcl)` | [`L2147`](silis/core/sdk/pipeline.py#L2147) | Inserts decap & standard cell filler cells and checks metal layer densities. |
| `gds` | `(self, tcl)` | [`L2162`](silis/core/sdk/pipeline.py#L2162) | Streams out physical layout into standard GDSII using Magic. |
| `signoff` | `(self, step, tcl)` | [`L2184`](silis/core/sdk/pipeline.py#L2184) | Executes final verification and signoff checks: |
| `dft` | `(self, tcl)` | [`L2228`](silis/core/sdk/pipeline.py#L2228) | Executes full DFT scan chain stitching and ATPG signoff analysis. Returns DFTSignoffReport. |
| `lvs` | `(self, tcl)` | [`L2232`](silis/core/sdk/pipeline.py#L2232) | Executes Layout Versus Schematic (LVS) comparison. Returns LVSSignoffReport. |
| `gls` | `(self, tcl)` | [`L2236`](silis/core/sdk/pipeline.py#L2236) | Executes Gate-Level Simulation (GLS) with SDF timing back-annotation. Returns GLSSignoffReport. |
| `simulate` | `(self, trace_format, coverage, threads, timeout_sec)` | [`L2240`](silis/core/sdk/pipeline.py#L2240) | Executes high-speed cycle-accurate SystemVerilog / UVM simulation using Verilator. |
| `lint` | `(self)` | [`L2332`](silis/core/sdk/pipeline.py#L2332) | Runs fast static linting across project RTL using bundled Verilator. |
| `export_sdf` | `(self)` | [`L2357`](silis/core/sdk/pipeline.py#L2357) | Exports Standard Delay Format (SDF) timing file from physical design. |
| `tapeout` | `(self, tcl)` | [`L2364`](silis/core/sdk/pipeline.py#L2364) | Packages final foundry tapeout GDS and generates signoff checklist manifest. |
| `export_macro` | `(self, macro_name, pdk_name, corners, def_path, gds_path, verilog_path, sdc_path)` | [`L2368`](silis/core/sdk/pipeline.py#L2368) | Exports the current physical design as a foundry-grade Hard Macro Package |
| `run_step` | `(self, step_name)` | [`L2448`](silis/core/sdk/pipeline.py#L2448) | Dispatches an individual step by name. |
| `run_until` | `(self, target_step)` | [`L2498`](silis/core/sdk/pipeline.py#L2498) | Executes flow steps sequentially starting from 'synthesis' up to and |
| `run_from` | `(self, start_step, end_step)` | [`L2518`](silis/core/sdk/pipeline.py#L2518) | Executes flow steps sequentially from start_step to end_step (inclusive). |
| `run_all` | `(self)` | [`L2546`](silis/core/sdk/pipeline.py#L2546) | Executes full ASIC flow end-to-end: synthesis through signoff. |
| `get_synthesis_report` | `(self)` | [`L2553`](silis/core/sdk/pipeline.py#L2553) | Retrieves parsed post-synthesis report. |
| `get_signoff_report` | `(self)` | [`L2557`](silis/core/sdk/pipeline.py#L2557) | Retrieves parsed post-route PAT signoff report. |
| `get_drc_report` | `(self)` | [`L2561`](silis/core/sdk/pipeline.py#L2561) | Retrieves parsed DRC verification report. |
| `get_dft_report` | `(self)` | [`L2565`](silis/core/sdk/pipeline.py#L2565) | Retrieves parsed DFT scan chain and fault coverage report. |
| `get_lvs_report` | `(self)` | [`L2569`](silis/core/sdk/pipeline.py#L2569) | Retrieves parsed LVS signoff report. |
| `get_gls_report` | `(self)` | [`L2573`](silis/core/sdk/pipeline.py#L2573) | Retrieves parsed Gate-Level Simulation (GLS) signoff report. |
| `get_tapeout_report` | `(self)` | [`L2577`](silis/core/sdk/pipeline.py#L2577) | Retrieves parsed Foundry Tapeout checklist manifest report. |
| `get_reports` | `(self)` | [`L2581`](silis/core/sdk/pipeline.py#L2581) | Returns all parsed reports for the pipeline project. |
| `get_sizes` | `(self, refresh)` | [`L2588`](silis/core/sdk/pipeline.py#L2588) | Returns design sizes JSON containing total cell area and module breakdown. |
| `get_modules` | `(self, refresh)` | [`L2592`](silis/core/sdk/pipeline.py#L2592) | Returns list of hierarchical module instance names. |
| `get_module_area` | `(self, module, refresh)` | [`L2596`](silis/core/sdk/pipeline.py#L2596) | Returns standard cell area in um^2 for module or core. |
| `get_utilization` | `(self, module_or_region, area, refresh)` | [`L2600`](silis/core/sdk/pipeline.py#L2600) | Calculates and returns cell utilization (0.0 to 1.0+) for a module or region. |
| `get_required_area` | `(self, module, target_density, refresh)` | [`L2616`](silis/core/sdk/pipeline.py#L2616) | Returns required physical area in um^2 for target density. |
| `suggest_box` | `(self, module, origin, target_density, aspect_ratio, grid_snap, refresh)` | [`L2627`](silis/core/sdk/pipeline.py#L2627) | Calculates optimal [x1, y1, x2, y2] bounding box for target density and aspect ratio. |
| `convert` | `(self, src, src_lang, out, std, fsynopsys, use_latches, hls_top, hls_memory_policy, hls_channels)` | [`L2649`](silis/core/sdk/pipeline.py#L2649) | Lowers source HDL/HLS code (SystemVerilog, VHDL-2008, C/C++) to standard synthesizable Verilog. |
| `formal` | `(self, properties, engine, mode, depth)` | [`L2719`](silis/core/sdk/pipeline.py#L2719) | Executes formal property verification using SymbiYosys (SBY). |
| `get_heatmap` | `(self, heatmap_type, grid_size, def_path)` | [`L2769`](silis/core/sdk/pipeline.py#L2769) | Calculates and returns physical heatmap data directly as a NumPy array. |
| `compute_minimum_die_for_pads` | `(self, num_pads, core_w, core_h, strategy, target_aspect, pad_margin, min_pitch)` | [`L2942`](silis/core/sdk/pipeline.py#L2942) | Calculates the minimum PDK-legal die dimensions and per-edge pad allocations |
| `optimize_die` | `(self, target_density, padring, strategy, pad_margin)` | [`L3009`](silis/core/sdk/pipeline.py#L3009) | Optimizes core and die dimensions based on synthesized standard cell area |
| `apply_clock_ndr` | `(self, rule_name, min_layer, max_layer, clock_nets)` | [`L3051`](silis/core/sdk/pipeline.py#L3051) | Applies Non-Default Routing (NDR) rules to clock trees. |
| `repair_clock_buffers` | `(self)` | [`L3071`](silis/core/sdk/pipeline.py#L3071) | Repairs and balances clock buffer chains in OpenROAD. |
| `repair_antennas` | `(self, iterations, diode_cell)` | [`L3078`](silis/core/sdk/pipeline.py#L3078) | Inserts antenna diodes on long gate routing nets. |
| `save_checkpoint` | `(self, tag)` | [`L3095`](silis/core/sdk/pipeline.py#L3095) | Saves current layout and database checkpoint to results/{tag}.odb and results/{tag}.def. |
| `load_checkpoint` | `(self, tag)` | [`L3120`](silis/core/sdk/pipeline.py#L3120) | Loads a previously saved database checkpoint from results/{tag}.odb. |
| `close` | `(self)` | [`L3136`](silis/core/sdk/pipeline.py#L3136) | Gracefully closes child OpenROAD processes and flushes events. |
| `__enter__` | `(self)` | [`L3155`](silis/core/sdk/pipeline.py#L3155) | - |
| `__exit__` | `(self, exc_type, exc_val, exc_tb)` | [`L3158`](silis/core/sdk/pipeline.py#L3158) | - |

### `class Project` (silis/core/sdk/project.py:30)
> Programmatic abstraction of a Silis ASIC Project (.silisproj).
Handles configuration parsing, file discovery, macro binding, and report extraction.

| Method | Arguments | File Line | Description |
|---|---|---|---|
| `__init__` | `(self, path_or_name)` | [`L36`](silis/core/sdk/project.py#L36) | - |
| `get_floorplan` | `(self)` | [`L105`](silis/core/sdk/project.py#L105) | Returns the strongly-typed Floorplan entity for physical placement. |
| `get_power_network` | `(self)` | [`L112`](silis/core/sdk/project.py#L112) | Returns the strongly-typed IEEE 1801 UPF PowerNetwork coordinator. |
| `get_timing_graph` | `(self)` | [`L119`](silis/core/sdk/project.py#L119) | Returns the live in-memory TimingGraph for on-the-fly static timing slack inspection. |
| `get_layout` | `(self)` | [`L126`](silis/core/sdk/project.py#L126) | Returns the in-memory Layout engine for real-time physical change analysis. |
| `get_rtl_files` | `(self)` | [`L154`](silis/core/sdk/project.py#L154) | Discovers existing RTL source files from config and rtl/ or source/ directory. |
| `is_vhdl` | `(self)` | [`L168`](silis/core/sdk/project.py#L168) | Returns True if the project contains any VHDL source files. |
| `get_vhdl_files` | `(self)` | [`L172`](silis/core/sdk/project.py#L172) | Discovers existing VHDL source files (*.vhd, *.vhdl). |
| `get_verilog_files` | `(self)` | [`L176`](silis/core/sdk/project.py#L176) | Discovers existing Verilog source files (*.v, *.sv). |
| `get_sdc_files` | `(self)` | [`L180`](silis/core/sdk/project.py#L180) | Discovers existing SDC timing constraint files. |
| `get_upf_file` | `(self)` | [`L191`](silis/core/sdk/project.py#L191) | Discovers existing UPF power intent specification file. |
| `get_power_domains` | `(self)` | [`L210`](silis/core/sdk/project.py#L210) | Returns parsed power_domain objects from the project UPF file. |
| `get_pin_order_file` | `(self)` | [`L218`](silis/core/sdk/project.py#L218) | Discovers existing I/O pin / pad ordering configuration file. |
| `get_tb_files` | `(self)` | [`L235`](silis/core/sdk/project.py#L235) | Discovers existing testbench files. |
| `get_netlists` | `(self)` | [`L249`](silis/core/sdk/project.py#L249) | Returns all synthesized Verilog netlists in netlist/ directory. |
| `get_netlist` | `(self)` | [`L258`](silis/core/sdk/project.py#L258) | Returns primary synthesized netlist path or None. |
| `get_defs` | `(self)` | [`L266`](silis/core/sdk/project.py#L266) | Returns all layout DEF files in results/ and root. |
| `get_def` | `(self)` | [`L274`](silis/core/sdk/project.py#L274) | Returns primary DEF file (temp.def or latest). |
| `get_gds_files` | `(self)` | [`L285`](silis/core/sdk/project.py#L285) | Returns all stream GDSII files in results/. |
| `get_gds` | `(self)` | [`L294`](silis/core/sdk/project.py#L294) | Returns primary GDS file (design.gds or <top>.gds). |
| `get_odbs` | `(self)` | [`L306`](silis/core/sdk/project.py#L306) | Returns all OpenROAD database checkpoints (*.odb) in results/. |
| `get_vcd_files` | `(self)` | [`L312`](silis/core/sdk/project.py#L312) | Returns waveform VCD files in project. |
| `get_macro_lefs_and_libs` | `(self)` | [`L319`](silis/core/sdk/project.py#L319) | Locates LEF and Liberty LIB files for all hard macros in the project. |
| `get_pdk_info` | `(self)` | [`L368`](silis/core/sdk/project.py#L368) | Finds configured PDK files (tlef, lef, lib, tech, gds) matching target PDK. |
| `get_synthesis_report` | `(self)` | [`L389`](silis/core/sdk/project.py#L389) | Loads and returns the SynthesisReport for this project. |
| `get_signoff_report` | `(self)` | [`L393`](silis/core/sdk/project.py#L393) | Loads and returns the SignoffReport (PAT) for this project. |
| `get_drc_report` | `(self)` | [`L397`](silis/core/sdk/project.py#L397) | Loads and returns the DRCReport for this project. |
| `get_antenna_report` | `(self)` | [`L401`](silis/core/sdk/project.py#L401) | Loads and returns the AntennaSignoffReport for this project. |
| `get_dft_report` | `(self)` | [`L406`](silis/core/sdk/project.py#L406) | Loads and returns the DFTSignoffReport for this project. |
| `get_lvs_report` | `(self)` | [`L410`](silis/core/sdk/project.py#L410) | Loads and returns the LVSSignoffReport for this project. |
| `get_gls_report` | `(self)` | [`L415`](silis/core/sdk/project.py#L415) | Loads and returns the GLSSignoffReport for this project. |
| `get_tapeout_report` | `(self)` | [`L420`](silis/core/sdk/project.py#L420) | Loads and returns the TapeoutManifestReport for this project. |
| `get_reports` | `(self)` | [`L425`](silis/core/sdk/project.py#L425) | Discovers and parses all project reports. |
| `get_sizes` | `(self, refresh)` | [`L452`](silis/core/sdk/project.py#L452) | Discovers, parses, and caches the design sizes JSON ({top_module}_sizes.json). |
| `get_modules` | `(self, refresh)` | [`L479`](silis/core/sdk/project.py#L479) | Returns a list of all hierarchical module instance names discovered in the netlist. |
| `get_module_area` | `(self, module, refresh)` | [`L484`](silis/core/sdk/project.py#L484) | Returns the standard cell area in um^2 for a specific module or the entire core. |
| `get_utilization` | `(self, module_or_region, area, macros, refresh)` | [`L526`](silis/core/sdk/project.py#L526) | Calculates and returns cell utilization (0.0 to 1.0+) for a module or region. |
| `get_required_area` | `(self, module, target_density, macro_area, refresh)` | [`L605`](silis/core/sdk/project.py#L605) | Returns the required physical area in um^2 to achieve target_density (0.0 to 1.0) |
| `suggest_box` | `(self, module, origin, target_density, macro_area, aspect_ratio, grid_snap, refresh)` | [`L622`](silis/core/sdk/project.py#L622) | Calculates and returns an optimal bounding box [x1, y1, x2, y2] starting at origin |
| `add_macro` | `(self, macro_name, lef, lib, gds)` | [`L664`](silis/core/sdk/project.py#L664) | Registers a hard macro in the project, optionally copying LEF, LIB, and GDS into rtl/ or source/. |
| `add_rtl` | `(self)` | [`L689`](silis/core/sdk/project.py#L689) | Adds RTL source files to the project. |
| `add_tb` | `(self)` | [`L697`](silis/core/sdk/project.py#L697) | Adds testbench files to the project. |
| `add_sdc` | `(self)` | [`L705`](silis/core/sdk/project.py#L705) | Adds SDC constraint files to the project. |
| `save` | `(self, path)` | [`L713`](silis/core/sdk/project.py#L713) | Saves project configuration to .silisproj file. |
| `import_macro` | `(self, macro_name, lef, lib, gds, generate_stub)` | [`L733`](silis/core/sdk/project.py#L733) | Imports a hard macro into the project. |
| `import_upf` | `(self, path, copy)` | [`L793`](silis/core/sdk/project.py#L793) | Imports an IEEE 1801 UPF or CPF power intent file into the project. |
| `set_power_domain_supply_type` | `(self, domain_name, supply_type)` | [`L811`](silis/core/sdk/project.py#L811) | Configures the physical power supply type for a power domain: |
| `import_io_config` | `(self, path, copy)` | [`L834`](silis/core/sdk/project.py#L834) | Imports an I/O pin ordering configuration into io/<filename>. |
| `to_dict` | `(self)` | [`L857`](silis/core/sdk/project.py#L857) | Returns project configuration dictionary. |
| `summary` | `(self)` | [`L861`](silis/core/sdk/project.py#L861) | Returns a high-level overview string of project status. |
| `load` | `(cls, path_or_name)` | [`L889`](silis/core/sdk/project.py#L889) | Loads and returns a Project instance. |
| `create` | `(cls, name, top, pdk, loc, rtl, tb, sdc, macros)` | [`L894`](silis/core/sdk/project.py#L894) | Creates a new Silis ASIC project workspace with standard directory layout |

### `class Floorplan` (silis/core/sdk/floorplan.py:131)
> Authoritative physical floorplan representation:
Die boundary, core rectangle, manufacturing grid quantization, and macro arrangement.

| Method | Arguments | File Line | Description |
|---|---|---|---|
| `__init__` | `(self, project)` | [`L136`](silis/core/sdk/floorplan.py#L136) | - |
| `set_die_dimensions` | `(self, width, height, margins)` | [`L145`](silis/core/sdk/floorplan.py#L145) | Sets die bounds with defensive dimension assertions. |
| `get_die_bbox` | `(self)` | [`L164`](silis/core/sdk/floorplan.py#L164) | - |
| `get_core_bbox` | `(self)` | [`L167`](silis/core/sdk/floorplan.py#L167) | - |
| `get_core_dimensions` | `(self)` | [`L175`](silis/core/sdk/floorplan.py#L175) | - |
| `add_macro` | `(self, name, master, x, y, width, height, orientation, halo)` | [`L179`](silis/core/sdk/floorplan.py#L179) | Adds a macro instance to the physical floorplan context. |
| `get_macro` | `(self, name)` | [`L206`](silis/core/sdk/floorplan.py#L206) | - |
| `get_macros` | `(self)` | [`L209`](silis/core/sdk/floorplan.py#L209) | - |
| `verify_legal_placement` | `(self)` | [`L212`](silis/core/sdk/floorplan.py#L212) | Executes pre-flight DRC checks: |

### `class MacroInstance` (silis/core/sdk/floorplan.py:61)
> Physical macro block representation with exact bounding box, halo keepout,
orientation, and terminal locations.

| Method | Arguments | File Line | Description |
|---|---|---|---|
| `__init__` | `(self, name, master, x, y, width, height, orientation, halo, parent_floorplan)` | [`L66`](silis/core/sdk/floorplan.py#L66) | - |
| `move_to` | `(self, x, y)` | [`L88`](silis/core/sdk/floorplan.py#L88) | Moves macro origin with manufacturing grid quantization. |
| `set_orientation` | `(self, orient)` | [`L95`](silis/core/sdk/floorplan.py#L95) | - |
| `set_halo` | `(self, left, right, top, bottom)` | [`L100`](silis/core/sdk/floorplan.py#L100) | - |
| `get_bbox` | `(self)` | [`L105`](silis/core/sdk/floorplan.py#L105) | Returns exact physical bounding box (x1, y1, x2, y2) in microns. |
| `get_halo_bbox` | `(self)` | [`L109`](silis/core/sdk/floorplan.py#L109) | Returns physical bounding box including keepout halo margins (x1, y1, x2, y2). |
| `overlaps` | `(self, other)` | [`L118`](silis/core/sdk/floorplan.py#L118) | Collision invariant: BoundingBox(M_i + Halo_i) intersect BoundingBox(M_j + Halo_j) == empty. |

### `class PowerNetwork` (silis/core/sdk/power.py:80)
> IEEE 1801 multi-voltage architecture coordinator.
Validates domain exclusivities, level shifter mandates, and power intent completeness.

| Method | Arguments | File Line | Description |
|---|---|---|---|
| `__init__` | `(self, project)` | [`L85`](silis/core/sdk/power.py#L85) | - |
| `create_domain` | `(self, name, primary_voltage, elements)` | [`L115`](silis/core/sdk/power.py#L115) | - |
| `get_domain` | `(self, name)` | [`L122`](silis/core/sdk/power.py#L122) | - |
| `get_domains` | `(self)` | [`L125`](silis/core/sdk/power.py#L125) | - |
| `verify_power_intent` | `(self)` | [`L128`](silis/core/sdk/power.py#L128) | Validates IEEE 1801 verification rules: |

### `class PowerDomain` (silis/core/backendflow/floorplanner/power_domain_manager.py:24)
> Represents a physical or logical power domain.

| Method | Arguments | File Line | Description |
|---|---|---|---|
| `is_top` | `(self)` | [`L27`](silis/core/backendflow/floorplanner/power_domain_manager.py#L27) | - |
| `__init__` | `(self, name, voltage, domain_type, parent_domain, pmu_instance, elements, switch_topology, switch_pitch, enable_srpg, iso_en, sleep_en, sleep_ack, tapcell_type)` | [`L30`](silis/core/backendflow/floorplanner/power_domain_manager.py#L30) | - |
| `to_dict` | `(self)` | [`L62`](silis/core/backendflow/floorplanner/power_domain_manager.py#L62) | - |
| `from_dict` | `(cls, data)` | [`L81`](silis/core/backendflow/floorplanner/power_domain_manager.py#L81) | - |

### `class TimingGraph` (silis/core/sdk/timing.py:32)
> Live Static Timing Graph wrapping OpenROAD / OpenSTA.
Queries timing slack and transitions directly in memory.

| Method | Arguments | File Line | Description |
|---|---|---|---|
| `__init__` | `(self, project)` | [`L37`](silis/core/sdk/timing.py#L37) | - |
| `query_live_metrics` | `(self, force_refresh)` | [`L43`](silis/core/sdk/timing.py#L43) | Queries WNS and TNS from the active OpenROAD runtime. |
| `get_wns` | `(self, corner)` | [`L113`](silis/core/sdk/timing.py#L113) | Returns Worst Negative Slack in nanoseconds (negative indicates violation). |
| `get_tns` | `(self, corner)` | [`L118`](silis/core/sdk/timing.py#L118) | Returns Total Negative Slack in nanoseconds. |
| `get_pin_slack` | `(self, pin_name, delay_type)` | [`L123`](silis/core/sdk/timing.py#L123) | Queries on-the-fly static timing slack for an individual instance terminal. |
| `get_equivalent_cells` | `(self, master_name)` | [`L158`](silis/core/sdk/timing.py#L158) | Returns sizing alternatives for cell driver optimization (e.g. buf_1 -> buf_2, buf_4, buf_8). |

### `class Layout` (silis/core/sdk/layout.py:23)
> Authoritative In-Memory Physical Design Layout Engine.
Exposes real-time instance coordinate mutation, boundary inspection,
and net connectivity graphs.

| Method | Arguments | File Line | Description |
|---|---|---|---|
| `__init__` | `(self, project)` | [`L29`](silis/core/sdk/layout.py#L29) | - |
| `get_instances` | `(self)` | [`L54`](silis/core/sdk/layout.py#L54) | Returns all physical standard cell and macro instances in the active design. |
| `find_instance` | `(self, name)` | [`L59`](silis/core/sdk/layout.py#L59) | Finds an instance by hierarchical name. |
| `set_instance_location` | `(self, name, x, y, orientation)` | [`L64`](silis/core/sdk/layout.py#L64) | Mutates the instance location directly in the in-memory layout representation |
| `die_area` | `(self)` | [`L79`](silis/core/sdk/layout.py#L79) | Returns die boundary [x1, y1, x2, y2] in microns. |
| `core_area` | `(self)` | [`L84`](silis/core/sdk/layout.py#L84) | Returns core boundary [x1, y1, x2, y2] in microns. |
| `utilization` | `(self)` | [`L89`](silis/core/sdk/layout.py#L89) | Returns standard cell core area utilization percentage. |
| `get_die_area` | `(self)` | [`L93`](silis/core/sdk/layout.py#L93) | Returns die boundary [x1, y1, x2, y2] in microns. |
| `get_core_area` | `(self)` | [`L98`](silis/core/sdk/layout.py#L98) | Returns core boundary [x1, y1, x2, y2] in microns. |
| `get_utilization` | `(self)` | [`L103`](silis/core/sdk/layout.py#L103) | Returns standard cell core area utilization percentage. |
| `get_pins` | `(self)` | [`L108`](silis/core/sdk/layout.py#L108) | Returns top-level I/O boundary pins. |

## 2. Floorplanner & Physical Flow Architecture

### `class InteractiveFloorplannerWidget` (silis/core/backendflow/floorplanner/floorplanner.py:1444)
> Silis Floorplan & Power Studio (FPS)
Unified ASIC Floorplanning, Multi-Domain Power Intent (IEEE-1801 UPF),
and I/O Pad/Pin Co-Optimization Workbench.

- **Key Methods**: _get_project_context, __init__, _init_top_menu_bar, _init_layout_and_splitters, _setup_keyboard_shortcuts, keyPressEvent, reject, closeEvent, toggle_hud_visibility, _trigger_autosave, _do_transactional_autosave, _serialize_session_state, save_session, save_snapshot_as, load_session, revert_to_saved, verify_netlist_integrity, on_reset_from_netlist, select_all_canvas, clear_selection, delete_selected_entities, fit_core, toggle_halos_visibility, scan_narrow_corridors, open_die_core_setup_dialog

### `class HeadlessASICRunner` (silis/core/cli/flow.py:100)
- **Key Methods**: __init__, close, __del__, _streaming_read_stdout, _ensure_backend_running, execute_tcl, _wait_for_backend, run_synthesis, _get_io_lefs, _get_macro_lefs_and_libs, ensure_design_loaded, run_init, run_floorplan, run_step, run_fill, run_lvs, run_gls, export_sdf, run_tapeout

### `class BackendWidget` (silis/core/backendflow/flow/backendflow.py:220)
- **Key Methods**: __init__, load_custom_odb, load_custom_def, run_psm_integrity_check, run_bondpad_studio, apply_clock_ndr, repair_clock_buffers, repair_antenna_violations, launch_gds3d_view, run_signoff_pipeline, _on_signoff_pipeline_failed, _on_signoff_pipeline_succeeded, _on_signoff_pipeline_finished, _get_io_lefs, _get_io_gds, _get_macro_files, update_spinner, start_spinner, stop_spinner, launch_magic_gui, ask_command, kill_active_backend_process, reset_backend, on_tab_changed, run_flow_step

### `class ReportEngine` (silis/core/synthesisscripts/synthesisthread.py:13)
> Parses generated report files for robust metric extraction.

- **Key Methods**: parse_files, _bar, generate_markdown_report, generate_report

## 3. Floorplan & Macro Core Helper Functions

| Function | File Line | Summary |
|---|---|---|
| `generate_floorplan_tcl_from_data` | [`silis/core/backendflow/floorplanner/floorplanner.py:L7684`](silis/core/backendflow/floorplanner/floorplanner.py#L7684) | Headless & programmatic ASIC floorplan TCL generator. |
| `compute_peripheral_macro_placement` | [`silis/core/backendflow/floorplanner/floorplanner.py:L7514`](silis/core/backendflow/floorplanner/floorplanner.py#L7514) | Computes strict non-overlapping peripheral macro placement for all macros. |
| `check_floorplan_collisions` | [`silis/core/sdk/pipeline.py:L69`](silis/core/sdk/pipeline.py#L69) | Performs comprehensive 2D geometric collision and containment checks between: |

## 4. OpenROAD TCL Shims & Floorplan Commands

| TCL Command / Proc | File Line | Arguments |
|---|---|---|
| `NULL` | [`silis/core/backendflow/shims/openroad_upf_shim.tcl:L3`](silis/core/backendflow/shims/openroad_upf_shim.tcl#L3) | `args` |
| `_silis_snap` | [`silis/core/backendflow/floorplanner/silis_fp.tcl:L6`](silis/core/backendflow/floorplanner/silis_fp.tcl#L6) | `val` |
| `add_power_state` | [`silis/core/backendflow/shims/openroad_upf_shim.tcl:L44`](silis/core/backendflow/shims/openroad_upf_shim.tcl#L44) | `args` |
| `add_pst_state` | [`silis/core/backendflow/shims/openroad_upf_shim.tcl:L46`](silis/core/backendflow/shims/openroad_upf_shim.tcl#L46) | `args` |
| `connect_supply_net` | [`silis/core/backendflow/shims/openroad_upf_shim.tcl:L35`](silis/core/backendflow/shims/openroad_upf_shim.tcl#L35) | `args` |
| `create_fence` | [`silis/core/backendflow/floorplanner/silis_fp.tcl:L15`](silis/core/backendflow/floorplanner/silis_fp.tcl#L15) | `args` |
| `create_power_domain` | [`silis/core/backendflow/shims/openroad_upf_shim.tcl:L56`](silis/core/backendflow/shims/openroad_upf_shim.tcl#L56) | `name args` |
| `create_power_switch` | [`silis/core/backendflow/shims/openroad_upf_shim.tcl:L84`](silis/core/backendflow/shims/openroad_upf_shim.tcl#L84) | `name args` |
| `create_pst` | [`silis/core/backendflow/shims/openroad_upf_shim.tcl:L45`](silis/core/backendflow/shims/openroad_upf_shim.tcl#L45) | `args` |
| `create_region` | [`silis/core/backendflow/floorplanner/silis_fp.tcl:L56`](silis/core/backendflow/floorplanner/silis_fp.tcl#L56) | `args` |
| `create_supply_net` | [`silis/core/backendflow/shims/openroad_upf_shim.tcl:L33`](silis/core/backendflow/shims/openroad_upf_shim.tcl#L33) | `args` |
| `create_supply_port` | [`silis/core/backendflow/shims/openroad_upf_shim.tcl:L32`](silis/core/backendflow/shims/openroad_upf_shim.tcl#L32) | `args` |
| `create_supply_set` | [`silis/core/backendflow/shims/openroad_upf_shim.tcl:L36`](silis/core/backendflow/shims/openroad_upf_shim.tcl#L36) | `args` |
| `describe_state_model` | [`silis/core/backendflow/shims/openroad_upf_shim.tcl:L47`](silis/core/backendflow/shims/openroad_upf_shim.tcl#L47) | `args` |
| `gds` | [`silis/examples/cpp_macro_to_sv_chip/chip_top_proj/run_cts.tcl:L35`](silis/examples/cpp_macro_to_sv_chip/chip_top_proj/run_cts.tcl#L35) | `args` |
| `init` | [`silis/examples/cpp_macro_to_sv_chip/chip_top_proj/run_cts.tcl:L11`](silis/examples/cpp_macro_to_sv_chip/chip_top_proj/run_cts.tcl#L11) | `args` |
| `iopins` | [`silis/examples/cpp_macro_to_sv_chip/chip_top_proj/run_cts.tcl:L30`](silis/examples/cpp_macro_to_sv_chip/chip_top_proj/run_cts.tcl#L30) | `args` |
| `pdn` | [`silis/examples/cpp_macro_to_sv_chip/chip_top_proj/run_cts.tcl:L22`](silis/examples/cpp_macro_to_sv_chip/chip_top_proj/run_cts.tcl#L22) | `args` |
| `place_macro` | [`silis/core/backendflow/floorplanner/silis_fp.tcl:L223`](silis/core/backendflow/floorplanner/silis_fp.tcl#L223) | `args` |
| `set_design_attributes` | [`silis/core/backendflow/shims/openroad_upf_shim.tcl:L28`](silis/core/backendflow/shims/openroad_upf_shim.tcl#L28) | `args` |
| `set_domain_supply_net` | [`silis/core/backendflow/shims/openroad_upf_shim.tcl:L34`](silis/core/backendflow/shims/openroad_upf_shim.tcl#L34) | `args` |
| `set_isolation` | [`silis/core/backendflow/shims/openroad_upf_shim.tcl:L161`](silis/core/backendflow/shims/openroad_upf_shim.tcl#L161) | `name args` |
| `set_isolation_control` | [`silis/core/backendflow/shims/openroad_upf_shim.tcl:L39`](silis/core/backendflow/shims/openroad_upf_shim.tcl#L39) | `args` |
| `set_retention` | [`silis/core/backendflow/shims/openroad_upf_shim.tcl:L40`](silis/core/backendflow/shims/openroad_upf_shim.tcl#L40) | `args` |
| `set_retention_control` | [`silis/core/backendflow/shims/openroad_upf_shim.tcl:L41`](silis/core/backendflow/shims/openroad_upf_shim.tcl#L41) | `args` |
| `set_scope` | [`silis/core/backendflow/shims/openroad_upf_shim.tcl:L29`](silis/core/backendflow/shims/openroad_upf_shim.tcl#L29) | `args` |
| `synth` | [`silis/examples/cpp_macro_to_sv_chip/chip_top_proj/run_cts.tcl:L4`](silis/examples/cpp_macro_to_sv_chip/chip_top_proj/run_cts.tcl#L4) | `args` |
| `tapcells` | [`silis/examples/cpp_macro_to_sv_chip/chip_top_proj/run_cts.tcl:L17`](silis/examples/cpp_macro_to_sv_chip/chip_top_proj/run_cts.tcl#L17) | `args` |
| `upf_version` | [`silis/core/backendflow/shims/openroad_upf_shim.tcl:L27`](silis/core/backendflow/shims/openroad_upf_shim.tcl#L27) | `args` |
